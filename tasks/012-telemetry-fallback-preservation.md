# TB-012. Сохранять telemetry-настройки при конфликте exporter

- **Статус:** cancelled
- **Приоритет:** P2
- **Тип:** Баг

## Причина отмены

Заменено политикой [TB-011](011-prometheus-multiple-runtimes.md): SDK runtime initialization failure,
включая конфликт Prometheus endpoint, теперь пробрасывается без повторного создания runtime с отключённой
telemetry. Восстановления через fallback больше нет, поэтому сохранять его настройки не требуется.
TB-011 также использует фактический backend/address для диагностики, не разбирает host:port и сохраняет
исходные SDK ошибки. Исходные критерии ниже описывают удалённый fallback и сохраняются как история задачи.

## Исходная проблема и подтверждение

До TB-011 в [TemporalRuntimeBuilder.build()](../temporal_boost/temporal/runtime.py) fallback создавал пустой `TelemetryConfig()`, теряя logging, tags, prefix и service-name настройки. Ветка зависела от поля `_prometheus_bind_address`, поэтому не охватывала явно переданный `metrics=PrometheusConfig(...)` при `None` в этом поле. Разбор адреса через `split(":")` мог дополнительно сломаться на IPv6 и скрыть первоначальную ошибку.

Восстановление после конфликта порта меняло не только metrics, а диагностика зависела от способа задания одной и той же конфигурации.

## Что сделать

1. Определять фактический используемый metrics backend и его bind address.
2. При выбранной политике отключения metrics сохранять остальные поля исходного `TelemetryConfig`.
3. Не разбирать host:port небезопасным `split(":")`; логировать фактический endpoint.
4. Не классифицировать произвольную ошибку SDK как bind conflict; сохранять исходную причину.
5. Согласовать поведение с общей топологией metrics, не подменяя её тихим fallback.

## Исходные критерии приёмки

- [ ] После fallback сохранены logging, global tags, attach_service_name и metric_prefix.
- [ ] Одинаковые Prometheus-настройки через поле адреса и через `metrics` дают одинаковый результат.
- [ ] IPv4, hostname и IPv6 не вызывают вторичную ошибку обработки исключения.
- [ ] Ошибки, не связанные с конфликтом порта, пробрасываются без изменения; log не сообщает о несуществующем exporter.

## Проверка

Изначально планировалось проверить оба вызова конструктора SDK Runtime и все поля telemetry в
[test_temporal_runtime.py](../tests/test_temporal_runtime.py). После TB-011 корректен ровно один вызов:
ошибка SDK пробрасывается, повторной сборки с отключёнными metrics нет.

## Повторная проверка TB-012

При повторном обращении к задаче продуктовая политика TB-011 подтверждена без изменений. Возвращать
fallback с отключением metrics не требуется. Статус остаётся `cancelled`, как у задачи, заменённой TB-011.

В [test_metrics_topology.py](../tests/test_metrics_topology.py) добавлены **8 regression-сценариев**
и усилены существующие assertions:

| Требование | Проверенное поведение |
| --- | --- |
| Logging, tags, service name и prefix | Единственный вызов SDK получает исходный custom `LoggingConfig` по идентичности, global tags, `attach_service_name=False` и custom prefix; второй runtime не создаётся |
| Фактический Prometheus backend | Проверяются поле bind address, явный `metrics` при bind address `None` и явный `metrics`, перекрывающий другое поле адреса |
| IPv4, hostname, IPv6 | Ошибка сохраняется исходным объектом, в диагностике остаётся весь endpoint без вторичной ошибки разбора |
| Успешный bind | Логируется фактический endpoint, включая IPv6, без ложного default/override address |
| Прочие SDK ошибки | Ошибка logging при Prometheus сохраняет исходную причину и не превращается в bind conflict; ошибки OTEL/MetricBuffer не дают сообщений о Prometheus |

Обновлены описание покрытия в `ARCHITECTURE.md` и устаревшая рекомендация выполнять fallback-fix отдельно
в `tasks/README.md`. Продуктовый код и публичный API не изменены.

## Фактическая проверка аудита

Выполнено 2026-11-08 на Python 3.13.9. Общий префикс команд:
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync`.

- `pytest tests/test_temporal_runtime.py tests/test_metrics_topology.py -q --tb=short -k 'not real'`
  — **37 passed, 5 deselected**, без bind/сетевых сервисов.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short` — **417 passed, 2 skipped**,
  покрытие **88%**, `temporal/runtime.py` **100%**. Opt-in real Temporal server tests для CRON/metrics
  пропущены; текущие изменения касаются unit-проверок. Полный набор выполнен вне sandbox для
  существующих localhost exporter/ASGI tests.
- `ruff check --no-fix temporal_boost/ tests/test_metrics_topology.py --output-format concise`
  — **passed**.
- `ruff format --check temporal_boost/ tests/test_metrics_topology.py` — **passed**, 25 файлов.
- Общие `ruff check --no-fix temporal_boost/ examples/ --output-format concise` и
  `ruff format --check temporal_boost/ examples/` сохраняют **39 существующих lint errors** и
  **4 formatting failures** в неизменённых examples.
- `mypy temporal_boost/` — **passed**, 24 файла.
- `mkdocs build --strict` — **passed**; прежние информационные сообщения о ссылках
  в `faststream_integration.md` остаются.
- `git diff --check` — **passed**.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-011](011-prometheus-multiple-runtimes.md), [TB-021](021-isolate-runtime-tests-from-network.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

