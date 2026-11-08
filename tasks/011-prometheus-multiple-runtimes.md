# TB-011. Обеспечить полные метрики нескольких worker и процессов

- **Статус:** done
- **Приоритет:** P1
- **Тип:** Доработка

## Проблема и подтверждение

Каждый [TemporalBoostWorker](../temporal_boost/workers/temporal.py) создаёт собственный runtime. При одном `TEMPORAL_PROMETHEUS_BIND_ADDRESS` несколько runtimes претендуют на одинаковый порт, а [runtime builder](../temporal_boost/temporal/runtime.py) отключает telemetry при конфликте. [Подготовка PROMETHEUS_MULTIPROC_DIR](../temporal_boost/cli/prometheus.py) не подключает объединение SDK-метрик.

Endpoint может работать, но показывать только часть worker, создавая ложное представление о состоянии сервиса.

## Что сделать

1. Описать топологию metrics для нескольких потоков внутри процесса и для нескольких процессов.
2. Выбрать поддерживаемую реализацию: совместно используемый runtime внутри процесса, отдельные endpoints с service discovery или поддерживаемый telemetry collector.
3. Сделать владение runtime и metrics-портом явным; при несовместимой конфигурации давать проверяемую ошибку или явное предупреждение о неполных данных.
4. Документировать различие SDK exporter и Python Prometheus multiprocess directory.
5. Если появляется общий runtime API, определить его lifecycle и не переносить готовый SDK runtime между процессами.

## Критерии приёмки

- [x] В поддерживаемой конфигурации видны метрики каждого из двух Temporal worker.
- [x] Для двух процессов явно показано, как собрать полный набор метрик; каталог сам по себе не объявляется агрегатором.
- [x] Порт занят предсказуемо, без случайного выбора единственного наблюдаемого worker.
- [x] Документация и тесты не обещают автоматическое разделение runtime, если оно не реализовано.

## Проверка

Unit-тесты выбора/владения runtime и отдельный интеграционный тест двух worker/processes с чтением metrics. Не ограничиваться проверкой, что bind первого exporter успешен.

## Реализация

- Выбрана топология отдельных endpoints: каждый `TemporalBoostWorker` по-прежнему лениво создаёт
  свой SDK runtime и передаёт его своему client. Каждый concurrent Prometheus runtime владеет отдельным
  endpoint. В одном процессе два worker требуют два endpoints; два таких процесса на одном host — четыре.
  В разных network namespaces допускаются одинаковые порты, но scrape нужны все endpoints каждой replica.
  Автоматическое разделение runtime/socket и назначение портов внешним `--workers N` не вводятся.
- `TemporalRuntimeBuilder.build()` больше не создаёт runtime с пустой telemetry после конфликта порта.
  Исходный SDK `ValueError` пробрасывается без замены и без второго вызова конструктора. Startup failure
  достигает coordinator/supervisor и останавливает peers вместо продолжения с неполными метриками.
  Это намеренное изменение поведения; migration guide требует отдельных endpoints либо внешнего collector.
- Диагностика использует фактический `metrics` backend: явный `metrics=PrometheusConfig(...)` приоритетен
  над полем адреса, и логируется именно его endpoint. Нет разбора `host:port` или классификации ошибки
  по подстроке SDK message; IPv4, hostname и IPv6 не создают вторичную ошибку. Для OTEL/MetricBuffer/None
  не выводится ложный success log Prometheus bind. Telemetry config не меняется при отказе.
- Добавлены **16 сценариев**, включая unit-проверки runtime/client identity, cache и независимого cleanup;
  **5 интеграционных сценариев** читают настоящие SDK metrics через HTTP. Два worker runtimes работают
  на разных Python threads в каждом процессе; для одного/двух процессов проверены оба/все четыре endpoints,
  значения counters, process metadata и суммы. Дубликаты адреса внутри процесса и между процессами
  фатальны; существующие exporters продолжают работать.
- Opt-in интеграция запускает ephemeral Temporal dev server и два дочерних процесса с двумя настоящими
  SDK workers в каждом. Выполнены workflows/activities для четырёх разных очередей; с каждого endpoint
  прочитаны activity counter и native `temporal_activity_execution_latency_count`, проверены task queues
  и process metadata. Готовые SDK runtimes между процессами не передаются.
- Старые runtime builder unit-тесты теперь подменяют SDK Runtime вместо bind фиксированных 9090/9091;
  сетевое поведение проверяется явно на временных портах. Обновлены annotations и формат этого модуля.
- `examples/example_metrics.py` показывает два отдельных процесса с разными `METRICS_BASE_PORT`
  (переменная самого примера), по два exporter в каждом. Guide содержит все четыре static scrape targets,
  рекомендации service discovery, различие SDK exporter и Python `PROMETHEUS_MULTIPROC_DIR`, владение
  native handles, запрет переноса runtime через fork и отсутствие shared-runtime API.
  В locked SDK `global_tags` наблюдаются в resource `target_info`, а не в каждом counter; это проверено
  scrape и описано отдельно. Исправлена ложная формулировка об автоматическом sharing в advanced guide,
  standalone builder fragment передаёт runtime client builder до `build()`.
- Обновлены configuration/API/examples/`ARCHITECTURE.md`. TB-012 отменена со ссылкой на эту задачу:
  fallback удалён выбранной политикой, сохранять его настройки больше не требуется. Legacy directory
  setup/cleanup остаётся TB-028; новый runtime sharing API не добавлен.

## Фактическая проверка

Выполнено 2026-11-08 на Python 3.13.9 и locked Temporal Python SDK 1.14.1.
Общий префикс команд: `UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync`.

- До реализации regression в `tests/test_temporal_runtime.py` — **1 failed, 17 passed**:
  старый builder повторно создаёт runtime после ошибки bind.
- `TEMPORAL_BOOST_INTEGRATION=1 ... pytest tests/test_temporal_runtime.py tests/test_metrics_topology.py -q --tb=short`
  — **34 passed**, включая настоящий Temporal server. `TEMPORAL_CLI_PATH` указывал на ранее закешированный
  SDK CLI executable: Temporal CLI **1.10.0**, Server **1.32.2**; сервер ephemeral/in-memory,
  внешние namespace и production services не использовались. Новых загрузок не потребовалось.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short` — **409 passed, 2 skipped**,
  покрытие **88%**, `temporal/runtime.py` **100%**. В стандартном наборе пропущены opt-in Temporal
  integrations для CRON и metrics; metrics integration отдельно выполнена выше. Проверки с реальными
  exporters/dev server и полный набор выполнены вне sandbox для localhost bind/scrape.
- `ruff check --no-fix temporal_boost/ tests/test_metrics_topology.py tests/metrics_exporter_app.py tests/test_temporal_runtime.py examples/example_metrics.py --output-format concise`
  — **passed**.
- `ruff format --check temporal_boost/ tests/test_metrics_topology.py tests/metrics_exporter_app.py tests/test_temporal_runtime.py examples/example_metrics.py`
  — **passed**, 28 файлов.
- Общие `ruff check --no-fix temporal_boost/ examples/ --output-format concise` и
  `ruff format --check temporal_boost/ examples/` сохраняют **39 существующих lint errors** и
  **4 formatting failures** в прежних examples; новый metrics example проходит обе проверки.
- `mypy temporal_boost/` — **passed**, 24 файла.
- `mkdocs build --strict` — **passed**; прежние информационные сообщения о ссылках
  в `faststream_integration.md` остаются.
- `git diff --check` — **passed**.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-009](009-multiprocess-supervision.md), [TB-012](012-telemetry-fallback-preservation.md), [TB-023](023-runtime-documentation-examples.md), [TB-028](028-prometheus-temp-directory-ownership.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

