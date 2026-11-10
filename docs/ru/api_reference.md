# Справочник API {#api-reference}

Полный справочник Temporal-boost.

## BoostApp {#boostapp}

Основной класс приложения.

### `BoostApp.__init__()` {#boostapp__init__}

Создаёт экземпляр BoostApp.

```python
BoostApp(
    name: str | None = None,
    *,
    temporal_endpoint: str | None = None,
    temporal_namespace: str | None = None,
    debug_mode: bool = False,
    use_pydantic: bool | None = None,
    logger_config: dict[str, Any] | str | Path | None = DEFAULT_LOGGING_CONFIG,
    shutdown_timeout: float = 30.0,
) -> None
```

**Параметры:**

- `name` (str | None): имя приложения, по умолчанию `"temporal_generic_service"`.
- `temporal_endpoint` (str | None): заменяет импортированный `TEMPORAL_TARGET_HOST`; `None` наследует его.
- `temporal_namespace` (str | None): заменяет импортированный `TEMPORAL_NAMESPACE`; `None` наследует его.
- `debug_mode` (bool): режим отладки, по умолчанию `False`.
- `use_pydantic` (bool | None): `None` наследует `TEMPORAL_USE_PYDANTIC_DATA_CONVERTER`, `True` включает Pydantic, `False` отключает автоматический выбор. Явный `data_converter` клиента приоритетнее.
- `logger_config` (dict | str | Path | None): словарь настройки логов или путь к JSON/YAML либо файлу конфигурации logging.
- `shutdown_timeout` (float): общий бюджет секунд на согласованную остановку и ожидание потоков; конечный и неотрицательный, независим от настроек SDK.

**Пример:**

```python
app = BoostApp(
    name="my-service",
    temporal_endpoint="localhost:7233",
    temporal_namespace="default",
    use_pydantic=True,
)
```

### `BoostApp.add_worker()` {#boostappadd_worker}

Добавляет воркер Temporal.

```python
add_worker(
    worker_name: str,
    task_queue: str,
    *,
    activities: list[Callable[..., Any]] | None = None,
    workflows: list[type] | None = None,
    interceptors: list[Interceptor] | None = None,
    cron_schedule: str | None = None,
    cron_runner: MethodAsyncNoParam[Any, Any] | None = None,
    cron_workflow_id: str | None = None,
    **worker_kwargs: Any,
) -> TemporalBoostWorker
```

**Параметры:**

- `worker_name` (str): уникальное имя; запрещены `"run"`, `"cron"`, `"exec"`, `"all"`.
- `task_queue` (str): имя очереди задач Temporal.
- `activities` (list[Callable] | None): функции activity.
- `workflows` (list[type] | None): классы workflow.
- `interceptors` (list[Interceptor] | None): перехватчики Temporal.
- `cron_schedule` (str | None): расписание CRON.
- `cron_runner` (MethodAsyncNoParam | None): метод запуска workflow для CRON.
- `cron_workflow_id` (str | None): стабильный ID в настроенном namespace. По умолчанию `temporal-boost/cron/<percent-encoded task_queue>/<percent-encoded worker_name>`. Пустые и пробельные ID вызывают `ValueError`.
- `**worker_kwargs`: дополнительные настройки воркера.

`cron_schedule` и `cron_runner` передаются вместе или оба пропускаются. Неполная пара и пустое расписание вызывают `ValueError` при создании воркера до подключения. Синтаксис выражения проверяет SDK/сервер. Это относится и к прямому созданию `TemporalBoostWorker`. Один `cron_workflow_id` не включает CRON. `add_worker()` регистрирует локальные команды, но не создаёт расписание на сервере.

`graceful_shutdown_timeout=timedelta(...)` в `worker_kwargs` задаёт период завершения activity в SDK. Пропуск или `None` наследует `TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT` (30 секунд), ноль сохраняется, отрицательная длительность вызывает `ValueError` при регистрации. Параметр независим от `BoostApp.shutdown_timeout`: см. [конфигурацию](configuration.md#temporal_graceful_shutdown_timeout).

**Возвращает:**

- `TemporalBoostWorker`: созданный экземпляр.

**Пример:**

```python
worker = app.add_worker(
    "my_worker",
    "my_queue",
    activities=[my_activity],
    workflows=[MyWorkflow],
)
```

### `BoostApp.add_asgi_worker()` {#boostappadd_asgi_worker}

Добавляет приложение ASGI как воркер.

```python
add_asgi_worker(
    worker_name: str,
    asgi_app: Any,
    host: str,
    port: int,
    *,
    log_level: str | int | None = None,
    asgi_worker_type: ASGIWorkerType = ASGIWorkerType.auto,
    **asgi_worker_kwargs: Any,
) -> None
```

**Параметры:**

- `worker_name` (str): уникальное имя.
- `asgi_app` (Any): объект приложения ASGI или строковый путь.
- `host` (str): адрес прослушивания.
- `port` (int): порт.
- `log_level` (str | int | None): уровень логирования сервера.
- `asgi_worker_type` (ASGIWorkerType): auto, uvicorn, hypercorn или granian.
- `**asgi_worker_kwargs`: настройки одного асинхронного сервера. Перезагрузчики, несколько внутренних воркеров и нестандартные циклы отклоняются. Granian использует встроенный сервер; Hypercorn проверяет имена полей. См. [завершение ASGI](creating_application.md#managed-asgi-shutdown).

**Пример:**

```python
from fastapi import FastAPI

fastapi_app = FastAPI()
app.add_asgi_worker("api_worker", fastapi_app, "0.0.0.0", 8000)
```

### `BoostApp.add_faststream_worker()` {#boostappadd_faststream_worker}

Добавляет FastStream как воркер.

```python
add_faststream_worker(
    worker_name: str,
    faststream_app: Any,
    *,
    log_level: str | int | None = None,
    **faststream_kwargs: Any,
) -> FastStreamBoostWorker
```

**Параметры:**

- `worker_name` (str): уникальное имя.
- `faststream_app` (Any): экземпляр FastStream.
- `log_level` (str | int | None): уровень логирования.
- `**faststream_kwargs`: дополнительные настройки FastStream.

**Возвращает:**

- `FastStreamBoostWorker`: созданный экземпляр.

**Пример:**

```python
from faststream import FastStream

faststream_app = FastStream(broker)
app.add_faststream_worker("message_worker", faststream_app)
```

### `BoostApp.run()` {#boostapprun}

Запускает CLI приложения.

```python
run(args: list[str] | None = None, **kwargs: Any) -> Any
```

`args` — один список аргументов CLI. Пропуск или `None` использует `sys.argv[1:]`; `[]` остаётся пустым и вызывает настроенную справку/ошибку отсутствующей команды с кодом 2. Отдельные позиционные аргументы и единая строка команды не поддерживаются: используйте `app.run(["run", "worker_name"])`.

По умолчанию Typer вызывает `SystemExit`: справка и успешные команды дают 0, неизвестные команды, пропущенные аргументы и неверные значения — 2. Явный ненулевой код сохраняется. Необработанные ошибки воркера передаются и приводят к ненулевому статусу процесса. В `run all` успешный `SystemExit(0)`/`SystemExit(None)` воркера преобразуется на границе CLI в `RuntimeError`, чтобы ошибка координатора не сообщала об успехе. Прямой `run_all_workers()` сохраняет исходное исключение.

`standalone_mode=False`, `prog_name="service"` и другие параметры передаются Typer. Без standalone-режима `run()` возвращает результат команды и передаёт ошибки разбора/воркера, например `click.UsageError` и `RuntimeError`. Справка возвращает 0. Прямой `SystemExit` обработчика продолжает распространяться согласно Typer. Возвращаемое значение не является универсальным API кода выхода; в точке входа процесса используйте стандартный standalone-режим.

**Пример:**

```python
if __name__ == "__main__":
    app.run()
```

При встраивании зарегистрируйте `check` и вызовите `app.run(["exec", "check"], standalone_mode=False)`. Миграция: если код рассчитывал на подавление `SystemExit`, перехватывайте его явно или используйте non-standalone и обрабатывайте исключения.

### `BoostApp.run_all_workers()` и `BoostApp.stop()` {#boostapprun_all_workers-and-boostappstop}

```python
run_all_workers() -> None
stop() -> None
```

`run_all_workers()` создаёт поток для каждого воркера и ждёт остановки или ошибки. В главном потоке временно обрабатывает SIGINT/SIGTERM. `stop()` потокобезопасно запрашивает остановку, сразу возвращает управление и допускает повторы. Вызовы вне запуска не влияют на следующий запуск.

Координатор вызывает `request_stop()` живых воркеров и ждёт все потоки в пределах `shutdown_timeout`. Если более ранней ошибки нет, оставшиеся воркеры перечисляются в `TimeoutError`. Иначе таймаут логируется и передаётся первая ошибка. Daemon-потоки могут продолжить работу; пока они живы, повторный запуск запрещён. Одновременные вызовы также отклоняются.

Первая ошибка воркера инициирует остановку и после очистки передаётся с исходным traceback. Последующие ошибки только логируются. Возврат `run()` до общей остановки считается `RuntimeError`; конечному воркеру нужно вызвать `app.stop()` до возврата или запускаться отдельно. Обычный возврат, `asyncio.CancelledError` и `concurrent.futures.CancelledError` во время остановки допустимы. Отмена до stop и все другие исключения, включая `SystemExit`/`KeyboardInterrupt`, считаются ошибками. Такой порядок сохраняет и ошибки startup/запроса остановки. CLI преобразует успешный `SystemExit`, как описано выше. Внешний многопроцессный супервизор передаёт первый обнаруженный сбой дочернего процесса после остановки остальных.

Temporal, FastStream и встроенные ASGI поддерживают управляемую остановку. Собственным воркерам нужен `request_stop()` или `AsyncBoostWorker`: см. [корректное завершение](running_application.md#graceful-shutdown).

### `BoostApp.add_async_runtime()` {#boostappadd_async_runtime}

```python
add_async_runtime(worker_name: str, boost_worker: BaseBoostWorker) -> None
```

Регистрирует `run()` собственного воркера как CLI-команду и включает его в `run all`. `boost_worker` должен реализовать синхронный `run()` и асинхронный `shutdown()` контракта `BaseBoostWorker`. Для управляемой остановки нужен потокобезопасный `request_stop()` или [база AsyncBoostWorker](advanced_usage.md#custom-worker-shutdown).

Регистрация присваивает `boost_worker.name = worker_name`, заменяя прежнее имя. Это каноническое имя CLI, `get_registered_workers()`, логов и потока `worker-<worker_name>`. Параметры callback сохраняются, но `run all` вызывает `run()` без аргументов. Не меняйте имя; каждой регистрации приложения нужен отдельный экземпляр.

Все типы воркеров используют общее пространство имён. Зарезервированные `run`, `cron`, `exec`, `all`, дубликат имени и повтор объекта в одном приложении вызывают `RuntimeError` до изменения имени или команды. Возвращается `None`.

Заранее созданный `TemporalBoostWorker` сохраняет настройки клиента/runtime, debug-флаг и `cron_workflow_id`. Метод не применяет Temporal-настройки `BoostApp` и не регистрирует `cron`. Для наследования defaults и CRON используйте `add_worker()`; иначе настройте экземпляр явно до инициализации ресурсов.

**Миграция:** alias регистрации становится именем воркера. Если прежнее имя нужно бизнес-логике, храните его отдельно. Несколько aliases одного объекта запрещены: создавайте разные экземпляры. Неиспользуемые приватные списки CRON/ASGI удалены; используйте `get_registered_workers()`.

### `BoostApp.get_registered_workers()` {#boostappget_registered_workers}

Возвращает зарегистрированных воркеров.

```python
get_registered_workers() -> list[BaseBoostWorker]
```

**Результат:** `list[BaseBoostWorker]`, поверхностная копия единого реестра. Объекты сохраняют identity и канонические имена; изменение списка не меняет регистрацию.

## Запускатель процессов CLI {#cli-process-runner}

Строка приложения имеет вид `module:attribute.nested` с точечными идентификаторами. Сначала используется обычный путь импорта Python; текущий каталог и его непосредственный родитель проверяются только при отсутствии целевого модуля/пакета. Ошибки зависимостей и приложения передаются без изменений. Неверный формат, отсутствующая цель и атрибут дают разные `ValueError`; исходная ошибка поиска сохраняется как причина.

Неудача восстанавливает `sys.path`; успешный fallback оставляет только каталог найденной цели для следующих импортов. Рекурсивного поиска и очистки кэша модулей нет. См. [поиск приложения](running_application.md#application-import-lookup).

Перед путём приложения доступны `--workers N --shutdown-timeout SECONDS`. Таймаут действует при `--workers > 1`, по умолчанию 30 секунд, конечный и неотрицательный.

```python
from temporal_boost.cli.process_runner import run_multiprocess

run_multiprocess(
    app_path: str,
    number_of_processes: int,
    arguments: list[str],
    *,
    shutdown_timeout: float = 30.0,
) -> None
```

В каждом дочернем процессе запускается та же команда. Запускатель наблюдает каждый процесс, при первом ненулевом выходе останавливает остальные, дожидается завершения и закрывает дескрипторы. Автоперезапуска нет. После успеха всех возвращает `None`. Ошибка вызывает `SystemExit` с первым обнаруженным положительным статусом; сигнал `-N` преобразуется в `128 + N`. Ошибки startup/cleanup не заменяют более раннюю. Успешный `SystemExit(0)`/`SystemExit(None)` как ошибка превращается в `RuntimeError`. Неверное количество процессов или таймаут дают `ValueError` до создания процессов.

Выбор ASGI в `BoostApp` при `number_of_processes > 1` вызывает usage error в дочернем процессе до запуска воркеров; родитель передаёт код 2. Это относится к `run all` с любым `BaseAsgiWorker` и `run <asgi-name>` всех серверов. Temporal, CRON, exec и help разрешены даже при наличии ASGI-регистраций. Проверяется фактический callback после разбора; приложение не импортируется в родителе. Общего сокета нет: см. [ASGI и внешние процессы](running_application.md#asgi-and-external-processes).

Сначала родитель запрашивает управляемую остановку через отдельные однонаправленные каналы и наблюдателей детей, затем закрывает каналы. Общий grace deadline действует на всех; далее terminate до 5 секунд и kill до 5 секунд. В главном потоке SIGINT/SIGTERM временно перехватываются и затем восстанавливаются. После очистки выход 130/143, если ошибка не определила другой результат. Повторные сигналы не меняют первый запрос и сроки. Этот бюджет независим от приложения и SDK. См. [супервизию процессов](running_application.md#multi-process-supervision).

## Контракт остановки воркера {#worker-stop-contract}

`BaseBoostWorker.request_stop() -> bool` — неблокирующий потокобезопасный запрос. Реализация должна принимать повторы и запросы при старте. При поддержке возвращает `True`; стандартная реализация — `False`. Асинхронная очистка выполняется в цикле владельца ресурсов.

`AsyncBoostWorker`, экспортируемый из `temporal_boost` и `temporal_boost.workers`, реализует контракт для asyncio. Вызовите `super().__init__()`, задайте `name`, реализуйте async `run_async()`/`shutdown()` и наследуйте `run()`/`request_stop()`. База владеет циклом, один раз вызывает очистку за запуск и ждёт возврата `run_async()`. `shutdown()` должен учитывать частичный startup и разблокировать `run_async()`. При ошибке исполнения последующая ошибка очистки логируется; при отмене ошибка очистки передаётся, чтобы отмена не скрывала сбой. См. [пример](advanced_usage.md#custom-worker-shutdown).

## TemporalBoostWorker {#temporalboostworker}

Класс воркера Temporal. Приоритет endpoint и namespace по отдельности: последняя явная настройка воркера → параметры `BoostApp` → окружение импорта → `localhost:7233` и `default`. См. [приоритет конфигурации](configuration.md#configuration-priority).

### `TemporalBoostWorker.configure_temporal_client()` {#temporalboostworkerconfigure_temporal_client}

Настраивает клиент до инициализации или после очистки прошлого запуска. С начала инициализации и в состояниях building/running/stopping вызывает `RuntimeError`. Не переподключает живой клиент и не меняет SDK воркер; отклонённый вызов сохраняет сборщики.

```python
configure_temporal_client(
    *,
    target_host: str | None = None,
    namespace: str | None = None,
    api_key: str | None = None,
    identity: str | None = None,
    tls: bool | None = None,
    use_pydantic_data_converter: bool | None = None,
    **kwargs: Any,
) -> None
```

**Параметры:**

- `target_host` (str | None): адрес сервера.
- `namespace` (str | None): namespace.
- `api_key` (str | None): API-ключ Temporal Cloud.
- `identity` (str | None): идентификатор клиента.
- `tls` (bool | None): включение TLS.
- `use_pydantic_data_converter` (bool | None): `True` включает Pydantic, `False` отключает автоматический выбор; `None` наследует окружение при первом вызове и сохраняет существующий сборщик. Явный `data_converter` в `kwargs` приоритетнее.
- `**kwargs`: дополнительные параметры клиента.

У существующего сборщика пропущенные поля и `None` сохраняют значения. Пустые строки передаются setters буквально и не сбрасывают defaults. `tls=False` заменяет импортированный `True`. Настраивайте до инициализации; активный клиент не переподключается.

**Пример:**

```python
worker.configure_temporal_client(
    target_host="temporal.example.com:7233",
    namespace="production",
    use_pydantic_data_converter=True,
)
```

### `TemporalBoostWorker.configure_temporal_runtime()` {#temporalboostworkerconfigure_temporal_runtime}

Настраивает отдельный runtime воркера до использования. Одновременным runtime нужны разные endpoints Prometheus; автоматического разделения нет. Процесс должен предоставлять каждый endpoint: см. [метрики](advanced_usage.md#metrics-across-workers-and-processes).

После создания runtime и при активном запуске вызывает `RuntimeError`. Чтение `temporal_client_runtime` создаёт runtime и фиксирует параметры даже до `run()`. После очистки метод настраивает следующий запуск и не заменяет живой runtime. См. [срок действия настроек](configuration.md#when-configuration-becomes-fixed).

```python
configure_temporal_runtime(
    *,
    logging: LoggingConfig | None = None,
    metrics: OpenTelemetryConfig | PrometheusConfig | MetricBuffer | None = None,
    global_tags: Mapping[str, str] | None = None,
    attach_service_name: bool = True,
    metric_prefix: str | None = None,
    prometheus_bind_address: str | None = config.PROMETHEUS_BIND_ADDRESS,
    prometheus_counters_total_suffix: bool | None = config.PROMETHEUS_COUNTERS_TOTAL_SUFFIX,
    prometheus_unit_suffix: bool | None = config.PROMETHEUS_UNIT_SUFFIX,
    prometheus_durations_as_seconds: bool | None = config.PROMETHEUS_DURATIONS_AS_SECONDS,
) -> None
```

**Параметры:**

- `logging` (LoggingConfig | None): конфигурация логов.
- `metrics` (OpenTelemetryConfig | PrometheusConfig | MetricBuffer | None): конфигурация метрик.
- `global_tags` (Mapping[str, str] | None): глобальные теги.
- `attach_service_name` (bool): добавление имени сервиса.
- `metric_prefix` (str | None): префикс метрик.
- `prometheus_bind_address` (str | None): адрес экспортёра.
- `prometheus_counters_total_suffix` (bool | None): суффикс `_total` счётчиков.
- `prometheus_unit_suffix` (bool | None): суффикс единицы измерения.
- `prometheus_durations_as_seconds` (bool | None): длительности в секундах.

**Пример:**

```python
worker.configure_temporal_runtime(
    prometheus_bind_address="0.0.0.0:9090",
    global_tags={"environment": "production"},
)
```

### `TemporalBoostWorker.run()` {#temporalboostworkerrun}

Обрабатывает очередь воркера. Не регистрирует CRON даже при наличии параметров CRON. Используется `run <name>` и `run all` для каждого воркера.

```python
run() -> None
```

**Пример:**

```python
worker.run()
```

### `TemporalBoostWorker.cron()` {#temporalboostworkercron}

Запускает воркер в режиме CRON. Команда `cron <name>` доступна при обоих параметрах CRON. Прямой вызов без них даёт `RuntimeError` до цикла и подключения. Регистрирует задачу один раз при старте процесса и обрабатывает очередь до остановки.

Атомарно запускает или использует ID через `WorkflowIDConflictPolicy.USE_EXISTING`. Закрытые ID отклоняются с `WorkflowAlreadyStartedError` через `WorkflowIDReusePolicy.REJECT_DUPLICATE` в пределах хранения истории сервером. Повтор сохраняет расписание и конфигурацию. Локальная остановка не отменяет серверный workflow. См. [идентичность CRON](creating_application.md#cron-workflow-identity) и [миграцию UUID](running_application.md#migrating-existing-uuid-cron-workflows).

```python
cron() -> None
```

**Пример:**

```python
worker.cron()
```

Обе команды владеют циклом событий и единым жизненным циклом startup/исполнения/очистки. Остановка при старте отменяет подключение. Очистка CRON завершает локальное ожидание, отменяет незавершённую регистрацию и останавливает SDK воркер. Адаптер владеет задачей SDK `run()` и использует публичный `shutdown()` без дополнительного SDK async context manager. Обычный `run()` не регистрирует CRON, локальная остановка не удаляет серверный workflow.

Последовательные запуски создают новые клиент, runtime и SDK воркер в новом цикле. Одновременные `run()`/`cron()` одного адаптера дают `RuntimeError`. Ошибки startup/исполнения передаются после очистки; последующие ошибки очистки только логируются. Неожиданная отмена также передаётся. Сбой SDK-валидации до старта не ждёт незавершаемый SDK `shutdown()`. В поддерживаемом SDK нет публичного close клиента/runtime: адаптер освобождает ссылки свои и сборщиков, не закрывает executors вызывающего кода. Внешние ссылки могут удерживать SDK-объекты.

### `TemporalBoostWorker.request_stop()` и `TemporalBoostWorker.shutdown()` {#temporalboostworkerrequest_stop-and-temporalboostworkershutdown}

```python
def request_stop() -> bool
async def shutdown() -> None
```

`request_stop()` возвращает `True` и запрашивает остановку из любого потока без ожидания. Повторы безопасны. Запрос до первого запуска запоминается и предотвращает ресурсы; после остановки не влияет на следующий запуск. `shutdown()` до/после запуска ничего не делает; во время запуска должен вызываться в своём цикле, запрашивает остановку и ждёт завершения с ошибками. Ожидающие разделяют очистку; отмена одного не отменяет жизненный цикл. Чужой цикл даёт `RuntimeError` с указанием `request_stop()`. В callback воркера также используйте `request_stop()`.

SDK shutdown вызывается не более одного раза за активный SDK run. Если run уже завершён, извлекается результат без повторного shutdown. При ошибке остановки адаптер отменяет и дожидается SDK-задачи до освобождения ссылок. Зависшая операция SDK может превысить период завершения activity; `BoostApp.shutdown_timeout` ограничивает ожидание координатора, а не SDK.

### Состояния жизненного цикла {#lifecycle-states}

Свойство `state` доступно только для чтения:

| Значение | Смысл |
| --- | --- |
| `created` | Создан; активного запуска нет |
| `building` | Создание runtime, подключение клиента, создание SDK воркера |
| `running` | Задача SDK run запущена; регистрация CRON может продолжаться |
| `stopping` | Отмена startup/CRON и ожидание очистки SDK |
| `stopped` | Ссылки на ресурсы освобождены; разрешён следующий запуск |

Ранняя остановка/ошибка может пропустить `running`. Настраивайте до инициализации и запуска. `created` не означает отсутствие runtime: ленивое свойство может создать его без запуска. После `stopped` настройка доступна до следующей инициализации.

### Свойства {#properties}

- `temporal_client` (Client): экземпляр клиента.
- `temporal_worker` (Worker): экземпляр SDK воркера.
- `temporal_client_runtime` (Runtime): лениво создаёт/кэширует runtime и фиксирует конфигурацию; может открыть порт метрик. Повторное чтение возвращает объект до очистки запуска. При очистке чтение без runtime вызывает ошибку, предотвращая создание ресурсов.
- `temporal_cron_runner` (MethodAsyncNoParam): метод CRON.
- `cron_workflow_id` (str): вычисленный ID CRON, только чтение.
- `state`: текущее состояние. Свойства клиента и SDK воркера после очистки вызывают ошибки до новой сборки.

## TemporalClientBuilder {#temporalclientbuilder}

Сборщик клиента Temporal.

### `TemporalClientBuilder.__init__()` {#temporalclientbuilder__init__}

```python
__init__(
    target_host: str | None = None,
    namespace: str | None = None,
    api_key: str | None = None,
    identity: str | None = None,
    *,
    tls: bool | None = None,
    use_pydantic_data_converter: bool | None = None,
    **kwargs: Any,
) -> None
```

### `TemporalClientBuilder.build()` {#temporalclientbuilderbuild}

Создаёт и возвращает клиента.

```python
async def build() -> Client
```

**Результат:** `Client`.

Непустые аргументы конструктора `target_host`, `namespace`, `api_key`, `identity` заменяют импортированную конфигурацию; `None` и пустые строки используют её. Поздние setters заменяют сохранённые значения, включая пустые строки. `tls=None` наследует конфигурацию, `tls=False` заменяет её. У отдельного сборщика нет слоя `BoostApp`. Новые сборщики не перечитывают изменения окружения после импорта.

`use_pydantic_data_converter=None` наследует окружение; `True` включает Pydantic, `False` отключает автоматический выбор. Явный `data_converter` в kwargs конструктора или `set_kwargs()` приоритетнее флага.

### `TemporalClientBuilder.set_pydantic_data_converter()` {#temporalclientbuilderset_pydantic_data_converter}

```python
def set_pydantic_data_converter(*, enabled: bool = True) -> None
```

Меняет автоматический выбор Pydantic будущих сборок. Без аргументов включает; `enabled=False` отключает автоматический выбор, сохраняя явный `data_converter`.

## TemporalWorkerBuilder {#temporalworkerbuilder}

Сборщик воркера Temporal.

### `TemporalWorkerBuilder.__init__()` {#temporalworkerbuilder__init__}

```python
__init__(
    task_queue: str,
    *,
    debug_mode: bool = False,
    max_concurrent_workflow_tasks: int | None = None,
    max_concurrent_activities: int | None = None,
    max_concurrent_local_activities: int | None = None,
    max_concurrent_workflow_task_polls: int | None = None,
    nonsticky_to_sticky_poll_ratio: float | None = None,
    max_concurrent_activity_task_polls: int | None = None,
    graceful_shutdown_timeout: timedelta | None = None,
    **kwargs: Any,
) -> None
```

Для шести числовых параметров пропуск/`None` выбирает [окружение/default](configuration.md#temporal_max_concurrent_workflow_tasks). Параллелизм и число опросов — положительные целые числа. Коэффициент — конечный неотрицательный `int`/`float`; `0.0` сохраняется, значения больше `1.0` разрешены. Булевы значения, числовые строки и неверные типы дают `TypeError`, неверные диапазоны — `ValueError` при создании. Выбранные defaults проверяются так же. Нулевые счётчики теперь дают ошибку: используйте `None` или пропуск.

Дополнительные ограничения, например минимум два workflow при кэшировании, проверяет SDK при `build()`. Нулевой коэффициент не отключает non-sticky опрос: SDK сохраняет минимальное число poller.

### `TemporalWorkerBuilder.build()` {#temporalworkerbuilderbuild}

Создаёт и возвращает SDK воркер.

```python
def build() -> Worker
```

**Результат:** `Worker`.

`graceful_shutdown_timeout` передаётся прямо в SDK. Явный неотрицательный `datetime.timedelta`, включая ноль, заменяет окружение; пропуск/`None` использует `config.GRACEFUL_SHUTDOWN_TIMEOUT` (30 секунд). Выбранная отрицательная длительность даёт `ValueError` при создании сборщика. `BoostApp.add_worker()` и `TemporalBoostWorker` передают параметр через kwargs без дублирования.

Период начинается при запросе SDK shutdown и задаёт время завершения activity до запроса отмены. Он не ограничивает общее время остановки SDK, не инициирует stop и не меняет бюджеты приложения/процессов. Пропуск теперь использует default фреймворка вместо нуля SDK.

## TemporalRuntimeBuilder {#temporalruntimebuilder}

Сборщик runtime Temporal.

### `TemporalRuntimeBuilder.__init__()` {#temporalruntimebuilder__init__}

```python
__init__(
    *,
    logging: LoggingConfig | None = None,
    metrics: OpenTelemetryConfig | PrometheusConfig | MetricBuffer | None = None,
    global_tags: Mapping[str, str] | None = None,
    attach_service_name: bool = True,
    metric_prefix: str | None = None,
    prometheus_bind_address: str | None = config.PROMETHEUS_BIND_ADDRESS,
    prometheus_counters_total_suffix: bool | None = config.PROMETHEUS_COUNTERS_TOTAL_SUFFIX,
    prometheus_unit_suffix: bool | None = config.PROMETHEUS_UNIT_SUFFIX,
    prometheus_durations_as_seconds: bool | None = config.PROMETHEUS_DURATIONS_AS_SECONDS,
) -> None
```

### `TemporalRuntimeBuilder.build()` {#temporalruntimebuilderbuild}

Создаёт новый независимый runtime. Явный `metrics` приоритетнее `prometheus_bind_address`; логируется только реально используемый endpoint. Вызывающий код владеет результатом и должен передать его в `TemporalClientBuilder.set_runtime()` до сборки клиента. Не передавайте живой runtime между процессами.

Defaults четырёх `prometheus_*` фиксируются при определении функции во время импорта, как у `TemporalBoostWorker.configure_temporal_runtime()`. Изменение окружения/`config.PROMETHEUS_*` не обновляет пропущенные аргументы. При `metrics=None` явный `prometheus_bind_address=None` отключает неявный экспортёр; `False`/`None` флага суффикса или длительности даёт `False`. Настройка runtime воркера заменяет прежнюю целиком, используя defaults функции для пропусков. См. [конфигурацию runtime](configuration.md#runtime-configuration).

```python
def build() -> Runtime
```

**Результат:** `Runtime`.

**Исключения:** `ValueError` SDK при инициализации, включая конфликт порта. Повтора с отключёнными метриками нет. Одновременным runtime Prometheus нужны разные endpoints.

## Перечисления {#enums}

### `ASGIWorkerType` {#asgiworkertype}

`auto` выбирает доступный встроенный сервер в порядке **Uvicorn → Granian → Hypercorn**. Регистрация доступна при успешном импорте optional dependencies. Явный выбор обходит приоритет. Если есть только собственные серверы, выбирается лексикографически минимальный ключ. Повтор той же пары класс/ключ идемпотентен; другой класс с занятым ключом, включая встроенный, даёт `ValueError`.

- `auto`: автоматический выбор.
- `uvicorn`: Uvicorn.
- `hypercorn`: Hypercorn.
- `granian`: Granian.

## Константы конфигурации {#configuration-constants}

Defaults доступны в `temporal_boost.temporal.config` и читаются один раз при первом импорте. `.env` автоматически не загружается. Подготовьте окружение до импорта/CLI. Изменения `os.environ` не обновляют константы и SDK-объекты: см. [загрузку окружения](configuration.md#environment-loading).

- `TARGET_HOST`: адрес Temporal.
- `CLIENT_NAMESPACE`: namespace.
- `CLIENT_TLS`: флаг TLS.
- `CLIENT_API_KEY`: API-ключ.
- `CLIENT_IDENTITY`: идентификатор клиента.
- `USE_PYDANTIC_DATA_CONVERTER`: флаг Pydantic.
- `MAX_CONCURRENT_WORKFLOW_TASKS`: максимум задач workflow.
- `MAX_CONCURRENT_ACTIVITIES`: максимум activity.
- `MAX_CONCURRENT_LOCAL_ACTIVITIES`: максимум локальных activity.
- `MAX_WORKFLOW_TASK_POLLS`: максимум опросов workflow.
- `MAX_ACTIVITY_TASK_POLLS`: максимум опросов activity.
- `NONSTICKY_STICKY_RATIO`: соотношение опросов non-sticky/sticky.
- `GRACEFUL_SHUTDOWN_TIMEOUT`: период завершения activity SDK (`timedelta`, 30 секунд), независимый от бюджета приложения.
- `PROMETHEUS_BIND_ADDRESS`: адрес Prometheus.
- `PROMETHEUS_COUNTERS_TOTAL_SUFFIX`: суффикс счётчиков.
- `PROMETHEUS_UNIT_SUFFIX`: суффикс единиц измерения.
- `PROMETHEUS_DURATIONS_AS_SECONDS`: длительности в секундах.

Все настройки описаны в [руководстве по конфигурации](configuration.md).
