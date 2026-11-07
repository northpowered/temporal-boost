# TB-004. Подключить TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT к SDK worker

- **Статус:** done
- **Приоритет:** P1
- **Тип:** Баг

## Проблема и подтверждение

[config.py](../temporal_boost/temporal/config.py) читает `TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT` в `timedelta`, но [TemporalWorkerBuilder.build()](../temporal_boost/temporal/worker.py) эту константу не использует. [Руководство запуска](../docs/running_application.md) обещает ожидание activities до настроенного timeout.

Пользовательская настройка завершения не влияет на SDK worker; фактическое поведение расходится с настройками deployment.

## Что сделать

1. Добавить явный параметр `graceful_shutdown_timeout` в worker builder и передавать его в SDK `Worker`.
2. Использовать env-константу только при отсутствии явного значения; сохранить возможность настройки через `add_worker()`.
3. Проверять допустимость отрицательных значений и корректно обрабатывать явный нулевой `timedelta`.
4. Разграничить SDK grace period и общий timeout остановки приложения/процессов.

## Критерии приёмки

- [x] Default и значение из env доходят до конструктора SDK `Worker`.
- [x] Явный `timedelta` перекрывает env; передача через `worker_kwargs` не создаёт дублирующий аргумент.
- [x] Нулевое значение не заменяется default, отрицательное отклоняется понятной ошибкой.
- [x] Документация описывает фактический SDK timeout и его связь с общим shutdown budget.

## Проверка

Расширить [test_temporal_worker.py](../tests/test_temporal_worker.py), подменяя SDK `Worker`. Чтение env проверять в изолированном импорте или subprocess.

## Реализация и результаты проверки

В `TemporalWorkerBuilder` добавлен явный keyword-only параметр
`graceful_shutdown_timeout: timedelta | None = None`. Только `None` выбирает
`config.GRACEFUL_SHUTDOWN_TIMEOUT`; явно заданный `timedelta`, включая ноль, сохраняется.
Выбранная отрицательная длительность вызывает `ValueError` с именем параметра и требованием
неотрицательного значения при создании builder. Проверяется и отрицательный env, если выбран он;
неотрицательный override может его перекрыть. Существующее чтение env при импорте и fallback
нечислового текста к 30 секундам не менялись.

`build()` передаёт значение в SDK `Worker(graceful_shutdown_timeout=...)`. Цепочка
`BoostApp.add_worker(**worker_kwargs)` → `TemporalBoostWorker` → builder сохраняется без изменения
публичных сигнатур app/адаптера; явный параметр builder забирает значение из kwargs, поэтому дубля нет.

Контракт SDK сверен через Context7 и исходник установленного SDK (в lockfile Temporal SDK 1.14.1):
это grace period activities после запроса SDK shutdown, по истечении которого SDK запрашивает отмену.
Ноль пропускает grace period. SDK продолжает ждать activities, поэтому это не предел всей процедуры
shutdown. Бюджет `BoostApp.shutdown_timeout` и deadline внешнего supervisor остаются отдельными;
эта настройка сама не инициирует stop и не подключает Temporal adapter к coordinator (TB-005).

**Изменение поведения:** ранее при отсутствии override использовался default SDK — ноль;
теперь применяется framework default 30 секунд либо env. Миграция, пример per-worker override,
границы grace period и общего бюджета описаны в [configuration.md](../docs/configuration.md),
[running_application.md](../docs/running_application.md), [API reference](../docs/api_reference.md)
и [архитектуре](../ARCHITECTURE.md). Другие числовые параметры остаются областью TB-016.

В `tests/test_temporal_worker.py` добавлены 16 сценариев с подменой SDK `Worker`:
отсутствующий/положительный/нулевой/нечисловой/отрицательный env, `None`, положительный и нулевой
override, override отрицательного env, отрицательные секунды и микросекунды, передача через
`add_worker()` с сохранением остальных SDK kwargs и отказ при отрицательном значении регистрации.
Env проверяется через отдельный модуль config, загруженный `importlib.util`, без перезагрузки
общего модуля и нарушения ссылок других тестов. Temporal Server не требуется.

Проверки выполнены 2026-11-07 на Python 3.13.9. Использован префикс
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync` для существующего окружения:

- До исправления `pytest tests/test_temporal_worker.py -k graceful_shutdown_timeout --tb=short -q`:
  11 failed, 5 passed. После исправления полный файл: 54 passed.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short`: 215 passed, покрытие 70%,
  без предупреждений. Полный набор выполнен вне sandbox с ранее разрешённой командой:
  существующие runtime-тесты поднимают локальные Prometheus exporter.
- `ruff check --no-fix temporal_boost/ --output-format concise`: успешно.
- `ruff format --check temporal_boost/ tests/test_temporal_worker.py`: успешно, 24 файла.
- `mypy temporal_boost/`: успешно, 23 файла.
- `mkdocs build --strict`: успешно.
- `ruff check --no-fix temporal_boost/ examples/ --output-format concise`: 42 существующие ошибки
  только в неизменённых examples.
- `ruff format --check temporal_boost/ examples/ tests/test_temporal_worker.py`: пять существующих
  нарушений в неизменённых examples; остальные 34 файла отформатированы.
- `git diff --check`: успешно.

Фактическая длительность shutdown настоящих activities здесь не измерялась: проверен контракт
передачи аргумента в SDK, как предусмотрено задачей. Существующие ошибки examples не относятся к TB-004.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-002](002-application-graceful-shutdown.md), [TB-009](009-multiprocess-supervision.md), [TB-016](016-numeric-options-zero-fallback.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

