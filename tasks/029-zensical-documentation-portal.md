# TB-029. Перенести документацию с MkDocs на Zensical

- **Статус:** backlog
- **Приоритет:** P2
- **Тип:** Доработка портала документации
- **Дата исследования:** 2026-11-09
- **GitHub issue:** уже создана

Этот документ — план реализации для агента. Миграция, перевод страниц и изменение deployment сейчас
не выполняются. Все критерии реализации остаются открытыми. При выполнении задачи повторно проверить
версии и возможности зависимостей: выводы ниже привязаны к исследованной версии, а не к будущему latest.

## 1. Результат, который нужно получить

Статический портал Temporal-boost на Zensical, публикуемый через GitHub Pages по существующему адресу
`https://northpowered.github.io/temporal-boost/`. Портал должен быть удобен читателю и автору документации:

- Полные английская и русская версии с локализованными навигацией, интерфейсом и поиском.
- Добавление следующего языка через manifest и контент, без копирования сборочного кода.
- Оформление на основе официального бренда и документации Temporal: палитра, logomark,
  монохромные SVG, спокойная типографика, карточки входа и привычный интерфейс документации.
- Существующие английские URL и значимые anchors продолжают работать.
- Поиск, копирование кода, мобильная навигация, light/dark toggle и переключение языка работают
  при размещении под `/temporal-boost/`, включая прямое открытие вложенных страниц.
- Воспроизводимая сборка, проверки на pull request и публикация одного проверенного Pages-артефакта.
- Поддержка Python 3.10 у Python-пакета сохраняется; инструменты документации живут отдельно.

**Принятые рабочие решения:** исходный язык — English, второй язык первого релиза — русский.
English остаётся в корне project-site, русский размещается под `/ru/`. Это сохраняет публичные ссылки
и соответствует текущему английскому содержимому. Новые языки получают собственный префикс.

В эту задачу не входят изменение runtime/API фреймворка, перевод сайта Temporal, новый домен,
система пользовательских аккаунтов, SaaS CMS, платный Zensical Studio, блог и версия портала для каждого
релиза пакета. Возможности версионирования и автогенерации API не нужны для первого переезда.

## 2. Исходное состояние репозитория

| Область | Фактическое состояние | Последствие для миграции |
| --- | --- | --- |
| Конфигурация | [mkdocs.yml](../mkdocs.yml), Material, английский интерфейс | Сначала сравнить builders на прежней конфигурации |
| Контент | 10 Markdown-страниц в `docs/`, один PNG в `docs/img/` | Составить полную карту файлов, URL, anchors и assets |
| Навигация | Главная, guides, examples, API, troubleshooting, release notes | Сохранить покрытие всех страниц при новой группировке |
| Расширения | `tables`, `attr_list`, `md_in_html`, admonitions, PyMdown details/tasklist/highlight/inlinehilite/snippets/superfences | Проверить HTML и поведение каждого используемого расширения |
| Plugins | Только `tags` | Проверить native tags; не переносить плагины по предположению |
| Дублирование | `pymdownx.superfences` записан дважды | Убрать дубликат при нормализации конфигурации |
| Branding | Logo/favicon загружаются по внешнему GitHub URL | Перейти на проверенные локальные официальные SVG |
| Зависимости | Корневая группа `docs` содержит MkDocs Material и входит в default groups | Zensical нельзя безусловно добавить сюда с его Python minimum |
| Публикация | [documentation.yml](../.github/workflows/documentation.yml), Python 3.11, `mkdocs build --strict`, `peaceiris/actions-gh-pages` | Нужен поэтапный переход на Pages artifact/deploy |
| Domain | В workflow задан `cname: northpowered.github.io` | Для выбранного project-site убрать ошибочный custom-domain input |
| Canonical | `site_url` в MkDocs-конфигурации отсутствует | Явно задать правильные URL каждой локализации |
| Ссылки | [README](../README.md) ведёт на текущие английские пути | Не переводить все старые ссылки на новую схему URL |

В рабочем дереве могут находиться изменения других задач. Перед реализацией прочитать актуальные файлы
и `git status`; не восстанавливать устаревшие тексты из этого плана поверх более новых исправлений.

## 3. Что подтверждено внешней документацией

Источники перечислены в разделе 13; документация Zensical проверена через Context7 и официальный сайт.

1. На дату исследования PyPI публикует **Zensical 0.1.0**, `Requires-Python: >=3.11`;
   первый артефакт этой версии опубликован 2026-11-05. Это исходная проверяемая версия для spike.
2. Zensical читает существующий `mkdocs.yml`. TOML не обязателен для пробного запуска,
   поэтому production можно сохранить на MkDocs во время сравнения.
3. `classic` и `modern` — варианты темы. Для исходного сравнения подходит `classic`,
   для целевого портала выбираем `modern` с адаптацией к Temporal.
4. Произвольные MkDocs plugins не запускаются. **Неизвестная plugin-конфигурация может игнорироваться
   без предупреждения**; успешный strict build не доказывает совместимость plugins.
5. Native `tags` поддерживается, согласно compatibility matrix — с 0.0.58. Search встроен;
   язык поиска определяется `theme.language`, а не `plugins.search.lang`.
6. Один Zensical project имеет один canonical language. `extra.alternate` добавляет переключатель,
   но не переводит Markdown и не является системой синхронизации переводов.
7. `mkdocs-static-i18n` не перечислен среди поддерживаемых plugins исследованной версии.
   Не делать на нём архитектуру и не предполагать, что старый MkDocs plugin будет исполнен.
8. `zensical build` поддерживает `--config-file/-f`, `--clean/-c`, `--strict/-s`.
   **`--site-dir` и `gh-deploy` отсутствуют**: output задаётся через `project.site_dir`.
9. `docs_dir`, `site_dir`, `custom_dir` разрешаются относительно файла конфигурации;
   `docs_dir = "."` пока не поддерживается.
10. Overrides используют MiniJinja, а не Python Jinja: произвольные Python-вызовы недоступны.
    Документированы `main.html`, блок `extrahead`, partial `partials/alternate.html`.
11. Для JS при instant navigation документирован `document$.subscribe(...)`.
12. GitHub Pages поддерживается через официальный Actions flow с `configure-pages`,
    `upload-pages-artifact`, `deploy-pages`. Build cache Zensical на CI пока не рекомендуется.

Агент должен сохранить результаты capability-spike: версия, команды, какие возможности реально прошли
проверку, и ссылки на применимые разделы документации. Не считать roadmap-функции доступными.

## 4. Целевая структура и владение настройками

Предлагаемая структура после реализации:

```text
zensical.toml                       # общие настройки темы, extensions и plugins
tools/docs/
  pyproject.toml                    # отдельный docs project, Python >=3.11
  uv.lock                           # независимый lock инструментов документации
  .python-version                   # фиксированный Python для preview и CI
  portal.toml                       # locales, page IDs, routes, navigation labels
  README.md                         # команды, переводы, assets, обновление builder
  tests/                            # проверки сборщика/портала вне core pytest suite
scripts/docs/
  build_portal.py                   # staging, locale builds, сборка artifact
  check_portal.py                   # URLs, anchors, metadata, assets, translations
docs/
  en/                              # текущие страницы с прежними именами файлов
  ru/                              # те же page IDs, русский текст
  _shared/
    assets/
      brand/                       # официальные SVG, provenance и usage notes
      fonts/                       # только разрешённые к распространению файлы
      stylesheets/                 # tokens.css, temporal.css
      javascripts/                 # только необходимые расширения UX
    img/doc_v0_screen.png           # сохранённый существующий asset
overrides/
  main.html                        # минимальные block overrides, {{ super() }}
  partials/alternate.html           # переключатель соответствующих страниц
.cache/docs-portal/                 # generated staging/config/output, gitignored
site/                              # один финальный Pages artifact, gitignored
```

Не создавать отдельные копии общей конфигурации для каждого языка. Авторитетные inputs:
`zensical.toml`, `portal.toml`, Markdown и shared assets. Сборщик читает общие настройки и создаёт
**полные** локальные конфигурации; наличие native TOML inheritance не предполагается.

`portal.toml` должен задавать для каждого языка `code`, `label`, `url_prefix`, а для каждой страницы —
стабильный `page_id`, исходный путь, группу навигации и локализованные названия. Пути и язык страницы
не определяются эвристикой по переведённому заголовку.

Вместо копирования translation status в нескольких местах выбрать один источник: metadata RU-страницы
или manifest. Для перевода хранить hash исходной EN-страницы и статус review. Имена и сигнатуры Python,
CLI, env variables и payload keys не переводить.

### Отдельный docs project

- Начать spike с `zensical==0.1.0`; перед реализацией проверить доступность и при необходимости
  обоснованно выбрать более свежую версию. В любом случае зафиксировать точную версию в lockfile.
- Новый проект требует Python 3.11+; preview и CI используют одну конкретную проверенную версию Python.
- TOML читать стандартным `tomllib`; writer и прочие реально используемые зависимости объявить явно.
- Browser/check dependencies держать в отдельной группе этого проекта. Root `tests/` не должен
  случайно собирать browser tests и требовать Playwright при проверке самого пакета.
- Во время сравнения сохранить старую root docs-группу для MkDocs baseline.
- После cutover убрать MkDocs-only зависимости и `docs` из root default groups, обновить root lock.
  `requires-python` самого `temporal-boost` остаётся `>=3.10.0,<4.0.0`.

## 5. URL, локализация и поиск

### Контракт публичных адресов

| Page ID | English: сохранить | Русский: добавить |
| --- | --- | --- |
| `home` | `/temporal-boost/` | `/temporal-boost/ru/` |
| `creating_application` | `/temporal-boost/creating_application/` | `/temporal-boost/ru/creating_application/` |
| `running_application` | `/temporal-boost/running_application/` | `/temporal-boost/ru/running_application/` |
| `configuration` | `/temporal-boost/configuration/` | `/temporal-boost/ru/configuration/` |
| `advanced_usage` | `/temporal-boost/advanced_usage/` | `/temporal-boost/ru/advanced_usage/` |
| `faststream_integration` | `/temporal-boost/faststream_integration/` | `/temporal-boost/ru/faststream_integration/` |
| `examples` | `/temporal-boost/examples/` | `/temporal-boost/ru/examples/` |
| `api_reference` | `/temporal-boost/api_reference/` | `/temporal-boost/ru/api_reference/` |
| `troubleshooting` | `/temporal-boost/troubleshooting/` | `/temporal-boost/ru/troubleshooting/` |
| `release_notes_2_0_0` | `/temporal-boost/release_notes_2.0.0/` | `/temporal-boost/ru/release_notes_2.0.0/` |

English не переносить под `/en/`. Для первого релиза не переименовывать slugs в рамках редизайна.
Значение `site_url` для EN — `https://northpowered.github.io/temporal-boost/`,
для RU — `https://northpowered.github.io/temporal-boost/ru/`; `use_directory_urls = true`.

### Сборка языков

1. Проверить manifest, создать независимые staging-директории EN и RU.
2. В staging каждого языка скопировать только его Markdown и необходимые shared assets.
   Сохранить работоспособность относительных `img/`-ссылок и snippets.
3. Сгенерировать полные TOML-конфигурации с относительными `docs_dir`, `site_dir`, `custom_dir`.
   Не использовать symlinks как обязательную часть процесса.
4. Последовательно вызвать `zensical build --config-file ... --clean --strict` для каждого языка.
5. Только после успеха обеих сборок собрать новый финальный artifact: EN в корень `site/`, RU в `site/ru/`.
   Проверять коллизии output paths. Не собирать RU прямо в output EN с риском очистить соседний язык.
6. Записать языковой route manifest, `.nojekyll`, sitemap и необходимые metadata.
7. Проверить итоговый artifact; частично собранный портал не публиковать.

### Переключение языка

- В native `extra.alternate` указывать `/temporal-boost/` и `/temporal-boost/ru/`, а не `/en/`
  и `/ru/` без project prefix. Можно использовать полные canonical URLs.
- Language selector должен вести на соответствующий `page_id`, а не всегда на главную.
  Реализовать это минимальным `partials/alternate.html` override с route map из `project.extra`.
  Сначала проверить доступный MiniJinja context на выбранной версии; не вызывать Python из шаблона.
- Ссылки должны быть правильными в готовом HTML даже без JS. Дополнительный JS допустим для сохранения
  fragment, если такой anchor существует в целевой странице; иначе переходить к началу страницы.
- Для важных секций использовать стабильные explicit anchors. Не переносить автоматически EN hash
  в RU, если соответствующего target нет. Сохранить старые английские anchors или сделать mapping.
- Если включена instant navigation, проверить работу overrides и обработчиков после переходов;
  переключение языка должно обновлять язык документа и поиск, при необходимости через полный reload.

### Контент и поисковые индексы

- Для первого релиза перевести все 10 страниц, меню, карточки, описания и project-owned UI strings.
  Локализацию стандартных кнопок брать из Zensical `theme.language = "en"/"ru"`.
- Search index каждого build содержит только его язык; английский индекс не поглощает `ru/` после merge.
- Проверить реальные запросы: `worker`, `graceful shutdown`, `конфигурация`, `завершение`, `воркер`.
  Результаты ведут на текущую локаль с правильным project prefix.
- Не обещать морфологию, stemming или транслитерацию, пока это не подтверждено тестом native search.
- Не выдавать английский fallback за русский перевод. Неполные будущие локализации публиковать только
  с явной политикой fallback и статусом; запуск EN/RU требует полного покрытия текущих страниц.
- CI обнаруживает отсутствующие переводы и устаревший source hash. Обновление EN требует проверки
  связанной RU-страницы, а не автоматического проставления нового hash без review.

### SEO и ошибки

Каждая страница получает свой `lang`, canonical, title и description. В `main.html` через `extrahead`
добавить взаимные head-ссылки `hreflang=en`, `hreflang=ru`, `x-default` на EN-эквивалент.
Ссылки language selector сами по себе не заменяют head alternates.

Проверить генерацию sitemap в выбранной версии. При объединении не потерять ни одну локаль:
оставить отдельные locale sitemaps и корневой sitemap index либо построить их по manifest.
У project-site нет контроля над `https://northpowered.github.io/robots.txt`; не считать файл
в `/temporal-boost/robots.txt` настройкой всего origin.

Корневой `404.html` должен давать понятный EN/RU переход. GitHub Pages не предоставляет произвольные
HTTP rewrites/301: при необходимости использовать поддерживаемые static redirects Zensical и проверять
их fragments. Не имитировать все неизвестные URL переходом на главную и не маскировать реальные 404.

## 6. Дизайн по Temporal

Основной источник — [Temporal Brand](https://temporal.io/brand), reference интерфейса —
[Temporal Docs](https://docs.temporal.io/). Не переносить CSS Docusaurus в Zensical:
воспроизводить нужную систему через поддерживаемые `--md-*` variables, свои design tokens и небольшие overrides.

### Палитра и контраст

| Token / назначение | Цвет | Основание |
| --- | --- | --- |
| Primary UV | `#444CE7` | Официальный brand color; CTA, акценты, выбранные элементы |
| Space Black | `#141414` | Официальный brand color; основной dark background |
| Off White | `#F8FAFC` | Официальный brand color; dark text и light background |
| Dark card surface | `#1A1A1A` | Наблюдаемый card background основной документации |
| Dark link hover | `#BFDBFE` | Наблюдаемая primary/hover палитра Temporal Docs в dark mode |
| Light link hover | `#1D4ED8` | Наблюдаемая primary/hover палитра Temporal Docs в light mode |

Последние три цвета — reference реализации Docs, а не дополнительные официальные brand colors.
Использовать семантические tokens, чтобы менять тему без поиска hex по шаблонам.

Расчёт WCAG по указанным sRGB-цветам: UV на Space Black — примерно **3.01:1**,
UV на Off White — **5.85:1**, белый текст на UV — **6.12:1**.
Поэтому обычный dark-mode текст ссылок не делать UV: использовать светлый текст с подчёркиванием/
различимым состоянием и проверенным hover. Нормальный текст должен проходить 4.5:1, крупный текст
и необходимые UI boundaries — 3:1. Проверять фактический computed background, focus и disabled states.

Первое посещение — dark theme с Space Black, как рекомендует brand page; добавить доступный light toggle.
Сохранённый явный выбор пользователя должен переживать переключение языка и reload.

### SVG, иконки и шрифты

- Использовать оригинальные монохромные Temporal logomark/lockup со страницы бренда, сохранить пропорции.
  Logo разрешён в Space Black, Off White, чёрном или белом; не перекрашивать его в UV и не снижать opacity.
- Соблюсти clear space минимум в размер заглавной T — это опубликованное правило Temporal.
- В header оставить явное имя **Temporal-boost**; официальный знак не заменяет имя нашего проекта.
- Logo, favicon и используемые icons хранить локально, без зависимости от `raw.githubusercontent.com`
  в каждом пользовательском запросе.
- Для тематических изображений использовать исходные SVG из официального набора/репозитория Docs,
  где они применимы: например Python SDK. Для search, copy, chevrons, GitHub и theme toggle использовать
  согласованные SVG формы reference Docs или близкие встроенные Zensical icons одного стиля.
  Не заменять функциональные иконки emoji и не копировать случайные наборы с разной геометрией.
- Для каждого заимствованного asset записать source URL, дату, checksum и условия использования.
  Проверить контраст в обеих темах; декоративные SVG скрывать от screen reader, кнопки подписывать.
- В текущем CSS Temporal Docs обнаружен **Aeonik**. Использовать его только при доступности разрешённых
  к распространению файлов и проверенном Cyrillic coverage. Не считать публичный WOFF2 разрешением
  на redistributing. Базовый рабочий fallback — локальный Inter с кириллицей и подходящий monospace.
- Отключить неявную загрузку Google Fonts; используемые файлы и license notices держать в assets.

Официальные ссылки для logomark:

- [Белый / light SVG](https://images.ctfassets.net/0uuz8ydxyd9p/6h19hCTYqrDacnDV8havze/58f49e40aa15d91f34654290ddc91e75/Temporal_Symbol_light.svg).
- [Чёрный / dark SVG](https://images.ctfassets.net/0uuz8ydxyd9p/3B1zR4imcNyF9oHQxT06AD/9fce8b9ead280e66c21805c58d115176/Temporal_Symbol_dark.svg).

### Структура интерфейса

| Зона | Содержание и поведение |
| --- | --- |
| Header | Temporal-boost, поиск, language selector, theme toggle, GitHub |
| Верхний уровень | Get started, Guides, Operations, Examples, API, Releases; названия локализуются |
| Левое меню | Текущий раздел и страница, различимое active state, мобильный drawer |
| Справа | Оглавление текущей страницы, корректный scroll offset при sticky header |
| Главная | Короткое описание, quick start и карточки: создать приложение, запустить, настроить, интеграции, API |
| Контент | Удобная ширина чтения, чёткие heading levels, copy buttons, code tabs, аккуратные admonitions |
| Footer | Соседние страницы, ссылка на GitHub/edit, источник бренда и необходимые notices |

Кодовые листинги и широкие таблицы прокручиваются внутри своего контейнера; вся страница не должна
выходить за viewport. Проверить 360 px, 768 px и desktop. Цель — узнаваемый Temporal-style интерфейс
на штатной архитектуре Zensical, а не fork темы или копия маркетингового сайта.

## 7. План реализации по этапам

### Этап A. Зафиксировать baseline и capability matrix

1. Прочитать `AGENTS.md`, текущую архитектуру, workflow, docs dependencies, изменения соседних задач.
2. Собрать старый сайт в изолированный baseline output, не меняя production.
3. Сохранить список 10 страниц, опубликованных URL, generated anchors, assets и внутренних ссылок.
4. Проверить текущие внешние ссылки на страницы из README и guides, составить список обязательной совместимости.
5. В отдельном docs project установить pinned Zensical и собрать прежний `mkdocs.yml` с `classic`.
6. Заполнить matrix: Markdown, tags, nav features, search, snippets, logo, URL/anchor stability.
   Проверить, что ни один важный plugin/option не оказался silently ignored.
7. Отдельно проверить `modern`, RU search, alternate override и custom assets.

**Выход:** записанная matrix и baseline. Если обязательная возможность не работает, сначала определить
поддерживаемую замену. Не переключать production на непроверенный builder.

### Этап B. Добавить изолированные инструменты

1. Создать `tools/docs/pyproject.toml`, lock и Python pin; runtime dependencies пакета не менять.
2. Добавить base `zensical.toml`, `portal.toml`, staging/merge/check scripts.
3. Генерировать полные configs; соблюдать относительные пути и отдельный output каждого языка.
4. Добавить команды single-locale preview и preview итогового project-site.
5. Проверить воспроизводимость сборки без Zensical build cache; uv dependency cache допустим.

**Выход:** локальная side-by-side сборка, старый deployment всё ещё работает.

### Этап C. Перестроить контент и добавить RU

1. Перенести EN-файлы с сохранением slugs; обновить ссылки относительно нового source layout.
2. Перенести общий PNG и другие реально используемые assets без потери старых image URLs либо с mapping.
3. Создать RU-эквивалент каждой из 10 страниц и локализованную navigation map.
4. Составить короткий glossary: workflow, activity, worker, task queue, namespace, runtime,
   graceful shutdown. Обеспечить одинаковую терминологию и корректные CLI snippets.
5. Добавить source hashes/status review; проверить кодовые блоки и env names на случайные переводы.
6. Исторические release notes переводить как исторические, не выдавать их за текущий API.

**Выход:** два полноценных источника с одинаковым набором page IDs.

### Этап D. Реализовать тему Temporal и UX

1. Добавить локальные brand assets, tokens и fonts/fallback с источниками.
2. Настроить `modern`, dark/light palette, навигацию, поиск и главную с карточками.
3. Сделать минимальные MiniJinja overrides для page-preserving language selector и head alternates.
4. Если нужен JS, подключать через `extra_javascript` и поддерживать instant navigation через `document$`.
5. Проверить keyboard UX, focus, clear space logo, контраст, кириллицу, code copy и mobile drawer.

**Выход:** screenshots EN/RU × dark/light на главной, Configuration и API Reference.

### Этап E. Закрыть совместимость URL и metadata

1. Сравнить итоговые английские маршруты/anchors с baseline.
2. Добавить explicit anchors или native redirects для неизбежных различий; без redirect loops.
3. Проверить canonical и reciprocal hreflang для каждой пары страниц, включая главную.
4. Собрать sitemaps без потери English или RU, добавить понятный root 404.
5. Проверить локализованные edit links на реальные source-файлы, а не generated staging.
6. Проверить artifact на утечки абсолютных локальных путей и generated configuration.

**Выход:** машинно проверенная route map и полностью собранный `site/`.

### Этап F. Настроить PR checks и GitHub Pages

1. Обновить `.github/workflows/documentation.yml`: отдельные build/check и deploy jobs.
2. Собирать и проверять обе локали на PR, push в main и `workflow_dispatch`.
3. Публиковать только на main через `configure-pages`, `upload-pages-artifact`, `deploy-pages`.
   Использовать pinned commit SHA актуальных Actions; не копировать неподтверждённые major tags из примера.
4. Build job: `contents: read`; deploy: `pages: write`, `id-token: write`, environment `github-pages`.
   PR из fork не должен получать deployment permissions и не должен публиковать сайт.
5. Настроить concurrency для Pages и передавать в deploy именно проверенный artifact, не пересобирать его.
6. Добавить path filters для контента, configs, overrides, scripts, tools/docs locks/tests и workflow.
7. Убрать `cname: northpowered.github.io`; проверить actual Pages source в настройках репозитория
   и переключить его на GitHub Actions при cutover. DNS и домен проекта не менять.
8. Не кешировать output/build state Zensical. Не добавлять `|| true` к обязательным docs checks.
9. Для PR сохранять обычный downloadable preview artifact; отдельный hosting preview не требуется.

**Выход:** полный проверяемый pipeline без изменения URL и без публикации PR-контента.

### Этап G. Cutover, cleanup и сопровождение

1. До переключения сохранить baseline commit/workflow и восстановимый старый site artifact.
2. После успешного preview перевести единственный production deploy на новый artifact.
3. Проверить live HTTPS URLs, asset loading, поиск, оба языка и старые deep links.
4. Удалить `mkdocs.yml` и MkDocs-only dependencies после прохождения cutover checks;
   обновить root lock, AGENTS, README, архитектуру и команды локальной разработки.
5. В `tools/docs/README.md` описать: добавить страницу, добавить язык, обновить перевод,
   обновить Zensical, заменить brand asset, собрать preview и восстановить deployment.
6. Записать реальные результаты и закрыть эту задачу только после выполнения критериев.

**Откат:** восстановить предыдущий проверенный site artifact через активный Pages deployment;
если artifact недоступен, собрать старый MkDocs baseline в отдельном окружении и опубликовать его
тем же Pages flow. Возврат старого branch-deploy потребует возврата Pages source — не считать это
автоматическим откатом. Не делать `git reset` и не удалять более новые пользовательские изменения.

## 8. Матрица проверок для агента

| Проверка | Что должно быть доказано |
| --- | --- |
| Strict build | Обе локали собираются pinned builder, нет предупреждений, принятых через blanket ignore |
| Configuration | Все существенные plugins/features имеют проверенную реализацию, а не silently ignored config |
| Source coverage | Все 10 page IDs есть в EN и RU, переводы review-актуальны |
| Links | Внутренние paths и fragments существуют в final artifact; отсутствуют пути staging |
| Project prefix | Прямой переход на `/temporal-boost/ru/configuration/` загружает CSS/JS/fonts/search |
| Legacy URLs | Старые английские страницы и значимые anchors сохранены либо имеют проверенный redirect |
| Language switch | Переход сохраняет page ID, меняет `html lang`, labels и поисковую локаль |
| Search | EN/RU запросы дают валидные результаты своей локали; после switch нет устаревшего индекса |
| SEO | Canonical, reciprocal head hreflang, x-default и sitemaps соответствуют published paths |
| Branding | Logo variants, clear space, dark/light tokens и SVG совпадают с выбранными официальными источниками |
| Accessibility | Keyboard/focus, подписанные кнопки, contrast, 200% zoom, Cyrillic glyphs, reduced motion |
| Browser | Главная/Configuration/API в EN/RU, 360/768/desktop; нет console errors и запросов к несуществующим assets |
| Isolation | Установка и core tests на Python 3.10 не требуют Zensical/Playwright |
| Deployment | PR не публикуется; main deploy использует один проверенный artifact; CNAME не подменяет project domain |
| Rollback | Предыдущий site artifact и процедура восстановления доступны и проверены до cutover |

Для browser checks использовать фиксированную версию Playwright в docs checks group. Browser binaries
устанавливать отдельным шагом CI. Тесты документации хранить в `tools/docs/tests/`, не добавлять их
неявно в pytest suite пакета. Скриншоты — review artifacts, а не snapshot tests каждой строки текста.

Не ограничиваться `file://` или открытием главной: локальный HTTP preview должен монтировать сайт
именно под `/temporal-boost/`. Например, обслуживать parent-каталог с одноимённой вложенной директорией.
Проверку специфичного поведения GitHub Pages 404 дополнить live smoke после deploy.

### Предлагаемые команды после реализации

Команды ниже задают целевой интерфейс будущих scripts, сейчас этих scripts ещё нет:

```bash
uv sync --project tools/docs --locked
uv run --project tools/docs --locked python scripts/docs/build_portal.py --all --strict
uv run --project tools/docs --locked python scripts/docs/check_portal.py --site site
uv run --project tools/docs --locked python scripts/docs/build_portal.py --serve --locale ru
uv run --project tools/docs --locked python scripts/docs/build_portal.py --serve --all --mount /temporal-boost/
uv run --project tools/docs --locked pytest -c tools/docs/pyproject.toml tools/docs/tests/
```

Внутри wrapper вызывается документированный CLI, например:

```bash
zensical build --config-file .cache/docs-portal/en/zensical.toml --clean --strict
zensical build --config-file .cache/docs-portal/ru/zensical.toml --clean --strict
```

Не добавлять несуществующие `zensical build --site-dir` или `zensical gh-deploy`.

## 9. Рекомендуемое разбиение изменений

| Порция | Содержание | Production |
| --- | --- | --- |
| A | Capability report, isolated docs project, сравнение старой и новой сборки | MkDocs остаётся |
| B | Locale structure, сборщик, переводы, тема Temporal, URL/SEO/browser checks | Только preview artifacts |
| C | Pages workflow, cutover, rollback evidence, удаление MkDocs и обновление contributor docs | Переключение единственного deploy |

Это последовательные части одной задачи, а не требование создавать несколько issues.
Если capability report меняет архитектурное решение, обновить план до продолжения реализации.

## 10. Критерии приёмки

- [ ] Production собирается Zensical с зафиксированной версией в отдельном docs project.
- [ ] Пакет сохраняет Python 3.10 и не получает docs-only runtime dependencies.
- [ ] Все 10 страниц опубликованы на английском и русском; язык интерфейса и поиска соответствует странице.
- [ ] Новый язык добавляется через manifest и Markdown, без изменения логики сборщика.
- [ ] Существующие English URL и значимые fragments продолжают работать.
- [ ] Language selector ведёт на соответствующую страницу и корректно работает с project prefix.
- [ ] Палитра и SVG основаны на Temporal Brand; logo usage, контраст и Cyrillic fonts проверены.
- [ ] Light/dark, mobile navigation, code copy и search проходят browser checks.
- [ ] В final artifact корректны lang, canonical, reciprocal hreflang, sitemap и root 404.
- [ ] На PR выполняется strict build/check обоих языков; ошибки блокируют merge.
- [ ] GitHub Pages публикует только проверенный main artifact без ошибочного CNAME.
- [ ] Выполнены live smoke и проверка доступного rollback artifact/procedure.
- [ ] Обновлены contributor commands, `AGENTS.md`, README и архитектура.
- [ ] В карточке записаны фактические команды, результаты и ограничения; реализация проверена по matrix.

## 11. Связанные задачи и границы ответственности

Жёстких зависимостей нет: migration spike можно начать отдельно от исправлений Python runtime.

- [TB-022](022-enforce-ci-quality-checks.md), GitHub [#61](https://github.com/northpowered/temporal-boost/issues/61):
  согласовать docs checks с общим CI, не создавать два deployment workflow.
- [TB-023](023-runtime-documentation-examples.md), GitHub [#62](https://github.com/northpowered/temporal-boost/issues/62):
  переносить актуальные исправленные примеры; migration не заменяет отдельный аудит их семантики.
- [TB-017](017-configuration-priority-documentation.md), GitHub [#56](https://github.com/northpowered/temporal-boost/issues/56):
  сохранить актуальный контракт конфигурации при переводе и переносе.

Изменения публичного API фреймворка не требуются. При конфликте веток сохранить более новые исправления
документации, затем обновить source hashes и переводы.

## 12. Источники и проверка самого плана

Проверено 2026-11-09. Версионные факты взяты из PyPI и официальных страниц, а не из предположения
о полной обратной совместимости с MkDocs.

- [Zensical: Get started](https://zensical.org/docs/get-started/).
- [Migration](https://zensical.org/docs/compatibility/mkdocs/migration/).
- [Plugin compatibility](https://zensical.org/docs/compatibility/mkdocs/plugins/).
- [Language and alternates](https://zensical.org/docs/setup/language/).
- [Site search](https://zensical.org/docs/setup/search/).
- [Configuration basics](https://zensical.org/docs/setup/basics/).
- [Build CLI](https://zensical.org/docs/usage/build/).
- [Customization, MiniJinja, documented partials](https://zensical.org/docs/customization/).
- [Redirects](https://zensical.org/docs/setup/redirects/).
- [GitHub Pages publication](https://zensical.org/docs/publish-your-site/).
- [PyPI metadata: version and Requires-Python](https://pypi.org/pypi/zensical/json).
- [Temporal Brand: colors, downloads and logo guidelines](https://temporal.io/brand).
- [Temporal Docs: UI, typography and theme reference](https://docs.temporal.io/).

Для подготовки плана прочитаны текущие конфигурация, dependencies, workflow, карта страниц и ссылки README;
официальная документация найдена через Context7, ключевые ограничения сверены с первоисточниками.
Миграционная сборка Zensical и визуальные/browser tests пока **не выполнялись**: это действия этапов A–G.
GitHub issue не создаётся по уточнению пользователя. Проверки этого изменения ограничиваются
структурой Markdown, локальными ссылками, согласованностью task ID и полнотой реестра задач.
