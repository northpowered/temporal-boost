# TB-006. Исключить дублирование CRON workflow при перезапуске

- **Статус:** done
- **Приоритет:** P1
- **Тип:** Баг

## Проблема и подтверждение

[TemporalBoostWorker._run_with_cron()](../temporal_boost/workers/temporal.py) при каждом запуске генерирует новый UUID и вызывает `start_workflow(cron_schedule=...)`. Локальная остановка не отменяет серверный workflow. Повторный deployment или несколько процессов создают независимые расписания одной бизнес-задачи.

Одна плановая операция может выполняться несколько раз после рестартов и масштабирования.

## Что сделать

1. Добавить поддерживаемый способ задать стабильный workflow ID; выбрать и описать default и миграцию со старых UUID.
2. Определить поведение при уже существующем запущенном workflow и при завершённом workflow с тем же ID через поддерживаемые SDK policies.
3. Сделать одновременный запуск нескольких runner безопасным и наблюдаемым.
4. Документировать, что остановка локального consumer не удаляет серверное расписание и как управлять уже созданными дублями.
5. Сохранить текущий механизм `cron_schedule`; переход на Temporal Schedules рассматривать отдельно.

## Критерии приёмки

- [x] Повторный запуск с одним логическим CRON ID не создаёт вторую активную цепочку.
- [x] Гонка двух процессов обрабатывается штатно, без создания разных UUID для одной регистрации.
- [x] Политики для существующего и завершённого workflow заданы явно и покрыты тестами.
- [x] В документации есть порядок перехода и обнаружения старых UUID-расписаний без автоматического удаления пользовательских workflow.

## Проверка

Unit-тесты аргументов и конфликтов `start_workflow()` плюс интеграционный сценарий повторного/конкурентного запуска с тестовым Temporal Server.

## Реализация

- В `BoostApp.add_worker()` и прямой конструктор `TemporalBoostWorker` добавлен `cron_workflow_id`;
  он не передаётся в SDK Worker kwargs. Default —
  `temporal-boost/cron/<percent-encoded task_queue>/<percent-encoded worker_name>`,
  доступен через read-only property. Явный ID сохраняется без изменений; пустой/пробельный запрещён.
- `_register_cron()` использует серверные `USE_EXISTING` для running и `REJECT_DUPLICATE` для closed.
  Ошибки не скрываются, fallback на UUID отсутствует. Защита closed ID ограничена retention истории.
  Лог содержит namespace, workflow ID и run ID ответа, не обещает отличить создание от reuse.
- Guides, API reference, CRON example и архитектура описывают стабильность ID, неизменность конфигурации
  при reuse и сохранение серверной цепочки после локального stop. Migration guide включает инвентаризацию
  старых UUID, сохранение выбранного UUID или переход на новый ID и ручное закрытие проверенных дублей.
  Автоматической отмены/удаления пользовательских workflow нет; механизм остаётся SDK `cron_schedule`.
- Добавлены 11 unit-тестов и opt-in интеграционный тест настоящего Temporal dev server. Последний
  проверяет одновременную регистрацию из двух отдельных Python-процессов, повторную регистрацию
  из нового процесса и отказ для terminated/completed ID. Длительный lifecycle worker остаётся TB-005;
  валидация пары CRON-параметров — TB-007.

## Фактическая проверка

Все команды ниже выполнены с `UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync`:

- `pytest tests/test_cron_workflow_idempotency.py -q --tb=short` — **11 passed**.
- `TEMPORAL_BOOST_INTEGRATION=1 … pytest tests/test_cron_integration.py -q --tb=short` — **1 passed**,
  Temporal CLI **1.10.0**, Server **1.32.2**. После отказа скачивания в sandbox выполнено с разрешением
  на сеть и запуск локального сервера. Проверка не использует внешний namespace.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short` — **226 passed, 1 skipped**,
  покрытие **71%**; opt-in integration пропущен здесь и отдельно выполнен выше. Полный набор выполнен
  вне sandbox из-за существующих runtime-тестов с localhost Prometheus bind.
- `ruff check --no-fix temporal_boost/ examples/example_cron.py tests/test_cron_workflow_idempotency.py tests/test_cron_integration.py`
  и `ruff format --check` с теми же путями — **passed**.
- Общий `ruff check --no-fix temporal_boost/ examples/` — **39 существующих ошибок в других examples**;
  общий `ruff format --check temporal_boost/ examples/` — **4 других example-файла требуют форматирования**.
  Эти файлы не изменены в рамках задачи.
- `mypy temporal_boost/` — **passed**, 23 source files.
- `mkdocs build --strict` — **passed**; остаются информационные сообщения о старых ссылках
  в `faststream_integration.md`.
- `git diff --check` — **passed**.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-007](007-cron-registration-and-run-contract.md), [TB-009](009-multiprocess-supervision.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

