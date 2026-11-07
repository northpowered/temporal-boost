# TB-003. Передавать ошибки worker из потоков координатору

- **Статус:** done
- **Приоритет:** P1
- **Тип:** Баг

## Проблема и подтверждение

В [run_all_workers()](../temporal_boost/boost_app.py) `threading.Thread(target=worker.run)` не передаёт исключение в главный поток. Если один worker упал, приложение продолжает ждать остальные; если упали все, метод возвращается без сообщения об общей неудаче. Существующий тест имитирует ошибку через необработанный `KeyboardInterrupt` в потоке и получает pytest warning.

Процесс выглядит работающим или успешно завершённым при частично либо полностью неработающем сервисе.

## Что сделать

1. Перехватывать результат каждого worker в обёртке потока и передавать исходное исключение координатору.
2. Зафиксировать политику первой фатальной ошибки: инициировать остановку остальных worker и вернуть ошибку вызывающему коду.
3. Отличать штатную отмену при shutdown от аварии; определить поведение неожиданного нормального возврата долгоживущего worker.
4. Заменить тест с необработанным исключением потока проверкой наблюдаемого результата.

## Критерии приёмки

- [x] Ошибка одного worker наблюдается координатором, даже если другой worker продолжает работать.
- [x] Остальные worker получают запрос остановки; исходная ошибка сохраняется после cleanup.
- [x] `run all` не сообщает успешный результат при фатальной ошибке worker.
- [x] В тестах отсутствует `PytestUnhandledThreadExceptionWarning` от искусственного падения worker.

## Проверка

Обновить [test_boost_app.py](../tests/test_boost_app.py): один worker падает, второй ждёт stop, оба завершаются за ограниченное время. Проверить итоговый CLI exit code после TB-008.

## Реализация и результаты проверки

После TB-002 запуск потоков находится в `WorkerCoordinator`; старый тест с необработанным
`KeyboardInterrupt` уже заменён. Подтверждённая оставшаяся проблема — отсутствие передачи результатов
`worker.run()` координатору — исправлена обёрткой потока, перехватывающей `BaseException`.
Объект ошибки и его traceback передаются через потокобезопасную FIFO `SimpleQueue`.

Первая опубликованная ошибка запрашивает stop. Coordinator прекращает запуск следующих регистраций,
рассылает stop живым worker и дожидается потоков в рамках общего бюджета TB-002, после чего поднимает
первую ошибку в вызывающем потоке. Последующие отказы worker, startup, stop callback и timeout
логируются и не заменяют первую ошибку. Отказ одного stop callback не мешает запросить остановку
остальных worker. Ошибки больше не уходят в `threading.excepthook`.

Контракт `run all` считает регистрации долгоживущими сервисами. Нормальный возврат `run()` до
запроса остановки приложения теперь означает `RuntimeError` с именем worker и остановку остальных.
Возврат после stop штатен. `asyncio.CancelledError` / `concurrent.futures.CancelledError` штатны
только после запроса stop; до него передаются как ошибки. Остальные исключения, включая
`KeyboardInterrupt` / `SystemExit`, фатальны и при shutdown.

**Миграция:** finite worker, ранее просто возвращавшийся из `run all`, должен вызвать `app.stop()`
перед возвратом для штатного завершения приложения либо запускаться отдельной командой `run <name>`.
Worker-local stop сам по себе не запрашивает остановку приложения. В тесте нормального завершения
callback теперь явно вызывает `app.stop()`.

`AsyncBoostWorker` дополнительно сохраняет ошибку `run_async()`, если его собственный `shutdown()`
тоже завершился ошибкой: вторичная ошибка логируется. Если основной результат — отмена, отказ cleanup
передаётся наружу, чтобы штатная отмена после stop не скрыла отказ очистки. Существующие собственные
cleanup пути реальных адаптеров не изменялись; их lifecycle остаётся в связанных задачах, включая TB-005.

Обновлены [руководство запуска](../docs/running_application.md),
[пример custom lifecycle](../docs/advanced_usage.md), [API reference](../docs/api_reference.md)
и [архитектура](../ARCHITECTURE.md). Добавлены 18 регрессионных сценариев: ошибки при работающем peer,
сохранение исходного объекта/traceback, peer/own cleanup failure, timeout, unexpected return,
отмена до/после stop, остальные ошибки при shutdown, продолжение рассылки stop после ошибки callback.
Внутренняя команда Typer `run all` проверена настоящим `CliRunner` на ненулевой код и исходную ошибку
при `RuntimeError` worker. API тестирования Typer сверен через Context7.

Проверки выполнены 2026-11-07 на Python 3.13.9. Использован префикс
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync` для существующего окружения:

- До реализации четыре сценария `test_worker_failure_stops_peer_and_reaches_caller` падали;
  необработанные ошибки потоков дополнительно превращались в ошибки через
  `-W error::pytest.PytestUnhandledThreadExceptionWarning`.
- `pytest tests/test_boost_app.py tests/test_worker_coordinator.py --tb=short -q
  -W error::pytest.PytestUnhandledThreadExceptionWarning`: 70 passed, без предупреждений.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short`: 199 passed,
  покрытие 70%, без предупреждений. Выполнено вне sandbox с ранее разрешённой командой:
  существующие runtime-тесты открывают локальные Prometheus-порты.
- `ruff check --no-fix temporal_boost/ tests/test_worker_coordinator.py --output-format concise`:
  успешно.
- `ruff format --check temporal_boost/ tests/test_boost_app.py tests/test_worker_coordinator.py`:
  успешно, 25 файлов.
- `mypy temporal_boost/`: успешно, 23 файла.
- `mkdocs build --strict`: успешно.
- `ruff check --no-fix temporal_boost/ examples/ tests/test_worker_coordinator.py --output-format concise`:
  42 существующие ошибки только в неизменённых examples.
- `ruff format --check temporal_boost/ examples/ tests/test_boost_app.py tests/test_worker_coordinator.py`:
  пять существующих нарушений в неизменённых examples; остальные 35 файлов отформатированы.
- `git diff --check`: успешно.

Полная проверка кодов ОС через `BoostApp.run()` / внешний CLI, включая обработку `SystemExit`,
остаётся в TB-008 и TB-009, как предусмотрено исходной секцией проверки. Здесь подтверждены проброс
ошибок координатором и ненулевой результат внутренней команды Typer при обычной ошибке worker.
Существующие нарушения lint/format в examples не относятся к TB-003.

## Зависимости и связи

Зависит от: [TB-002](002-application-graceful-shutdown.md).

Связанные задачи: [TB-008](008-cli-exit-codes.md), [TB-020](020-meaningful-cli-unit-tests.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

