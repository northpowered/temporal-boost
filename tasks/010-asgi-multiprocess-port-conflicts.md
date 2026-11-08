# TB-010. Предотвратить конфликт ASGI-портов при внешнем масштабировании

- **Статус:** done
- **Приоритет:** P2
- **Тип:** Доработка

## Проблема и подтверждение

[Внешний runner](../temporal_boost/cli/process_runner.py) запускает один и тот же набор CLI-аргументов в каждом процессе. При `--workers 3 ... run all` все ASGI-регистрации из [BoostApp](../temporal_boost/boost_app.py) получают один `host:port`. Общего listening socket или распределения ролей нет.

Штатная команда масштабирования Temporal consumer может одновременно запустить несколько конкурирующих HTTP-серверов и получить bind errors.

## Что сделать

1. Явно определить поддерживаемые сочетания внешних процессов и ASGI-регистраций.
2. Добавить проверяемую защиту: отклонять неподдерживаемый запуск с понятной рекомендацией либо реализовать поддерживаемое backend разделение socket.
3. Различать `run all`, выбор Temporal worker и выбор ASGI worker; не запрещать безопасные сценарии.
4. Обновить deployment-примеры: HTTP и Temporal consumers могут масштабироваться отдельно.

## Критерии приёмки

- [x] Неподдерживаемый запуск не приводит к нескольким молча падающим HTTP-серверам.
- [x] Для `--workers > 1` документированы безопасные команды с конкретным worker.
- [x] Защита учитывает фактически выбранную команду, а не просто наличие ASGI в приложении.
- [x] Если поддержан общий socket, есть интеграционное доказательство корректного приёма запросов и shutdown.
  Не применяется: выбран явный отказ, общий socket не реализован и не заявлен.

## Проверка

Добавить тесты preflight/выбора команд и subprocess-сценарий с двумя процессами. В тестах использовать временный порт; базовый вариант не должен требовать Temporal Server.

## Реализация

- Выбран общий для всех ASGI backend контракт: внешний `--workers > 1` отклоняет `run all`, если
  среди worker есть ASGI, и `run <asgi-name>`. Ошибка Typer с code 2 возникает до запуска любого
  выбранного worker; сообщение перечисляет ASGI workers и рекомендует `--workers 1` для HTTP,
  отдельный `run <consumer-name>` для масштабирования Temporal. Supervisor TB-009 сохраняет code 2.
- Process runner передаёт число процессов child target. `cli/process_context.py` ограничивает его
  контекстом CLI через `ContextVar` с восстановлением в `finally`; новый parent-side import приложения
  не нужен. Проверки выполняются в фактически выбранных callback после штатного разбора Typer,
  без повторного разбора argv или отдельного вызова CLI для preflight.
- Для `run all` проверяется фактический список `get_registered_workers()` перед coordinator. Для
  отдельного ASGI callback используется обёртка с `functools.wraps`, сохраняющая сигнатуру и исходный
  bound method. Проверка `isinstance(BaseAsgiWorker)` покрывает Uvicorn, Hypercorn, Granian и custom
  ASGI, в том числе через `add_async_runtime()`, без опоры на неиспользуемый ASGI registry-list.
- `--workers 1` и прямой CLI приложения остаются допустимы. Выбор Temporal worker, CRON, exec и help
  допустим при зарегистрированном ASGI; неизвестные команды/параметры сохраняют обычную диагностику.
  Произвольный запуск HTTP из exec/import-time кода остаётся ответственностью приложения.
- Добавлены **30 сценариев**, из них **7 subprocess** через установленную entry point без Temporal
  Server и optional ASGI backend. Проверены code 2 до HTTP bind/старта peers для двух процессов,
  выполнение Temporal/CRON/exec в двух разных PID, HTTP help, single-process bind на временном порту,
  все backend, custom registration, сохранение CLI-параметров и reset контекста после ошибки.
  Socket probe — настоящий `BaseAsgiWorker` с bind/listen; Temporal subclass только фиксирует dispatch
  без сетевого соединения. Реальные lifecycle сторонних ASGI серверов не менялись и остаются TB-014.
- Running guide/API/`ARCHITECTURE.md` описывают матрицу сочетаний и миграцию. Deployment-примеры и
  заголовок `examples/example_fastapi.py` показывают отдельные HTTP/consumer команды; Compose использует
  контейнерный порт для балансировщика без общего фиксированного host port у HTTP replicas.
  Backend-specific kwargs не включают shared-socket режим внешнего launcher.

## Фактическая проверка

Выполнено 2026-11-08 на Python 3.13.9. Общий префикс команд:
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync`.

- Исходные regression tests до добавления защиты — **7 failed, 13 passed**.
- `pytest tests/test_asgi_multiprocess.py tests/test_process_runner.py tests/test_cli.py tests/test_boost_app.py -q --tb=short`
  — **178 passed**; затем добавлена финальная проверка сохранения параметров custom ASGI, вошедшая
  в полный набор ниже.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short` — **394 passed, 1 skipped**,
  покрытие **88%**, `cli/process_context.py` **100%**, `boost_app.py` **96%**. Opt-in real Temporal
  integration пропущен: политика запуска проверяется без внешних сервисов.
  Проверки с временными портами и полный набор выполнены вне sandbox: внутри sandbox fixture
  `unused_tcp_port` получает `PermissionError` при localhost bind; существующие Prometheus tests
  также требуют localhost bind.
- `ruff check --no-fix temporal_boost/ tests/test_asgi_multiprocess.py tests/asgi_multiprocess_app.py --output-format concise`
  — **passed**.
- `ruff format --check temporal_boost/ tests/test_asgi_multiprocess.py tests/asgi_multiprocess_app.py`
  — **passed**, 26 файлов.
- Общие `ruff check --no-fix temporal_boost/ examples/ --output-format concise` и
  `ruff format --check temporal_boost/ examples/` сохраняют **39 существующих lint errors** и
  **4 formatting failures** в коде examples. В FastAPI example изменены только инструкции запуска;
  существующие ошибки самого примера не исправлялись в этой задаче.
- `mypy temporal_boost/` — **passed**, 24 файла.
- `mkdocs build --strict` — **passed**; старые информационные сообщения о ссылках
  в `faststream_integration.md` остаются.
- `git diff --check` — **passed**.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-009](009-multiprocess-supervision.md), [TB-014](014-asgi-lifecycle-and-event-loops.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

