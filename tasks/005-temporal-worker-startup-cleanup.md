# TB-005. Сделать lifecycle Temporal worker безопасным при частичном старте

- **Статус:** done
- **Приоритет:** P2
- **Тип:** Баг

## Проблема и подтверждение

В [TemporalBoostWorker._run_worker()](../temporal_boost/workers/temporal.py) `_build_worker()` вызывается до `try/finally`. Ошибка после создания части SDK-объектов не проходит через cleanup. Публичный `shutdown()` обращается к обязательному свойству `temporal_worker` и выбрасывает `RuntimeError`, если worker ещё не построен. В CRON-пути shutdown не завершает ожидающий `_cron_future`.

Координатор не может единообразно остановить неуспешно запущенный worker; cleanup способен скрыть первоначальную ошибку или оставить ожидающий CRON runner.

## Что сделать

1. Описать состояния created/building/running/stopping/stopped и правила повторного запуска.
2. Охватить сборку и выполнение единым обработчиком ошибок и cleanup.
3. Сделать stop/shutdown безопасным до старта, после частичной сборки и при повторном вызове.
4. Завершать ожидание CRON runner при остановке и учитывать cleanup контекстного менеджера SDK.
5. Освобождать только принадлежащие адаптеру ресурсы через поддерживаемый SDK API; не предполагать наличие `close()` у каждого объекта.

## Критерии приёмки

- [x] Ошибка client build или worker build остаётся основной наблюдаемой ошибкой.
- [x] `shutdown()` до старта и повторный `shutdown()` безопасны.
- [x] Остановка CRON завершает ожидающий runner; cleanup SDK worker не выполняется конфликтующими путями.
- [x] Все созданные ресурсы имеют определённого владельца и проверяемый порядок завершения.

## Проверка

Дополнить [test_temporal_worker.py](../tests/test_temporal_worker.py) сценариями отказа на каждой стадии, повторного shutdown, остановки CRON и исключения в cleanup.

## Реализация и результаты проверки

Обычный и CRON-запуск используют общий lifecycle, охватывающий сборку, исполнение и cleanup.
Read-only `state` сообщает `created` → `building` → `running` → `stopping` → `stopped`;
ранний stop/ошибка может пропустить `running`. Одновременные запуски одного adapter отклоняются;
после завершения/ошибки допустим новый запуск со свежими loop/client/runtime/SDK worker.

`TemporalBoostWorker.request_stop()` подключает adapter к coordinator TB-002: неблокирующий
потокобезопасный запрос доставляется в owning loop через `call_soon_threadsafe()`.
Запрос до первого запуска предотвращает создание ресурсов; после остановки не переносится в следующий запуск.
`shutdown()` до/после запуска — no-op; на active owning loop запрашивает stop и ждёт lifecycle task
через `shield()`. Повторы разделяют cleanup. Отмена одного ожидающего не отменяет lifecycle;
повторная отмена owner task также не бросает cleanup. Foreign-loop shutdown отклоняется с указанием
использовать `request_stop()`; этот же неблокирующий метод нужен внутри worker callbacks.

При stop сначала завершается локальный CRON future, отменяются и дожидаются pending build/registration
tasks, затем останавливается и дожидается принадлежащая adapter SDK run task. SDK shutdown выполняется
не более одного раза при активном run; результат завершившегося run получается без повторного shutdown.
CRON больше не входит в SDK async context manager: явные публичные `run()` / `shutdown()` дают один
путь cleanup вместо конфликта с `__aexit__()`.

SDK 1.14.1 может выбросить ошибку валидации из `run()` до выставления SDK shutdown-complete event.
Adapter наблюдает SDK run и shutdown tasks одновременно: ошибка run отменяет лишнее ожидание shutdown,
поэтому первоначальная ошибка не превращается в зависание. При отказе shutdown принадлежащая adapter
SDK task отменяется и дожидается. Исходные ошибки runtime/client/worker build, CRON registration и
исполнения сохраняют объект/traceback; вторичные ошибки cleanup логируются. Неожиданная отмена больше
не подавляется. Если на фоне отмены cleanup падает, его ошибка пробрасывается и не маскируется штатной
отменой coordinator.

После cleanup снимаются ссылки adapter на SDK worker/client/runtime и ссылки builders на client/runtime.
Для этого `TemporalWorkerBuilder.set_client()` и `TemporalClientBuilder.set_runtime()` допускают `None`.
Контракт SDK сверен через Context7 и исходники установленного SDK: у `Client` / `Runtime` нет публичных
`close()` / `shutdown()`. Такие методы не придумывались; SDK управляет native handles, внешние ссылки
могут продлить их жизнь. Переданные пользователем executors не закрываются adapter. Loop закрывается
его `asyncio.run()` после завершения lifecycle.

CRON по-прежнему создаёт workflow с UUID только при явном `cron()`; `run all` обслуживает очередь без
регистрации расписания. Локальный stop не удаляет/не отменяет server-side workflow. Идемпотентность ID
и проверка пары CRON-параметров остаются в TB-006/TB-007; поведение поздней конфигурации — в TB-015.
Жёсткий предел ожидания coordinator задаёт `BoostApp.shutdown_timeout`; SDK activity grace period
не гарантирует завершения activities, игнорирующих отмену.

Контракт, миграция к thread-safe stop, состояния и границы владения описаны в
[API reference](../docs/api_reference.md), [руководстве запуска](../docs/running_application.md),
[configuration.md](../docs/configuration.md) и [архитектуре](../ARCHITECTURE.md).
После cleanup свойства client/SDK worker больше не возвращают объекты завершённого запуска;
следующий запуск собирает их заново. Старый unit-тест, вручную присваивавший не запущенный SDK worker
и вызывавший shutdown, заменён проверкой безопасного повторного idle shutdown: настоящее SDK shutdown
не запущенного worker само по себе может ждать его будущего run бесконечно.

Добавлены 23 сценария в `tests/test_temporal_lifecycle.py` с SDK doubles: отказы всех стадий сборки,
исходная ошибка при отказе cleanup, normal/CRON repeated stop, ожидающая и завершённая CRON registration,
startup cancellation, состояния, отмена shutdown waiter, unexpected cancellation, early stop,
concurrent run rejection, fresh resources при restart, foreign-loop rejection, validation/shutdown race
с зависшим либо падающим shutdown. Настоящий coordinator проверен с Temporal adapter в отдельном потоке;
SDK cleanup выполняется на том же loop, и loop закрыт после join. Temporal Server не требуется.

Проверки выполнены 2026-11-07 на Python 3.13.9. Использован префикс
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync` для существующего окружения:

- До реализации шесть выбранных lifecycle regression scenarios падали.
- `pytest tests/test_temporal_lifecycle.py tests/test_temporal_worker.py tests/test_worker_coordinator.py
  --tb=short -q -W error::pytest.PytestUnhandledThreadExceptionWarning`: 105 passed, без предупреждений.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short`: 238 passed, покрытие 76%,
  без предупреждений. Выполнено вне sandbox с ранее разрешённой командой, поскольку существующие
  runtime-тесты открывают локальные Prometheus-порты.
- `ruff check --no-fix temporal_boost/ tests/test_temporal_lifecycle.py --output-format concise`: успешно.
- `ruff format --check temporal_boost/ tests/test_temporal_lifecycle.py tests/test_temporal_worker.py`:
  успешно, 25 файлов.
- `mypy temporal_boost/`: успешно, 23 файла.
- `mkdocs build --strict`: успешно.
- `ruff check --no-fix temporal_boost/ examples/ --output-format concise`: 42 существующие ошибки
  только в неизменённых examples.
- `ruff format --check temporal_boost/ examples/ tests/test_temporal_lifecycle.py tests/test_temporal_worker.py`:
  пять существующих нарушений в неизменённых examples; остальные 35 файлов отформатированы.
- `git diff --check`: успешно.

Интеграция с живым Temporal Server и фактическая длительность завершения activities здесь не проверялись;
проверены ownership и lifecycle adapter на SDK doubles. Existing lint/format failures examples вне TB-005.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-002](002-application-graceful-shutdown.md), [TB-007](007-cron-registration-and-run-contract.md), [TB-015](015-configuration-after-initialization.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

