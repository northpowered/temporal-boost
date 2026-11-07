# Технический бэклог Temporal-boost

Бэклог составлен по коду версии `2.0.2`, тестам и локальной документации, разобранным в
[ARCHITECTURE.md](../ARCHITECTURE.md). Каждая проблема хранится в отдельном файле с постоянным ID `TB-NNN`.
Всего **28 задач**: P1 — 8, P2 — 16, P3 — 4. Актуальные статусы и результаты проверок указаны в карточках;
создание карточки не означает, что исправление уже выполнено.

## Приоритеты и типы

- **P1** — потеря ошибок, нарушение остановки, дублирование выполнения или существенная потеря наблюдаемости.
- **P2** — функциональная корректность, совместимость, надёжность проверок и документация рабочего API.
- **P3** — предсказуемость выбора реализаций, отдельные примеры и вспомогательная инфраструктура.

Приоритеты — начальная техническая оценка, а не согласованный срок релиза. Подтверждённые баги отмечены
в поле «Тип». Доработки и проверки совместимости сформулированы отдельно: отсутствие теста не считается
доказательством конкретного сбоя зависимости. Проверяемые предположения указаны внутри соответствующих задач.

## Реестр

| ID | Приоритет | Тип | Задача | Зависит от |
| --- | --- | --- | --- | --- |
| [TB-001](001-pydantic-converter-boolean-override.md) | P1 | Баг | Исправить отключение Pydantic converter | — |
| [TB-002](002-application-graceful-shutdown.md) | P1 | Доработка | Добавить согласованное завершение приложения | — |
| [TB-003](003-thread-worker-failure-propagation.md) | P1 | Баг | Передавать ошибки worker из потоков координатору | [TB-002](002-application-graceful-shutdown.md) |
| [TB-004](004-wire-graceful-shutdown-timeout.md) | P1 | Баг | Подключить TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT к SDK worker | — |
| [TB-005](005-temporal-worker-startup-cleanup.md) | P2 | Баг | Сделать lifecycle Temporal worker безопасным при частичном старте | — |
| [TB-006](006-cron-workflow-idempotency.md) | P1 | Баг | Исключить дублирование CRON workflow при перезапуске | — |
| [TB-007](007-cron-registration-and-run-contract.md) | P2 | Баг и документация | Валидировать CRON-регистрацию и явно описать режимы запуска | — |
| [TB-008](008-cli-exit-codes.md) | P1 | Баг | Сохранять коды завершения CLI | — |
| [TB-009](009-multiprocess-supervision.md) | P1 | Баг | Контролировать отказ и завершение дочерних процессов | [TB-002](002-application-graceful-shutdown.md), [TB-008](008-cli-exit-codes.md) |
| [TB-010](010-asgi-multiprocess-port-conflicts.md) | P2 | Доработка | Предотвратить конфликт ASGI-портов при внешнем масштабировании | — |
| [TB-011](011-prometheus-multiple-runtimes.md) | P1 | Доработка | Обеспечить полные метрики нескольких worker и процессов | — |
| [TB-012](012-telemetry-fallback-preservation.md) | P2 | Баг | Сохранять telemetry-настройки при конфликте exporter | — |
| [TB-013](013-faststream-managed-shutdown.md) | P2 | Доработка | Реализовать управляемую остановку FastStream worker | [TB-002](002-application-graceful-shutdown.md) |
| [TB-014](014-asgi-lifecycle-and-event-loops.md) | P2 | Доработка | Унифицировать lifecycle ASGI-адаптеров | [TB-002](002-application-graceful-shutdown.md) |
| [TB-015](015-configuration-after-initialization.md) | P2 | Баг | Исключить молчаливое игнорирование поздней конфигурации | — |
| [TB-016](016-numeric-options-zero-fallback.md) | P2 | Баг | Различать None и ноль в настройках SDK worker | — |
| [TB-017](017-configuration-priority-documentation.md) | P2 | Документация | Согласовать документацию и тесты приоритета конфигурации | — |
| [TB-018](018-custom-worker-registration-contract.md) | P2 | Баг | Исправить регистрацию пользовательских worker | — |
| [TB-019](019-importer-error-diagnostics.md) | P2 | Баг | Различать отсутствие приложения и ошибки его зависимостей | — |
| [TB-020](020-meaningful-cli-unit-tests.md) | P2 | Тесты | Устранить ложноположительные тесты BoostApp.run | — |
| [TB-021](021-isolate-runtime-tests-from-network.md) | P2 | Тесты | Отделить unit-тесты runtime от сетевых exporter | — |
| [TB-022](022-enforce-ci-quality-checks.md) | P2 | Технический долг | Сделать проверки типов и примеров обязательными в CI | — |
| [TB-023](023-runtime-documentation-examples.md) | P2 | Документация | Исправить примеры построения и разделения runtime | — |
| [TB-024](024-runnable-custom-worker-example.md) | P3 | Баг в примере | Сделать пример пользовательского worker исполнимым | [TB-018](018-custom-worker-registration-contract.md) |
| [TB-025](025-declare-direct-click-dependency.md) | P3 | Зависимости | Объявить используемую напрямую зависимость Click | — |
| [TB-026](026-remove-private-sdk-cli-apis.md) | P2 | Совместимость | Устранить зависимость от приватных API SDK и Click | — |
| [TB-027](027-explicit-asgi-auto-priority.md) | P3 | Доработка | Сделать приоритет автоматического ASGI backend явным | — |
| [TB-028](028-prometheus-temp-directory-ownership.md) | P3 | Технический долг | Определить необходимость и cleanup Prometheus multiprocess directory | [TB-011](011-prometheus-multiple-runtimes.md) |

## Порядок работы

Независимые исправления [TB-001](001-pydantic-converter-boolean-override.md), [TB-004](004-wire-graceful-shutdown-timeout.md), [TB-006](006-cron-workflow-idempotency.md) и [TB-008](008-cli-exit-codes.md) можно брать первыми.
[TB-002](002-application-graceful-shutdown.md) задаёт общий контракт остановки; после него выполняются [TB-003](003-thread-worker-failure-propagation.md), [TB-013](013-faststream-managed-shutdown.md), [TB-014](014-asgi-lifecycle-and-event-loops.md)
и вместе с [TB-008](008-cli-exit-codes.md) — [TB-009](009-multiprocess-supervision.md). Для metrics сначала нужно определить топологию в [TB-011](011-prometheus-multiple-runtimes.md),
после чего решать судьбу multiprocess directory в [TB-028](028-prometheus-temp-directory-ownership.md). Исправление fallback [TB-012](012-telemetry-fallback-preservation.md)
можно делать отдельно, не считая его решением полноты metrics.

Исправления тестов [TB-020](020-meaningful-cli-unit-tests.md) и [TB-021](021-isolate-runtime-tests-from-network.md) полезно делать рано. Ужесточение CI [TB-022](022-enforce-ci-quality-checks.md) должно
сопровождаться устранением обнаруженных ошибок; нельзя просто скрыть их другими blanket-исключениями.
Это рекомендуемая последовательность, жёсткие зависимости перечислены в таблице и самих карточках.

## Как выполнять и закрывать задачи

1. Прочитать [AGENTS.md](../AGENTS.md), архитектуру, исходники и связанные задачи. Ссылки на код
   показывают подтверждение на момент составления; перед реализацией проверить актуальное состояние.
2. Взять одну проблему, уточнить контракт и обновить статус на `in_progress`. При несовместимом изменении
   явно описать миграцию; не расширять задачу новым продуктовым поведением без основания.
3. Добавить содержательный регрессионный тест, реализовать изменение, обновить затронутые guides,
   примеры и `ARCHITECTURE.md`. Тесты не должны просто повторять детали реализации.
4. Выполнить релевантные проверки и полный набор, требуемый правилами репозитория. Для документационных
   задач проверить Markdown/ссылки и MkDocs, если меняется сайт. Документацию зависимостей искать через Context7.
5. Отметить критерии приёмки, записать фактические команды и результат в карточку, затем поставить `done`.
   Непроверенный сценарий указать явно; код без необходимых проверок не считается завершением задачи.

Допустимые статусы: `backlog`, `in_progress`, `blocked`, `done`, `cancelled`.
У `blocked` должна быть конкретная причина, у `cancelled` — объяснение и ссылка на замену при наличии.
«Зависит от» означает порядок выполнения; «Связанные задачи» — общий контекст и границу ответственности,
а не дополнительную блокировку. ID и имена существующих карточек сохраняются для стабильных ссылок.

