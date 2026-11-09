# TB-015. Исключить молчаливое игнорирование поздней конфигурации

- **Статус:** done
- **Приоритет:** P2
- **Тип:** Баг

## Проблема и подтверждение

[configure_temporal_runtime()](../temporal_boost/workers/temporal.py) заменяет `_runtime_builder`, но закешированный `_runtime` остаётся прежним. Аналогично изменение client builder после `_build_worker()` не меняет уже подключённый `_client` или SDK worker. Вызовы выглядят успешными, хотя параметры не применены.

Изменение endpoint, namespace или telemetry может не иметь эффекта без какой-либо ошибки.

## Что сделать

1. Выбрать контракт конфигурации по состояниям lifecycle: безопасная перестройка до запуска или явная ошибка после соответствующей инициализации.
2. Не оставлять builder и действующие объекты в противоречащих друг другу состояниях.
3. Не выполнять неявный reconnect или замену runtime работающего worker.
4. Описать момент фиксации настроек, включая побочный эффект обращения к `temporal_client_runtime`.

## Критерии приёмки

- [x] Настройка до инициализации применяется.
- [x] После первого создания runtime новый вызов configure либо безопасно меняет ещё не используемый runtime, либо явно отклоняется.
- [x] Поздняя настройка client/worker не принимается молча без эффекта.
- [x] Тесты охватывают created, initialized, running и stopped состояния по выбранному контракту.

## Проверка

Расширить [test_temporal_worker.py](../tests/test_temporal_worker.py) проверками идентичности runtime/client, вызовов builders и ошибок недопустимой конфигурации.

## Реализация и результаты проверки

Выбран контракт явного отказа до завершения cleanup, без автоматической замены объектов:

- Runtime-конфигурация фиксируется при первом успешном создании SDK runtime. Чтение
  `temporal_client_runtime` создаёт/кеширует runtime и может открыть Prometheus-порт, даже когда
  lifecycle ещё `created`. После этого `configure_temporal_runtime()` выбрасывает `RuntimeError`.
  Client до начала собственной инициализации по-прежнему можно настроить.
- Client-конфигурация фиксируется в начале `_build_worker()`, до await подключения. Guard покрывает
  и прямую инициализацию без активного lifecycle. Повторная сборка уже созданных ресурсов отклоняется,
  вместо неявного reconnect и замены SDK worker. Наличие client/worker также запрещает configure.
- Во всех активных состояниях `building`, `running`, `stopping` обе configure-функции отклоняются,
  включая вызовы до создания соответствующего SDK объекта. Guard и изменения builders выполняются
  под lifecycle lock. Ленивое создание runtime сериализовано тем же lock. Default builders создаются
  внутренними путями, без вызова публичных configure-функций во время запуска.
- После полного cleanup (`stopped`) ссылки освобождены и настройки снова доступны для следующего
  run. Следующий запуск использует свежие runtime/client/SDK worker с новыми endpoint/namespace/telemetry.
  Чтение runtime property после cleanup снова фиксирует его параметры. Ошибка конструктора runtime
  без кешированного объекта позволяет перенастройку перед retry вне активного lifecycle.
- Отклонённый вызов не меняет builders или действующие SDK objects. Во время stopping runtime
  property не создаёт отсутствующий runtime. Runtime/Client SDK не получают придуманных close API;
  внешние ссылки могут продлить жизнь старого exporter. Worker tuning остаётся настройкой конструктора,
  standalone builders сохраняют изменяемость для будущих build.

Миграция: перенести configure до run/cron и до первого чтения runtime property либо дождаться
stop/join/cleanup и настроить следующий run. Для замены initialized preview без запуска используется
новый adapter; освобождение внешних runtime references нужно учитывать перед повторным bind порта.
Контракт и побочный эффект runtime property описаны в [configuration guide](../docs/configuration.md#when-configuration-becomes-fixed),
[API](../docs/api_reference.md) и [архитектуре](../ARCHITECTURE.md).

Добавлены семь тестов в `test_temporal_worker.py` / `test_temporal_lifecycle.py`: pre-initialization
overrides, freeze runtime property, identity и неизменность builders после отказа, запрет повторной
сборки, pending client connect без активного run, retry failed runtime, запрет конфигурации в
building/running/stopping (в том числе из другого потока), перенастройка stopped и fresh objects
следующего запуска. Проверены реальные передаваемые SDK kwargs и telemetry configuration на doubles.
Существующий converter regression теперь проверяет отказ позднего configure и перенастройку после
освобождения ресурсов, сохраняя проверку приоритета explicit converter. Partial-startup failure tests
дополнены проверкой доступности configure после cleanup.

Проверки выполнены 2026-11-09 на Python 3.13.9 с префиксом
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync`:

- До исправления два regression-теста падали: configure после runtime property и configure после
  создания SDK objects не выбрасывали исключений.
- `pytest tests/test_temporal_worker.py tests/test_temporal_lifecycle.py tests/test_temporal_client.py
  -k 'not configure_pydantic_override_matrix and not temporal_client_runtime_property and not test_build_worker'
  -q --tb=short`: **124 passed, 8 deselected**. Сценарии с настоящим runtime включены в полный suite.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short`: **535 passed, 2 skipped**,
  покрытие пакета **94%**, Temporal adapter **95%**. Полный suite выполнен вне sandbox для существующих
  HTTP/metrics tests с локальным bind. Opt-in Temporal Server tests пропущены; остаётся одно upstream
  FastStream Redis deprecation warning. Живой Temporal Server не требовался для новых тестов.
- `ruff check --no-fix temporal_boost/ tests/test_temporal_lifecycle.py`: успешно.
- `ruff check --no-fix tests/test_temporal_worker.py --output-format concise`: 60 существующих
  нарушений. Сравнение с `git show HEAD:tests/test_temporal_worker.py` через тот же Ruff показывает
  те же 60 нарушений; новые тесты не добавляют diagnostics. Legacy lint cleanup остаётся вне TB-015.
- `ruff format --check temporal_boost/ tests/test_temporal_worker.py tests/test_temporal_lifecycle.py`:
  успешно, 27 файлов.
- `mypy temporal_boost/`: успешно, 25 файлов.
- `mkdocs build --strict`: успешно; сохраняются существующие INFO-диагностики ссылок FastStream guide.
- `ruff check --no-fix temporal_boost/ examples/ --output-format concise`: 39 существующих ошибок
  только в неизменённых examples.
- `ruff format --check temporal_boost/ examples/ tests/test_temporal_worker.py tests/test_temporal_lifecycle.py`:
  четыре существующих нарушения в неизменённых examples; остальные 39 файлов отформатированы.
- `git diff --check`: успешно.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-005](005-temporal-worker-startup-cleanup.md), [TB-011](011-prometheus-multiple-runtimes.md), [TB-017](017-configuration-priority-documentation.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

