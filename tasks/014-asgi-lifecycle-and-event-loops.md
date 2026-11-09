# TB-014. Унифицировать lifecycle ASGI-адаптеров

- **Статус:** done
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

- [x] Каждый поддерживаемый backend проходит запуск, обработку HTTP-запроса и управляемую остановку.
- [x] После stop нет незавершённых server tasks и повторного lifespan shutdown.
- [x] Ошибка старта не маскируется ошибкой cleanup.
- [x] Неподдерживаемый backend/mode имеет явную диагностику; отсутствие extras не ломает импорт пакета.

## Проверка

Добавить unit-тесты каждого адаптера и parametrized smoke-тесты установленных backend с временным портом, ASGI lifespan counters и ограниченным ожиданием.

## Реализация и результаты проверки

Встроенные адаптеры используют внутренний `ManagedAsgiWorker`: один owning loop на run,
потокобезопасный `request_stop()`, безопасный idle/repeated shutdown, отдельные server tasks и
shield ожидания cleanup при отмене owner/waiters. Одновременный run отклоняется; последовательный
создаёт свежий server и loop. Stop до первого run не создаёт ресурсов; поздний stop не переносится
в следующий запуск. Foreign-loop shutdown и ожидание собственного shutdown из ASGI callback
отклоняются с подсказкой использовать `request_stop()`; ContextVar покрывает дочерние backend tasks.

Публичные контракты проверены через Context7 и исходники установленных версий из lockfile:

- **Uvicorn 0.35.0:** `await Server.serve()` и `should_exit`. Adapter ждёт окончания startup перед
  выставлением stop: эта версия возвращается без shutdown, если флаг установлен раньше.
  Native serve выполняет обычный cleanup; при ошибке main loop adapter вызывает shutdown только
  если тот ещё не запускался. Исходная ошибка не маскируется вторичной cleanup error; при обычной
  отмене ошибка cleanup получает приоритет. Ошибки startup/lifespan больше не становятся успехом.
- **Hypercorn 0.17.3:** `await serve(app, config, mode="asgi", shutdown_trigger=event.wait)`.
  Обычный stop завершает trigger, затем adapter join-ит native graceful shutdown; serve task
  не отменяется вместо штатного stop. kwargs валидируются как существующие поля Config.
- **Granian 2.4.2:** experimental `granian.server.embed.Server` с async `serve()` и публичным
  `stop()` в owning loop. Старый process-manager server не используется; повторный server.shutdown
  не вызывается. Observer сохраняет explicit lifespan failure messages, которые native protocol
  иначе может только записать и вернуть успешный результат. Отдельный subprocess проверяет
  фактическое распространение startup/shutdown failure.

Main-thread run устанавливает и восстанавливает SIGINT/SIGTERM handlers. Worker-thread run их
не меняет. Smoke-тест выявил зависание idle Granian при `call_soon()` из signal handler:
`call_soon_threadsafe()` будит selector, после чего stop доходит до backend. Исправление проверено
SIGINT/SIGTERM на app object и строковом пути. Fatal errors служебных tasks возвращаются owner
как результат и пробрасываются после закрытия loop, не прерывая cleanup на полпути.

Uvicorn сохраняет native импорт строки и factory. Hypercorn/Granian разрешают `module:attribute`
общим importer без eval и валидируют callable; Granian factory вызывается один раз. Hypercorn
требует уже созданный app. kwargs logging/backlog и app object/string покрыты тестами.
Все backend работают с одним server в asyncio loop: иные `workers`, reload и custom loop modes
отклоняются. Hypercorn требует `worker_class="asyncio"`, `debug=False`. Granian принимает options
своего embedded constructor; старые process-manager options несовместимы.

Миграция, ограничения и stop-контракт описаны в
[создании приложения](../docs/creating_application.md#managed-asgi-shutdown),
[руководстве запуска](../docs/running_application.md), [API](../docs/api_reference.md) и
[архитектуре](../ARCHITECTURE.md). Автоматический выбор backend не изменён (TB-027).
Защита внешнего multiprocess ASGI запуска TB-010 сохранена. Custom `BaseAsgiWorker` автоматически
не получает новый lifecycle; изменение касается трёх встроенных адаптеров.

Stop во время startup позволяет native hook завершиться, затем запускает graceful shutdown.
Зависший hook/cleanup может превысить `BoostApp.shutdown_timeout`; принудительного завершения
потока нет. Backend grace/timeout options и внешний process deadline остаются отдельными бюджетами.

Проверки выполнены 2026-11-08 на Python 3.13.9 с префиксом
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync`:

- `tests/test_asgi_workers.py`: новые **86 сценариев** прошли в составе полного
  suite. Включены doubles, optional imports, early/repeated stop, partial startup, ошибки/отмена,
  kwargs и modes. **41 subprocess smoke-сценарий** использует настоящие backend, временный порт,
  HTTP, lifespan counters/state, main/thread/coordinator, SIGINT/SIGTERM, object/string/factory,
  startup/shutdown failure и bind занятого порта. Проверены один lifespan shutdown, закрытый loop,
  отсутствие pending tasks и слушающего socket после успешной остановки.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short`: **528 passed, 2 skipped**,
  **94%** покрытия пакета. Общий ASGI lifecycle — **97%**, Uvicorn/Hypercorn — **100%**,
  Granian — **86%**. Выполнено вне sandbox: реальные HTTP/metrics tests требуют локального bind.
  Opt-in Temporal Server tests пропущены; остаётся одно upstream FastStream Redis deprecation warning.
- `ruff check --no-fix temporal_boost/ tests/test_asgi_workers.py tests/asgi_lifecycle_app.py`:
  успешно.
- `ruff format --check temporal_boost/ examples/ tests/test_asgi_workers.py tests/asgi_lifecycle_app.py`:
  четыре существующих нарушения только в неизменённых examples; остальные 39 файлов отформатированы.
- `ruff check --no-fix temporal_boost/ examples/ --output-format concise`: 39 существующих ошибок
  в неизменённых examples; package и новые тесты проходят отдельную проверку.
- `mypy temporal_boost/`: успешно, 25 файлов.
- `mkdocs build --strict`: успешно; остаются существующие INFO-диагностики ссылок FastStream guide.
- `git diff --check`: успешно.

## Зависимости и связи

Зависит от: [TB-002](002-application-graceful-shutdown.md).

Связанные задачи: [TB-005](005-temporal-worker-startup-cleanup.md), [TB-010](010-asgi-multiprocess-port-conflicts.md), [TB-013](013-faststream-managed-shutdown.md), [TB-027](027-explicit-asgi-auto-priority.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

