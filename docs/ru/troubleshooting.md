# Устранение неполадок {#troubleshooting}

Частые проблемы при работе с Temporal-boost и способы диагностики.

## Содержание {#table-of-contents}

- [Подключение](#connection-issues)
- [Воркеры](#worker-issues)
- [Activity](#activity-issues)
- [Workflow](#workflow-issues)
- [Производительность](#performance-issues)
- [Конфигурация](#configuration-issues)
- [Развёртывание](#deployment-issues)

## Проблемы подключения {#connection-issues}

### Не удаётся подключиться к Temporal {#cannot-connect-to-temporal-server}

**Симптомы:** таймаут подключения, «Connection refused», воркер не запускается.

**Решения:**

1. **Проверьте доступность сервера:**
   ```bash
   telnet temporal-host 7233
   ```

2. **Проверьте окружение:**
   ```bash
   echo $TEMPORAL_TARGET_HOST
   echo $TEMPORAL_NAMESPACE
   ```

3. **Проверьте сеть:**
   ```bash
   ping temporal-host
   curl -v temporal-host:7233
   ```

4. **Проверьте firewall:** порт 7233 должен быть открыт; проверьте security groups.
5. **Для TLS:**
   ```bash
   export TEMPORAL_TLS=true
   export TEMPORAL_API_KEY=your-api-key
   ```

### Ошибки согласования TLS {#tls-handshake-errors}

**Симптомы:** ошибки SSL/TLS и проверки сертификата.

**Решения:**

1. **Проверьте настройки TLS:**
   ```python
   # Check if TLS is enabled
   import os
   print(os.getenv("TEMPORAL_TLS"))
   ```

2. **Temporal Cloud:** проверьте наличие и действительность `TEMPORAL_API_KEY`.
3. **Собственный сервер с TLS:** проверьте конфигурацию и срок действия сертификатов.

## Проблемы воркеров {#worker-issues}

### Воркер не запускается {#worker-not-starting}

**Симптомы:** ошибка инициализации, задачи не обрабатываются.

**Решения:**

1. **Проверьте регистрацию:**
   ```python
   workers = app.get_registered_workers()
   for worker in workers:
       print(worker.name)
   ```

2. **Проверьте конфигурацию:**
   ```python
   worker = app.add_worker("test", "test_queue", activities=[...])
   print(worker.name)
   ```

3. **Проверьте имена:** не используйте `run`, `cron`, `exec`, `all`; выбирайте уникальные понятные имена.
4. **Проверьте наличие activity или workflow:**
   ```python
   # Ensure at least one activity or workflow
   if not activities and not workflows:
       raise ValueError("Worker must have activities or workflows")
   ```

### Воркер не обрабатывает задачи {#worker-not-processing-tasks}

**Симптомы:** процесс работает, но задачи остаются в очереди.

**Решения:**

1. **Проверьте совпадение очереди:**
   ```python
   # In workflow
   await workflow.execute_activity(
       my_activity,
       data,
       task_queue="my_queue",  # Must match worker queue
   )
   ```

2. **Проверьте подключение:** найдите логи подключения и убедитесь в доступности Temporal.
3. **Проверьте очередь в Temporal UI:** наличие задач и ожидающих заданий.
4. **Проверьте имена activity/workflow:**
   ```python
   @activity.defn(name="my_activity")  # Must match
   async def my_activity(...):
       ...
   ```

## Проблемы activity {#activity-issues}

### Activity не найдена {#activity-not-found}

**Симптомы:** «Activity not found», activity не выполняется.

**Решения:**

1. **Проверьте имя activity:**
   ```python
   @activity.defn(name="my_activity")
   async def my_activity(...):
       ...
   
   # In workflow, use the function, not string
   await workflow.execute_activity(
       my_activity,  # Use function, not "my_activity"
       data,
   )
   ```

2. **Проверьте регистрацию:**
   ```python
   app.add_worker(
       "worker",
       "queue",
       activities=[my_activity],  # Must include activity
   )
   ```

3. **Проверьте очередь:** activity должна быть зарегистрирована у воркера той же очереди.

### Таймаут activity {#activity-timeout}

**Симптомы:** ошибки и сообщения «Activity timeout».

**Решения:**

1. **Увеличьте таймаут:**
   ```python
   await workflow.execute_activity(
       my_activity,
       data,
       start_to_close_timeout=timedelta(minutes=10),  # Increase timeout
   )
   ```

2. **Измерьте длительность:** логируйте начало/конец и оптимизируйте медленные операции.
3. **Для долгих activity используйте heartbeat:**
   ```python
   @activity.defn(name="long_activity")
   async def long_activity(data: str) -> str:
       for i in range(100):
           await asyncio.sleep(1)
           activity.heartbeat(f"Progress: {i}%")
       return "Done"
   ```

### Проблемы повторов activity {#activity-retry-issues}

**Симптомы:** бесконечные повторы или их отсутствие.

**Решения:**

1. **Настройте политику повторов:**
   ```python
   @activity.defn(
       name="retryable_activity",
       retry_policy=RetryPolicy(
           maximum_attempts=3,
           initial_interval=timedelta(seconds=1),
       ),
   )
   async def retryable_activity(...):
       ...
   ```

2. **Проверьте типы ошибок:** ошибки Temporal повторяются, ошибки приложения могут быть неповторяемыми.

## Проблемы workflow {#workflow-issues}

### Workflow не запускается {#workflow-not-starting}

**Симптомы:** workflow не выполняется, запусков нет.

**Решения:**

1. **Проверьте регистрацию:**
   ```python
   app.add_worker(
       "worker",
       "queue",
       workflows=[MyWorkflow],  # Must include workflow
   )
   ```

2. **Проверьте имя workflow:**
   ```python
   @workflow.defn(name="MyWorkflow")
   class MyWorkflow:
       ...
   ```

3. **Проверьте клиентское подключение:**
   ```python
   client = await Client.connect("localhost:7233")
   await client.start_workflow(
       "MyWorkflow",  # Must match @workflow.defn name
       data,
       task_queue="queue",
   )
   ```

### Нарушение детерминированности workflow {#workflow-determinism-errors}

**Симптомы:** «Non-deterministic workflow», ошибки выполнения.

**Решения:**

1. **Не используйте обычный random:**
   ```python
   # ❌ Wrong
   import random
   value = random.randint(1, 10)
   
   # ✅ Correct
   value = workflow.random().randint(1, 10)
   ```

2. **Не используйте datetime.now():**
   ```python
   # ❌ Wrong
   from datetime import datetime
   now = datetime.now()
   
   # ✅ Correct
   now = workflow.now()
   ```

3. **Не выполняйте ввод-вывод напрямую:**
   ```python
   # ❌ Wrong
   import httpx
   response = httpx.get("https://api.example.com")
   
   # ✅ Correct - Use activity
   response = await workflow.execute_activity(
       fetch_data,
       task_queue="api_queue",
   )
   ```

### Таймаут workflow {#workflow-timeout}

**Симптомы:** таймаут выполнения, падение долгих workflow.

**Решения:**

1. **Используйте continue-as-new:**
   ```python
   @workflow.defn(sandboxed=False, name="LongWorkflow")
   class LongWorkflow:
       @workflow.run
       async def run(self, data: list) -> None:
           for i, item in enumerate(data):
               if i > 0 and i % 100 == 0:
                   await workflow.continue_as_new(data[i:])
               await workflow.execute_activity(
                   process_item,
                   item,
                   task_queue="queue",
               )
   ```

2. **Разбейте процесс:** выделите небольшие и дочерние workflow.

## Проблемы производительности {#performance-issues}

### Высокое потребление памяти {#high-memory-usage}

**Симптомы:** рост памяти, нехватка памяти.

**Решения:**

1. **Уменьшите параллелизм:**
   ```bash
   export TEMPORAL_MAX_CONCURRENT_ACTIVITIES=100
   export TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=100
   ```

2. **Ограничьте размер результатов activity:** большие объекты храните во внешнем хранилище.
3. **Измеряйте память:**
   ```python
   import psutil
   process = psutil.Process()
   print(f"Memory: {process.memory_info().rss / 1024 / 1024} MB")
   ```

### Медленное выполнение workflow {#slow-workflow-execution}

**Симптомы:** долгая обработка, низкая пропускная способность.

**Решения:**

1. **Увеличьте параллелизм:**
   ```bash
   export TEMPORAL_MAX_CONCURRENT_ACTIVITIES=500
   export TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=300
   ```

2. **Выполняйте activity параллельно:**
   ```python
   results = await asyncio.gather(
       workflow.execute_activity(activity1, data1),
       workflow.execute_activity(activity2, data2),
   )
   ```

3. **Оптимизируйте activity:** уменьшите ввод-вывод, используйте пулы соединений и подходящее кэширование.
4. **Используйте sticky workflow:**
   ```python
   worker = app.add_worker(
       "worker",
       "queue",
       workflows=[MyWorkflow],
       nonsticky_to_sticky_poll_ratio=0.1,  # Prefer sticky
   )
   ```

## Ошибки импорта приложения {#application-import-errors}

Внешний запускатель различает следующие ошибки:

| Ошибка | Значение | Действие |
| --- | --- | --- |
| `Import string ... must be in format ...` | Некорректный путь `module:attribute` | Используйте `package.module:app` или `package.module:container.app` без выражений. |
| `Could not import module ...` с причиной `ModuleNotFoundError` | Нет модуля или префикса пакета | Проверьте имя и каталог запуска; установите проект или задайте `PYTHONPATH` для структуры `src`. |
| `ModuleNotFoundError: No module named ...` для зависимости | Приложение найдено, его импорт не удался | Исправьте зависимость по исходному traceback. Другие каталоги не перебираются. |
| `Attribute ... not found in module ...` | Не найден атрибут загруженного модуля | Проверьте экспортируемый объект и вложенные атрибуты. Причина `AttributeError` сохраняется. |
| `SyntaxError`, `ImportError` и другие исключения приложения | Ошибка исполнения Python-кода | Исправьте указанный исходник. Поиск по каталогам не обрабатывает ошибки инициализации. |

Неудачный импорт восстанавливает `sys.path`. Успешный fallback сохраняет только каталог, из которого найдено приложение, для его следующих импортов. Ограниченный поиск в текущем/родительском каталоге и кэш модулей описаны в разделе [поиск приложения](running_application.md#application-import-lookup).

## Проблемы конфигурации {#configuration-issues}

### Окружение не загружается {#environment-variables-not-loading}

**Симптомы:** настройки не применяются, используются defaults.

**Решения:**

1. **Проверьте окружение:**
   ```bash
   env | grep TEMPORAL
   ```

2. **Загрузите .env до первого импорта:** пакет не делает этого сам. Для прямого запуска установите `python-dotenv` отдельно:
   ```python
   from dotenv import load_dotenv
   load_dotenv(".env")

   from temporal_boost import BoostApp
   app = BoostApp()
   ```

   Для установленного CLI подготовьте окружение до команды: загрузка внутри модуля приложения слишком поздняя. Изменения после импорта пакета не обновляют defaults.
3. **Проверьте имена:** точное `TEMPORAL_TARGET_HOST`, регистр имеет значение.
4. **Проверьте значение в коде:**
   ```python
   from temporal_boost.temporal import config
   print(config.TARGET_HOST)
   ```

Явные endpoint/namespace приложения и воркера приоритетнее окружения. См. [приоритет настроек](configuration.md#configuration-priority), если значение отличается от окружения процесса.

### Метрики Prometheus не работают {#prometheus-metrics-not-working}

**Симптомы:** endpoint недоступен, метрик нет.

**Решения:**

1. **Проверьте адрес:**
   ```bash
   export TEMPORAL_PROMETHEUS_BIND_ADDRESS=0.0.0.0:9090
   ```

2. **Проверьте порт:**
   ```bash
   netstat -an | grep 9090
   ```

3. **Проверьте endpoint:**
   ```bash
   curl http://localhost:9090/metrics
   ```

4. **Проверьте runtime:**
   ```python
   worker.configure_temporal_runtime(
       prometheus_bind_address="0.0.0.0:9090",
   )
   ```

## Проблемы развёртывания {#deployment-issues}

### Проблемы контейнера Docker {#docker-container-issues}

**Симптомы:** контейнер не стартует, ошибки подключения.

**Решения:**

1. **Проверьте сеть:**
   ```yaml
   # docker-compose.yml
   services:
     worker:
       network_mode: "host"  # Or use proper network
   ```

2. **Проверьте окружение:**
   ```yaml
   environment:
     - TEMPORAL_TARGET_HOST=temporal:7233
   ```

3. **Посмотрите логи:**
   ```bash
   docker logs container_name
   ```

### Проблемы Kubernetes {#kubernetes-deployment-issues}

**Симптомы:** pod не стартуют, ошибки подключения.

**Решения:**

1. **Проверьте связь с сервисом:**
   ```yaml
   env:
     - name: TEMPORAL_TARGET_HOST
       value: "temporal-service:7233"
   ```

2. **Проверьте DNS:**
   ```bash
   kubectl exec -it pod-name -- nslookup temporal-service
   ```

3. **Проверьте секреты:**
   ```yaml
   env:
     - name: TEMPORAL_API_KEY
       valueFrom:
         secretKeyRef:
           name: temporal-secrets
           key: api-key
   ```

## Советы по отладке {#debugging-tips}

### Включение режима отладки {#enable-debug-mode}

```python
app = BoostApp(debug_mode=True)
```

Или:

```bash
export TEMPORAL_DEBUG=true
```

### Подробные логи {#enable-verbose-logging}

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Проверка Temporal UI {#check-temporal-ui}

- Откройте `http://localhost:8088`.
- Посмотрите работающие workflow, очереди задач и историю выполнения.

### Типовые сообщения логов {#common-log-patterns}

```python
# Log worker startup
logger.info(f"Worker {worker.name} starting")

# Log activity execution
logger.info(f"Executing activity: {activity_name}")

# Log workflow state
logger.info(f"Workflow state: {workflow_state}")
```

### Получение помощи {#getting-help}

Если проблема сохраняется:

1. Прочтите [документацию Temporal](https://docs.temporal.io).
2. Проверьте [документацию Python SDK](https://python.temporal.io).
3. Найдите [issues Temporal-boost](https://github.com/northpowered/temporal-boost/issues).
4. Включите отладочные логи приложения.
5. Проверьте логи сервера Temporal.
