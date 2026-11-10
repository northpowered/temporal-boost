# Расширенное использование {#advanced-usage}

Сложные сценарии, настройка и приёмы работы с Temporal-boost.

## Содержание {#table-of-contents}

- [Настройка runtime](#custom-runtime-configuration)
- [Метрики воркеров и процессов](#metrics-across-workers-and-processes)
- [Настройка воркеров](#worker-customization)
- [Перехватчики](#interceptors)
- [Логирование](#custom-logging)
- [Несколько клиентов](#multiple-clients)
- [Жизненный цикл](#worker-lifecycle)
- [Обработка ошибок](#error-handling-patterns)
- [Производительность](#performance-optimization)

## Настройка runtime {#custom-runtime-configuration}

Настройте телеметрию и метрики runtime Temporal:

```python
from temporal_boost import BoostApp
from temporalio.runtime import LoggingConfig, PrometheusConfig, Runtime

app = BoostApp("advanced-app")

worker = app.add_worker("custom_worker", "custom_queue", activities=[...])

# Configure custom runtime
worker.configure_temporal_runtime(
    prometheus_bind_address="0.0.0.0:9090",
    prometheus_counters_total_suffix=True,
    prometheus_unit_suffix=True,
    prometheus_durations_as_seconds=True,
    global_tags={"environment": "production", "service": "my-service"},
    attach_service_name=True,
    metric_prefix="temporal_boost",
)
```

### Настройка логирования {#custom-logging-configuration}

```python
import logging
import logging.config
from temporal_boost import BoostApp

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "detailed": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "json": {
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "detailed",
            "level": "INFO",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "temporal.log",
            "maxBytes": 10485760,
            "backupCount": 5,
            "formatter": "json",
            "level": "DEBUG",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file"],
    },
}

app = BoostApp(logger_config=LOGGING_CONFIG)
```

## Настройка воркеров {#worker-customization}

### Индивидуальная конфигурация {#per-worker-configuration}

Задайте параметры отдельного воркера:

```python
worker = app.add_worker(
    "high_throughput_worker",
    "high_throughput_queue",
    activities=[...],
    max_concurrent_activities=1000,
    max_concurrent_workflow_tasks=500,
)

# Configure client
worker.configure_temporal_client(
    target_host="temporal.example.com:7233",
    namespace="production",
    use_pydantic_data_converter=True,
)

# Configure runtime
worker.configure_temporal_runtime(
    prometheus_bind_address="0.0.0.0:9091",
)
```

### Использование сборщиков {#worker-builder-pattern}

Прямое использование сборщиков делает владение runtime явным. Запускаемый пример [`example_runtime.py`](https://github.com/northpowered/temporal-boost/blob/main/examples/example_runtime.py) содержит полный асинхронный жизненный цикл:

```python
import asyncio

from temporalio import activity

from temporal_boost.temporal.client import TemporalClientBuilder
from temporal_boost.temporal.runtime import TemporalRuntimeBuilder
from temporal_boost.temporal.worker import TemporalWorkerBuilder


@activity.defn
async def greet(name: str) -> str:
    return f"Hello, {name}!"


async def run_worker() -> None:
    runtime = TemporalRuntimeBuilder(prometheus_bind_address="127.0.0.1:9090").build()
    client_builder = TemporalClientBuilder(target_host="localhost:7233", namespace="default")
    client_builder.set_runtime(runtime)
    client = await client_builder.build()
    worker_builder = TemporalWorkerBuilder(task_queue="custom_queue")
    worker_builder.set_client(client)
    worker_builder.set_activities([greet])
    worker = worker_builder.build()
    async with worker:
        # Keep serving until cancelled; the context shuts down the SDK worker.
        await asyncio.Event().wait()
```

Вызывающий код удерживает runtime, пока им пользуются клиент и воркер. У поддерживаемого SDK нет публичного `close()` для runtime: после остановки освободите ссылки на воркер, клиент, сборщики и runtime. Внешняя ссылка может удерживать экспортёр. Этот отдельный пример создаёт один runtime; воркеры `BoostApp` создают собственные runtime.

## Метрики воркеров и процессов {#metrics-across-workers-and-processes}

CLI больше не создаёт, не проверяет и не меняет `PROMETHEUS_MULTIPROC_DIR`. Экспортёры SDK не используют каталог многопроцессного режима Python-клиента Prometheus. Если переменная нужна другой части приложения, приложение отвечает за путь, проверку и очистку. CLI не меняет каталоги, обычные файлы, отсутствующие пути и окружение. После обновления автоматического временного каталога нет: настраивайте и собирайте endpoints SDK явно.

Каждый `TemporalBoostWorker` владеет отдельными runtime и клиентом. **Автоматического совместного использования runtime нет**. Экспортёр принадлежит runtime и открывает собственный сокет. Каждому одновременно работающему runtime нужен отдельный endpoint, опрашиваемый Prometheus. Вместо этого `OpenTelemetryConfig` SDK может отправлять метрики во внешний коллектор.

| Развёртывание | Endpoints для сбора |
| --- | --- |
| Два воркера в одном процессе | Два адреса, например `:9100` и `:9101` |
| Два процесса по два воркера на одном хосте | Четыре адреса, например `:9100`–`:9103` |
| Два контейнера/pod по два воркера | Оба порта каждого, например `pod-a:9100`, `pod-a:9101`, `pod-b:9100`, `pod-b:9101` |

Настройте каждый воркер до старта и чтения `temporal_client_runtime`. В этом фрагменте `payments` и `notifications` возвращены из `app.add_worker(...)`:

```python
payments.configure_temporal_runtime(
    prometheus_bind_address="0.0.0.0:9100",
    global_tags={"boost_worker": "payments"},
)
notifications.configure_temporal_runtime(
    prometheus_bind_address="0.0.0.0:9101",
    global_tags={"boost_worker": "notifications"},
)
```

`TEMPORAL_PROMETHEUS_BIND_ADDRESS` применяется к каждому воркеру, поэтому фиксированный адрес подходит одному runtime. Для нескольких переопределяйте его у каждого. Процессам с общим сетевым адресом выделяйте диапазоны портов. Внешний `--workers N` повторяет конфигурацию, но не распределяет порты и не объединяет метрики. Используйте процессы с явными диапазонами или pod с отдельными адресами. Собирайте каждый endpoint каждой реплики через статические targets или service discovery.

Запускаемый [пример метрик](https://github.com/northpowered/temporal-boost/blob/main/examples/example_metrics.py) содержит два воркера. При доступном Temporal запустите два процесса в отдельных терминалах:

```bash
METRICS_BASE_PORT=9100 uv run python examples/example_metrics.py run all
METRICS_BASE_PORT=9102 uv run python examples/example_metrics.py run all
```

`METRICS_BASE_PORT` реализована самим примером и не является настройкой Temporal-boost. Prometheus на том же хосте может опрашивать четыре экспортёра:

```yaml
scrape_configs:
  - job_name: temporal-workers
    metrics_path: /metrics
    static_configs:
      - targets: ["127.0.0.1:9100", "127.0.0.1:9101", "127.0.0.1:9102", "127.0.0.1:9103"]
```

Сохраняйте label `instance` для различения endpoints перед агрегацией реплик. Метрики воркеров SDK содержат labels очередей. В зафиксированном SDK `global_tags` попадают в ресурсные метаданные `target_info`, а не в каждый счётчик. Собирайте `target_info` и при необходимости объединяйте по `job`/`instance`.

**Владение и ошибки:** runtime создаётся лениво в процессе воркера и передаётся его клиенту. Очистка освобождает ссылки; нативными ресурсами управляет SDK без публичного `Runtime.close()`. Внешние ссылки на runtime и meter могут продлить жизнь экспортёра. Не создавайте живой runtime в родителе для передачи дочернему процессу: SDK runtime не работает через fork. API общего runtime здесь нет.

Ошибка инициализации экспортёра, включая конфликт порта, прерывает запуск. Лог указывает реальный endpoint; повторной попытки с отключёнными метриками нет. `run all` останавливает соседние воркеры, а внешний супервизор передаёт ошибку. Выделяйте разные endpoints.

**Миграция:** старые версии могли продолжить работу без метрик после конфликта. Теперь такой запуск завершается ошибкой. Назначьте каждому runtime отдельный endpoint или используйте внешний коллектор. Явный `metrics=PrometheusConfig(...)` приоритетнее `prometheus_bind_address` и следует той же политике ошибок.

`PROMETHEUS_MULTIPROC_DIR` относится к отдельно установленному и настроенному Python `prometheus_client`. Экспортёр Temporal туда не пишет; Temporal-boost не объединяет через него метрики SDK. Прежнее автоматическое создание каталога удалено; каталог приложения остаётся в его владении.

## Перехватчики {#interceptors}

Перехватчики добавляют сквозное логирование, метрики и аутентификацию.

### Создание перехватчика {#creating-an-interceptor}

```python
import logging
from typing import Any

from temporalio.worker import (
    ActivityInboundInterceptor,
    ExecuteActivityInput,
    ExecuteWorkflowInput,
    Interceptor,
    WorkflowInboundInterceptor,
    WorkflowInterceptorClassInput,
)


class LoggingActivityInboundInterceptor(ActivityInboundInterceptor):
    async def execute_activity(self, input: ExecuteActivityInput) -> Any:
        logging.getLogger(__name__).info("Executing activity: %s", input.fn.__name__)
        return await super().execute_activity(input)


class LoggingWorkflowInboundInterceptor(WorkflowInboundInterceptor):
    async def execute_workflow(self, input: ExecuteWorkflowInput) -> Any:
        # Use workflow.logger for replay-aware logging inside workflow code.
        from temporalio import workflow
        workflow.logger.info("Executing workflow: %s", input.type.__name__)
        return await super().execute_workflow(input)


class LoggingInterceptor(Interceptor):
    def intercept_activity(self, next: ActivityInboundInterceptor) -> ActivityInboundInterceptor:
        return LoggingActivityInboundInterceptor(next)

    def workflow_interceptor_class(
        self, input: WorkflowInterceptorClassInput
    ) -> type[WorkflowInboundInterceptor]:
        return LoggingWorkflowInboundInterceptor
```

### Использование перехватчиков {#using-interceptors}

Предполагается, что `app`, `my_activity` и `my_workflow` уже определены:

```python
worker = app.add_worker(
    "logged_worker",
    "logged_queue",
    activities=[my_activity],
    workflows=[my_workflow],
    interceptors=[LoggingInterceptor()],
)
```

Типы импортируются из публичного `temporalio.worker`. Минимальный SDK — 1.14.1, соответствующий проверенному lockfile; новые версии разрешены без произвольной верхней границы. CLI использует публичный API Typer. Аргументы `BoostApp.run([...])` передаются буквально, а `run()` оставляет обработку аргументов, включая раскрытие в Windows, Typer/Click. Для встраивания можно отключить раскрытие через `windows_expand_args=False`.

## Логирование {#custom-logging}

### Структурированные логи с контекстом {#structured-logging-with-context}

```python
import logging
import logging.config
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

class ContextualFormatter(logging.Formatter):
    def format(self, record):
        record.request_id = request_id_var.get()
        return super().format(record)

logging_config = {
    "version": 1,
    "formatters": {
        "contextual": {
            "()": ContextualFormatter,
            "format": "%(asctime)s [%(levelname)s] [%(request_id)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "contextual",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}

app = BoostApp(logger_config=logging_config)
```

### Декоратор логирования activity {#activity-logging-decorator}

```python
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def log_activity(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger.info(f"Starting activity: {func.__name__}")
        try:
            result = await func(*args, **kwargs)
            logger.info(f"Completed activity: {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"Failed activity: {func.__name__}, error: {e}")
            raise
    return wrapper

@activity.defn(name="logged_activity")
@log_activity
async def my_activity(data: str) -> str:
    return f"Processed: {data}"
```

## Несколько клиентов {#multiple-clients}

### Несколько кластеров Temporal {#multiple-temporal-clusters}

```python
app = BoostApp("multi-cluster")

# Worker 1: Production cluster
worker1 = app.add_worker("prod_worker", "prod_queue", activities=[...])
worker1.configure_temporal_client(
    target_host="prod.temporal.example.com:7233",
    namespace="production",
)

# Worker 2: Staging cluster
worker2 = app.add_worker("staging_worker", "staging_queue", activities=[...])
worker2.configure_temporal_client(
    target_host="staging.temporal.example.com:7233",
    namespace="staging",
)
```

## Жизненный цикл воркера {#worker-lifecycle}

### Регистрация собственного воркера {#custom-worker-registration}

`app.add_async_runtime("service", worker)` регистрирует экземпляр подкласса `BaseBoostWorker` и присваивает `worker.name = "service"`, заменяя прежнее имя. Начальное имя необязательно. CLI, `get_registered_workers()`, логи и поток `worker-service` используют имя регистрации. Не меняйте его; создавайте отдельный экземпляр для каждой регистрации в приложении.

Имена общие для Temporal, ASGI, FastStream и собственных воркеров. `run`, `cron`, `exec`, `all` зарезервированы. Повтор имени или повторная регистрация объекта вызывает `RuntimeError` до изменения объекта и добавления команды. Сигнатура `run()` определяет отдельные CLI-аргументы; задавайте defaults, поскольку `run all` вызывает метод без аргументов.

Заранее созданный Temporal воркер сохраняет конфигурацию. `add_async_runtime()` не применяет defaults endpoint/namespace/Pydantic приложения, не меняет CRON ID и не регистрирует команды CRON. Настройте воркер явно до инициализации или используйте `add_worker()`.

Для прямого подкласса `BaseBoostWorker` реализуйте `run()` и async `shutdown()`. Управляемая остановка требует потокобезопасного `request_stop()` с очисткой в своём цикле. Для asyncio этот жизненный цикл предоставляет `AsyncBoostWorker`.

Самостоятельный `examples/example_custom_worker.py` не требует внешних сервисов:

```bash
uv run python examples/example_custom_worker.py run all
# Ctrl+C requests managed shutdown.
```

Он также проверяется через `uv run mypy examples/example_custom_worker.py`.

### Завершение собственного воркера {#custom-worker-shutdown}

```python
import asyncio

from temporal_boost import AsyncBoostWorker, BoostApp


class ServiceWorker(AsyncBoostWorker):
    def __init__(self) -> None:
        super().__init__()
        self.name = "service"
        self.finished: asyncio.Event | None = None

    async def run_async(self) -> None:
        # Create loop-bound resources here.
        self.finished = asyncio.Event()
        await self.finished.wait()

    async def shutdown(self) -> None:
        # Close resources here, on the loop that created them.
        # This must also be safe during partial startup.
        if self.finished is not None:
            self.finished.set()


app = BoostApp("lifecycle-example", shutdown_timeout=30.0)
app.add_async_runtime("service", ServiceWorker())

if __name__ == "__main__":
    app.run()
```

Запуск: `python main.py run all`. Сохраните реализации `run()` и потокобезопасного `request_stop()` из `AsyncBoostWorker`, переопределите `run_async()` и `shutdown()`. Очистка выполняется один раз за запуск, включая обычный возврат `run_async()`, должна учитывать частичный startup и разблокировать `run_async()`. Запрос до создания цикла запоминается. Последовательные запуски создают новые циклы; одновременные отклоняются.

В `run all` исключение или возврат до общей остановки останавливают соседей и считаются ошибкой. Конечный воркер должен вызвать `app.stop()` до возврата или запускаться отдельно. Первая ошибка остаётся основной при сбое или таймауте очистки. Ошибка `run_async()` сохраняется и при собственной ошибке очистки; ошибка очистки при отмене также передаётся вызывающему коду.

Прямой async `shutdown()` предназначен для своего цикла. Для другой модели потоков/циклов реализуйте `BaseBoostWorker.request_stop()` её потокобезопасными средствами. Бюджеты и ограничения описаны в [руководстве по остановке](running_application.md#graceful-shutdown).

## Обработка ошибок {#error-handling-patterns}

### Повтор activity с собственной логикой {#activity-retry-with-custom-logic}

```python
from temporalio import activity
from temporalio.common import RetryPolicy
from datetime import timedelta

@activity.defn(
    name="retryable_activity",
    start_to_close_timeout=timedelta(minutes=5),
    retry_policy=RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=60),
        maximum_attempts=3,
    ),
)
async def retryable_activity(data: str) -> str:
    try:
        # Your logic here
        return process_data(data)
    except TransientError:
        # Will be retried automatically
        raise
    except PermanentError:
        # Will not be retried
        raise
```

### Ошибки workflow {#workflow-error-handling}

```python
from temporalio import workflow
from temporalio.exceptions import ActivityError, ApplicationError

@workflow.defn(sandboxed=False, name="ErrorHandlingWorkflow")
class ErrorHandlingWorkflow:
    @workflow.run
    async def run(self, data: str) -> dict:
        try:
            result = await workflow.execute_activity(
                risky_activity,
                data,
                task_queue="error_queue",
                start_to_close_timeout=timedelta(minutes=5),
            )
            return {"status": "success", "result": result}
        except ActivityError as e:
            # Activity failed
            workflow.logger.error(f"Activity failed: {e}")
            return {"status": "failed", "error": str(e)}
        except ApplicationError as e:
            # Application-specific error
            workflow.logger.error(f"Application error: {e}")
            raise
```

## Оптимизация производительности {#performance-optimization}

### Настройка параллелизма {#tuning-concurrency}

```python
# High-throughput worker
high_throughput_worker = app.add_worker(
    "high_throughput",
    "high_throughput_queue",
    activities=[...],
    max_concurrent_activities=1000,
    max_concurrent_workflow_tasks=500,
    max_concurrent_activity_task_polls=50,
    max_concurrent_workflow_task_polls=50,
)

# Low-latency worker
low_latency_worker = app.add_worker(
    "low_latency",
    "low_latency_queue",
    activities=[...],
    max_concurrent_activities=100,
    max_concurrent_workflow_tasks=50,
    nonsticky_to_sticky_poll_ratio=0.1,  # Prefer sticky workflows
)
```

### Sticky workflow {#sticky-workflows}

Сохранение состояния workflow в памяти повышает производительность:

```python
# High sticky ratio for better performance
worker.configure_temporal_runtime(
    # Worker polls are configured at worker level
)

# In worker configuration
worker = app.add_worker(
    "sticky_worker",
    "sticky_queue",
    workflows=[MyWorkflow],
    nonsticky_to_sticky_poll_ratio=0.1,  # 10% non-sticky, 90% sticky
)
```

### Пулы подключений {#connection-pooling}

SDK-клиенты управляют подключениями самостоятельно. Воркеры Temporal-boost создают отдельные клиенты и runtime; отдельный сборщик или runtime не разделяется с ними автоматически. Для самостоятельных сборщиков вызовите `client_builder.set_runtime(runtime)` перед `await build()`. Для нескольких воркеров следуйте [схеме endpoints метрик](#metrics-across-workers-and-processes).

### Кэширование результатов activity {#activity-result-caching}

Для дорогих операций, результаты которых можно кэшировать:

```python
from functools import lru_cache
from temporalio import activity

# Cache at activity level (use with caution)
@activity.defn(name="cached_activity")
async def cached_activity(key: str) -> str:
    return expensive_operation(key)

# Or implement caching in workflow
@workflow.defn(sandboxed=False, name="CachedWorkflow")
class CachedWorkflow:
    def __init__(self):
        self._cache: dict[str, str] = {}

    @workflow.run
    async def run(self, key: str) -> str:
        if key in self._cache:
            return self._cache[key]
        
        result = await workflow.execute_activity(
            cached_activity,
            key,
            task_queue="cache_queue",
            start_to_close_timeout=timedelta(minutes=5),
        )
        self._cache[key] = result
        return result
```

## Сложные сценарии {#advanced-patterns}

### Версионирование workflow {#workflow-versioning}

```python
@workflow.defn(sandboxed=False, name="VersionedWorkflow")
class VersionedWorkflow:
    @workflow.run
    async def run(self, data: dict) -> dict:
        version = data.get("version", 1)
        
        if version == 1:
            return await self._run_v1(data)
        elif version == 2:
            return await self._run_v2(data)
        else:
            raise ValueError(f"Unsupported version: {version}")
    
    async def _run_v1(self, data: dict) -> dict:
        # V1 logic
        pass
    
    async def _run_v2(self, data: dict) -> dict:
        # V2 logic
        pass
```

### Собственный преобразователь данных {#custom-data-converter}

```python
from temporalio.converter import DataConverter, PayloadCodec
from temporal_boost.temporal.client import TemporalClientBuilder

class CustomPayloadCodec(PayloadCodec):
    def encode(self, payloads: list[Payload]) -> list[Payload]:
        # Custom encoding logic
        return payloads
    
    def decode(self, payloads: list[Payload]) -> list[Payload]:
        # Custom decoding logic
        return payloads

custom_converter = DataConverter(
    payload_converter=DefaultPayloadConverter(),
    payload_codec=CustomPayloadCodec(),
)

client_builder = TemporalClientBuilder()
client_builder.set_kwargs(data_converter=custom_converter)
```

Дополнительные сценарии приведены в разделе [примеры](examples.md).
