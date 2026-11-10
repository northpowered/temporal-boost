# Интеграция с FastStream {#faststream-integration}

FastStream — фреймворк асинхронных потребителей и производителей сообщений. Интеграция Temporal-boost позволяет связать событийную архитектуру с workflow Temporal.

## Обзор {#overview}

Интеграция позволяет:

- Получать сообщения Redis, RabbitMQ, Kafka и других брокеров.
- Запускать workflow Temporal по событиям.
- Асинхронно обрабатывать события с надёжным выполнением.
- Объединять событийную архитектуру и оркестрацию workflow.

## Установка {#installation}

Установите Temporal-boost с поддержкой FastStream:

```bash
pip install "temporal-boost[faststream]"
```

Будут установлены FastStream и зависимости, включая `anyio`.

## Быстрый старт {#quick-start}

### Базовый пример {#basic-example}

```python
from faststream import FastStream
from faststream.redis import RedisBroker
from pydantic import BaseModel
from temporal_boost import BoostApp

# Message model
class TaskMessage(BaseModel):
    task_id: str
    description: str
    priority: int

# Initialize FastStream
broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)

@broker.subscriber("tasks")
async def process_task(message: TaskMessage):
    """Process task messages."""
    logger.info(f"Processing task: {message.task_id}")

# Initialize Temporal-boost
app = BoostApp("faststream-example")

# Register FastStream worker
app.add_faststream_worker("message_processor", faststream_app)

if __name__ == "__main__":
    app.run()
```

## Схемы интеграции {#integration-patterns}

### Схема 1: очередь сообщений → workflow Temporal {#pattern-1-message-queue-temporal-workflow}

Запускайте workflow по событиям очереди:

```python
from faststream import FastStream
from faststream.redis import RedisBroker
from temporalio.client import Client
from temporal_boost import BoostApp

broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)

@broker.subscriber("orders")
async def handle_order(message: OrderMessage):
    """Handle order message and start workflow."""
    client = await Client.connect("localhost:7233")
    
    await client.start_workflow(
        "OrderWorkflow",
        message.dict(),
        id=f"order-{message.order_id}",
        task_queue="order_queue",
    )

app = BoostApp("order-service")
app.add_worker("order_worker", "order_queue", workflows=[OrderWorkflow])
app.add_faststream_worker("message_processor", faststream_app)
```

### Схема 2: несколько очередей {#pattern-2-multiple-message-queues}

Обрабатывайте разные очереди отдельными обработчиками:

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

@broker.subscriber("emails")
async def handle_emails(message: EmailMessage):
    """Handle email messages."""
    # Process emails...

app.add_faststream_worker("message_processor", faststream_app)
```

### Схема 3: условная обработка {#pattern-3-conditional-processing}

Выбирайте маршрут по содержимому сообщения:

```python
@broker.subscriber("tasks")
async def handle_task(message: TaskMessage):
    """Handle tasks with conditional routing."""
    if message.priority > 5:
        # High priority: execute immediately
        await process_high_priority_task(message)
    else:
        # Normal priority: start workflow
        client = await Client.connect("localhost:7233")
        await client.start_workflow(
            "TaskWorkflow",
            message.dict(),
            task_queue="task_queue",
        )
```

## Поддерживаемые брокеры {#supported-brokers}

FastStream поддерживает несколько брокеров сообщений:

### Redis {#redis}

```python
from faststream.redis import RedisBroker

broker = RedisBroker("redis://localhost:6379")
faststream_app = FastStream(broker)
```

### RabbitMQ {#rabbitmq}

```python
from faststream.rabbit import RabbitBroker

broker = RabbitBroker("amqp://guest:guest@localhost:5672/")
faststream_app = FastStream(broker)
```

### Kafka {#kafka}

```python
from faststream.kafka import KafkaBroker

broker = KafkaBroker("localhost:9092")
faststream_app = FastStream(broker)
```

## Конфигурация {#configuration}

### Настройки воркера {#worker-configuration}

Передайте дополнительные параметры:

```python
app.add_faststream_worker(
    "message_processor",
    faststream_app,
    log_level=logging.DEBUG,  # Custom log level
    region="west",  # Passed to startup hooks and the lifespan context
)
```

### Управляемое завершение {#managed-shutdown}

Воркеры FastStream поддерживают `app.stop()` при запуске через `run all`. Координатор запрашивает остановку и ждёт очистки до `BoostApp(shutdown_timeout=...)`. Можно сохранить результат `add_faststream_worker()` и вызвать его потокобезопасный `worker.request_stop()`, в том числе при запуске. Повторные запросы безопасны.

Адаптер вызывает публичные `start()` и `stop()` FastStream и контекст lifespan в одном своём цикле событий. Незавершённый startup отменяется и дожидается до shutdown-хуков и очистки брокера. Ошибки старта и очистки доходят до вызывающего кода; ошибка очистки не заменяет более раннюю ошибку запуска. Если shutdown-хук падает до закрытия брокера, адаптер дополнительно пытается вызвать публичный `stop()` брокера.

Async `worker.shutdown()` ждёт очистку в своём цикле и безопасен до/после запуска. Из другого потока, цикла и внутри lifecycle-хука используйте `worker.request_stop()`. Отмена одного ожидающего не отменяет очистку. Зависший брокер или хук может превысить бюджет координатора.

Жизненный цикл и передача параметров проверены на FastStream **0.5.48** из lockfile с брокером в памяти. Сигнатура `run(log_level, options)` этой версии принимает позиционный словарь. Адаптер управляет жизненным циклом напрямую: `FastStream.run()` устанавливает обработчики сигналов, недоступные в рабочем потоке `run all`. Параметры запуска по-прежнему передаются startup-хукам и lifespan. Код с `FastStream.exit()` или переопределённым `FastStream.run()` должен перенести остановку в `worker.request_stop()`, а инициализацию/очистку — в lifecycle-хуки. При отдельном запуске в главном потоке адаптер обрабатывает SIGINT/SIGTERM и восстанавливает обработчики после очистки.

### Настройки брокера сообщений {#message-broker-configuration}

Настройте подключение к брокеру:

```python
# Redis with authentication
broker = RedisBroker("redis://user:password@localhost:6379")

# Redis with custom settings
broker = RedisBroker(
    "redis://localhost:6379",
    max_connections=10,
    socket_keepalive=True,
)

# RabbitMQ with custom settings
broker = RabbitBroker(
    "amqp://guest:guest@localhost:5672/",
    max_connections=10,
    virtualhost="/",
)
```

## Обработка ошибок {#error-handling}

### Ошибки обработки сообщений {#message-processing-errors}

Обрабатывайте ошибки потребителя:

```python
@broker.subscriber("orders")
async def handle_order(message: OrderMessage):
    """Handle order with error handling."""
    try:
        client = await Client.connect("localhost:7233")
        await client.start_workflow(
            "OrderWorkflow",
            message.dict(),
            task_queue="order_queue",
        )
    except Exception as e:
        logger.error(f"Failed to process order {message.order_id}: {e}")
        # Optionally publish to dead-letter queue
        await broker.publish(message.dict(), "orders-dlq")
        raise
```

### Очереди ошибок {#dead-letter-queues}

Отправляйте неудачные сообщения в dead-letter queue:

```python
@broker.subscriber("orders")
async def handle_order(message: OrderMessage):
    """Handle order with DLQ support."""
    try:
        # Process message...
        pass
    except Exception:
        # Publish to dead-letter queue
        await broker.publish(message.dict(), "orders-dlq")
        raise
```

## Рекомендации {#best-practices}

1. Описывайте схемы сообщений моделями Pydantic.
2. По возможности делайте обработку идемпотентной.
3. Настраивайте обработку ошибок, повторы или DLQ.
4. Используйте workflow для сложной оркестрации.
5. Маршрутизируйте сообщения фильтрами FastStream.
6. Следите за скоростью обработки и ошибками.
7. Ограничивайте параллелизм в соответствии с ресурсами.

## Примеры {#examples}

В [каталоге примеров](https://github.com/northpowered/temporal-boost/tree/main/examples):

- `example_simple_faststream.py` — базовая интеграция.
- `example_faststream_temporal.py` — FastStream с workflow Temporal.
- `example_faststream_advanced.py` — расширенные сценарии и ошибки.
- `example_faststream_producer.py` — отправка сообщений.

## Дополнительные материалы {#additional-resources}

- [Документация FastStream](https://faststream.airt.ai/).
- [Примеры Temporal-boost](https://github.com/northpowered/temporal-boost/tree/main/examples).
- [Создание приложения](creating_application.md#faststream-workers).
