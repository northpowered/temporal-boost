# Начало работы {#getting-started}

Создавайте надёжные сервисы на Python с Temporal.

<div class="grid cards" markdown>

- **[Создать приложение](creating_application.md)**

    Регистрация activity, workflow и воркеров.

- **[Запустить сервис](running_application.md)**

    Разработка и развёртывание в production.

- **[Настроить воркеры](configuration.md)**

    Подключение, параллелизм и телеметрия.

- **[Подключить интеграции](faststream_integration.md)**

    Обработка сообщений с FastStream.

- **[Изучить API](api_reference.md)**

    Методы, параметры и жизненный цикл.

</div>

## О фреймворке {#about-the-framework}

**Temporal-boost** — лёгкий высокоуровневый фреймворк для быстрой разработки микросервисов на Python с Temporal. Он основан на официальном [Temporal Python SDK](https://github.com/temporalio/sdk-python) и предлагает декларативный API в стиле FastAPI.

Если вам знаком подход FastAPI и нужны надёжные масштабируемые workflow, этот фреймворк поможет организовать приложение.

### Почему Temporal-boost? {#why-temporal-boost}

- **API в стиле FastAPI**: организация воркеров похожа на организацию маршрутов FastAPI.
- **Меньше шаблонного кода**: сосредоточьтесь на бизнес-логике.
- **Эксплуатация**: встроенные логи, трассировка, метрики и согласованное завершение управляемых воркеров.
- **Гибкость**: activity, workflow, CRON и приложения ASGI.
- **Типизация**: аннотации типов и интеграция с Pydantic.

### Основные зависимости {#main-dependencies}

- [**Temporal SDK (Python)**](https://github.com/temporalio/sdk-python) — основные возможности Temporal.
- [**Pydantic**](https://github.com/pydantic/pydantic) — проверка и сериализация данных.
- [**Typer**](https://github.com/fastapi/typer) — интерфейс командной строки.
- **Python logging** — настройка структурированного логирования.
- **Серверы ASGI** — Hypercorn, Uvicorn и Granian для веб-приложений.

### Основные возможности {#main-features}

- Приложение в стиле FastAPI с подключаемыми воркерами.
- Централизованная настройка логов и трассировки.
- Декларативное расписание CRON для workflow.
- Интеграция с FastAPI, Starlette и другими приложениями ASGI.
- Интеграция с FastStream для событийной архитектуры.
- Настройка через переменные окружения.
- Метрики Prometheus.
- Корректное завершение воркеров, реализующих контракт управляемой остановки.
- CLI для запуска воркеров по отдельности и вместе.

## Установка {#installation}

### Базовая установка {#basic-installation}

Установите основной пакет:

```bash
pip install temporal-boost
```

Или используйте uv:

```bash
uv add temporal-boost
```

### Дополнительные зависимости {#optional-extras}

Установите нужные интеграции:

```bash
# FastStream integration for event-driven workers
pip install "temporal-boost[faststream]"

# ASGI server support (choose one or more)
pip install "temporal-boost[uvicorn]"      # Uvicorn ASGI server
pip install "temporal-boost[hypercorn]"    # Hypercorn ASGI server
pip install "temporal-boost[granian]"      # Granian ASGI server

# Install all extras
pip install "temporal-boost[faststream,uvicorn,hypercorn,granian]"
```

### Требования {#requirements}

- Python >= 3.10.
- Доступ к локальному или удалённому серверу Temporal.

## Быстрый старт {#quick-start}

### Первое приложение Temporal-boost {#your-first-temporal-boost-application}

Создайте файл `main.py`:

```python
import logging
from datetime import timedelta
from temporalio import activity, workflow
from temporal_boost import BoostApp

logging.basicConfig(level=logging.INFO)

# Create your BoostApp instance
app = BoostApp(name="my-first-app")

# Define an activity
@activity.defn(name="greet_activity")
async def greet_activity(name: str) -> str:
    return f"Hello, {name}!"

# Define a workflow
@workflow.defn(sandboxed=False, name="GreetingWorkflow")
class GreetingWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            greet_activity,
            name,
            task_queue="greeting_queue",
            start_to_close_timeout=timedelta(minutes=1),
        )

# Register workers
app.add_worker(
    "greeting_worker",
    "greeting_queue",
    activities=[greet_activity],
    workflows=[GreetingWorkflow],
)

if __name__ == "__main__":
    app.run()
```

### Конфигурация {#configuration}

Задайте переменные окружения или используйте значения по умолчанию:

```bash
export TEMPORAL_TARGET_HOST=localhost:7233
export TEMPORAL_NAMESPACE=default
```

Все параметры описаны в [руководстве по конфигурации](configuration.md).

### Запуск приложения {#running-your-application}

Запустите все воркеры:

```bash
python3 main.py run all
```

Или один воркер:

```bash
python3 main.py run greeting_worker
```

### Следующие шаги {#whats-next}

- [Создание приложения](creating_application.md) — структура и регистрация воркеров.
- [Запуск приложения](running_application.md) — развёртывание и эксплуатация.
- [Конфигурация](configuration.md) — полный справочник настроек.
- [Примеры](examples.md) — типовые решения.
- [Расширенное использование](advanced_usage.md) — настройка и сложные сценарии.

### Пример: выполнение workflow {#example-execute-a-workflow}

Создайте клиентский скрипт для запуска workflow:

```python
import asyncio
from temporalio.client import Client

async def main():
    client = await Client.connect("localhost:7233")
    
    result = await client.execute_workflow(
        "GreetingWorkflow",
        "World",
        id="greeting-workflow-1",
        task_queue="greeting_queue",
    )
    
    print(f"Workflow result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

Запустите его:

```bash
python3 client.py
# Output: Workflow result: Hello, World!
```
