# TB-007. Валидировать CRON-регистрацию и явно описать режимы запуска

- **Статус:** done
- **Приоритет:** P2
- **Тип:** Баг и документация

## Проблема и подтверждение

[BoostApp.add_worker()](../temporal_boost/boost_app.py) создаёт CRON-команду только если одновременно truthy `cron_schedule` и `cron_runner`. Один переданный параметр молча принимается. `run <name>` и `run all` вызывают обычный `run()`, поэтому сами не создают расписание. В пользовательском API граница обслуживания очереди и регистрации CRON недостаточно очевидна.

Приложение может успешно запуститься с незарегистрированной плановой задачей, а ошибка обнаружится только по отсутствию результата.

## Что сделать

1. Проверять наличие пары CRON-параметров при регистрации через `BoostApp` и прямое создание worker.
2. Описать контракт `run`, `run all`, `cron <name>` в guides и примере CRON.
3. Сохранить явное создание расписания через `cron`; не добавлять неявный серверный side effect в обычный запуск.
4. Проверить ошибки получения `temporal_cron_runner` и ручного вызова `cron()` без полной конфигурации.

## Критерии приёмки

- [x] Передача только одного CRON-параметра сразу даёт понятную ошибку.
- [x] Обычный `run all` не вызывает `start_workflow()`; CRON-команда регистрируется только для полной конфигурации.
- [x] Примеры запуска различают consumer и создание/поддержание CRON workflow.
- [x] Все проверки выполняются до открытия подключения, когда это возможно.

## Проверка

Обновить [test_boost_app.py](../tests/test_boost_app.py), [test_temporal_worker.py](../tests/test_temporal_worker.py) и [example_cron.py](../examples/example_cron.py). CLI проверять через `CliRunner`.

## Реализация

- Конструктор `TemporalBoostWorker` проверяет пару `cron_schedule` / `cron_runner` до создания builder.
  Пара должна быть полностью задана либо полностью отсутствовать; явно пустое или пробельное расписание
  также вызывает `ValueError`. Через `BoostApp.add_worker()` ошибка происходит до настройки client,
  добавления worker в реестры и регистрации CLI-команд. Для перехода со старой частичной конфигурации
  нужно добавить недостающий параметр либо убрать оба CRON-параметра.
- `cron()` проверяет конфигурацию до `asyncio.run()`; async entry point и registration helper — до
  сборки/обращения к client. Ручной запуск CRON на consumer даёт понятный `RuntimeError`.
  Свойство `temporal_cron_runner` сохраняет понятную ошибку при отсутствии runner.
- `run <name>` и `run all` обслуживают очереди без вызова `start_workflow()`; `cron <name>` доступен
  только для полной пары и регистрирует/переиспользует цепочку один раз, продолжая обслуживать очередь.
  CLI help, guides, API reference, CRON example и архитектура описывают этот контракт и отсутствие
  серверной регистрации при локальном `add_worker()`.
- При проверке исходного checkout обнаружено повреждённое объединение TB-005/TB-006: отсутствовали
  импорты `Literal`, `threading`, `FutureCancelledError`; второй `_register_cron()` перекрывал стабильные
  ID старым UUID-путём, а CRON entry point повторно запускал сборку через SDK context manager.
  Восстановлены импорты и один lifecycle: `_register_cron()` возвращает handle со стабильным ID,
  `_register_cron_and_wait()` выполняет регистрацию и локальное ожидание под общим cleanup TB-005.
  CRON/lifecycle doubles обновлены под этот общий путь; идемпотентность TB-006 сохранена.
- Добавлены 18 regression scenarios: неполные/пустые пары в обоих API, отсутствие частичной
  регистрации, ошибки ручного и async CRON до сборки, отсутствие CRON-команды у consumer и реальные
  вызовы `CliRunner` для всех трёх режимов с выполнением lifecycle на SDK doubles.

## Фактическая проверка

Проверки выполнены 2026-11-08 на Python 3.13.9. Общий префикс команд:
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync`.

- До исправления 14 выбранных новых validation scenarios падали. Исходный checkout также не проходил
  collection из-за отсутствующего импорта `Literal`.
- `pytest tests/test_temporal_worker.py tests/test_boost_app.py tests/test_temporal_lifecycle.py
  tests/test_cron_workflow_idempotency.py -q --tb=short
  -W error::pytest.PytestUnhandledThreadExceptionWarning` — **148 passed**.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short` — **267 passed, 1 skipped**,
  покрытие **76%**, Temporal adapter **95%**. Opt-in integration проверен отдельно.
  Полный набор выполнен вне sandbox из-за существующих localhost Prometheus bind.
- `TEMPORAL_BOOST_INTEGRATION=1 … pytest tests/test_cron_integration.py -q --tb=short` — **1 passed**,
  Temporal CLI **1.10.0**, Server **1.32.2**: отдельные процессы используют одну цепочку,
  закрытые ID отклоняются. Выполнено с разрешением на запуск локального сервера.
- `ruff check --no-fix temporal_boost/ examples/example_cron.py tests/test_cron_workflow_idempotency.py
  tests/test_temporal_lifecycle.py --output-format concise` — **passed**.
- `ruff format --check temporal_boost/ examples/example_cron.py tests/test_boost_app.py
  tests/test_temporal_worker.py tests/test_temporal_lifecycle.py tests/test_cron_workflow_idempotency.py`
  — **passed**, 28 файлов.
- Общие `ruff check --no-fix temporal_boost/ examples/ --output-format concise` и
  `ruff format --check temporal_boost/ examples/` сохраняют **39 существующих lint errors** и
  **4 formatting failures** только в других, неизменённых examples.
- `mypy temporal_boost/` — **passed**, 23 файла.
- `mkdocs build --strict` — **passed**; старые информационные сообщения о ссылках
  в `faststream_integration.md` остаются.
- `git diff --check` — **passed**.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-005](005-temporal-worker-startup-cleanup.md), [TB-006](006-cron-workflow-idempotency.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

