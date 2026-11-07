# TB-023. Исправить примеры построения и разделения runtime

- **Статус:** backlog
- **Приоритет:** P2
- **Тип:** Документация

## Проблема и подтверждение

В [advanced_usage.md](../docs/advanced_usage.md) пример строит runtime отдельно, но не вызывает `client_builder.set_runtime(runtime)` до создания client. Там же сказано, что runtime разделяется автоматически, хотя [TemporalBoostWorker](../temporal_boost/workers/temporal.py) создаёт собственный экземпляр для каждого worker.

Пользователь копирует конфигурацию, которая не применяется к client, и рассчитывает на несуществующее разделение metrics exporter.

## Что сделать

1. Исправить последовательность: build runtime → set runtime on client builder → build client → build worker.
2. Удалить обещание автоматического shared runtime; показать только поддерживаемый публичный способ управления runtime.
3. Если TB-011 добавит новый API, обновить guide под него отдельным изменением.
4. Сверить связанные statements в API reference и примерах, сохранив исторический характер release notes.

## Критерии приёмки

- [ ] В примере настроенный runtime действительно передаётся в `Client.connect()`.
- [ ] В документации нет утверждения о разделении runtime, которого не обеспечивает код.
- [ ] Пример самодостаточен по импортам и async-контексту либо явно помечен как фрагмент.
- [ ] Показанный lifecycle соответствует владению SDK-объектами.

## Проверка

Проверить пример с mocked `Client.connect()` по идентичности переданного runtime. Выполнить строгую сборку MkDocs.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-011](011-prometheus-multiple-runtimes.md), [TB-015](015-configuration-after-initialization.md), [TB-017](017-configuration-priority-documentation.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

