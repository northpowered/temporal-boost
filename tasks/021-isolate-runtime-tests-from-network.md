# TB-021. Отделить unit-тесты runtime от сетевых exporter

- **Статус:** done
- **Приоритет:** P2
- **Тип:** Тесты

## Проблема и подтверждение

Несколько тестов [test_temporal_runtime.py](../tests/test_temporal_runtime.py) создают настоящий SDK runtime и bind на фиксированные `0.0.0.0:9090`/`9091`. Они падают в sandbox с `Operation not permitted` и конкурируют за порты при параллельном запуске. Тестам конфигурации не нужен настоящий listener.

Базовая suite требует сетевых разрешений и свободных портов, а bind conflict может менять фактически проверяемую ветку на fallback.

## Что сделать

1. В unit-тестах подменить SDK Runtime и проверять содержимое `TelemetryConfig`/`PrometheusConfig`.
2. Вынести настоящий exporter в явно помеченные integration tests с отдельной командой запуска.
3. Для integration использовать loopback и выделенный временный порт/поддерживаемый bind на порт 0, гарантировать cleanup.
4. Не маскировать отказ exporter успехом по условию `runtime is not None`.

## Критерии приёмки

- [x] Unit suite проходит без открытия listening sockets.
- [x] Конфигурация и fallback проверяются по аргументам конструктора SDK.
- [x] Настоящий exporter проверяется отдельным тестом чтения metrics, а не лишь создания runtime.
- [x] Повторные/параллельные integration-запуски не зависят от фиксированных портов 9090/9091.

## Проверка

Запустить unit suite в sandbox без права bind, затем integration subset в окружении с разрешёнными локальными портами. Маркеры и команды отразить в `pyproject.toml` и документации разработки.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-011](011-prometheus-multiple-runtimes.md), [TB-012](012-telemetry-fallback-preservation.md), [TB-022](022-enforce-ci-quality-checks.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).


## Результат выполнения

SDK Runtime в конфигурационных тестах заменён doubles; проверяются identity и конкретные поля
TelemetryConfig/PrometheusConfig, а также кеширование runtime. Реальные HTTP/exporter тесты имеют
marker `integration`, по умолчанию исключённый через addopts. Autouse fixture запрещает Python
listening sockets в unit-группе; native SDK exporter в unit-тестах замокан. Реальные интеграции
читают metrics с временных loopback endpoints и завершают дочерние процессы.

Unit-группа прошла в sandbox без bind-разрешений: **774 passed, 1 skipped**.
Отдельная integration-группа с разрешёнными локальными портами: **52 passed, 2 skipped**.
Маркеры и команды описаны в корневом README; соответствующие группы добавлены в CI.
Fallback с отключёнными metrics не восстанавливается: сохраняется фатальная политика TB-011/TB-012.

Проверки выполнены после реализации всей серии 020–028 по явному указанию пользователя.
Общие команды и итоги: [результат серии](README.md#проверка-серии-tb-020tb-028).
