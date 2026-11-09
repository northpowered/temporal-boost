# TB-026. Устранить зависимость от приватных API SDK и Click

- **Статус:** in_progress
- **Приоритет:** P2
- **Тип:** Совместимость

## Проблема и подтверждение

[boost_app.py](../temporal_boost/boost_app.py), [temporal/worker.py](../temporal_boost/temporal/worker.py) и [workers/temporal.py](../temporal_boost/workers/temporal.py) импортируют `temporalio.worker._interceptor.Interceptor`. Windows-ветка `BoostApp.run()` вызывает `click.utils._expand_args`. Версия `temporalio` в зависимостях не ограничена; приватные символы могут меняться без публичного контракта.

Обновление SDK/CLI dependency может сломать импорт всего пакета или Windows-запуск.

## Что сделать

1. Найти и использовать поддерживаемый публичный экспорт Interceptor; сверить его с поддерживаемыми версиями SDK.
2. Передать разбор/расширение аргументов документированному API Typer/Click либо локальной совместимой реализации.
3. Проверить, что реально передаваемые Typer аргументы совпадают с нормализованными, включая программный список и Windows.
4. Зафиксировать проверяемый диапазон совместимости; не добавлять широкие верхние ограничения без основания.
5. Обновить приватные импорты в документации и примерах.

## Критерии приёмки

- [x] В runtime-коде и актуальных примерах нет прямых импортов `_interceptor` и вызова `_expand_args`.
- [x] Worker interceptors продолжают передаваться SDK без изменения смысла.
- [ ] CLI проходит проверки аргументов на поддерживаемых ОС, включая Windows.
- [x] Базовый импорт проверен на минимально заявленной и locked версии SDK, если они различаются.

## Проверка

Проверить API по Context7 при реализации. Запустить mypy, unit suite и CLI smoke tests; Windows-сценарий выполнять на Windows CI, а не только через подмену `os.name`.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-008](008-cli-exit-codes.md), [TB-020](020-meaningful-cli-unit-tests.md), [TB-022](022-enforce-ci-quality-checks.md), [TB-025](025-declare-direct-click-dependency.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).


## Результат выполнения

Во всех трёх runtime-модулях используется публичный `temporalio.worker.Interceptor`.
Guide также переведён на публичные типы и корректный subclass Interceptor, включая async inbound
methods. API сверены через Context7 (Temporal SDK Python и Click). Приватный `_expand_args` уже
удалён в TB-008: явный список передаётся буквально, args=None оставляет native argv и Windows
expansion публичному API Typer/Click; документирован windows_expand_args=False.

Минимум SDK установлен как `temporalio>=1.14.1`: это проверенная locked версия, без произвольной
верхней границы. Минимальная и locked версии совпадают; wheel smoke в чистом базовом окружении,
mypy и общая suite прошли. Проверены literal аргументы с пробелами, glob/env/home и передача
interceptor по identity. Для Windows исправлен путь console script (.exe).

**Остаётся проверка:** настоящий Windows job добавлен в `ci_prepare.yml` (Python 3.13, без extras),
он запускает test_cli.py и test_cli_arguments.py, включая native environment expansion. Здесь macOS:
этот единственный Windows-specific тест корректно skipped. Windows CI ещё не запускался; поэтому
критерий ОС оставлен открытым и карточка остаётся in_progress до результата Windows job.

Проверки выполнены после реализации всей серии 020–028 по явному указанию пользователя.
Общие команды и итоги: [результат серии](README.md#проверка-серии-tb-020tb-028).
