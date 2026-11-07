# TB-014. Унифицировать lifecycle ASGI-адаптеров

- **Статус:** backlog
- **Приоритет:** P2
- **Тип:** Доработка

## Проблема и подтверждение

[Uvicorn adapter](../temporal_boost/workers/uvicorn_worker.py) вызывает `Server.run()`, затем ещё один `asyncio.run(server.shutdown())`. [Hypercorn adapter](../temporal_boost/workers/hypercorn_worker.py) отменяет serve task и выбрасывает ошибку при shutdown до старта. [Granian adapter](../temporal_boost/workers/granian_worker.py) делегирует `shutdown()` серверу без тестов этого контракта. Штатный stop и владение loop отличаются между backend.

Общий worker API не даёт одинаковой гарантии безопасной остановки; повторный cleanup или вызов в чужом loop могут приводить к ошибкам. Конкретные backend-сбои требуют воспроизведения.

## Что сделать

1. Зафиксировать stop-контракт каждого backend на публичных API версии из lockfile.
2. Удерживать асинхронный cleanup в event loop владельца; исключить конфликтующие повторные shutdown.
3. Сделать остановку до старта и повторную остановку безопасной.
4. Проверить запуск из главного потока и из worker-потока `run all`, включая ограничения backend на signals/процессы.
5. Проверить передачу app object/string и kwargs; неподдерживаемые комбинации отклонять явно.

## Критерии приёмки

- [ ] Каждый поддерживаемый backend проходит запуск, обработку HTTP-запроса и управляемую остановку.
- [ ] После stop нет незавершённых server tasks и повторного lifespan shutdown.
- [ ] Ошибка старта не маскируется ошибкой cleanup.
- [ ] Неподдерживаемый backend/mode имеет явную диагностику; отсутствие extras не ломает импорт пакета.

## Проверка

Добавить unit-тесты каждого адаптера и parametrized smoke-тесты установленных backend с временным портом, ASGI lifespan counters и ограниченным ожиданием.

## Зависимости и связи

Зависит от: [TB-002](002-application-graceful-shutdown.md).

Связанные задачи: [TB-005](005-temporal-worker-startup-cleanup.md), [TB-010](010-asgi-multiprocess-port-conflicts.md), [TB-013](013-faststream-managed-shutdown.md), [TB-027](027-explicit-asgi-auto-priority.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

