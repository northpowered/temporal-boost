# TB-008. Сохранять коды завершения CLI

- **Статус:** done
- **Приоритет:** P1
- **Тип:** Баг

## Проблема и подтверждение

[BoostApp.run()](../temporal_boost/boost_app.py) перехватывает `SystemExit` от Typer и только логирует `exc.code`. Ошибка неизвестной команды или аргументов поэтому может закончиться exit code 0 пользовательского скрипта и дочернего процесса. Текущий тест `test_run_with_args` допускает прохождение без фактического исполнения выбранной команды.

Shell, CI и process manager не могут достоверно определить неуспешный запуск.

## Что сделать

1. Определить контракт `run()` для терминального и программного вызова: проброс `SystemExit` либо явный возврат кода с передачей наружу.
2. Обеспечить одинаковый результат для `python main.py ...` и entry point `temporal-boost`.
3. Сохранить код Typer для ошибок разбора и help; код фатальной ошибки worker должен быть ненулевым.
4. Проверять аргументы единым списком и реальное исполнение команды вместо подмены instance `__call__`.

## Критерии приёмки

- [x] Неизвестная команда и неверные аргументы дают стандартный ненулевой код Typer на уровне ОС.
- [x] `--help` и успешная команда завершаются с кодом 0.
- [x] Ошибка worker не преобразуется в успешное завершение.
- [x] Программный вызов со списком аргументов имеет документированный и протестированный результат.

## Проверка

Добавить проверки `CliRunner` и небольшого subprocess с приложением без внешних сервисов. Дочерние процессы должны наблюдать тот же код.

## Реализация

- `BoostApp.run(args: list[str] | None = None, **kwargs) -> Any` больше не подавляет `SystemExit`.
  По умолчанию сохраняются коды Typer: help/успех — 0, usage errors — 2, явно заданный ненулевой
  exit code — без изменения. Необработанная обычная ошибка worker даёт 1; достигший Typer
  `KeyboardInterrupt` — 130 (подтверждено установленным Typer 0.16 и subprocess).
- Аргументы передаются одним списком; `None` использует `sys.argv[1:]`, явный `[]` остаётся пустым.
  Строка вместо списка отклоняется с `TypeError`; раздельные positional arguments больше не являются API.
  Копия явного списка используется для разбора и логирования без изменения исходного списка.
  Обработку argv и расширение Windows-аргументов выполняет Typer/Click, прежний лишний private вызов удалён.
- `standalone_mode=False` возвращает значение callback и сохраняет parsing/worker exceptions;
  help возвращает 0. Это нативный контракт Typer, а не универсальный возврат exit status.
  Guides и API reference описывают терминальный/программный вызов, `--` для forwarding options
  внешним launcher и миграцию со старого подавления `SystemExit`.
- Для `run all` добавлена CLI-обёртка: фатальный worker `SystemExit(0)` / `SystemExit(None)` становится
  `RuntimeError`, чтобы coordinator failure не давал успешный OS status. Ненулевые коды сохраняются.
  Прямой `run_all_workers()` по-прежнему пробрасывает исходный объект исключения после cleanup.
- `tests/test_cli.py` содержит 51 сценарий, включая 26 subprocess-запусков реального script и
  установленной `.venv/bin/temporal-boost` entry point на приложении `tests/cli_exit_app.py` без сервисов.
  Проверены help, пустые/неверные аргументы, options, выбранный worker, failure, явный code 7,
  interrupt, программный результат и `run all` с ложным success exit. Два дублирующихся
  `test_run_with_args` заменены отдельными тестами списка аргументов и `sys.argv` с реальным dispatch.
- Обновлён `ARCHITECTURE.md`. Агрегация/cleanup нескольких процессов остаётся TB-009;
  process-selection doubles и оставшиеся вопросы CLI-тестов — TB-020.

## Фактическая проверка

Выполнено 2026-11-08 на Python 3.13.9. Общий префикс команд:
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync`.

- До реализации выбранные regression tests: **9 failed, 2 passed**.
- `pytest tests/test_cli.py tests/test_boost_app.py -q --tb=short` — **104 passed**.
- `pytest tests/test_boost_app.py --collect-only -q -k 'run_with_argument_list or run_without_arguments'`
  — собираются **2 разных теста**, без перезаписи имён.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short` — **319 passed, 1 skipped**,
  покрытие **81%**, `boost_app.py` **96%**. Opt-in real Temporal integration пропущен: изменение
  касается CLI и проверено без внешних сервисов. Полный набор выполнен вне sandbox из-за существующих
  runtime-тестов с localhost Prometheus bind.
- `ruff check --no-fix temporal_boost/ tests/test_cli.py tests/cli_exit_app.py --output-format concise`
  — **passed**.
- `ruff format --check temporal_boost/ tests/test_cli.py tests/cli_exit_app.py tests/test_boost_app.py`
  — **passed**, 26 файлов.
- Общие `ruff check --no-fix temporal_boost/ examples/ --output-format concise` и
  `ruff format --check temporal_boost/ examples/` сохраняют **39 существующих lint errors** и
  **4 formatting failures** только в неизменённых examples.
- `mypy temporal_boost/` — **passed**, 23 файла.
- `mkdocs build --strict` — **passed**; старые информационные сообщения о ссылках
  в `faststream_integration.md` остаются.
- `git diff --check` — **passed**.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-003](003-thread-worker-failure-propagation.md), [TB-009](009-multiprocess-supervision.md), [TB-020](020-meaningful-cli-unit-tests.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

