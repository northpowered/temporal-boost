# Запуск приложения {#running-application}

Запуск Temporal-boost при разработке, тестировании и в production.

## Содержание {#table-of-contents}

- [Разработка](#development)
- [Поиск приложения при импорте](#application-import-lookup)
- [Коды CLI и вызов из Python](#cli-exit-codes-and-programmatic-invocation)
- [Production](#production-deployment)
- [Docker](#docker-deployment)
- [Kubernetes](#kubernetes-deployment)
- [Управление процессами](#process-management)
- [Мониторинг](#monitoring-and-observability)
- [Устранение неполадок](#troubleshooting)

## Разработка {#development}

### Запуск всех воркеров {#running-all-workers}

Запустите зарегистрированные воркеры в отдельных потоках:

```bash
python3 main.py run all
```

Команда запускает все регистрации, сохраняет процесс до прерывания и согласует завершение по SIGTERM/SIGINT для воркеров с контрактом управляемой остановки.

Воркеры с параметрами CRON здесь также работают только как потребители. `run all` не создаёт серверные цепочки CRON; для регистрации каждой задачи вызовите `cron <name>`.

### Запуск отдельного воркера {#running-individual-workers}

Выберите воркер по имени:

```bash
python3 main.py run worker_name
```

Пример:

```bash
python3 main.py run payment_worker
```

Для Temporal это обработка своей очереди, включая задачи уже зарегистрированной цепочки CRON. `start_workflow()` не вызывается даже при наличии CRON-конфигурации.

### Запуск воркеров CRON {#running-cron-workers}

Запустите воркер CRON:

```bash
python3 main.py cron cron_worker_name
```

Пример:

```bash
python3 main.py cron daily_report_cron
```

Команда регистрирует или использует одну серверную цепочку и обрабатывает очередь. У всех реплик должен быть одинаковый `cron_workflow_id`. Лог содержит namespace, ID workflow и возвращённый run ID. Повторные и конкурентные старты используют работающий ID; закрытый отклоняется. `run <name>`/`run all` не регистрируют цепочку.

| Команда | Обработка задач | Регистрация серверного CRON |
| --- | --- | --- |
| `run <name>` | Выбранный воркер | Нет |
| `run all` | Все воркеры | Нет |
| `cron <name>` | Выбранный CRON-воркер | Запуск или повторное использование стабильного ID |

`cron <name>` доступен только при `cron_schedule` и `cron_runner`. Неполная пара или пустое/пробельное выражение даёт `ValueError` при настройке приложения. Прямой `worker.cron()` обычного потребителя даёт `RuntimeError` до подключения. Исправьте прежние неполные конфигурации: задайте оба параметра или уберите оба.

Локальная остановка не отменяет, не завершает принудительно и не удаляет CRON workflow на сервере. Он продолжает работу через других потребителей; без них задачи ждут в очереди. Для отмены/принудительного завершения конкретной цепочки используйте Temporal Web или клиент. Для постоянной остановки отключите регистраторы: после истечения хранения истории защита закрытого ID исчезает. Новый ID создаёт отдельную задачу. Изменение выражения, типа или очереди с прежним активным ID не меняет цепочку.

### Миграция существующих UUID workflow CRON {#migrating-existing-uuid-cron-workflows}

Старые версии создавали UUID на каждый старт `cron`. Стабильный default не может определить назначение прежних UUID; одно обновление оставит старые цепочки активными. Автоматической отмены/удаления нет.

1. Остановите старые процессы регистрации и их автоматический перезапуск. Запишите endpoint, namespace, тип workflow, очередь и выражение.
2. В Temporal Web отфильтруйте namespace, например `WorkflowType = 'DailyReportWorkflow' AND ExecutionStatus = 'Running'`. Проверьте **все страницы** результатов, очередь, `cronSchedule` первого события `WorkflowExecutionStarted` и бизнес-владение. UUID сам по себе не доказывает дубликат. Составьте список workflow ID и run ID; проверьте закрытую историю, если предлагаемый ID мог использоваться.
3. Чтобы сохранить активную цепочку, задайте её UUID как `cron_workflow_id` всем новым репликам. Отменяйте/завершайте только проверенные дубликаты через Web или `client.get_workflow_handle(workflow_id).cancel()` / `.terminate(reason=...)`. Отмена кооперативная: подтвердите закрытие и согласуйте незавершённую бизнес-работу.
4. При переходе на новый стабильный ID сначала остановите и подтвердите закрытие **всех** старых цепочек этой задачи, согласовав работу во избежание дублирования эффектов. Не удаляйте посторонние workflow по широкому запросу.
5. Запустите новую версию, сравните логируемый ID со списком и подтвердите одну активную цепочку. Повторите регистрацию и проверьте повторное использование.

Тот же подход нужен при изменении расписания, типа и очереди. Закрытый ID отклоняется в пределах хранения истории; для намеренной замены выбирайте проверенный новый версионированный ID.

### Рекомендации при разработке {#development-best-practices}

1. Запускайте разные типы воркеров в отдельных терминалах для отладки.
2. Используйте уровень `DEBUG` для подробных логов.
3. Запускайте локальный Temporal через Docker.
4. Для перезапуска при изменениях используйте `watchdog` или `nodemon`.

### Подготовка окружения {#environment-setup}

Создайте `.env`:

```bash
# .env
TEMPORAL_TARGET_HOST=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_USE_PYDANTIC_DATA_CONVERTER=true
TEMPORAL_MAX_CONCURRENT_ACTIVITIES=10
TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=10
```

Пакет не загружает его автоматически. Для прямого запуска отдельно установите `python-dotenv` и загрузите файл до первого импорта `temporal_boost` или модулей воркеров:

```python
from dotenv import load_dotenv

load_dotenv(".env")

from temporal_boost import BoostApp

app = BoostApp()
```

Установленный `temporal-boost` импортирует пакет до вашего модуля: подготовьте окружение перед командой. Изменения после импорта не обновляют defaults. Явные endpoint/namespace приложения и воркера приоритетнее окружения: см. [конфигурацию](configuration.md#configuration-priority).

## Поиск приложения при импорте {#application-import-lookup}

Запускатель принимает `package.module:app` и вложенные атрибуты, например `package.module:container.app`. Части должны быть точечными Python-идентификаторами; `app()` и другие выражения не вычисляются.

Порядок поиска:

1. Существующий `sys.path`, включая установленные пакеты и `PYTHONPATH`.
2. Текущий рабочий каталог, если его ещё нет в пути.
3. Непосредственный родитель, если его ещё нет в пути.

Поиск заканчивается при первом успешном импорте. Fallback применяется только при отсутствии целевого модуля или префикса его пакета. Отсутствующая зависимость, синтаксическая ошибка и сбой инициализации сразу передаются с исходным traceback. По traceback даже `ModuleNotFoundError` с совпадающим `name`, брошенный кодом приложения/пакета, отличают от отсутствующей цели. Если цель не найдена, вызывается `ValueError: Could not import module ...` с причиной `ModuleNotFoundError`. Для неверной строки и отсутствующих атрибутов отдельные сообщения `ValueError`. Каждый вложенный атрибут читается один раз.

Неудача, включая поиск атрибута, восстанавливает `sys.path`. При успешном fallback только выбранный каталог добавляется в начало для отложенных импортов приложения. Неудачные кандидаты удаляются. Успех по обычному пути ничего не добавляет. Кэш модулей Python действует как обычно; импортёр не выгружает модули и не отменяет побочные эффекты. Выполняйте импорты при настройке до запуска потоков.

Другие предки и произвольные каталоги не обходятся. Для `src` установите проект или подготовьте `PYTHONPATH`, например из корня:

```bash
PYTHONPATH="$PWD/src" uv run temporal-boost service.main:app run all
```

Правила относятся к импорту приложения внешним запускателем. Строки приложений ASGI загружаются своим загрузчиком через обычный Python path.

## Коды выхода CLI и вызов из Python {#cli-exit-codes-and-programmatic-invocation}

Аргументы команды одинаковы у скрипта и установленного однопроцессного запускателя:

```bash
uv run python main.py run payment_worker
uv run temporal-boost service.main:app run payment_worker

# Forward application options, including help, after --
uv run temporal-boost service.main:app -- --help
uv run temporal-boost service.main:app -- exec check --verbose
```

У внешнего запускателя одна команда Typer: дополнительный `run` перед `service.main:app` не нужен. `temporal-boost --help` показывает его справку; `--` передаёт следующие параметры приложению.

| Результат | Код процесса |
| --- | --- |
| Явный `--help` или успех | 0 |
| Неизвестная команда, неверный/пропущенный аргумент, пустой список аргументов приложения | 2 |
| Необработанное обычное исключение воркера | 1 |
| Явный ненулевой `SystemExit` | Указанный код |
| `KeyboardInterrupt`, дошедший до Typer | 130 |

`BoostApp.run()` сохраняет `SystemExit` Typer. В `run all` любое исключение воркера — ошибка координатора, поэтому даже `SystemExit(0)`/`SystemExit(None)` даёт CLI-код 1. Корректная остановка приложения завершается успешно. Это действует для скрипта и стандартного однопроцессного запуска. При `--workers > 1` супервизор сохраняет первый обнаруженный сбой ребёнка после остановки остальных: см. [супервизию](#multi-process-supervision).

Из Python передавайте один список. Пропуск/`None` читает `sys.argv[1:]`; пустой список остаётся пустым. Не используйте `app.run("run", "payment_worker")` или строку команды.

```python
app.run(["run", "payment_worker"])  # Raises SystemExit, including 0 after success
```

При встраивании отключите standalone-режим, чтобы получать результаты и обрабатывать исключения:

```python
from temporal_boost import BoostApp

app = BoostApp(logger_config=None)

def greet(name: str) -> str:
    return f"Hello {name}"

app.add_exec_method_sync("greet", greet)
message = app.run(["exec", "greet", "Ada"], standalone_mode=False)
assert message == "Hello Ada"
```

Ошибки разбора, например `click.UsageError`, и обычные ошибки воркера передаются. Справка возвращает 0; прямой `SystemExit` callback также передаётся. Результат команды — значение, а не обязательно код ОС. В `if __name__ == "__main__": app.run()` сохраняйте стандартный режим для передачи ошибок shell/CI.

**Миграция:** раньше `run()` подавлял `SystemExit`, и неверный вызов мог выглядеть успешным. Теперь перехватывайте исключение явно или используйте non-standalone с обработкой ошибок. Обычные терминальные точки входа не требуют изменений.

## Развёртывание в production {#production-deployment}

### Предварительные условия {#prerequisites}

1. Доступный сервер/кластер Temporal.
2. Настроенная сеть между воркерами и Temporal.
3. Необходимые переменные окружения.
4. Endpoint метрик Prometheus.
5. Централизованные логи, например CloudWatch или Datadog.

### Переменные окружения {#environment-variables}

Задайте production-настройки:

```bash
export TEMPORAL_TARGET_HOST=temporal.production.example.com:7233
export TEMPORAL_NAMESPACE=production
export TEMPORAL_TLS=true
export TEMPORAL_API_KEY=your-api-key-here
export TEMPORAL_USE_PYDANTIC_DATA_CONVERTER=true
export TEMPORAL_MAX_CONCURRENT_ACTIVITIES=300
export TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=300
export TEMPORAL_PROMETHEUS_BIND_ADDRESS=0.0.0.0:9090
```

### Управление процессами {#process-management}

#### systemd {#using-systemd}

Создайте `/etc/systemd/system/temporal-worker.service`:

```ini
[Unit]
Description=Temporal Boost Worker
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/temporal-worker
Environment="TEMPORAL_TARGET_HOST=temporal.example.com:7233"
Environment="TEMPORAL_NAMESPACE=production"
ExecStart=/usr/bin/python3 /opt/temporal-worker/main.py run all
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Включите и запустите сервис:

```bash
sudo systemctl enable temporal-worker
sudo systemctl start temporal-worker
sudo systemctl status temporal-worker
```

#### supervisord {#using-supervisord}

Создайте `/etc/supervisor/conf.d/temporal-worker.conf`:

```ini
[program:temporal-worker]
command=/usr/bin/python3 /opt/temporal-worker/main.py run all
directory=/opt/temporal-worker
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/temporal-worker.err.log
stdout_logfile=/var/log/temporal-worker.out.log
environment=TEMPORAL_TARGET_HOST="temporal.example.com:7233",TEMPORAL_NAMESPACE="production"
```

Перечитайте конфигурацию и запустите:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start temporal-worker
```

## Развёртывание в Docker {#docker-deployment}

### Базовый Dockerfile {#basic-dockerfile}

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV TEMPORAL_TARGET_HOST=localhost:7233
ENV TEMPORAL_NAMESPACE=default
ENV PYTHONUNBUFFERED=1

# Run application
CMD ["python", "main.py", "run", "all"]
```

### Docker Compose {#docker-compose}

Создайте `docker-compose.yml`:

```yaml
version: '3.8'

services:
  temporal-worker:
    build: .
    environment:
      - TEMPORAL_TARGET_HOST=temporal:7233
      - TEMPORAL_NAMESPACE=default
      - TEMPORAL_USE_PYDANTIC_DATA_CONVERTER=true
    depends_on:
      - temporal
    restart: unless-stopped

  temporal:
    image: temporalio/auto-setup:latest
    ports:
      - "7233:7233"
      - "8088:8088"
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=temporal
      - POSTGRES_SEEDS=postgresql
    depends_on:
      - postgresql

  postgresql:
    image: postgres:14
    environment:
      - POSTGRES_USER=temporal
      - POSTGRES_PASSWORD=temporal
      - POSTGRES_DB=temporal
    volumes:
      - temporal-db:/var/lib/postgresql/data

volumes:
  temporal-db:
```

Запустите:

```bash
docker-compose up -d
```

Если образ регистрирует HTTP и Temporal, дайте каждому развёртыванию свою команду. Например, с регистрациями `examples/example_fastapi.py` и установленным extra `uvicorn`:

```yaml
services:
  http:
    image: your-temporal-service
    command: ["temporal-boost", "--workers", "1", "examples.example_fastapi:app", "run", "api_worker"]
    expose:
      - "8000"
  consumers:
    image: your-temporal-service
    command: ["temporal-boost", "--workers", "3", "examples.example_fastapi:app", "run", "order_worker"]
```

Настройте Temporal-окружение обоих сервисов. Каждый HTTP-контейнер владеет своим сокетом; потребители не открывают HTTP-порт. Направляйте балансировщик на 8000 в контейнерной сети, не назначая одинаковый фиксированный порт хоста нескольким репликам. Масштабируйте HTTP и потребителей независимо: см. [политику ASGI](#asgi-and-external-processes).

### Многоэтапная сборка Docker {#multi-stage-docker-build}

Уменьшите образ:

```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv export --locked --no-default-groups --no-emit-project --no-hashes --output-file requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run application
CMD ["python", "main.py", "run", "all"]
```

## Развёртывание в Kubernetes {#kubernetes-deployment}

### Манифест Deployment {#deployment-manifest}

Создайте `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: temporal-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: temporal-worker
  template:
    metadata:
      labels:
        app: temporal-worker
    spec:
      containers:
      - name: worker
        image: your-registry/temporal-worker:latest
        env:
        - name: TEMPORAL_TARGET_HOST
          value: "temporal.example.com:7233"
        - name: TEMPORAL_NAMESPACE
          value: "production"
        - name: TEMPORAL_USE_PYDANTIC_DATA_CONVERTER
          value: "true"
        - name: TEMPORAL_PROMETHEUS_BIND_ADDRESS
          value: "0.0.0.0:9090"
        ports:
        - containerPort: 9090
          name: metrics
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /metrics
            port: 9090
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /metrics
            port: 9090
          initialDelaySeconds: 10
          periodSeconds: 5
```

### Service метрик {#service-for-metrics}

```yaml
apiVersion: v1
kind: Service
metadata:
  name: temporal-worker-metrics
spec:
  selector:
    app: temporal-worker
  ports:
  - port: 9090
    targetPort: 9090
    name: metrics
```

### ConfigMap настроек {#configmap-for-configuration}

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: temporal-worker-config
data:
  TEMPORAL_TARGET_HOST: "temporal.example.com:7233"
  TEMPORAL_NAMESPACE: "production"
  TEMPORAL_USE_PYDANTIC_DATA_CONVERTER: "true"
```

### Секреты {#using-secrets}

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: temporal-credentials
type: Opaque
stringData:
  TEMPORAL_API_KEY: "your-api-key"
```

Ссылка из Deployment:

```yaml
env:
- name: TEMPORAL_API_KEY
  valueFrom:
    secretKeyRef:
      name: temporal-credentials
      key: TEMPORAL_API_KEY
```

## Управление процессами {#process-management_1}

### Несколько воркеров {#running-multiple-workers}

В production можно запускать воркеры отдельно:

```bash
# Terminal 1: Activity workers
python3 main.py run activity_worker

# Terminal 2: Workflow workers
python3 main.py run workflow_worker

# Terminal 3: CRON workers
python3 main.py cron daily_cron
```

Или через PM2:

```bash
pm2 start "python3 main.py run activity_worker" --name activity-worker
pm2 start "python3 main.py run workflow_worker" --name workflow-worker
pm2 start "python3 main.py cron daily_cron" --name cron-worker
pm2 save
```

### Супервизия нескольких процессов {#multi-process-supervision}

Масштабируйте выбранного потребителя Temporal внешним запускателем:

```bash
uv run temporal-boost --workers 3 --shutdown-timeout 40 service.main:app run activity_worker
```

Каждый ребёнок импортирует приложение и выполняет тот же список аргументов. Родитель проверяет всех с интервалом до 50 мс. Ненулевой выход любого останавливает остальных, даже если более ранний процесс ещё работает. Первый обнаруженный сбой определяет статус родителя: положительный сохраняется, сигнал N даёт `128 + N`. Ошибка старта также инициирует очистку и передаётся. Последующие ошибки очистки логируются. Успешно завершившийся конечный процесс дожидается, остальные продолжают; после успеха всех запускатель возвращает 0. Автоперезапуска нет.

При ошибке или SIGINT/SIGTERM родитель отправляет stop по отдельному однонаправленному каналу каждого ребёнка и закрывает свой endpoint. Наблюдатель ребёнка вызывает `app.stop()` для `run all` либо потокобезопасный `request_stop()` выбранного воркера для `run <name>`/`cron <name>`. Запрос до dispatch пропускает исполнение; stop приложения повторяется при старте координатора. Собственные воркеры должны поддерживать контракт. Неуправляемым адаптерам и долгим `exec` может понадобиться принудительная остановка.

`--shutdown-timeout` — конечные неотрицательные секунды, по умолчанию **30**. Это общий кооперативный период всех детей; ноль разрешает немедленную эскалацию. Затем `terminate()` выживших и ожидание до **5 секунд**, далее `kill()` и ещё до **5 секунд**. Deadline общий на фазу, не на процесс. Запущенные дети дожидаются, дескрипторы закрываются и при частичном сбое старта. Процессы, созданные кодом приложения, остаются его ответственностью.

В главном потоке обработчики сигналов временно устанавливаются и затем восстанавливаются. SIGINT родителя даёт **130**, SIGTERM — **143**, если ошибка ребёнка/startup/cleanup ранее не определила результат. Повторные сигналы сохраняют первый запрос и сроки. Дети игнорируют унаследованный SIGINT до установки обработчиков приложения; запросом управляет родитель. Для кооперативного завершения посылайте сигнал супервизору.

Бюджет процессов независим от `BoostApp(shutdown_timeout=...)` и периода SDK activity. Выделите достаточно времени: например 40 секунд вокруг 30-секундного бюджета приложения и ещё 10 секунд для принудительных фаз до финального kill развёртывания. Из Python доступен `run_multiprocess(path, count, arguments, shutdown_timeout=40)` в `temporal_boost.cli.process_runner`: обычное завершение возвращает `None`, ошибки/сигналы передаются.

**Миграция:** раньше родитель мог только залогировать ошибку и вернуть 0 или зависнуть на здоровом ребёнке. Теперь после очистки выходит с ошибкой; сбой старта останавливает уже созданных детей. Настройте grace budget и `request_stop()` собственных воркеров. `run all` повторяет все регистрации в каждом процессе и запрещён с ASGI. Этот механизм освобождает ресурсы процессов; владение каталогом Prometheus рассматривалось в TB-028.

### ASGI и внешние процессы {#asgi-and-external-processes}

Запускатель не разделяет сокеты. При `--workers > 1` команда, запускающая ASGI, завершается usage-кодом **2** до старта выбранных воркеров. Диагностика называет воркеры и рекомендует один HTTP-процесс с отдельным масштабированием потребителей. Супервизор передаёт статус после очистки детей.

| Команда | `--workers 1` | `--workers > 1` |
| --- | --- | --- |
| `run all`, без ASGI | Разрешена | Разрешена |
| `run all`, с ASGI | Разрешена | Отклоняется до запуска |
| `run <asgi-name>` | Разрешена | Отклоняется до сервера |
| `run <temporal-name>` | Разрешена | Разрешена, даже с ASGI-регистрацией |
| `cron <temporal-name>` | Разрешена | Разрешена с прежними правилами ID |
| `exec <command>` | Разрешена | Разрешена; callback принадлежит приложению |
| Справка, включая `run <asgi-name> --help` | Разрешена | Разрешена без запуска |

Проверка выполняется в ребёнке после выбора и разбора команды Typer. Импорты остаются в детях; справка и ошибки разбора сохраняют поведение. Правило действует для Uvicorn, Hypercorn, Granian и собственных `BaseAsgiWorker`, включая `add_async_runtime()`. Параметры сервера не включают общий сокет. Произвольные `exec` и запуск сервера при импорте остаются ответственностью приложения.

Для FastAPI-примера используйте отдельные терминалы/сервисы:

```bash
# One HTTP process, with the uvicorn extra installed
uv run temporal-boost --workers 1 examples.example_fastapi:app run api_worker

# Three Temporal consumers; registering the API does not start it here
uv run temporal-boost --workers 3 examples.example_fastapi:app run order_worker
```

**Миграция:** замените реплицированный `run all`/`run <asgi-name>` отдельными HTTP- и consumer-командами. Однопроцессный `run all` поддерживается. Нативные менеджеры процессов серверов и сокеты — отдельные развёртывания; адаптер не получает общий сокет от запускателя. Контейнеры/pod могут использовать одинаковый внутренний порт при разных сетевых адресах с соответствующей маршрутизацией.

### Корректное завершение {#graceful-shutdown}

`app.run_all_workers()` и `python main.py run all` координируют кооперативную остановку. В главном потоке SIGINT/SIGTERM эквивалентны `app.stop()`. Прежние обработчики восстанавливаются и при ошибках. Повторный stop безопасен и сохраняет первый deadline.

`BoostApp(shutdown_timeout=30.0)` задаёт общий бюджет секунд на остановку и ожидание всех начатых потоков. Число конечное и неотрицательное; ноль исключает ожидание. Координатор проверяет запросы до 50 мс, запрашивает всех до ожидания с общим deadline. `request_stop()` должен быстро возвращаться. Живые потоки по истечении срока перечисляются в `TimeoutError`; при более ранней ошибке таймаут только логируется. Python не может принудительно остановить поток: daemon-потоки могут работать до выхода процесса. Пока они живы, новый запуск запрещён.

При работе в фоновом потоке вызовите `app.stop()` из другого потока и дождитесь возврата `run_all_workers()`. Обработчики сигналов не устанавливаются. `stop()` не блокирует; до/после запуска не влияет на следующий. Регистрация воркеров должна закончиться до координатора.

`run all` считает воркеры долгоживущими сервисами. Первая ошибка на границе `run()` запрашивает общую остановку и передаётся в вызывающем потоке после ограниченной очистки с исходным объектом и traceback. Последующие ошибки воркеров, stop и таймауты логируются. После обнаружения stop новые воркеры не запускаются.

Обычный возврат до остановки — `RuntimeError` с именем: приложение не должно работать без сервиса или сообщать успех при неожиданном выходе. Возврат при остановке допустим. `asyncio.CancelledError`/`concurrent.futures.CancelledError` нормальны только после stop; иначе это ошибка. Остальные исключения, включая `KeyboardInterrupt`/`SystemExit`, остаются ошибками и при остановке.

**Миграция:** конечному custom-воркеру нужно вызвать `app.stop()` до возврата из `run all` или запускаться отдельно. Локальный stop воркера не останавливает приложение. Координатор передаёт ошибки; `BoostApp.run()` сохраняет CLI exits. Даже успешный `SystemExit` воркера считается ошибкой `run all`. Внешний супервизор передаёт ненулевой статус ребёнка после остановки соседей.

Контракт `BaseBoostWorker.request_stop() -> bool` требует потокобезопасного неблокирующего повторяемого запроса, включая startup. Поддержка возвращает `True`; стандартный `False` вызывает предупреждение. Координатор не запускает async `shutdown()` в другом цикле. `AsyncBoostWorker` владеет циклом на запуск, переносит stop в него, один раз вызывает `shutdown()` и ждёт `run_async()`: см. [пример](advanced_usage.md#custom-worker-shutdown).

`TemporalBoostWorker` поддерживает normal и локальный CRON. `request_stop()` безопасен из других потоков и при startup. Незавершённые подключение/регистрация отменяются, локальное CRON-ожидание завершается, SDK воркер останавливается в своём цикле. Startup-ошибка сохраняется при сбое очистки. Последовательные запуски создают новые SDK-объекты; одновременные normal/CRON одного адаптера запрещены.

Async `worker.shutdown()` безопасен до/после запуска и повторяем в своём цикле. Он ждёт жизненный цикл; отмена ожидающего не отменяет очистку. Чужой активный цикл даёт `RuntimeError`: используйте `request_stop()`. В callback также не ждите собственную остановку.

`FastStreamBoostWorker` поддерживает отмену startup, shutdown-хуки, брокер и выход lifespan в своём цикле: см. [FastStream](faststream_integration.md#managed-shutdown). Uvicorn, Hypercorn и Granian используют публичные async API в serving-цикле без повторной очистки: см. [ASGI](creating_application.md#managed-asgi-shutdown). Зависший startup/cleanup может превысить таймаут координатора. Отдельные `run <name>`/`cron <name>` используют lifecycle адаптера; сигналы координатора относятся к `run all`. Внешний CLI останавливает выбранного воркера через [наблюдатель ребёнка](#multi-process-supervision) с отдельным deadline. Остановка локального CRON не удаляет серверный workflow (TB-006).

Бюджет приложения независим от периода SDK activity. Сборщик передаёт `TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT` (целые секунды, default 30) как `graceful_shutdown_timeout`. Явный `datetime.timedelta` у `app.add_worker(...)` приоритетнее окружения, включая ноль; пропуск/`None` наследует его. Отрицательные длительности запрещены.

После начала SDK shutdown activity получают период до запроса отмены; ноль его пропускает. Это не общий deadline: SDK продолжает ждать activity, которые могут игнорировать отмену. Параметр не инициирует stop и не меняет бюджеты приложения/супервизора. Учитывайте период, отмену и очистку внутри внешних бюджетов: см. [настройку и миграцию](configuration.md#temporal_graceful_shutdown_timeout).

## Мониторинг и наблюдаемость {#monitoring-and-observability}

### Метрики Prometheus {#prometheus-metrics}

Включите метрики:

```bash
export TEMPORAL_PROMETHEUS_BIND_ADDRESS=0.0.0.0:9090
```

Endpoint: `http://localhost:9090/metrics`.

### Основные метрики {#key-metrics-to-monitor}

- `temporal_workflow_tasks_started` — начатые задачи workflow.
- `temporal_activity_tasks_started` — начатые задачи activity.
- `temporal_workflow_tasks_completed` — завершённые задачи workflow.
- `temporal_activity_tasks_completed` — завершённые задачи activity.
- `temporal_workflow_tasks_failed` — ошибки задач workflow.
- `temporal_activity_tasks_failed` — ошибки задач activity.

### Логирование {#logging}

Настройте структурированные логи:

```python
import logging
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
app = BoostApp(logger_config=LOGGING_CONFIG)
```

### Проверки работоспособности {#health-checks}

Для ASGI добавьте health endpoint:

```python
from fastapi import FastAPI

fastapi_app = FastAPI()

@fastapi_app.get("/health")
async def health():
    return {"status": "healthy"}
```

Для Temporal используйте endpoint метрик Prometheus как проверку состояния.

## Устранение неполадок {#troubleshooting}

### Воркер не запускается {#worker-not-starting}

**Проблема:** ошибка запуска.

1. Проверьте подключение: `telnet temporal-host 7233`.
2. Проверьте переменные окружения.
3. Найдите ошибки подключения в логах.
4. Убедитесь, что Temporal работает и доступен.

### Таймаут подключения {#connection-timeout}

**Проблема:** невозможно подключиться к Temporal.

1. Проверьте `TEMPORAL_TARGET_HOST`.
2. Проверьте сеть и firewall.
3. Для TLS задайте `TEMPORAL_TLS=true`.
4. Убедитесь, что сервер принимает соединения.

### Activity не выполняются {#activities-not-executing}

**Проблема:** activity зарегистрированы, но не исполняются.

1. Проверьте очередь воркера.
2. Проверьте очередь в workflow.
3. Запустите `python3 main.py run worker_name`.
4. Проверьте ожидающие задачи в Temporal UI.

### Проблемы памяти {#memory-issues}

**Проблема:** высокое потребление памяти.

1. Уменьшите `TEMPORAL_MAX_CONCURRENT_ACTIVITIES`.
2. Уменьшите `TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS`.
3. Ограничьте размер результатов activity.
4. Следите за памятью через Prometheus.

### Проблемы производительности {#performance-issues}

**Проблема:** медленное выполнение workflow.

1. Подберите ограничения параллелизма.
2. Разделяйте нагрузки по очередям.
3. Оптимизируйте длительность activity.
4. Ищите узкие места по метрикам.
5. Рассмотрите горизонтальное масштабирование воркеров.

### Режим отладки {#debug-mode}

Для подробных логов включите отладку:

```python
app = BoostApp(debug_mode=True)
```

Или задайте переменную окружения:

```bash
export TEMPORAL_DEBUG=true
```

Подробные логи выполнения помогут найти причину ошибки.
