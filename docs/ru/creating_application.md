# Создание приложения {#creating-application}

Руководство по созданию приложений Temporal-boost: от начальной настройки до сложных сценариев.

## Содержание {#table-of-contents}

- [Структура приложения](#application-structure)
- [Инициализация BoostApp](#boostapp-initialization)
- [Определение activity](#defining-activities)
- [Определение workflow](#defining-workflows)
- [Добавление воркеров](#adding-workers)
- [Воркеры CRON](#cron-workers)
- [Воркеры ASGI](#asgi-workers)
- [Воркеры FastStream](#faststream-workers)
- [Рекомендации](#best-practices)

## Структура приложения {#application-structure}

Типичная структура приложения Temporal-boost:

```
my_app/
├── main.py              # Application entry point
├── activities.py        # Activity definitions
├── workflows.py         # Workflow definitions
├── config.py            # Configuration (optional)
└── requirements.txt     # Dependencies
```

## Инициализация BoostApp {#boostapp-initialization}

`BoostApp` — центральный объект приложения. Создайте его в точке входа:

```python
from temporal_boost import BoostApp

app = BoostApp(
    name="my-service",              # Application name (optional)
    temporal_endpoint=None,          # Override TEMPORAL_TARGET_HOST (optional)
    temporal_namespace=None,         # Override TEMPORAL_NAMESPACE (optional)
    debug_mode=False,                # Enable debug mode (optional)
    use_pydantic=None,               # Override Pydantic converter (optional)
    logger_config=None,              # Custom logging config (optional)
)
```

### Приоритет конфигурации {#configuration-priority}

Endpoint и namespace выбираются независимо, от высшего приоритета к низшему:

1. **Явная настройка воркера** через `worker.configure_temporal_client(target_host=..., namespace=...)`.
2. **Параметры конструктора BoostApp**.
3. **Окружение, прочитанное при импорте**.
4. **Встроенные значения**: `localhost:7233` и `default`.

Например, при `TEMPORAL_TARGET_HOST=temporal.prod:7233` вызов `BoostApp(temporal_endpoint="temporal.dev:7233")` выбирает `temporal.dev:7233`. До инициализации клиента явная настройка воркера может заменить адрес. У существующего сборщика пропущенные поля и `None` сохраняют настройки; побеждает последнее явно переданное значение каждого поля.

Окружение читается при первом импорте `temporal_boost`. Пакет не загружает `.env` автоматически; изменение `os.environ` после импорта не обновляет значения по умолчанию. Загрузите файл окружения до импорта или подготовьте окружение перед запуском установленного CLI. Для булевых и числовых параметров, пустых строк и runtime действуют отдельные правила: см. [приоритет конфигурации](configuration.md#configuration-priority) и [загрузку окружения](configuration.md#environment-loading).

## Определение activity {#defining-activities}

Activity — функция, выполняющая работу. Она может выполнять ввод-вывод и не обязана быть детерминированной.

### Простая activity {#basic-activity}

```python
from temporalio import activity

@activity.defn(name="process_payment")
async def process_payment(amount: float, currency: str) -> dict:
    """Process a payment transaction."""
    # Your business logic here
    return {"status": "success", "amount": amount, "currency": currency}
```

### Activity с моделями Pydantic {#activity-with-pydantic-models}

Модели Pydantic обеспечивают типизацию и проверку данных:

```python
from pydantic import BaseModel
from temporalio import activity

class PaymentRequest(BaseModel):
    amount: float
    currency: str
    customer_id: str

class PaymentResponse(BaseModel):
    transaction_id: str
    status: str
    amount: float

@activity.defn(name="process_payment")
async def process_payment(request: PaymentRequest) -> PaymentResponse:
    """Process a payment with type-safe models."""
    # Process payment...
    return PaymentResponse(
        transaction_id="tx_123",
        status="completed",
        amount=request.amount,
    )
```

### Activity с повторами {#activity-with-retry-options}

Для activity можно настроить политику повторов:

```python
from temporalio import activity
from temporalio.common import RetryPolicy

@activity.defn(
    name="unreliable_api_call",
    start_to_close_timeout=timedelta(seconds=30),
    retry_policy=RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=60),
        maximum_attempts=5,
    ),
)
async def unreliable_api_call(url: str) -> dict:
    """Activity with custom retry policy."""
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

### Рекомендации для activity {#activity-best-practices}

- По возможности обеспечивайте идемпотентность.
- Настраивайте таймауты, включая `start_to_close_timeout`.
- Обрабатывайте ошибки.
- Используйте Pydantic для сложных структур данных.
- Записывайте важные операции в лог.
- Исходное руководство рекомендует избегать случайных чисел и текущего времени в activity.
- Избегайте операций, которые нельзя безопасно повторить.

## Определение workflow {#defining-workflows}

Workflow организует вызовы activity и описывает бизнес-логику. Его выполнение должно быть детерминированным.

### Простой workflow {#basic-workflow}

```python
from datetime import timedelta
from temporalio import workflow

@workflow.defn(sandboxed=False, name="OrderProcessingWorkflow")
class OrderProcessingWorkflow:
    @workflow.run
    async def run(self, order_id: str) -> dict:
        """Process an order through multiple steps."""
        # Step 1: Validate order
        validation_result = await workflow.execute_activity(
            validate_order,
            order_id,
            task_queue="order_queue",
            start_to_close_timeout=timedelta(minutes=5),
        )
        
        if not validation_result["valid"]:
            return {"status": "failed", "reason": "validation_failed"}
        
        # Step 2: Process payment
        payment_result = await workflow.execute_activity(
            process_payment,
            validation_result["amount"],
            task_queue="payment_queue",
            start_to_close_timeout=timedelta(minutes=10),
        )
        
        # Step 3: Fulfill order
        fulfillment_result = await workflow.execute_activity(
            fulfill_order,
            order_id,
            task_queue="fulfillment_queue",
            start_to_close_timeout=timedelta(minutes=30),
        )
        
        return {
            "status": "completed",
            "order_id": order_id,
            "payment": payment_result,
            "fulfillment": fulfillment_result,
        }
```

### Workflow с сигналами {#workflow-with-signals}

Сигналы позволяют внешним системам передавать данные работающему workflow:

```python
from temporalio import workflow

@workflow.defn(sandboxed=False, name="ApprovalWorkflow")
class ApprovalWorkflow:
    def __init__(self):
        self.approved = False
        self.rejected = False

    @workflow.run
    async def run(self, request_id: str) -> dict:
        """Wait for approval signal."""
        await workflow.wait_condition(lambda: self.approved or self.rejected)
        
        if self.approved:
            return {"status": "approved", "request_id": request_id}
        return {"status": "rejected", "request_id": request_id}

    @workflow.signal(name="approve")
    def approve(self) -> None:
        """Signal handler for approval."""
        self.approved = True

    @workflow.signal(name="reject")
    def reject(self) -> None:
        """Signal handler for rejection."""
        self.rejected = True
```

### Workflow с запросами {#workflow-with-queries}

Запросы позволяют читать состояние workflow без изменения хода выполнения:

```python
from temporalio import workflow

@workflow.defn(sandboxed=False, name="OrderStatusWorkflow")
class OrderStatusWorkflow:
    def __init__(self):
        self.status = "pending"
        self.progress = 0

    @workflow.run
    async def run(self, order_id: str) -> dict:
        """Process order and update status."""
        self.status = "processing"
        await workflow.execute_activity(
            process_order,
            order_id,
            task_queue="order_queue",
            start_to_close_timeout=timedelta(minutes=30),
        )
        self.status = "completed"
        self.progress = 100
        return {"status": self.status, "order_id": order_id}

    @workflow.query(name="status")
    def get_status(self) -> dict:
        """Query workflow status."""
        return {"status": self.status, "progress": self.progress}
```

### Рекомендации для workflow {#workflow-best-practices}

- Сохраняйте детерминированность: избегайте обычных случайных чисел, времени и ввода-вывода.
- Задавайте подходящие таймауты activity.
- Обрабатывайте ошибки через try/except.
- Принимайте внешние данные через сигналы.
- Используйте запросы для чтения состояния.
- В примерах этого руководства используется `sandboxed=False` для уменьшения накладных расходов.
- Вместо `datetime.now()` вызывайте `workflow.now()`.
- Не выполняйте ввод-вывод непосредственно в workflow.

## Добавление воркеров {#adding-workers}

Воркеры связывают activity и workflow с очередями задач Temporal.

### Базовая регистрация воркера {#basic-worker-registration}

```python
app.add_worker(
    worker_name="payment_worker",
    task_queue="payment_queue",
    activities=[process_payment, refund_payment],
    workflows=[PaymentWorkflow],
)
```

### Параметры воркера {#worker-parameters}

Метод `add_worker` принимает следующие параметры:

```python
app.add_worker(
    worker_name: str,                    # Unique worker name
    task_queue: str,                     # Temporal task queue name
    activities: list[Callable] | None,   # List of activity functions
    workflows: list[type] | None,        # List of workflow classes
    interceptors: list[Interceptor] | None,  # Optional interceptors
    cron_schedule: str | None,           # CRON schedule (for CRON workers)
    cron_runner: Callable | None,        # CRON runner method
    cron_workflow_id: str | None,        # Stable workflow ID (optional override)
    **worker_kwargs: Any,                # Additional worker options
) -> TemporalBoostWorker
```

### Пример с несколькими воркерами {#multiple-workers-example}

```python
# Activity-only worker
app.add_worker(
    "payment_activities",
    "payment_queue",
    activities=[process_payment, refund_payment, validate_payment],
)

# Workflow-only worker
app.add_worker(
    "order_workflows",
    "order_queue",
    workflows=[OrderWorkflow, RefundWorkflow],
)

# Combined worker
app.add_worker(
    "combined_worker",
    "main_queue",
    activities=[process_order, send_notification],
    workflows=[OrderWorkflow],
)
```

### Настройка воркера {#worker-configuration}

После добавления воркер можно настроить:

```python
worker = app.add_worker(
    "custom_worker",
    "custom_queue",
    activities=[my_activity],
)

# Configure Temporal client
worker.configure_temporal_client(
    target_host="custom-host:7233",
    namespace="custom_namespace",
    use_pydantic_data_converter=True,
)

# Configure runtime with Prometheus metrics
worker.configure_temporal_runtime(
    prometheus_bind_address="0.0.0.0:9090",
)
```

## Воркеры CRON {#cron-workers}

Воркеры CRON настраивают повторяющиеся workflow на сервере. `add_worker()` сохраняет конфигурацию и регистрирует локальные команды CLI. `cron <name>` создаёт или повторно использует серверную цепочку и обрабатывает её очередь; `run <name>` и `run all` только обрабатывают очереди.

### Создание воркера CRON {#creating-a-cron-worker}

```python
@workflow.defn(sandboxed=False, name="DailyReportWorkflow")
class DailyReportWorkflow:
    @workflow.run
    async def run(self) -> None:
        """Generate daily report."""
        await workflow.execute_activity(
            generate_report,
            task_queue="report_queue",
            start_to_close_timeout=timedelta(minutes=30),
        )

app.add_worker(
    "daily_report_cron",
    "report_queue",
    workflows=[DailyReportWorkflow],
    cron_schedule="0 0 * * *",  # Run at midnight every day
    cron_runner=DailyReportWorkflow.run,
    cron_workflow_id="reports/daily-v1",  # Same ID on every replica and restart
)
```

Передайте одновременно `cron_schedule` и `cron_runner` или пропустите оба для обычного обработчика. Неполная пара и пустое расписание вызывают `ValueError` до подключения. Такая же проверка действует при прямом создании `TemporalBoostWorker(...)`. Синтаксис CRON проверяет SDK/сервер при регистрации. При миграции дополните неполную пару или удалите параметры CRON. Один `cron_workflow_id` не включает режим CRON.

### Идентификатор workflow CRON {#cron-workflow-identity}

`cron_workflow_id` определяет одну логическую задачу CRON внутри namespace. Параметр поддерживается и в конструкторе `TemporalBoostWorker`. По умолчанию ID имеет вид `temporal-boost/cron/<escaped task_queue>/<escaped worker_name>`; компоненты кодируются как URL, включая `/` и `%`. Очередь `report_queue` и воркер `daily_report_cron` дают `temporal-boost/cron/report_queue/daily_report_cron`. Явный ID должен содержать непробельный символ и сохраняется без других изменений.

Для стандартного ID сохраняйте имена воркера и очереди. Явный ID позволяет сохранить идентичность при переименовании или смене очереди. Независимым задачам с одинаковыми именами нужны разные ID; репликам одной задачи нужны одинаковые ID и namespace.

Для работающего workflow используется `WorkflowIDConflictPolicy.USE_EXISTING`, для закрытого — `WorkflowIDReusePolicy.REJECT_DUPLICATE`. Конкурентные процессы и перезапуски атомарно используют активную цепочку. Завершённый, упавший, отменённый или принудительно остановленный ID вызывает `WorkflowAlreadyStartedError`; новый ID не генерируется. Защита закрытого ID действует, пока Temporal хранит историю. Работающий workflow с таким ID используется даже при создании вне приложения: резервируйте ID под конкретные задачи.

Повторное использование не меняет тип workflow, очередь и расписание. Изменение конфигурации требует явной миграции. В логах регистрации есть namespace, ID workflow и ID запуска от сервера; сообщение «registered or already running» означает создание или повторное использование.

Механизм использует SDK `cron_schedule`, а не Temporal Schedules. Локальная остановка сохраняет серверную цепочку. Перед обновлением со случайных UUID выполните [процедуру миграции](running_application.md#migrating-existing-uuid-cron-workflows).

### Формат расписания CRON {#cron-schedule-format}

Стандартный формат: `minute hour day month weekday`.

- `"0 * * * *"` — каждый час в нулевую минуту.
- `"0 0 * * *"` — ежедневно в полночь.
- `"0 9 * * 1"` — каждый понедельник в 9 утра.
- `"*/5 * * * *"` — каждые пять минут.
- `"0 0 1 * *"` — первого числа каждого месяца.

### Запуск воркеров CRON {#running-cron-workers}

```bash
# Register/reuse the server-side chain and consume the queue
python3 main.py cron daily_report_cron

# Consume the queue for an already registered chain
python3 main.py run daily_report_cron

# Run all consumers; this does not create schedules
python3 main.py run all
```

Команда `cron <name>` доступна только при обоих параметрах CRON. Прямой `worker.cron()` без них вызывает `RuntimeError` до создания цикла и подключения. Регистрация выполняется один раз при старте процесса; Temporal продолжает цепочку на сервере. Процесс обрабатывает очередь до остановки, которая не удаляет серверную цепочку.

## Воркеры ASGI {#asgi-workers}

Воркеры ASGI запускают FastAPI, Starlette и другие приложения ASGI вместе с воркерами Temporal.

### Базовый воркер ASGI {#basic-asgi-worker}

```python
from fastapi import FastAPI
from temporal_boost import BoostApp, ASGIWorkerType

app = BoostApp("my-service")

# Create your FastAPI app
fastapi_app = FastAPI(title="My API")

@fastapi_app.get("/health")
async def health():
    return {"status": "healthy"}

# Add ASGI worker
app.add_asgi_worker(
    "api_worker",
    fastapi_app,
    host="0.0.0.0",
    port=8000,
    asgi_worker_type=ASGIWorkerType.auto,  # Priority: Uvicorn, Granian, Hypercorn
)
```

### Выбор сервера ASGI {#specifying-asgi-server}

```python
# Use Uvicorn
app.add_asgi_worker(
    "api_worker",
    fastapi_app,
    "0.0.0.0",
    8000,
    asgi_worker_type=ASGIWorkerType.uvicorn,
)

# Use Hypercorn
app.add_asgi_worker(
    "api_worker",
    fastapi_app,
    "0.0.0.0",
    8000,
    asgi_worker_type=ASGIWorkerType.hypercorn,
)

# Use Granian
app.add_asgi_worker(
    "api_worker",
    fastapi_app,
    "0.0.0.0",
    8000,
    asgi_worker_type=ASGIWorkerType.granian,
)
```

### Воркер ASGI из строкового пути {#asgi-worker-from-string-path}

Приложение можно загрузить по строковому пути:

```python
app.add_asgi_worker(
    "api_worker",
    "myapp.api:app",  # Module path to ASGI app
    "0.0.0.0",
    8000,
)
```

### Управляемое завершение ASGI {#managed-asgi-shutdown}

Uvicorn, Hypercorn и Granian поддерживают `BoostApp.stop()` в `run all`. Обслуживание запросов и очистка выполняются в одном цикле событий на запуск. Координатор запрашивает остановку из другого потока и ждёт до `BoostApp(shutdown_timeout=...)`; очистка сервера не переносится в другой цикл. В главном потоке обрабатываются SIGINT/SIGTERM с восстановлением прежних обработчиков. В рабочих потоках сигналы остаются у координатора или супервизора CLI.

Жизненный цикл проверен HTTP-запросами и счётчиками ASGI lifespan на версиях из lockfile:

| Сервер | API запуска | Остановка | Приложение |
| --- | --- | --- | --- |
| Uvicorn 0.35.0 | `Server.serve()` | `should_exit` после завершения запуска | Объект или `module:attribute`; поддерживается `factory=True` |
| Hypercorn 0.17.3 | `hypercorn.asyncio.serve()` | Завершение `shutdown_trigger` | Объект или `module:attribute`; передавайте созданное приложение |
| Granian 2.4.2 | `granian.server.embed.Server.serve()` | Публичный `stop()` и ожидание задачи сервера | Объект или `module:attribute`; поддерживается `factory=True` |

Обычную очистку выполняет API сервера. Адаптер не вызывает её повторно после завершения. Uvicorn очищается и при ошибке главного цикла. Явные сообщения об ошибке запуска или завершения lifespan приводят к исключениям, в том числе у Granian, который иначе только записывает некоторые ошибки. Ошибки импорта и запуска доходят до вызывающего кода.

Встроенные адаптеры предоставляют потокобезопасный повторяемый `worker.request_stop()`. Асинхронный `worker.shutdown()` безопасен до и после запуска; в своём цикле он запрашивает остановку и ждёт очистки. Из другого цикла или ASGI-обработчика используйте `request_stop()`. Отмена ожидающего не отменяет очистку. Остановка до первого запуска не создаёт серверные ресурсы; завершённый адаптер может запускаться снова в новом цикле. Начатому startup-хуку дают закончить; зависший хук может превысить бюджет координатора.

Адаптер запускает один сервер в своём asyncio-цикле. Используйте `workers=1` и отключите перезагрузчики (`reload=False`, для Hypercorn — `use_reloader=False`). Другие количества процессов и перезагрузчики отклоняются. Для Uvicorn и Granian допустимы `asyncio`/`auto`; для Hypercorn нужны `worker_class="asyncio"` и `debug=False`. Циклом управляет адаптер. Масштабирование HTTP описано в разделе [ASGI и внешние процессы](running_application.md#asgi-and-external-processes).

Миграция: Granian использует экспериментальный встроенный асинхронный сервер; параметры должны принадлежать его конструктору. Параметры менеджера процессов, например `workers_lifetime`, недоступны. Hypercorn проверяет имена настроек и отклоняет опечатки. Он не принимает `factory`: вызовите фабрику сами. Uvicorn и Granian отклоняют нестандартный выбор цикла вместо изменения глобальной политики.

### Воркер ASGI с интеграцией Temporal {#asgi-worker-with-temporal-integration}

Свяжите HTTP-обработчики с workflow:

```python
from fastapi import FastAPI
from temporalio.client import Client

fastapi_app = FastAPI()

@fastapi_app.post("/orders")
async def create_order(order_data: dict):
    """Create an order via Temporal workflow."""
    client = await Client.connect("localhost:7233")
    workflow_id = await client.start_workflow(
        "OrderWorkflow",
        order_data,
        id=f"order-{order_data['id']}",
        task_queue="order_queue",
    )
    return {"workflow_id": workflow_id}
```

## Воркеры FastStream {#faststream-workers}

FastStream связывает событийную архитектуру с Temporal и поддерживает асинхронных потребителей и производителей сообщений для Redis, RabbitMQ, Kafka и других брокеров.

### Базовый воркер FastStream {#basic-faststream-worker}

```python
from faststream import FastStream
from faststream.redis import RedisBroker
from temporal_boost import BoostApp

# Initialize FastStream broker and app
broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)

@broker.subscriber("tasks")
async def process_task(message: dict):
    """Process task from message queue."""
    logger.info(f"Processing task: {message['task_id']}")

app = BoostApp("event-driven-service")
app.add_faststream_worker("message_processor", faststream_app)
```

### FastStream с моделями Pydantic {#faststream-with-pydantic-models}

Типизированная обработка сообщений:

```python
from pydantic import BaseModel
from faststream import FastStream
from faststream.redis import RedisBroker
from temporal_boost import BoostApp

class OrderMessage(BaseModel):
    order_id: str
    customer_id: str
    items: list[dict]
    total: float

broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)

@broker.subscriber("orders")
async def handle_order(message: OrderMessage):
    """Handle order messages."""
    logger.info(f"Received order: {message.order_id}")

app = BoostApp("order-service")
app.add_faststream_worker("order_processor", faststream_app)
```

### FastStream с workflow Temporal {#faststream-with-temporal-workflows}

Свяжите потребителей сообщений с workflow:

```python
from faststream import FastStream
from faststream.redis import RedisBroker
from temporalio.client import Client
from temporalio import activity, workflow
from temporal_boost import BoostApp
from datetime import timedelta

app = BoostApp("faststream-temporal")

# Temporal workflow
@workflow.defn(sandboxed=False, name="OrderWorkflow")
class OrderWorkflow:
    @workflow.run
    async def run(self, order_data: dict) -> dict:
        # Process order...
        return {"status": "completed"}

# FastStream app
broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)

@broker.subscriber("orders")
async def handle_order(message: OrderMessage):
    """Handle order and start Temporal workflow."""
    client = await Client.connect("localhost:7233")
    
    workflow_id = await client.start_workflow(
        "OrderWorkflow",
        message.dict(),
        id=f"order-{message.order_id}",
        task_queue="order_queue",
    )
    
    logger.info(f"Started workflow {workflow_id}")

# Register both workers
app.add_worker("order_worker", "order_queue", workflows=[OrderWorkflow])
app.add_faststream_worker("message_processor", faststream_app)
```

### Несколько очередей сообщений {#multiple-message-queues}

Обработка нескольких очередей:

```python
broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)

@broker.subscriber("orders")
async def handle_orders(message: OrderMessage):
    """Handle order messages."""
    # Process orders...

@broker.subscriber("notifications")
async def handle_notifications(message: NotificationMessage):
    """Handle notification messages."""
    # Process notifications...

app.add_faststream_worker("message_processor", faststream_app)
```

### Разные брокеры FastStream {#faststream-with-different-brokers}

Примеры поддерживаемых брокеров:

**Redis:**

```python
from faststream.redis import RedisBroker
broker = RedisBroker("redis://localhost:6379")
```

**RabbitMQ:**

```python
from faststream.rabbit import RabbitBroker
broker = RabbitBroker("amqp://guest:guest@localhost:5672/")
```

**Kafka:**

```python
from faststream.kafka import KafkaBroker
broker = KafkaBroker("localhost:9092")
```

### Настройка воркера FastStream {#faststream-worker-configuration}

Передайте дополнительные параметры:

```python
app.add_faststream_worker(
    "message_processor",
    faststream_app,
    log_level=logging.DEBUG,  # Custom log level
    # Additional FastStream options can be passed here
)
```

### Рекомендации по интеграции FastStream {#best-practices-for-faststream-integration}

1. **Модели Pydantic**: описывайте и проверяйте схемы сообщений.
2. **Ошибки**: обрабатывайте сбои потребителей сообщений.
3. **Идемпотентность**: обеспечивайте безопасное повторение обработки.
4. **Оркестрация**: используйте workflow Temporal для сложных процессов.
5. **Фильтры**: маршрутизируйте сообщения средствами FastStream.
6. **Очереди ошибок**: отправляйте неудачные сообщения в dead-letter queue.
7. **Мониторинг**: следите за скоростью обработки и ошибками.

### Пример производителя FastStream {#faststream-producer-example}

Публикация сообщений в очереди:

```python
from faststream import FastStream
from faststream.redis import RedisBroker

broker = RedisBroker("redis://localhost:6379")
app = FastStream(broker)

async def publish_order(order_data: dict):
    """Publish order message."""
    await broker.publish(order_data, "orders")

# Use in your application
asyncio.run(publish_order({"order_id": "123", "total": 99.99}))
```

## Рекомендации {#best-practices}

### Структура приложения {#application-structure_1}

1. Разделяйте activity, workflow и конфигурацию по файлам.
2. Организуйте код в логические модули.
3. Используйте окружение для конфигурации.
4. Добавляйте аннотации типов для поддержки IDE.

### Организация воркеров {#worker-organization}

1. Выделяйте воркеры для каждой очереди задач.
2. Объединяйте связанные activity и workflow.
3. Разделяйте бизнес-домены между воркерами.
4. Настраивайте ограничения параллелизма.

### Обработка ошибок {#error-handling}

1. Задавайте политики повторов activity.
2. Настраивайте таймауты workflow.
3. Обрабатывайте ошибки внутри workflow.
4. Записывайте ошибки вместе с контекстом.

### Производительность {#performance}

1. Настройте `TEMPORAL_MAX_CONCURRENT_ACTIVITIES`.
2. Настройте `TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS`.
3. Разделяйте разные нагрузки по очередям.
4. Включите метрики Prometheus.

### Безопасность {#security}

1. Используйте TLS в production.
2. Используйте API-ключи для Temporal Cloud и защищённых кластеров.
3. Храните секреты в окружении или менеджере секретов.
4. Проверяйте входные данные activity и workflow.
