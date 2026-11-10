# Конфигурация {#configuration}

Temporal-boost использует окружение для значений по умолчанию и позволяет явно настраивать приложение и воркеры. Здесь описаны параметры, их приоритет и момент чтения.

## Содержание {#table-of-contents}

- [Загрузка окружения](#environment-loading)
- [Клиент Temporal](#temporal-client-configuration)
- [Настройки воркера](#worker-configuration)
- [Метрики Prometheus](#prometheus-metrics-configuration)
- [Настройки runtime](#runtime-configuration)
- [Приоритет конфигурации](#configuration-priority)
- [Примеры](#configuration-examples)

## Загрузка окружения {#environment-loading}

`temporal_boost.temporal.config` читает окружение один раз при первом импорте пакета. Подготовьте его до импорта `temporal_boost` или модулей, которые его импортируют. Изменение `os.environ` после импорта не обновляет константы даже для новых приложений и сборщиков. Для последующих изменений передавайте явные аргументы до инициализации: см. [момент фиксации настроек](#when-configuration-becomes-fixed).

Пакет не загружает `.env` автоматически. Загрузите файл до импорта или подготовьте окружение извне: см. [пример запуска](#using-configuration-files). Установленная команда `temporal-boost` импортирует пакет раньше модуля приложения; загрузчик `.env` внутри этого модуля вызывается слишком поздно для значений CLI по умолчанию.

## Настройки клиента Temporal {#temporal-client-configuration}

Эти параметры управляют подключением воркеров к серверу Temporal.

### `TEMPORAL_TARGET_HOST` {#temporal_target_host}

**Тип**: строка. **По умолчанию**: `localhost:7233`. **Назначение**: адрес сервера, host:port.

```bash
export TEMPORAL_TARGET_HOST=temporal.example.com:7233
```

### `TEMPORAL_NAMESPACE` {#temporal_namespace}

**Тип**: строка. **По умолчанию**: `default`. **Назначение**: namespace Temporal.

```bash
export TEMPORAL_NAMESPACE=production
```

### `TEMPORAL_TLS` {#temporal_tls}

**Тип**: булево значение. **По умолчанию**: `false`. **Назначение**: TLS для подключений.

```bash
export TEMPORAL_TLS=true
```

Принимает `true`, `1`, `yes` без учёта регистра.

### `TEMPORAL_API_KEY` {#temporal_api_key}

**Тип**: строка. **По умолчанию**: `None`. **Назначение**: API-ключ Temporal Cloud или защищённого кластера.

```bash
export TEMPORAL_API_KEY=your-api-key-here
```

Не сохраняйте API-ключи в системе контроля версий; используйте менеджер секретов.

### `TEMPORAL_IDENTITY` {#temporal_identity}

**Тип**: строка. **По умолчанию**: `None`. **Назначение**: идентификатор клиента.

```bash
export TEMPORAL_IDENTITY=worker-1
```

### `TEMPORAL_USE_PYDANTIC_DATA_CONVERTER` {#temporal_use_pydantic_data_converter}

**Тип**: булево значение. **По умолчанию**: `false`. **Назначение**: сериализация с преобразователем Pydantic.

```bash
export TEMPORAL_USE_PYDANTIC_DATA_CONVERTER=true
```

Преобразователь использует модели Pydantic для типизации и проверки сериализуемых данных. При создании клиентского сборщика `BoostApp(use_pydantic=...)` и `use_pydantic_data_converter` у `TemporalClientBuilder` или `worker.configure_temporal_client()` следуют общему правилу:

| Аргумент | Поведение |
| --- | --- |
| `None` (по умолчанию) | Наследуется `TEMPORAL_USE_PYDANTIC_DATA_CONVERTER` |
| `True` | Включается преобразователь Pydantic из SDK |
| `False` | Автоматический выбор Pydantic отключён даже при включении через окружение |

Явный `data_converter` у `TemporalClientBuilder`, `set_kwargs()` или `worker.configure_temporal_client()` приоритетнее флага и окружения. Отключение флага сохраняет явный преобразователь. Если он не задан, используется стандартный преобразователь SDK.

```python
app = BoostApp(use_pydantic=False)  # Overrides an environment value of true
worker = app.add_worker("example", "example-queue", activities=[my_activity])
worker.configure_temporal_client(data_converter=custom_converter)  # Explicit converter takes priority
```

До инициализации клиента и после очистки запуска `configure_temporal_client()` меняет флаг только при `True` или `False`; `None` сохраняет прежний выбор. Поздний вызов вызывает `RuntimeError`: см. [фиксацию настроек](#when-configuration-becomes-fixed). У отдельного сборщика отключайте Pydantic через `builder.set_pydantic_data_converter(enabled=False)`; вызов без аргументов включает его. Каждый `build()` использует текущий выбор без сохранения автоматически добавленного ранее преобразователя. Уже подключённый клиент не меняется.

**Миграция:** если код рассчитывал, что `False` включает Pydantic, передайте `True`. При одновременном явном преобразователе и включённом флаге теперь побеждает явный преобразователь; удалите его для использования Pydantic SDK.

## Настройки воркера {#worker-configuration}

Эти параметры управляют поведением и ресурсами воркера. Шесть числовых параметров ниже используют окружение только при пропуске аргумента или `None`. Проверка выполняется при создании `TemporalWorkerBuilder`, в том числе через `BoostApp.add_worker()`.

| Аргумент | Допустимые значения |
| --- | --- |
| `max_concurrent_workflow_tasks` | Положительное целое число |
| `max_concurrent_activities` | Положительное целое число |
| `max_concurrent_local_activities` | Положительное целое число |
| `max_concurrent_workflow_task_polls` | Положительное целое число |
| `max_concurrent_activity_task_polls` | Положительное целое число |
| `nonsticky_to_sticky_poll_ratio` | Конечное неотрицательное `int` или `float`, включая `0.0`, без верхнего предела |

Неверные типы, включая булевы значения и числовые строки, вызывают `TypeError`; выход за диапазон — `ValueError`. Для счётчиков запрещены дробные значения, включая `1.0`. Явный ноль больше не заменяется конфигурацией: используйте `None` или пропустите аргумент. Нулевой или отрицательный счётчик из окружения также отклоняется. Корректный явный аргумент может заменить неверный настроенный default. Окружение разбирается при импорте; неверный текст числа по-прежнему заменяется встроенным значением парсера.

Во время `build()` SDK проверяет дополнительные ограничения: при `max_cached_workflows > 0` параллелизм workflow и число опросов должны быть не меньше двух. Без кэширования допустима единица. Проверка коэффициента в сборщике отклоняет отрицательные и неконечные значения, которые SDK Core сам не проверяет; верхней границы `1.0` нет.

```python
app.add_worker("worker", "queue", workflows=[MyWorkflow], nonsticky_to_sticky_poll_ratio=0.0)
```

Нулевой коэффициент передаётся в SDK без изменений. При кэшировании SDK сохраняет минимум одного poller для каждой sticky/non-sticky очереди; ноль не отключает non-sticky опрос.

### `TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS` {#temporal_max_concurrent_workflow_tasks}

**Тип**: целое число. **По умолчанию**: `300`. Максимум одновременно выполняемых задач workflow на воркер.

```bash
export TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=500
```

Увеличьте для пропускной способности или уменьшите для ограничения ресурсов.

### `TEMPORAL_MAX_CONCURRENT_ACTIVITIES` {#temporal_max_concurrent_activities}

**Тип**: целое число. **По умолчанию**: `300`. Максимум одновременных activity на воркер.

```bash
export TEMPORAL_MAX_CONCURRENT_ACTIVITIES=200
```

Подбирайте значение под нагрузку и доступные ресурсы.

### `TEMPORAL_MAX_CONCURRENT_LOCAL_ACTIVITIES` {#temporal_max_concurrent_local_activities}

**Тип**: целое число. **По умолчанию**: `100`. Максимум одновременных локальных activity.

```bash
export TEMPORAL_MAX_CONCURRENT_LOCAL_ACTIVITIES=50
```

Локальные activity выполняются в том же процессе, что и workflow.

### `TEMPORAL_MAX_WORKFLOW_TASK_POLLS` {#temporal_max_workflow_task_polls}

**Тип**: целое число. **По умолчанию**: `10`. Максимум одновременных опросов задач workflow.

```bash
export TEMPORAL_MAX_WORKFLOW_TASK_POLLS=20
```

Определяет количество одновременно опрашиваемых задач workflow.

### `TEMPORAL_MAX_ACTIVITY_TASK_POLLS` {#temporal_max_activity_task_polls}

**Тип**: целое число. **По умолчанию**: `10`. Максимум одновременных опросов задач activity.

```bash
export TEMPORAL_MAX_ACTIVITY_TASK_POLLS=20
```

Определяет количество одновременно опрашиваемых задач activity.

### `TEMPORAL_NONSTICKY_TO_STICKY_RATIO` {#temporal_nonsticky_to_sticky_ratio}

**Тип**: дробное число. **По умолчанию**: `0.2`. Соотношение non-sticky и sticky опросов workflow.

```bash
export TEMPORAL_NONSTICKY_TO_STICKY_RATIO=0.3
```

Sticky workflow сохраняют состояние в памяти для повышения производительности.

### `TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT` {#temporal_graceful_shutdown_timeout}

**Тип**: целое число секунд. **По умолчанию**: `30`. Период ожидания завершения activity, передаваемый SDK как `graceful_shutdown_timeout`.

```bash
export TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT=60
```

При остановке SDK activity получают этот период для завершения до запроса отмены. Ноль запрашивает отмену сразу. SDK всё равно ждёт завершения activity; игнорирование отмены может продлить остановку сверх указанного времени.

Переопределите настройку конкретного воркера через `datetime.timedelta`:

```python
from datetime import timedelta

worker = app.add_worker(
    "payments",
    "payments_queue",
    activities=[process_payment],
    graceful_shutdown_timeout=timedelta(seconds=45),
)
```

Явное значение, включая `timedelta(0)`, приоритетно. Пропуск или `None` использует прочитанную при импорте константу; стандартный fallback — 30 секунд. Некорректный текст целого числа использует тот же fallback. Выбранная отрицательная длительность вызывает `ValueError` при создании сборщика. Явная неотрицательная длительность может заменить отрицательную из окружения.

**Изменение поведения:** без аргумента воркер теперь получает период из окружения или 30 секунд. Ранее настройка игнорировалась и SDK использовал ноль, если значение не передавалось явно.

У координатора отдельный бюджет `BoostApp(shutdown_timeout=30.0)` на ожидание всех потоков. Внешний запускатель имеет отдельный общий `--shutdown-timeout` для дочерних процессов (30 секунд), затем до 5 секунд после terminate и ещё 5 после kill. Внешний бюджет должен учитывать внутреннюю очистку. Эта переменная не меняет бюджеты и не инициирует остановку. Адаптер Temporal поддерживает `request_stop()`; очистка SDK зависит от соблюдения отмены activity. См. [корректное завершение](running_application.md#graceful-shutdown).

## Метрики Prometheus {#prometheus-metrics-configuration}

Параметры сбора и экспорта метрик.

### `TEMPORAL_PROMETHEUS_BIND_ADDRESS` {#temporal_prometheus_bind_address}

**Тип**: строка. **По умолчанию**: `None`. Адрес endpoint метрик Prometheus.

```bash
export TEMPORAL_PROMETHEUS_BIND_ADDRESS=0.0.0.0:9090
```

Каждый runtime воркера публикует `/metrics` на этом адресе. Одновременным runtime нужны разные endpoints; конфликт порта вызывает ошибку запуска, а не отключает телеметрию. Переопределяйте адрес через `configure_temporal_runtime()` и выделяйте каждому процессу порты или сетевые адреса. `--workers N` не распределяет порты метрик. Собирайте каждый endpoint: см. [метрики воркеров и процессов](advanced_usage.md#metrics-across-workers-and-processes).

Экспортёр SDK не использует `PROMETHEUS_MULTIPROC_DIR`; этот каталог не объединяет метрики SDK.

### `TEMPORAL_PROMETHEUS_COUNTERS_TOTAL_SUFFIX` {#temporal_prometheus_counters_total_suffix}

**Тип**: булево значение. **По умолчанию**: `false`. Добавляет `_total` к счётчикам.

```bash
export TEMPORAL_PROMETHEUS_COUNTERS_TOTAL_SUFFIX=true
```

### `TEMPORAL_PROMETHEUS_UNIT_SUFFIX` {#temporal_prometheus_unit_suffix}

**Тип**: булево значение. **По умолчанию**: `false`. Добавляет единицы измерения к именам метрик.

```bash
export TEMPORAL_PROMETHEUS_UNIT_SUFFIX=true
```

### `TEMPORAL_PROMETHEUS_DURATIONS_AS_SECONDS` {#temporal_prometheus_durations_as_seconds}

**Тип**: булево значение. **По умолчанию**: `false`. Выражает длительности в секундах вместо миллисекунд.

```bash
export TEMPORAL_PROMETHEUS_DURATIONS_AS_SECONDS=true
```

## Настройки runtime {#runtime-configuration}

Runtime настраивается программно: см. [расширенное использование](advanced_usage.md).

Defaults для `prometheus_bind_address`, `prometheus_counters_total_suffix`, `prometheus_unit_suffix` и `prometheus_durations_as_seconds` фиксируются при определении `TemporalRuntimeBuilder.__init__()` и `worker.configure_temporal_runtime()` во время импорта. Изменение `os.environ` и даже `config.PROMETHEUS_*` не обновляет пропущенные аргументы. Передавайте явные значения до создания runtime.

Каждый `configure_temporal_runtime()` заменяет конфигурацию целиком; пропущенные поля возвращаются к defaults функции. Явный `metrics` приоритетнее адреса. При `metrics=None` явный `prometheus_bind_address=None` отключает неявный экспортёр, даже если в окружении был адрес. Явные `False` и `None` у флагов суффиксов/длительности дают `False`; `None` не перечитывает окружение.

## Когда настройки фиксируются {#when-configuration-becomes-fixed}

Настройте воркер Temporal до запуска:

| Состояние воркера | Настройка runtime | Настройка клиента |
| --- | --- | --- |
| Создан, ресурсы не инициализированы | Разрешена | Разрешена |
| Runtime создан через `temporal_client_runtime`, клиент ещё не создан | `RuntimeError` | Разрешена |
| Инициализация клиента/SDK воркера началась или завершилась | `RuntimeError` | `RuntimeError` |
| Жизненный цикл `building`, `running` или `stopping` | `RuntimeError` | `RuntimeError` |
| Очистка завершена (`stopped`), ресурсы освобождены | Для следующего запуска | Для следующего запуска |

Первое чтение `temporal_client_runtime` создаёт и кэширует runtime даже до запуска и может занять порт Prometheus. Задавайте параметры до чтения. Повторное чтение возвращает тот же объект; изменение настроек отклоняется без изменения сборщика. Состояние `created` означает отсутствие активного запуска и допускает уже созданный через свойство runtime.

Отклонённая настройка клиента также сохраняет сборщики и SDK-объекты. Автоматического переподключения, замены runtime или изменения работающего SDK воркера нет. После очистки запуска или ошибки старта оба метода снова доступны; следующий запуск создаёт новые объекты. Чтение свойства runtime после очистки снова создаёт объект и фиксирует параметры. Если неудачный конструктор не оставил кэшированного runtime и активного запуска нет, можно перенастроить его перед повтором.

```python
worker = app.add_worker("consumer", "queue", activities=[my_activity])
worker.configure_temporal_runtime(prometheus_bind_address="127.0.0.1:9101")
worker.configure_temporal_client(namespace="production")
# Optional inspection now creates the runtime and fixes its telemetry options:
runtime = worker.temporal_client_runtime
```

**Миграция:** перенесите настройку до `run()`/`cron()` и первого чтения runtime. Для изменения остановите воркер, дождитесь возврата запуска и очистки, затем настройте следующий запуск. Чтобы отказаться от пробного runtime без запуска адаптера, создайте новый воркер. Внешние ссылки могут удерживать прежний экспортёр; освободите их до повторного использования порта.

Activity, interceptors и параллелизм задаются при создании адаптера или через `app.add_worker()`. Для их изменения нужен новый адаптер. Отдельные `TemporalClientBuilder`/`TemporalWorkerBuilder` остаются изменяемыми: setters влияют на будущие сборки и не меняют уже возвращённые объекты.

## Приоритет конфигурации {#configuration-priority}

Endpoint и namespace выбираются независимо, от высшего приоритета к низшему:

1. **Явная настройка воркера**: последнее не-`None` значение `target_host` или `namespace` в `configure_temporal_client()` до инициализации клиента.
2. **Параметры BoostApp**: `temporal_endpoint` и `temporal_namespace`.
3. **Окружение при импорте**: `TEMPORAL_TARGET_HOST` и `TEMPORAL_NAMESPACE`.
4. **Встроенные значения**: `localhost:7233` и `default`.

При повторной настройке сборщика клиента пропущенные поля и `None` сохраняют предыдущие значения. Изменение только namespace сохраняет endpoint. У отдельного `TemporalClientBuilder` нет слоя приложения: аргументы конструктора заменяют конфигурацию импорта, последующие setters заменяют сохранённые значения будущих сборок.

```bash
export TEMPORAL_TARGET_HOST=temporal.prod:7233
export TEMPORAL_NAMESPACE=production
```

```python
from temporal_boost import BoostApp

# The app endpoint wins over the environment; namespace still comes from the environment.
app = BoostApp(temporal_endpoint="temporal.dev:7233")
worker = app.add_worker("consumer", "queue", activities=[my_activity])
# This worker connects to temporal.dev:7233 in the isolated namespace.
worker.configure_temporal_client(namespace="isolated")
worker.configure_temporal_client(target_host=None)  # Keeps temporal.dev:7233
```

Остальные поля следуют собственным правилам:

| Поля | Правило выбора |
| --- | --- |
| Строковые аргументы конструктора клиента (`target_host`, `namespace`, `api_key`, `identity`) | `None` и пустая строка используют импортированную конфигурацию. Настройки воркера и endpoint/namespace приложения используют setters, сохраняющие явную пустую строку. Она не сбрасывает конфигурацию и может отклоняться SDK. |
| `tls` | При первой настройке `None` наследует конфигурацию, явный `False` заменяет `True`. У существующего сборщика `None` сохраняет настройку. |
| Флаг Pydantic / `data_converter` | Явный преобразователь приоритетнее флага; различаются `None`, `False`, `True`. См. [выбор преобразователя](#temporal_use_pydantic_data_converter). |
| Счётчики, коэффициент и период завершения activity | Только `None` выбирает конфигурацию. Ноль допустим для коэффициента и периода; счётчики положительны. См. [воркеры](#worker-configuration). |
| Defaults Prometheus | Пропуск использует значения времени импорта; явные аргументы подчиняются [правилам runtime](#runtime-configuration). |

## Примеры конфигурации {#configuration-examples}

### Разработка {#development-configuration}

```bash
# .env.development
TEMPORAL_TARGET_HOST=localhost:7233
TEMPORAL_NAMESPACE=development
TEMPORAL_USE_PYDANTIC_DATA_CONVERTER=true
TEMPORAL_MAX_CONCURRENT_ACTIVITIES=10
TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=10
```

### Production {#production-configuration}

```bash
# .env.production
TEMPORAL_TARGET_HOST=temporal.production.example.com:7233
TEMPORAL_NAMESPACE=production
TEMPORAL_TLS=true
TEMPORAL_API_KEY=${TEMPORAL_API_KEY}  # From secrets manager
TEMPORAL_USE_PYDANTIC_DATA_CONVERTER=true
TEMPORAL_MAX_CONCURRENT_ACTIVITIES=300
TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=300
TEMPORAL_PROMETHEUS_BIND_ADDRESS=0.0.0.0:9090
TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT=60
```

### Высокая производительность {#high-performance-configuration}

```bash
# .env.high-performance
TEMPORAL_TARGET_HOST=temporal.cluster.example.com:7233
TEMPORAL_NAMESPACE=production
TEMPORAL_TLS=true
TEMPORAL_MAX_CONCURRENT_ACTIVITIES=1000
TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=500
TEMPORAL_MAX_WORKFLOW_TASK_POLLS=50
TEMPORAL_MAX_ACTIVITY_TASK_POLLS=50
TEMPORAL_NONSTICKY_TO_STICKY_RATIO=0.1
TEMPORAL_PROMETHEUS_BIND_ADDRESS=0.0.0.0:9090
```

### Ограниченные ресурсы {#resource-limited-configuration}

```bash
# .env.limited-resources
TEMPORAL_TARGET_HOST=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_MAX_CONCURRENT_ACTIVITIES=50
TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS=50
TEMPORAL_MAX_CONCURRENT_LOCAL_ACTIVITIES=20
TEMPORAL_MAX_WORKFLOW_TASK_POLLS=5
TEMPORAL_MAX_ACTIVITY_TASK_POLLS=5
```

### Файлы конфигурации {#using-configuration-files}

Для прямого запуска скрипта установите `python-dotenv` отдельно и загрузите файл до импорта пакета и модулей воркеров:

```python
from dotenv import load_dotenv

load_dotenv(".env")  # Must run before importing temporal_boost

from temporal_boost import BoostApp

app = BoostApp()
```

По умолчанию `load_dotenv()` сохраняет переменные окружения процесса. Это подготавливает окружение; явные настройки приложения и воркера сохраняют свой приоритет.

### Проверка конфигурации {#configuration-validation}

Проверяйте настройки при запуске:

```python
import os
from temporal_boost import BoostApp

def validate_config():
    """Validate required configuration."""
    required_vars = [
        "TEMPORAL_TARGET_HOST",
        "TEMPORAL_NAMESPACE",
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise ValueError(f"Missing required environment variables: {missing}")

validate_config()
app = BoostApp()
```

### Окружение запуска и явные параметры {#startup-environment-and-explicit-overrides}

Подготовьте окружение до первого импорта в новом процессе:

```python
import os

# Set defaults before importing temporal_boost or your application modules.
os.environ["TEMPORAL_TARGET_HOST"] = "localhost:7233"
os.environ["TEMPORAL_NAMESPACE"] = "test"

from temporal_boost import BoostApp

app = BoostApp()
```

Если пакет уже импортирован, настройте новое приложение или воркер, клиент которого ещё не инициализирован:

```python
from temporal_boost import BoostApp

app = BoostApp(temporal_endpoint="localhost:7233", temporal_namespace="test")
worker = app.add_worker("consumer", "queue", activities=[my_activity])
worker.configure_temporal_client(namespace="another-test")
```

Вызовы влияют на будущее создание ресурсов и не меняют активный клиент или runtime.

### Советы по настройке {#configuration-tips}

1. Используйте `.env.development` и `.env.production` для разных сред.
2. Не сохраняйте секреты в репозитории; используйте менеджер секретов.
3. Документируйте значения по умолчанию.
4. Проверяйте настройки при старте.
5. Преобразуйте строковые переменные в нужные типы.
6. Логируйте конфигурацию без секретов.

### Типовые схемы конфигурации {#common-configuration-patterns}

#### Схема 1: окружение {#pattern-1-environment-based}

Выполните подготовку до импорта `temporal_boost` и модулей приложения:

```python
import os

env = os.getenv("ENVIRONMENT", "development")
if env == "production":
    os.environ.setdefault("TEMPORAL_TLS", "true")
    os.environ.setdefault("TEMPORAL_PROMETHEUS_BIND_ADDRESS", "0.0.0.0:9090")

from temporal_boost import BoostApp

app = BoostApp()
```

#### Схема 2: класс настроек {#pattern-2-configuration-class}

Класс настроек приложения читает окружение независимо. Передавайте значения явно в `BoostApp` или настройку воркера: создание объекта настроек не меняет константы пакета.

```python
from dataclasses import dataclass
import os

@dataclass
class TemporalConfig:
    host: str
    namespace: str
    tls: bool
    api_key: str | None = None
    
    @classmethod
    def from_env(cls):
        return cls(
            host=os.getenv("TEMPORAL_TARGET_HOST", "localhost:7233"),
            namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
            tls=os.getenv("TEMPORAL_TLS", "false").lower() == "true",
            api_key=os.getenv("TEMPORAL_API_KEY"),
        )

config = TemporalConfig.from_env()
```

#### Схема 3: Pydantic Settings {#pattern-3-pydantic-settings}

```python
from pydantic import BaseSettings

class TemporalSettings(BaseSettings):
    temporal_target_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_tls: bool = False
    temporal_api_key: str | None = None
    
    class Config:
        env_prefix = "TEMPORAL_"
        case_sensitive = False

settings = TemporalSettings()
```

### Рекомендации по безопасности {#security-best-practices}

1. Удаляйте API-ключи и другие секреты из логов.
2. Используйте AWS Secrets Manager, HashiCorp Vault или аналогичные средства.
3. Регулярно заменяйте ключи.
4. Включайте TLS в production.
5. Ограничивайте сетевой доступ к Temporal.
6. Регистрируйте изменения production-конфигурации.

### Диагностика конфигурации {#troubleshooting-configuration}

#### Просмотр текущих настроек {#check-current-configuration}

```python
import os
from temporal_boost.temporal import config

print(f"Host: {config.TARGET_HOST}")
print(f"Namespace: {config.CLIENT_NAMESPACE}")
print(f"TLS: {config.CLIENT_TLS}")
print(f"Max Activities: {config.MAX_CONCURRENT_ACTIVITIES}")
```

#### Проверка настроек {#validate-configuration}

```python
from temporal_boost.temporal import config

def validate():
    assert config.TARGET_HOST, "TEMPORAL_TARGET_HOST not set"
    assert config.CLIENT_NAMESPACE, "TEMPORAL_NAMESPACE not set"
    if config.CLIENT_TLS and not config.CLIENT_API_KEY:
        print("Warning: TLS enabled but no API key provided")

validate()
```
