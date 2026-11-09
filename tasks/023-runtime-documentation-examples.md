# TB-023. Исправить примеры построения и разделения runtime

- **Статус:** done
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

- [x] В примере настроенный runtime действительно передаётся в `Client.connect()`.
- [x] В документации нет утверждения о разделении runtime, которого не обеспечивает код.
- [x] Пример самодостаточен по импортам и async-контексту либо явно помечен как фрагмент.
- [x] Показанный lifecycle соответствует владению SDK-объектами.

## Проверка

Проверить пример с mocked `Client.connect()` по идентичности переданного runtime. Выполнить строгую сборку MkDocs.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-011](011-prometheus-multiple-runtimes.md), [TB-015](015-configuration-after-initialization.md), [TB-017](017-configuration-priority-documentation.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).


## Результат выполнения

В guide показан самодостаточный async lifecycle: runtime.build → client.set_runtime →
await client.build → worker.set_client/build → async context worker. Такой же исполнимый пример
добавлен в `examples/example_runtime.py`. Владение runtime и время жизни exporter описаны явно:
shared runtime не создаётся автоматически, публичного Runtime.close в поддерживаемом SDK нет.
API reference уже содержал корректный контракт после TB-011 и сверён с guide.

`test_documented_runtime_is_attached_before_connecting` исполняет именно Markdown fragment с
mocked Client.connect/Worker и проверяет runtime identity, client identity и выход из SDK worker
context при отмене. Тест прошёл в общем unit-прогоне; strict MkDocs и импорт standalone примера прошли.

Проверки выполнены после реализации всей серии 020–028 по явному указанию пользователя.
Общие команды и итоги: [результат серии](README.md#проверка-серии-tb-020tb-028).
