# TB-013. Реализовать управляемую остановку FastStream worker

- **Статус:** done
- **Приоритет:** P2
- **Тип:** Доработка

## Проблема и подтверждение

В [FastStreamBoostWorker](../temporal_boost/workers/faststream_worker.py) `shutdown()` только логирует завершение. Он не запрашивает остановку `app.run()` и не подтверждает завершение broker. `run()` владеет AnyIO loop, но cleanup запускается через отдельный `asyncio.run()`. Контракт вызова `app.run(log_level, faststream_kwargs)` не покрыт интеграционными тестами; несовместимость сигнатуры пока не подтверждена.

Общий coordinator не может надёжно остановить FastStream; фактическое закрытие ресурсов полностью зависит от внутреннего поведения приложения.

## Что сделать

1. Реализовать stop через публичный lifecycle API поддерживаемой версии FastStream и loop, владеющий ресурсами.
2. Обеспечить безопасный shutdown до старта, после ошибки и при повторном вызове.
3. Проверить текущую передачу аргументов `app.run()` по документации/сигнатуре и зафиксировать её тестом; менять её только при доказанном несоответствии.
4. Согласовать отмену, успешное завершение и ошибки: фатальная ошибка не должна теряться.
5. Обеспечить импорт базового пакета без extra faststream.

## Критерии приёмки

- [x] Внешний stop завершает `run()` за ограниченное время и приводит к закрытию broker через поддерживаемый API.
- [x] Cleanup не переносит loop-bound ресурсы в новый event loop.
- [x] Lifecycle и передача options проверены для версии из lockfile.
- [x] Отсутствующая зависимость и неверный тип app дают понятные ошибки без ложного сообщения об успешном shutdown.

## Проверка

Добавить `tests/test_faststream_worker.py` с lifecycle doubles и smoke-тест настоящего FastStream с тестовым/in-memory broker, если это поддерживается. Базовые unit-тесты не должны требовать Redis/Kafka/RabbitMQ.

## Реализация и результаты проверки

`FastStreamBoostWorker.request_stop()` подключён к coordinator: потокобезопасный неблокирующий
запрос запоминается до первого старта, отменяет pending startup и завершает managed wait.
Повторные stop/shutdown безопасны; поздний stop завершённого запуска не блокирует следующий запуск.
Concurrent run отклоняется. Async `shutdown()` дожидается общего cleanup на owning loop; из другого
loop или lifecycle callback нужно использовать `request_stop()`.

FastStream и AnyIO по-прежнему импортируются только при запуске. Неверный тип приложения отклоняется
до lifecycle, а отсутствующий extra даёт подсказку `Install temporal-boost[faststream]`.
Проверены импорт базового пакета без обеих optional dependencies и отсутствие ложного success log.

Контракт сверен через Context7 для FastStream 0.5.48 и установленный пакет из lockfile.
Прежняя позиционная передача `app.run(log_level, options)` корректна: второй параметр называется
`run_extra_options`; несовместимость сигнатуры не обнаружена. Причина перехода на публичные
`start(**options)` / `stop()` и `lifespan_context(**options)` — установка signal handlers внутри
`FastStream.run()`, невозможная в worker thread при `run all`.

Все ресурсы создаются и закрываются на одном asyncio loop, которым владеет AnyIO runner.
Lifespan входит/выходит в одной task, включая AnyIO task groups. Startup отменяется и join-ится
до stop; cleanup защищён от повторной отмены outer waiter и отменённого AnyIO scope lifespan.
При отказе shutdown hook дополнительно вызывается публичный `broker.stop()`. Исходная фатальная
ошибка сохраняется, вторичная cleanup error логируется; при обычной отмене ошибка cleanup получает
приоритет. `KeyboardInterrupt` / `SystemExit` доходят до вызывающего кода после закрытия loop.
Main-thread run обрабатывает SIGINT/SIGTERM и восстанавливает handlers; thread run их не меняет.

Миграция для кода с `app.exit()` / override `app.run()`: использовать `worker.request_stop()` и
публичные lifecycle hooks. Options по-прежнему доходят до startup hooks и lifespan. Это описано в
[FastStream guide](../docs/faststream_integration.md#managed-shutdown),
[running guide](../docs/running_application.md) и [архитектуре](../ARCHITECTURE.md).
Зависший пользовательский hook/broker может превысить бюджет coordinator; принудительного закрытия
потока adapter не выполняет. Живые Redis/Kafka/RabbitMQ здесь не запускались.

Проверки выполнены 2026-11-08 на Python 3.13.9 с префиксом
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync`:

- `pytest tests/test_faststream_worker.py -q --tb=short`: **25 passed**. Включены doubles,
  настоящий coordinator, subprocess SIGINT/SIGTERM и smoke FastStream 0.5.48 с
  `TestRedisBroker(connect_only=True)`: options, доставка сообщения, stop broker и lifespan exit.
  Сценарий ошибки background task в lifespan до исправления оставлял broker незакрытым.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short`: **442 passed, 2 skipped**,
  покрытие пакета **90%**, FastStream adapter **96%**. Выполнено вне sandbox после отказа
  локального bind в существующих ASGI/metrics tests. Opt-in Temporal Server tests пропущены.
- FastStream smoke выдаёт одно upstream `DeprecationWarning` о `JSONMessageFormat` Redis broker.
- `ruff check --no-fix temporal_boost/ tests/test_faststream_worker.py`: успешно.
- `ruff format --check temporal_boost/ tests/test_faststream_worker.py`: успешно, 25 файлов.
- `mypy temporal_boost/`: успешно, 24 файла.
- `mkdocs build --strict`: успешно; остаются существующие INFO-диагностики ссылок FastStream guide.
- `ruff check --no-fix temporal_boost/ examples/ tests/test_faststream_worker.py`: 39 существующих
  ошибок в неизменённых examples; package и новый тест проходят отдельную проверку.
- `ruff format --check temporal_boost/ examples/ tests/test_faststream_worker.py`: четыре существующих
  нарушения форматирования в неизменённых examples.
- `git diff --check`: успешно.

## Зависимости и связи

Зависит от: [TB-002](002-application-graceful-shutdown.md).

Связанные задачи: [TB-005](005-temporal-worker-startup-cleanup.md), [TB-009](009-multiprocess-supervision.md), [TB-022](022-enforce-ci-quality-checks.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

