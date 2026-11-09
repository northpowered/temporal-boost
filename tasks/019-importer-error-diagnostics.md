# TB-019. Различать отсутствие приложения и ошибки его зависимостей

- **Статус:** done
- **Приоритет:** P2
- **Тип:** Баг

## Проблема и подтверждение

[import_app_object()](../temporal_boost/cli/importer.py) ловит любой `ModuleNotFoundError` от импорта приложения и пробует другие `sys.path`. Если приложение найдено, но импортирует отсутствующую зависимость, верхнеуровневое сообщение всё равно становится `Could not import module`. Причина есть в exception chain, однако классификация и fallback вводят в заблуждение. Добавленные пути остаются в глобальном `sys.path`.

Диагностика запуска указывает на приложение вместо его зависимости; повторные вызовы importer могут зависеть от накопленных изменений пути.

## Что сделать

1. Использовать имя отсутствующего модуля для различения отсутствия целевого module/package и сбоя транзитивного импорта.
2. Не повторять импорт через новые каталоги при доказанной ошибке зависимости приложения.
3. Определить контракт поиска приложения: явный app-dir или ограниченный предсказуемый fallback.
4. Сохранять исходное исключение и контекст; документировать/ограничить изменения `sys.path`.

## Критерии приёмки

- [x] Неверный import string, отсутствующий целевой модуль и отсутствующая зависимость различимы.
- [x] Для `package.module:app.nested` корректно разрешаются вложенные атрибуты.
- [x] Ошибка внутри модуля не превращается в рекомендацию искать приложение в другом каталоге.
- [x] Неудачный импорт не оставляет непредусмотренные изменения `sys.path`; успешный поиск соответствует документированному контракту.

## Проверка

Новый `tests/test_cli_importer.py` с временными Python-модулями, отсутствующей транзитивной зависимостью и проверкой состояния `sys.path` после вызова.

## Решение и результаты

Importer проверяет `ModuleNotFoundError.name`: поиск продолжается только при отсутствии целевого
module или одного из его package prefixes. Traceback дополнительно отличает ошибку, поднятую кодом
самого module/package, даже если `name` совпадает. Ошибка зависимости, bare `ModuleNotFoundError`,
`ImportError`, `SyntaxError`, `RuntimeError`, `SystemExit` и `KeyboardInterrupt` сохраняются без замены
исключения и без повторного исполнения найденного приложения через другие каталоги.

Контракт поиска ограничен normal Python import path → cwd → непосредственный parent. Имеющиеся
entries повторно не добавляются; неуспешные кандидаты удаляются перед следующей попыткой. Любой
неуспешный вызов, включая attribute lookup, восстанавливает `sys.path` на момент входа. При успешном
fallback остаётся только использованный directory для deferred imports приложения; normal-path
success не добавляет путей. `sys.modules` и побочные эффекты imports не откатываются. Importer
используется при setup до запуска worker threads; для другого layout нужно установить проект либо
задать `PYTHONPATH`, рекурсивного поиска или нового app-dir API нет.

Неверный import string, отсутствующий target и отсутствующий attribute дают разные сообщения
`ValueError`; исходный lookup exception сохраняется как cause. Части module/attribute проверяются
как dotted identifiers, выражения не выполняются. Вложенные attributes читаются один раз через
`getattr()`; прежний `hasattr()` повторно вызывал properties.

В [test_cli_importer.py](../tests/test_cli_importer.py) добавлены **52 сценария** с настоящими временными
Python modules и уникальными именами; sys.path/cwd и созданные module-cache entries изолированы:

- Malformed paths до импорта, отсутствие root/package/submodule и chained causes, namespace package
  fallback, обычный sys.path/cwd/parent, отсутствие обхода дальнейших ancestors, повторные вызовы.
- Ошибки зависимостей при каждом пути поиска, ошибки package `__init__` и зависимости внутри того же
  package, name-less и application-named `ModuleNotFoundError`, остальные startup exceptions.
  Проверяются исходные traceback/source, имя зависимости и ровно одно исполнение application code.
- Deferred imports после успешного fallback; восстановление sys.path при module/attribute failures,
  включая изменения пути самим падающим модулем; nested attributes/properties, single evaluation,
  сохранение property exception identity и реальный внешний CLI dispatch с code 1 для dependency error.

До исправления регрессии подтверждали подмену dependency failure на общий `ValueError`, повторное
исполнение модуля, утечки sys.path и двойное чтение property. Обновлены
[running guide](../docs/running_application.md#application-import-lookup), [API](../docs/api_reference.md),
[troubleshooting](../docs/troubleshooting.md#application-import-errors) и [архитектура](../ARCHITECTURE.md).
ASGI loader использует свой обычный importlib path и не получает CLI fallback — это уточнено отдельно.

Проверки выполнены 2026-11-09 на Python 3.13.9 с префиксом
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync`:

- `pytest tests/test_cli_importer.py tests/test_cli.py tests/test_process_runner.py -q --tb=short`:
  **138 passed** до добавления последних 10 importer edge cases.
- `pytest tests/test_cli_importer.py -q --tb=short`: **52 passed**, окончательная матрица.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short`: **783 passed, 2 skipped**,
  пакет **96%**, importer **100%** с branch coverage. Полный suite выполнен вне sandbox для существующих
  ASGI/metrics checks с local TCP bind. Два opt-in live Temporal Server tests пропущены; остаётся
  одно upstream FastStream Redis deprecation warning. Новые тесты не требуют внешних сервисов.
- `ruff check --no-fix temporal_boost/ tests/test_cli_importer.py`: успешно.
- `ruff format --check temporal_boost/ tests/test_cli_importer.py`: успешно, 26 файлов.
- `mypy temporal_boost/`: успешно, 25 файлов.
- `mkdocs build --strict`: успешно; остаются существующие INFO-диагностики ссылок FastStream guide.
- `ruff check --no-fix temporal_boost/ examples/ --output-format concise`: 39 существующих ошибок
  только в неизменённых examples.
- `ruff format --check temporal_boost/ examples/ tests/test_cli_importer.py`: четыре существующих
  нарушения в неизменённых examples, остальные 39 файлов отформатированы.
- `git diff --check`: успешно.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-008](008-cli-exit-codes.md), [TB-020](020-meaningful-cli-unit-tests.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

