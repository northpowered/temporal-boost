# TB-002. Добавить согласованное завершение приложения

- **Статус:** done
- **Приоритет:** P1
- **Тип:** Доработка

## Проблема и подтверждение

[run_all_workers()](../temporal_boost/boost_app.py) запускает daemon-потоки и опрашивает `is_alive()`, но не вызывает `shutdown()` у зарегистрированных worker. У приложения нет общего stop-контракта и обработки SIGTERM. Асинхронный `shutdown()` из [BaseBoostWorker](../temporal_boost/workers/base.py) не определяет, как безопасно остановить worker из главного потока в его собственном event loop.

При остановке сервиса работающие компоненты могут завершаться без ожидаемого cleanup; заявленная гарантия graceful shutdown не выполняется на уровне всего приложения.

## Что сделать

1. Определить владение event loop и потокобезопасный способ запроса остановки каждого worker.
2. Добавить координатор запуска/остановки с ограниченным ожиданием завершения потоков.
3. Обрабатывать SIGINT/SIGTERM в главном потоке; при программном запуске из другого потока предоставить явный stop API.
4. Восстанавливать предыдущие signal handlers после выхода и корректно обрабатывать повторный запрос остановки.
5. Уточнить документацию о границах graceful shutdown; реальные адаптеры подключаются отдельными связанными задачами.

## Критерии приёмки

- [x] Управляемые тестовые worker получают stop-запрос и завершают `run()` до возврата координатора.
- [x] Cleanup выполняется в event loop владельца ресурсов, а не в новом произвольном loop.
- [x] Повторный stop безопасен; зависший worker ограничен документированным timeout.
- [x] SIGINT/SIGTERM и явный stop приводят к одному пути завершения без зависших потоков.

## Проверка

Добавить детерминированные тесты координатора с управляемыми worker, событиями и ограниченными ожиданиями. Signal-сценарии проверять отдельным subprocess; не отправлять сигналы процессу pytest.

## Реализация и результаты проверки

Добавлен `BaseBoostWorker.request_stop() -> bool`: неблокирующий потокобезопасный запрос,
безопасный при повторах и во время старта. Значение по умолчанию `False` сохраняет совместимость
существующих подклассов и явно сообщает coordinator об отсутствии поддержки stop.

Новая опциональная база `AsyncBoostWorker` владеет одним asyncio loop на запуск. Подклассы вызывают
`super().__init__()`, реализуют `run_async()` / `shutdown()` и сохраняют унаследованный `run()`.
Stop запоминается до создания loop, а затем доставляется через `call_soon_threadsafe()`.
Cleanup выполняется один раз на том же loop, после чего helper ждёт возврата `run_async()`.
`shutdown()` должен учитывать частичную инициализацию и обеспечивать завершение основной coroutine.
`add_async_runtime()` теперь принимает `BaseBoostWorker`, включая новую базу; правила имени регистрации
не менялись (TB-018).

`WorkerCoordinator` запускает daemon-потоки, запрашивает stop у всех живых worker и ожидает их по
одному общему deadline. `BoostApp(shutdown_timeout=30.0)` задаёт конечное неотрицательное число секунд;
нулевое значение допустимо. Отдельный `BoostApp.stop()` не блокирует и не переносит запрос в следующий
запуск. В главном потоке SIGINT/SIGTERM идут через тот же путь; прежние handlers восстанавливаются
при выходе, включая ошибку старта потока. Повторный stop не меняет deadline. В фоновом потоке
handlers не устанавливаются. Интервал обнаружения stop — до 50 мс, затем начинается бюджет остановки.

При превышении бюджета возникает `TimeoutError` с именами оставшихся worker. Python не может
принудительно завершить поток: зависшие daemon-потоки могут жить до выхода процесса. Повторный запуск
приложения отклоняется, пока они живы; одновременные запуски также отклоняются.

Реальные Temporal/FastStream/ASGI адаптеры пока возвращают `False` из `request_stop()`; coordinator
пишет предупреждение, а незавершившиеся потоки ограничивает timeout. Их подключение, передача ошибок
worker и supervision процессов остаются в связанных задачах. Общий бюджет приложения не связан с
`TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT` (TB-004). Границы и пример custom worker отражены в guides,
API reference, README и `ARCHITECTURE.md`.

Добавлены 15 сценариев в `tests/test_worker_coordinator.py`: несколько worker, владение loop/потоком,
ожидание cleanup, повторные/ранние stop, последовательные запуски, запрет одновременного запуска,
проверка timeout и неподдержанного worker, частичный отказ запуска потока, отсутствие signal handlers
в фоновом потоке. SIGINT/SIGTERM, повторный сигнал во время cleanup и восстановление handlers проверены
в отдельных subprocess с управляемым завершением через pipe. Процесс pytest сигналов не получает.
Тест с искусственным необработанным `KeyboardInterrupt` заменён проверкой нормального возврата worker.

Проверки выполнены 2026-11-07 на Python 3.13.9. Команды использовали префикс
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync` для существующего окружения:

- `pytest tests/test_worker_coordinator.py tests/test_boost_app.py --tb=short -q`: 52 passed.
- `pytest tests/test_worker_coordinator.py --tb=short -q`: 15 passed после финальной настройки
  subprocess handshake; worker-потоки явно дожидаются завершения при teardown.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short`: 181 passed, покрытие 68%,
  без предупреждений. Полный набор выполнен вне sandbox, поскольку три существующих runtime-теста
  открывают локальные Prometheus-порты. В sandbox эти три теста получили `Operation not permitted`.
- `ruff check --no-fix temporal_boost/ tests/test_worker_coordinator.py tests/signal_shutdown_app.py
  --output-format concise`: успешно.
- `ruff format --check temporal_boost/ tests/test_worker_coordinator.py tests/signal_shutdown_app.py
  tests/test_boost_app.py`: успешно.
- `mypy temporal_boost/`: успешно, 23 файла.
- `mkdocs build --strict`: успешно.
- `ruff check --no-fix temporal_boost/ examples/ --output-format concise`: 42 существующие ошибки
  только в неизменённых examples.
- `ruff format --check temporal_boost/ examples/ tests/test_worker_coordinator.py
  tests/signal_shutdown_app.py tests/test_boost_app.py`: пять существующих нарушений форматирования
  в неизменённых examples; остальные 36 файлов отформатированы.
- `git diff --check`: успешно.

Проверки с настоящими адаптерами и многопроцессным supervisor здесь не выполнялись: они относятся
к связанным задачам. Существующие ошибки lint/format в examples остаются вне области TB-002.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-003](003-thread-worker-failure-propagation.md), [TB-004](004-wire-graceful-shutdown-timeout.md), [TB-005](005-temporal-worker-startup-cleanup.md), [TB-009](009-multiprocess-supervision.md), [TB-013](013-faststream-managed-shutdown.md), [TB-014](014-asgi-lifecycle-and-event-loops.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

