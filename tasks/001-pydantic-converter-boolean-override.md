# TB-001. Исправить отключение Pydantic converter

- **Статус:** done
- **Приоритет:** P1
- **Тип:** Баг

## Проблема и подтверждение

В [TemporalClientBuilder](../temporal_boost/temporal/client.py) условие `use_pydantic_data_converter or config.USE_PYDANTIC_DATA_CONVERTER` не позволяет явному `False` перекрыть env `True`. В [configure_temporal_client()](../temporal_boost/workers/temporal.py) setter включения вызывается при любом значении, отличном от `None`. Поэтому даже `BoostApp(use_pydantic=False)` включает converter. Повторный `build()` также сохраняет выбранный converter в `_client_kwargs`.

Нельзя надёжно выбрать формат сериализации; изменение настроек способно неожиданно менять обработку payload.

## Что сделать

1. Ввести единый контракт: `None` наследует env, `True` включает Pydantic, `False` отключает его.
2. Поддержать переключение builder из `True` в `False` без сохранения ранее добавленного converter в kwargs.
3. Определить и документировать приоритет явно переданного `data_converter` относительно Pydantic-флага; не перезаписывать пользовательскую настройку молча.
4. Согласовать поведение constructor, worker configuration и параметра `BoostApp.use_pydantic`.

## Критерии приёмки

- [x] Матрица env `False`/`True` × аргумент `None`/`False`/`True` даёт ожидаемый converter.
- [x] `BoostApp(use_pydantic=False)` не включает Pydantic при регистрации worker.
- [x] После переключения `True → False` следующий `build()` не отправляет старый Pydantic converter.
- [x] Для пользовательского `data_converter` действует проверяемое правило приоритета.

## Проверка

Обновить [test_temporal_client.py](../tests/test_temporal_client.py), [test_temporal_worker.py](../tests/test_temporal_worker.py) и [test_boost_app.py](../tests/test_boost_app.py). Проверять kwargs `Client.connect()` через `AsyncMock`, без Temporal Server.

## Реализация и результаты проверки

`None` наследует env при создании builder; явные `True` / `False` перекрывают env во всех трёх точках
входа. При повторной настройке worker `None` оставляет предыдущий выбор без изменений, что позволяет
менять namespace и другие параметры без сброса флага. Setter
`set_pydantic_data_converter(*, enabled: bool = True)` сохраняет включение без аргументов и позволяет
отключить автоматический converter через `enabled=False`.

`build()` использует копию kwargs. Явный `data_converter`, переданный в конструктор, `set_kwargs()`
или конфигурацию worker, всегда имеет приоритет над флагом и сохраняется при его переключении.
Без явного converter отключение флага возвращает выбор по умолчанию SDK.
Контракт и миграция описаны в [configuration.md](../docs/configuration.md),
[API reference](../docs/api_reference.md) и [архитектуре](../ARCHITECTURE.md).

Добавлены 34 регрессионных сценария с `AsyncMock` для `Client.connect()`:
матрицы для constructor / worker / app, переключение после сборки и приоритет пользовательского converter.
До исправления 21 из них падал. Temporal Server не используется.

Проверки выполнены 2026-11-07 на Python 3.13.9. В командах использован префикс
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync` для существующего окружения:

- `pytest tests/test_temporal_client.py tests/test_temporal_worker.py tests/test_boost_app.py --tb=short -q`:
  115 passed, одно существующее предупреждение из `test_run_all_workers_with_workers`.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short`:
  166 passed, то же предупреждение, общее покрытие 62%. Полный набор запускался вне sandbox:
  три существующих runtime-теста поднимают Prometheus exporter на локальных портах.
- `ruff check --no-fix temporal_boost/`: успешно.
- `ruff format --check temporal_boost/ tests/test_temporal_client.py tests/test_temporal_worker.py tests/test_boost_app.py`:
  успешно, 24 файла.
- `mypy temporal_boost/`: успешно, 21 файл.
- `mkdocs build --strict`: успешно.
- `ruff check --no-fix temporal_boost/ examples/ --output-format concise`:
  42 существующие ошибки только в неизменённых examples.
- `ruff format --check temporal_boost/ examples/`:
  существующие нарушения форматирования в пяти неизменённых examples.
- `git diff --check`: успешно.

Ошибки lint/format в examples и предупреждение теста потоков находятся вне области TB-001.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-017](017-configuration-priority-documentation.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

