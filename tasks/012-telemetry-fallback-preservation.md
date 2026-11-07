# TB-012. Сохранять telemetry-настройки при конфликте exporter

- **Статус:** backlog
- **Приоритет:** P2
- **Тип:** Баг

## Проблема и подтверждение

В [TemporalRuntimeBuilder.build()](../temporal_boost/temporal/runtime.py) fallback создаёт пустой `TelemetryConfig()`, теряя logging, tags, prefix и service-name настройки. Ветка зависит от поля `_prometheus_bind_address`, поэтому не охватывает явно переданный `metrics=PrometheusConfig(...)` при `None` в этом поле. Разбор адреса через `split(":")` способен дополнительно сломаться на IPv6 и скрыть первоначальную ошибку.

Восстановление после конфликта порта меняет не только metrics, а диагностика зависит от способа задания одной и той же конфигурации.

## Что сделать

1. Определять фактический используемый metrics backend и его bind address.
2. При выбранной политике отключения metrics сохранять остальные поля исходного `TelemetryConfig`.
3. Не разбирать host:port небезопасным `split(":")`; логировать фактический endpoint.
4. Не классифицировать произвольную ошибку SDK как bind conflict; сохранять исходную причину.
5. Согласовать поведение с общей топологией metrics, не подменяя её тихим fallback.

## Критерии приёмки

- [ ] После fallback сохранены logging, global tags, attach_service_name и metric_prefix.
- [ ] Одинаковые Prometheus-настройки через поле адреса и через `metrics` дают одинаковый результат.
- [ ] IPv4, hostname и IPv6 не вызывают вторичную ошибку обработки исключения.
- [ ] Ошибки, не связанные с конфликтом порта, пробрасываются без изменения; log не сообщает о несуществующем exporter.

## Проверка

Обновить [test_temporal_runtime.py](../tests/test_temporal_runtime.py), проверяя оба вызова конструктора SDK Runtime и все поля telemetry, а не только количество вызовов.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-011](011-prometheus-multiple-runtimes.md), [TB-021](021-isolate-runtime-tests-from-network.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

