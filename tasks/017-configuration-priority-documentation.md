# TB-017. Согласовать документацию и тесты приоритета конфигурации

- **Статус:** done
- **Приоритет:** P2
- **Тип:** Документация

## Проблема и подтверждение

[configuration.md](../docs/configuration.md) и [creating_application.md](../docs/creating_application.md) объявляют env высшим приоритетом. [BoostApp.add_worker()](../temporal_boost/boost_app.py) и [TemporalClientBuilder](../temporal_boost/temporal/client.py) фактически дают приоритет явным endpoint/namespace и последующей настройке worker. [api_reference.md](../docs/api_reference.md) уже описывает параметры как override, поэтому guides противоречат друг другу.

Одинаковая конфигурация интерпретируется пользователем по-разному в зависимости от прочитанного руководства.

## Что сделать

1. Зафиксировать текущий приоритет endpoint/namespace: явная настройка worker → BoostApp → env → встроенный default.
2. Исправить пример, в котором env якобы перекрывает явный `temporal_endpoint`.
3. Документировать import-time чтение env, отсутствие автоматической загрузки `.env` и defaults runtime-аргументов, зафиксированные при импорте.
4. Отдельно описывать особенности bool/числовых параметров после соответствующих исправлений; не обещать одинаковую семантику для всех полей без тестов.

## Критерии приёмки

- [x] Все guides и API reference описывают единый приоритет endpoint/namespace.
- [x] Регрессионный тест проверяет конфликт env, app и worker настройки.
- [x] Пример с `.env` загружает его до импорта пакета или объясняет требуемый порядок.
- [x] Изменение окружения после импорта не объявляется поддерживаемой динамической перенастройкой.

## Проверка

Обновить документы и соответствующие тесты client/app. Выполнить `uv run mkdocs build --strict`; env-сценарии изолировать от остальных тестов.

## Решение и результаты

Guides, API reference и README теперь описывают один приоритет endpoint/namespace:
последняя явная настройка worker → параметры app → значения env при импорте → встроенный default.
Приоритет действует независимо для каждого поля. Пример с конфликтом адресов показывает победу
`temporal_endpoint`; повторный `configure_temporal_client(...=None)` сохраняет прежний выбор.
Отдельно описаны constructor fallback для пустых строк, setters, TLS/Pydantic bool, числовые
настройки TB-016 и runtime defaults, захваченные при определении функций. Runtime configure заменяет
настройки целиком; явный bind `None` отключает неявный exporter, а flags `None` дают `False`.

Примеры `.env` теперь явно вызывают loader до первого импорта пакета; `python-dotenv` устанавливается
отдельно. Поведение `load_dotenv()` с сохранением существующих env проверено через Context7 по
[документации python-dotenv](https://github.com/theskumar/python-dotenv#readme). Для установленного CLI
окружение готовится до запуска процесса, поскольку entry point импортирует пакет раньше app module.
Пример «Dynamic Configuration» заменён startup bootstrap и явной настройкой будущих объектов.
Изменение `os.environ` после импорта не представлено как динамическая перенастройка.

Обновлены [configuration](../docs/configuration.md), [creating application](../docs/creating_application.md),
[API](../docs/api_reference.md), [running application](../docs/running_application.md),
[troubleshooting](../docs/troubleshooting.md), [README](../README.md) и [архитектура](../ARCHITECTURE.md).
Поведение package не менялось; изменения исправляют документацию и фиксируют текущий контракт тестами.

В [test_configuration_priority.py](../tests/test_configuration_priority.py) добавлены **37 сценариев**:

- Конфликт env/app/worker, builtin defaults при отсутствии env, независимый выбор endpoint/namespace,
  повторные вызовы с None и явными значениями, app/worker empty strings. Проверяются фактические
  kwargs `Client.connect()` через app и SDK worker initialization.
- Standalone client constructor с None/empty/explicit и TLS False при config True; worker TLS None
  сохраняет явный False. Env читается в изолированный module object с восстановлением monkeypatch,
  общие модули не reload-ятся. Матрицы Pydantic и numeric options остаются в тестах TB-001/TB-016.
- Три subprocess tests: `.env` не загружается автоматически; новые builders после изменения env
  используют прежние constants; runtime defaults сохраняются даже после изменения config-констант,
  а явные None/False применяются. Subprocess запускаются из временного каталога с очищенными
  `TEMPORAL_*`; client/worker/runtime заменены doubles, внешний Temporal и bind порта не нужны.

Первый полный прогон выполнил все **687 tests**, но aggregation coverage упал из-за потери branch
settings при auto-detection pytest-cov 5 из временного cwd. Helper subprocess tests теперь передаёт
путь к project `pyproject.toml`, если plugin оставил auto-detection; coverage не отключается.
После исправления focused coverage прогон изолированных тестов прошёл успешно.

Проверки выполнены 2026-11-09 на Python 3.13.9 с префиксом
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync`:

- `pytest tests/test_configuration_priority.py tests/test_temporal_client.py tests/test_boost_app.py
  tests/test_config.py -q --tb=short`: **141 passed**.
- `pytest tests/test_configuration_priority.py --cov=temporal_boost --cov-report=term --tb=short`:
  **37 passed**, coverage subprocess data успешно объединены.
- Повторный `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short`: **687 passed, 2 skipped**,
  пакет **94%** с branch coverage; aggregation coverage успешен. Полный suite выполнен вне sandbox для
  существующих ASGI/metrics checks с локальным TCP bind. Два opt-in live Temporal Server tests
  пропущены; остаётся одно upstream FastStream Redis deprecation warning.
- `ruff check --no-fix temporal_boost/ tests/test_configuration_priority.py`: успешно.
- `ruff format --check temporal_boost/ tests/test_configuration_priority.py`: успешно, 26 файлов.
- `mypy temporal_boost/`: успешно, 25 файлов.
- `mkdocs build --strict`: успешно; остаются существующие INFO-диагностики ссылок FastStream guide.
- `ruff check --no-fix temporal_boost/ examples/ --output-format concise`: 39 существующих ошибок
  только в неизменённых examples.
- `ruff format --check temporal_boost/ examples/`: четыре существующих нарушения в неизменённых
  examples, остальные 37 файлов отформатированы.
- `git diff --check`: успешно.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-001](001-pydantic-converter-boolean-override.md), [TB-015](015-configuration-after-initialization.md), [TB-016](016-numeric-options-zero-fallback.md), [TB-023](023-runtime-documentation-examples.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

