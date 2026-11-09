# TB-016. Различать None и ноль в настройках SDK worker

- **Статус:** done
- **Приоритет:** P2
- **Тип:** Баг

## Проблема и подтверждение

В [TemporalWorkerBuilder.__init__()](../temporal_boost/temporal/worker.py) все числовые параметры выбираются через `value or config.VALUE`. Явный `nonsticky_to_sticky_poll_ratio=0.0` превращается в default `0.2`; нулевые concurrency/poll values также подменяются, вместо передачи или ошибки валидации.

Заданные пользователем параметры не доходят до SDK и не дают ожидаемой ошибки при недопустимом значении.

## Что сделать

1. Выбирать env/default только при `value is None`.
2. Проверить допустимые диапазоны по контракту SDK отдельно для ratio, concurrency и polls.
3. Сохранять допустимый ноль, а недопустимый отклонять понятной ошибкой вместо подмены.
4. Проверять отрицательные и нечисловые значения на согласованном уровне; не расширять диапазоны произвольно.

## Критерии приёмки

- [x] `nonsticky_to_sticky_poll_ratio=0.0` доходит до SDK без замены.
- [x] `None` продолжает использовать env/default.
- [x] Для каждого параметра поведение нуля явно определено и протестировано.
- [x] Некорректная настройка не исправляется молча в другое значение.

## Проверка

Параметризованные тесты [test_temporal_worker.py](../tests/test_temporal_worker.py) с `None`, нулём, положительным и отрицательным значениями; SDK Worker можно подменить для проверки аргументов.

## Решение и результаты

Все шесть опций выбирают config только при `None`. В конструкторе builder проверяется выбранное
значение, включая config/default: concurrency и poll counts требуют положительный `int`, ratio —
конечный неотрицательный `int`/`float`. Для неверного типа выбрасывается `TypeError`, для диапазона —
`ValueError`, сообщение содержит имя опции. Bool и numeric strings отклоняются; целочисленные counts
не принимают float даже `1.0`. Допустимые значения передаются SDK без подмены. Явный корректный
override перекрывает некорректный config; `add_worker()` отклоняет неверную опцию до регистрации.

Контракт проверен через Context7 и исходники установленного Python SDK 1.14.1:

- [Worker и poller behavior](https://github.com/temporalio/sdk-python/blob/1.14.1/temporalio/worker/_worker.py)
  и [SDK Core validation](https://github.com/temporalio/sdk-core/blob/24a3c23a6dc8842fddb5be3a52a534b863a01a7c/core-api/src/worker.rs):
  counts положительны, workflow concurrency/polls требуют минимум два с включённым cache.
  Эти дополнительные контекстные ограничения остаются проверкой SDK при `build()`; без cache допустим один.
- [SDK Core ratio calculation](https://github.com/temporalio/sdk-core/blob/24a3c23a6dc8842fddb5be3a52a534b863a01a7c/core/src/worker/mod.rs):
  у ratio нет проверки диапазона или лимита `1.0`, ноль допустим. Проверка конечного неотрицательного
  ratio добавлена на уровне framework; произвольный верхний лимит не вводится. Минимум pollers остаётся
  равным одному: передача ratio `0.0` не отключает non-sticky polling.

Миграция: вместо нулевых counts для выбора default передать `None` либо опустить опцию; теперь ноль
даёт ошибку. Import-time env parsing и его существующий fallback для нечислового текста не менялись.
Обновлены [configuration guide](../docs/configuration.md), [API](../docs/api_reference.md) и
[архитектура](../ARCHITECTURE.md).

Добавлены 115 параметризованных сценариев: None/default, целый и дробный ноль, положительные и
отрицательные значения, ratio выше единицы, строки, bool, list, NaN/±inf, config overrides,
передача zero ratio через app и отказ до регистрации. До исправления первый набор регрессий дал
**77 failed, 14 passed** (до расширения матрицы типов); проверяется вызов SDK Worker на double.

Проверки выполнены 2026-11-09 на Python 3.13.9 с префиксом
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync`:

- `pytest tests/test_temporal_worker.py -q --tb=short`: **182 passed**.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short`: **650 passed, 2 skipped**,
  пакет **94%**, `temporal/worker.py` **100%** с branch coverage. Полный suite выполнен вне sandbox
  для существующих локальных TCP/ASGI/metrics checks. Два opt-in live Temporal Server tests пропущены;
  одно существующее FastStream Redis deprecation warning. Новые тесты не требуют сервера Temporal.
- `ruff check --no-fix temporal_boost/`: успешно.
- `ruff format --check temporal_boost/temporal/worker.py tests/test_temporal_worker.py`: успешно.
- `mypy temporal_boost/`: успешно, 25 файлов.
- `mkdocs build --strict`: успешно; остаются существующие INFO-диагностики ссылок FastStream guide.
- `ruff check --no-fix temporal_boost/ examples/ --output-format concise`: 39 существующих ошибок
  в неизменённых examples. В `test_temporal_worker.py` сохраняются 60 legacy findings; сравнение
  JSON diagnostics с `git show HEAD:tests/test_temporal_worker.py` даёт те же количества по каждому
  правилу, без новых findings от этого изменения.
- `ruff format --check temporal_boost/ examples/ tests/test_temporal_worker.py`: четыре существующих
  нарушения в неизменённых examples; остальные 38 файлов отформатированы.
- `git diff --check`: успешно.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-004](004-wire-graceful-shutdown-timeout.md), [TB-017](017-configuration-priority-documentation.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

