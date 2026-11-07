# TB-011. Обеспечить полные метрики нескольких worker и процессов

- **Статус:** backlog
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

- [ ] В поддерживаемой конфигурации видны метрики каждого из двух Temporal worker.
- [ ] Для двух процессов явно показано, как собрать полный набор метрик; каталог сам по себе не объявляется агрегатором.
- [ ] Порт занят предсказуемо, без случайного выбора единственного наблюдаемого worker.
- [ ] Документация и тесты не обещают автоматическое разделение runtime, если оно не реализовано.

## Проверка

Unit-тесты выбора/владения runtime и отдельный интеграционный тест двух worker/processes с чтением metrics. Не ограничиваться проверкой, что bind первого exporter успешен.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-009](009-multiprocess-supervision.md), [TB-012](012-telemetry-fallback-preservation.md), [TB-023](023-runtime-documentation-examples.md), [TB-028](028-prometheus-temp-directory-ownership.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

