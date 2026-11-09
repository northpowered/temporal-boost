# TB-025. Объявить используемую напрямую зависимость Click

- **Статус:** done
- **Приоритет:** P3
- **Тип:** Зависимости

## Проблема и подтверждение

[boost_app.py](../temporal_boost/boost_app.py) импортирует `click` напрямую. В [pyproject.toml](../pyproject.toml) Click не указан среди зависимостей и доступен транзитивно через Typer.

Декларация пакета не отражает реальный import-контракт; совместимость Click полностью определяется чужим dependency constraint.

## Что сделать

1. Либо объявить Click прямой зависимостью с обоснованным диапазоном, либо убрать прямое использование, если оно не нужно после TB-026.
2. Не фиксировать произвольную версию без проверки совместимости Typer и поддерживаемого Python.
3. Обновить lockfile при изменении декларации.
4. Проверить установленный wheel в чистом окружении без dev dependencies.

## Критерии приёмки

- [x] Каждый прямой сторонний runtime import обеспечен явно объявленной зависимостью или удалён.
- [x] Базовый импорт и CLI работают после установки wheel без extras.
- [x] `uv sync --locked` согласован с новым `pyproject.toml`.
- [x] Изменение не требует установки ASGI/FastStream для базового CLI.

## Проверка

`uv lock`, сборка wheel и smoke-тест импорта/`--help` в отдельном чистом окружении. Зависимости из lockfile не подменять вручную.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-026](026-remove-private-sdk-cli-apis.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).


## Результат выполнения

Выбрана разрешённая альтернатива: прямое использование Click уже удалено в TB-008; в runtime
нет import click или обращения к приватным Click helpers. Добавлять неиспользуемую прямую зависимость
не требуется. AST-аудит runtime imports показал только явно объявленные базовые/optional зависимости
(yaml, typer, temporalio, anyio, faststream, uvicorn, hypercorn, granian).

`uv lock` и `uv sync --locked --all-extras` прошли; lockfile обновлён для минимума SDK из TB-026.
`uv build --wheel --out-dir /tmp/tb-020-028-dist` собрал wheel. Базовые зависимости экспортированы
`uv export --locked --no-default-groups --no-emit-project`, установлены через uv pip sync в отдельный
чистый venv; локальный wheel установлен с `--no-deps`. Из /tmp с Python `-I` проверены реальный путь
импорта из wheel, отсутствие pytest/mypy/Ruff/MkDocs/ASGI/FastStream, programmatic CLI и `--help`;
установленный console entry point `temporal-boost --help` завершился с exit 0. Использован locked SDK 1.14.1.

Проверки выполнены после реализации всей серии 020–028 по явному указанию пользователя.
Общие команды и итоги: [результат серии](README.md#проверка-серии-tb-020tb-028).
