# TB-004. Подключить TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT к SDK worker

- **Статус:** backlog
- **Приоритет:** P1
- **Тип:** Баг

## Проблема и подтверждение

[config.py](../temporal_boost/temporal/config.py) читает `TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT` в `timedelta`, но [TemporalWorkerBuilder.build()](../temporal_boost/temporal/worker.py) эту константу не использует. [Руководство запуска](../docs/running_application.md) обещает ожидание activities до настроенного timeout.

Пользовательская настройка завершения не влияет на SDK worker; фактическое поведение расходится с настройками deployment.

## Что сделать

1. Добавить явный параметр `graceful_shutdown_timeout` в worker builder и передавать его в SDK `Worker`.
2. Использовать env-константу только при отсутствии явного значения; сохранить возможность настройки через `add_worker()`.
3. Проверять допустимость отрицательных значений и корректно обрабатывать явный нулевой `timedelta`.
4. Разграничить SDK grace period и общий timeout остановки приложения/процессов.

## Критерии приёмки

- [ ] Default и значение из env доходят до конструктора SDK `Worker`.
- [ ] Явный `timedelta` перекрывает env; передача через `worker_kwargs` не создаёт дублирующий аргумент.
- [ ] Нулевое значение не заменяется default, отрицательное отклоняется понятной ошибкой.
- [ ] Документация описывает фактический SDK timeout и его связь с общим shutdown budget.

## Проверка

Расширить [test_temporal_worker.py](../tests/test_temporal_worker.py), подменяя SDK `Worker`. Чтение env проверять в изолированном импорте или subprocess.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-002](002-application-graceful-shutdown.md), [TB-009](009-multiprocess-supervision.md), [TB-016](016-numeric-options-zero-fallback.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

