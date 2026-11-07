# TB-017. Согласовать документацию и тесты приоритета конфигурации

- **Статус:** backlog
- **Приоритет:** P2
- **Тип:** Документация

## Проблема и подтверждение

[configuration.md](../docs/configuration.md) и [creating_application.md](../docs/creating_application.md) объявляют env высшим приоритетом. [BoostApp.add_worker()](../temporal_boost/boost_app.py) и [TemporalClientBuilder](../temporal_boost/temporal/client.py) фактически дают приоритет явным endpoint/namespace и последующей настройке worker. [api_reference.md](../docs/api_reference.md) уже описывает параметры как override, поэтому guides противоречат друг другу.

Одинаковая конфигурация интерпретируется пользователем по-разному в зависимости от прочитанного руководства.

## Что сделать

1. Зафиксировать текущий приоритет endpoint/namespace: явная настройка worker → BoostApp → env → встроенный default.
2. Исправить пример, в котором env якобы перекрывает явный `temporal_endpoint`.
3. Документировать import-time чтение env, отсутствие автоматической загрузки `.env` и defaults runtime-аргументов, зафиксированные при импорте.
4. Отдельно описывать особенности bool/числовых параметров после соответствующих исправлений; не обещать одинаковую семантику для всех полей без тестов.

## Критерии приёмки

- [ ] Все guides и API reference описывают единый приоритет endpoint/namespace.
- [ ] Регрессионный тест проверяет конфликт env, app и worker настройки.
- [ ] Пример с `.env` загружает его до импорта пакета или объясняет требуемый порядок.
- [ ] Изменение окружения после импорта не объявляется поддерживаемой динамической перенастройкой.

## Проверка

Обновить документы и соответствующие тесты client/app. Выполнить `uv run mkdocs build --strict`; env-сценарии изолировать от остальных тестов.

## Зависимости и связи

Жёстких зависимостей нет.

Связанные задачи: [TB-001](001-pydantic-converter-boolean-override.md), [TB-015](015-configuration-after-initialization.md), [TB-016](016-numeric-options-zero-fallback.md), [TB-023](023-runtime-documentation-examples.md).

Общий контекст: [ARCHITECTURE.md](../ARCHITECTURE.md). Правила выполнения: [README](README.md).

