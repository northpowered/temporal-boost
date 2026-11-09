# TB-018. Исправить регистрацию пользовательских worker

- **Статус:** done
- **Приоритет:** P2
- **Тип:** Баг

## Проблема и подтверждение

[BoostApp.add_async_runtime()](../temporal_boost/boost_app.py) принимает по аннотации `TemporalBoostWorker`, хотя регистрирует любой объект с `run()` и `name`. Метод не присваивает `worker_name` полю `boost_worker.name`; последующая проверка дублей сравнивает имя нового alias с прежним внутренним именем. Так регистрация под alias расходится с именем в списке, потоках и проверке уникальности.

Обещанный путь расширения плохо типизирован и может допускать повторную CLI-регистрацию одного имени.

## Что сделать

1. Поддержать контракт `BaseBoostWorker` и выбрать единый источник имени регистрации.
2. Либо присваивать имя через единый путь, либо хранить отдельную запись registration и явно поддерживать alias.
3. Централизовать проверку reserved names и дублей для Temporal, ASGI, FastStream и custom worker.
4. Определить, применяются ли общие Temporal-настройки к заранее созданному Temporal worker; не менять это молча.
5. Разобраться с неиспользуемыми специализированными списками регистраций, не создавая новых конкурирующих источников истины.

## Критерии приёмки

- [x] Custom subclass `BaseBoostWorker` с `run()` и `shutdown()` принимается типизацией и запускается.
- [x] Разные внутреннее имя и alias не обходят проверку дублирования.
- [x] CLI, `get_registered_workers()` и имена потоков согласованы по выбранному контракту.
- [x] Проверяются дубли между всеми типами worker и повторная регистрация одного объекта.

## Проверка

Расширить [test_boost_app.py](../tests/test_boost_app.py), добавить mypy-проверяемый пример custom worker. Проверять фактическую CLI-команду, а не только размер списка.

## Решение и результаты

Выбран единый источник имени: регистрация присваивает `worker.name = worker_name` через общий
`_register_worker()`. CLI, `get_registered_workers()`, logs и потоки `worker-<name>` используют это имя.
Все четыре пути (Temporal, ASGI, FastStream, custom) используют `_validate_worker_registration()`:
factories отклоняют reserved names и дубли имён до создания worker, а общий путь дополнительно проверяет
identity перед присвоением имени и регистрацией callback. Один объект нельзя зарегистрировать дважды
в одном app ни под тем же, ни под другим именем. Registry остаётся один — `_registered_workers`;
неиспользуемые `_registered_cron_workers` и `_registered_asgi_workers` удалены, тесты проверяют CLI.

Аннотация `add_async_runtime(..., boost_worker: BaseBoostWorker)` уже исправлена в TB-002; теперь её
контракт проверяется прямым subclass с `run()`/async `shutdown()` и mypy-проверяемым примером.
Managed stop по-прежнему требует `request_stop()` либо базы `AsyncBoostWorker`; coordinator не вызывает
async cleanup на чужом loop. Сигнатура `run()` сохраняется для CLI; `run all` вызывает её без аргументов.

Поведение заранее созданного Temporal worker сохранено явно: app defaults не применяются, client/
runtime/debug settings и существующий `cron_workflow_id` не меняются, CRON-команда не создаётся.
Для app defaults и CRON используется `add_worker()`; для существующего объекта — явный configure до
инициализации. Миграция: alias теперь становится `worker.name`, старое внутреннее имя при необходимости
нужно хранить отдельно; повторные aliases одного объекта требуют отдельных instances. После регистрации
имя сохраняется, для регистрации в другом app создаётся отдельный экземпляр.

Добавлены **44 сценария** в [test_boost_app.py](../tests/test_boost_app.py):

- Реальный CLI `run alias --label selected` и `run all` для прямого `BaseBoostWorker`, проверка canonical
  name, registry identity, имени coordinator thread и async cleanup; старое внутреннее имя не является командой.
- Матрица всех 16 пар типов для одинакового имени, 16 reserved-name случаев и повторная регистрация
  объекта из любого factory через custom API под прежним/другим alias. Отказ сохраняет объект и CLI registry.
- Два случая заранее созданного Temporal worker (явно настроенный / ещё не настроенный) проверяют
  фактические kwargs `Client.connect()`, отсутствие Pydantic из app defaults, прежний builder и CRON ID.

До исправления новые регрессии дали **13 failed, 31 passed**. Добавлен самостоятельный
[example_custom_worker.py](../examples/example_custom_worker.py), использующий тип `BaseBoostWorker`
и lifecycle `AsyncBoostWorker`, без внешних сервисов. Smoke с заранее запрошенным stop прошёл через
настоящий `app.run(["run", "service"], standalone_mode=False)` и подтвердил завершение cleanup.
Пример указан в [README examples](../examples/README.md); прежний `TestAsyncRuntime` в `example_app.py`
остаётся отдельной задачей TB-024. [API](../docs/api_reference.md),
[guide](../docs/advanced_usage.md#custom-worker-registration) и [архитектура](../ARCHITECTURE.md) обновлены.
Семантика Typer command name/callback проверена через Context7 по официальной документации.

Проверки выполнены 2026-11-09 на Python 3.13.9 с префиксом
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync`:

- `pytest tests/test_boost_app.py tests/test_worker_coordinator.py tests/test_asgi_multiprocess.py
  -q --tb=short`: **155 passed**. Первоначальный sandbox-прогон дал 148 passed и 7 setup errors из-за
  запрещённого local TCP bind; повтор выполнен вне sandbox.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short`: **731 passed, 2 skipped**,
  пакет **94%**, `boost_app.py` **100%** с branch coverage. Полный suite выполнен вне sandbox для
  существующих ASGI/metrics checks. Два opt-in live Temporal Server tests пропущены; остаётся одно
  upstream FastStream Redis deprecation warning.
- `ruff check --no-fix temporal_boost/ examples/example_custom_worker.py`: успешно.
- `ruff format --check temporal_boost/ tests/test_boost_app.py examples/example_custom_worker.py`:
  успешно, 27 файлов.
- `mypy temporal_boost/ examples/example_custom_worker.py`: успешно, 26 файлов.
- `mkdocs build --strict`: успешно; остаются существующие INFO-диагностики ссылок FastStream guide.
- `ruff check --no-fix temporal_boost/ examples/ --output-format concise`: 39 существующих ошибок
  только в неизменённых examples. В `test_boost_app.py` те же 57 legacy findings, что и в
  `git show HEAD:tests/test_boost_app.py`; сравнение JSON diagnostics не выявило новых правил/количеств.
- `ruff format --check temporal_boost/ examples/ tests/test_boost_app.py`: четыре существующих
  нарушения в неизменённых examples, остальные 39 файлов отформатированы.
- `git diff --check`: успешно.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-002](002-application-graceful-shutdown.md), [TB-024](024-runnable-custom-worker-example.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

