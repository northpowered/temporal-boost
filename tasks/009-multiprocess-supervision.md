# TB-009. Контролировать отказ и завершение дочерних процессов

- **Статус:** done
- **Приоритет:** P1
- **Тип:** Баг

## Проблема и подтверждение

[run_multiprocess()](../temporal_boost/cli/process_runner.py) делает `join()` по порядку создания. Если первый процесс работает бесконечно, падение следующего не замечается. Ненулевой exit code только логируется. Цикл `process.start()` расположен до `try`, поэтому ошибка запуска очередного процесса оставляет ранее запущенные без управляемого cleanup. SIGTERM родителя отдельно не обрабатывается.

Deployment может оставаться частично работающим, возвращать успешный статус или оставлять дочерние процессы после сбоя родителя.

## Что сделать

1. Наблюдать за всеми процессами независимо от порядка их создания.
2. Определить политику первой фатальной ошибки: остановить остальные процессы и завершить родителя с ненулевым кодом.
3. Охватить запуск и ожидание общим cleanup, включая отказ `Process.start()`.
4. Сначала запрашивать штатную остановку, затем применять ограниченные timeout и принудительное завершение.
5. Гарантировать `join()` завершённых детей и очистку ресурсов процесса; не добавлять автоматический restart без отдельного требования.

## Критерии приёмки

- [x] Падение второго процесса обнаруживается, даже когда первый ещё работает.
- [x] Родитель возвращает ненулевой статус при фатальной ошибке любого ребёнка.
- [x] Отказ на втором `start()` не оставляет первый процесс работающим.
- [x] SIGINT/SIGTERM завершают всё дерево; принудительная остановка применяется только после grace period.

## Проверка

Новый `tests/test_process_runner.py`: unit-тесты отказов через управляемые process doubles и subprocess-тесты короткоживущих worker с ограниченными ожиданиями.

## Реализация

- `_ProcessSupervisor` наблюдает всех детей раз в 50 мс, делает неблокирующий `join(0)` завершённых
  процессов и закрывает process handles. Успешный finite child не останавливает peers; после успешного
  завершения всех родитель возвращается нормально. Перезапуска нет.
- Первый замеченный отказ инициирует cleanup и определяет результат: положительный child exit code
  сохраняется, signal exit `-N` превращается в `128 + N`. Ошибка start/monitoring/cleanup пробрасывается,
  последующие ошибки логируются без замены первичной. Фатальный `SystemExit(0/None)` supervisor
  нормализуется в `RuntimeError`.
- Создание и запуск входят в общий cleanup; process object отслеживается до `start()`, включая
  неудачный запуск до/после присвоения PID. Ошибка join, stop или close одного ребёнка не пропускает остальных.
- Для cooperative stop каждому ребёнку отправляется одно сообщение через выделенный однонаправленный
  `multiprocessing.Pipe`. Нет общего IPC lock, который мог бы остаться захваченным после kill.
  Child watcher вызывает `app.stop()` с повторением во время startup либо `request_stop()` выбранного
  `run`/`cron` worker. Ранний stop до dispatch пропускает выполнение; концы каналов закрываются.
- `--shutdown-timeout` внешнего CLI и одноимённый keyword `run_multiprocess()` задают общий grace period:
  default 30 секунд, допустим 0, отрицательные/бесконечные/NaN значения отклоняются. Затем идут terminate
  с общим deadline 5 секунд и kill с ещё одним общим deadline 5 секунд. Бюджет независим от coordinator/SDK.
- Main-thread SIGINT/SIGTERM handlers только записывают первый сигнал, восстанавливаются после cleanup;
  повторы не меняют deadlines. Если ошибкой не определён другой результат, родитель возвращает 130/143.
  Child игнорирует унаследованный SIGINT и сбрасывает SIGTERM перед импортом; coordinator может установить
  собственные handlers. `run_single_process()` сохраняет обработку interrupt внешним Typer.
- Добавлены 45 сценариев, включая 11 настоящих subprocess-тестов без внешних сервисов. Проверены поздний
  отказ, частичный start, общие deadlines, ошибки cleanup/каналов, сигналы и их повторы для `run all` и
  выбранного worker, kill stubborn workers после grace, OS exit codes установленной entry point,
  отсутствие оставшихся детей и восстановление handlers. Фикстура владеет отдельной POSIX session
  и очищает её при неудаче теста.
- Обновлены running guide, configuration, API reference и `ARCHITECTURE.md`, включая миграцию и бюджеты.
  Собственные потомки пользовательского приложения остаются ответственностью его cleanup; managed stop
  FastStream/ASGI, socket sharing и ownership каталога Prometheus остаются отдельными задачами.

## Фактическая проверка

Выполнено 2026-11-08 на Python 3.13.9. Общий префикс команд:
`UV_CACHE_DIR=/tmp/temporal-boost-uv-cache uv run --offline --no-sync`.

- До реализации исходные regression tests — **14 failed**.
- `pytest tests/test_process_runner.py tests/test_cli.py -q --tb=short` — **96 passed**.
- `pytest tests/ --cov=temporal_boost --cov-report=term --tb=short` — **364 passed, 1 skipped**,
  покрытие **86%**, `cli/process_runner.py` **95%**. Opt-in real Temporal integration пропущен;
  process supervision проверена настоящими процессами без Temporal server. POSIX integration выполнена
  на текущей платформе; на non-POSIX эти сценарии пропускаются. Полный набор выполнен вне sandbox из-за
  существующих runtime-тестов с localhost Prometheus bind.
- `ruff check --no-fix temporal_boost/ tests/test_process_runner.py tests/process_supervision_app.py --output-format concise`
  — **passed**.
- `ruff format --check temporal_boost/ tests/test_process_runner.py tests/process_supervision_app.py`
  — **passed**, 25 файлов.
- Общие `ruff check --no-fix temporal_boost/ examples/ --output-format concise` и
  `ruff format --check temporal_boost/ examples/` сохраняют **39 существующих lint errors** и
  **4 formatting failures** только в неизменённых examples.
- `mypy temporal_boost/` — **passed**, 23 файла.
- `mkdocs build --strict` — **passed**; старые информационные сообщения о ссылках
  в `faststream_integration.md` остаются.
- `git diff --check` — **passed**.

## Зависимости и связи

Зависит от: [TB-002](002-application-graceful-shutdown.md), [TB-008](008-cli-exit-codes.md).

Связанные задачи: [TB-003](003-thread-worker-failure-propagation.md), [TB-004](004-wire-graceful-shutdown-timeout.md), [TB-010](010-asgi-multiprocess-port-conflicts.md), [TB-011](011-prometheus-multiple-runtimes.md), [TB-028](028-prometheus-temp-directory-ownership.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

