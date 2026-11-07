# TB-005. Сделать lifecycle Temporal worker безопасным при частичном старте

- **Статус:** backlog
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

- [ ] Ошибка client build или worker build остаётся основной наблюдаемой ошибкой.
- [ ] `shutdown()` до старта и повторный `shutdown()` безопасны.
- [ ] Остановка CRON завершает ожидающий runner; cleanup SDK worker не выполняется конфликтующими путями.
- [ ] Все созданные ресурсы имеют определённого владельца и проверяемый порядок завершения.

## Проверка

Дополнить [test_temporal_worker.py](../tests/test_temporal_worker.py) сценариями отказа на каждой стадии, повторного shutdown, остановки CRON и исключения в cleanup.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-002](002-application-graceful-shutdown.md), [TB-007](007-cron-registration-and-run-contract.md), [TB-015](015-configuration-after-initialization.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

