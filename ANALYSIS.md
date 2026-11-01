# ANALYSIS.md — Анализ исходного кода проекта «Investing Demo»

> Задание №1 (анализ исходного кода) и основа для задания №2 (восстановление требований).
> Документ описывает **фактически реализованное** поведение. Варианты «как должно быть»
> вынесены в `REQUIREMENTS.md`, раздел «Выявленные неоднозначности и дефекты реализации».
> Предположения, не подтверждённые кодом напрямую, помечены как **[Предположение]**.
>
> **Область действия ссылок на код.** Разделы **1–6** описывают **исходную ревизию**
> проекта (состояние после `initial import`, до заданий №3–4) — именно её требует
> проанализировать задание №1. Все номера строк в разделах 1–6 относятся к этой ревизии.
> В заданиях №3–4 часть файлов изменена, поэтому в текущем дереве те же строки могут
> содержать другой код; изменения описаны в разделах **7** и **8**, а также в
> `MODERNIZATION.md` и `FEATURE_REPORT.md`.

---

## 1. Назначение приложения и технологический стек

### 1.1 Назначение

`Investing Demo` — учебное веб-приложение-«дашборд» для просмотра справочника акций,
торгуемых на Московской бирже, с данными из **Tinkoff Invest API**.

Реализованные возможности (по коду):

- просмотр списка акций из локальной БД (`dashboard/views.py:20-26`);
- карточка акции с ценой, временем обновления и графиком дневных свечей за 180 дней
  (`dashboard/views.py:29-38`, `dashboard/services/graph.py:11-36`);
- CRUD-операции над справочником акций для авторизованных пользователей
  (`dashboard/views.py:41-63`);
- регистрация, вход и выход (`user/views.py:8-64`);
- REST API над справочником акций (`dashboard/api/v1/views.py:16-22`);
- первичная загрузка справочника из Tinkoff API management-командой
  (`dashboard/management/commands/add_shares.py:11-22`);
- периодическое фоновое обновление цен через Celery Beat + Worker
  (`config/celery.py:13-18`, `dashboard/tasks.py:7-28`);
- индикация направления цены («растёт/падает») на основе сравнения с предыдущим значением
  (`dashboard/tasks.py:15-22`, `dashboard/templates/dashboard/list.html:35-40`).

Чего в приложении **нет** (важно для задания №4 — функциональность отсутствует, а не сломана):
портфеля, сделок, списков наблюдения, истории цен в БД, стратегий, уведомлений,
привязки акций к пользователю. Пользователь — это только аутентификация: `Share` не имеет
FK на `User` (`dashboard/models.py:4-21`).

Приложение не является торговым терминалом: операции покупки/продажи не реализованы,
внешний API используется только на чтение (`get_last_prices`, `get_all_candles`,
`instruments.shares`).

### 1.2 Технологический стек (с обоснованием)

| Слой | Технология | Обоснование по коду |
|---|---|---|
| Язык | Python 3.x | `manage.py:1` (`#!/usr/bin/env python`), синтаксис f-strings (`dashboard/services/market_data.py:10`) |
| Версия Python | не зафиксирована в репозитории | нет `runtime.txt` / `pyproject.toml` / `setup.py`. **[Предположение]** 3.9–3.10: `Django==4.1.7` поддерживает 3.8–3.11 (`requirements.txt (исх. ред.):13`), наличие `tomli==2.0.1` (`requirements.txt (исх. ред.):37`) указывает на Python < 3.11, где `tomllib` ещё не встроен |
| Веб-фреймворк | Django 4.1.7 | `requirements.txt (исх. ред.):13`; `INSTALLED_APPS` (`config/settings.py:13-26`); `ROOT_URLCONF = "config.urls"` (`config/settings.py:71`); `WSGI_APPLICATION` (`config/settings.py:89`) |
| Архитектурный паттерн | MVT (Model–View–Template), class-based views | `ListView`/`CreateView`/`UpdateView`/`DeleteView`/`View` (`dashboard/views.py:3`, `user/views.py:3`); шаблоны в `templates/<app>/` |
| Точка входа | `manage.py` | `manage.py:9` — `DJANGO_SETTINGS_MODULE=config.settings`, `manage.py:18` — `execute_from_command_line` |
| Проектный пакет | `config` | `config/settings.py:71`, `config/wsgi.py:14`, `config/asgi.py:14` |
| REST API | Django REST Framework 3.14.0 | `requirements.txt (исх. ред.):16`; `rest_framework` в `INSTALLED_APPS` (`config/settings.py:24`); `viewsets.ModelViewSet` (`dashboard/api/v1/views.py:16`); `routers.DefaultRouter` (`dashboard/api/v1/router.py:5`) |
| Фильтрация/поиск/сортировка API | django-filter 22.1 + DRF `SearchFilter`/`OrderingFilter` | `requirements.txt (исх. ред.):15`; `config/settings.py:34`; `dashboard/api/v1/views.py:19-22` |
| БД | PostgreSQL | `ENGINE = django.db.backends.postgresql` (`config/settings.py:97`); `psycopg2-binary==2.9.5` (`requirements.txt (исх. ред.):27`); сервис `db: image: postgres` (`docker-compose.yml:3-4`). SQLite-конфигурация закомментирована (`config/settings.py:92-95`) |
| Драйвер БД | psycopg2-binary 2.9.5 | `requirements.txt (исх. ред.):27` |
| Асинхронные задачи | Celery 5.2.7 | `requirements.txt (исх. ред.):7`; `config/celery.py:7-11`; `@app.task` (`dashboard/tasks.py:7`) |
| Брокер / очередь | Redis 4.5.1 | `CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"` (`config/settings.py:141`); `redis: image: redis` (`docker-compose.yml:16-19`) |
| Планировщик | Celery Beat | `app.conf.beat_schedule` (`config/celery.py:13-18`); README `celery -A config beat` (`README.md:13`) |
| Внешний API | Tinkoff Invest API (gRPC) | `from tinkoff.invest import Client` (`dashboard/services/market_data.py:1`, `dashboard/services/graph.py:5`, `dashboard/management/commands/add_shares.py:2`); `grpcio==1.51.3`, `protobuf==3.20.3` (`requirements.txt (исх. ред.):17,26`) |
| Визуализация | Plotly 5.13.1 (offline-режим, `output_type="div"`) | `requirements.txt (исх. ред.):24`; `plotly.offline.plot(...)` (`dashboard/services/graph.py:21-35`) |
| Формы / UI | django-crispy-forms 2.0 + crispy-bootstrap3 2022.1 | `requirements.txt (исх. ред.):12,14`; `CRISPY_TEMPLATE_PACK = "bootstrap3"` (`config/settings.py:28-29`); `{% load crispy_forms_tags %}` (`dashboard/templates/dashboard/create.html:8`) |
| CSS/JS фронтенда | Bootstrap + jQuery/Popper/Font-Awesome/Moment/Tempus Dominus с CDN | `dashboard/templates/dashboard/base.html:10-24`; локальные копии `bootstrap.min.css` (`dashboard/static/dashboard/css/`, `user/static/user/css/`) |
| Логирование | стандартный `logging` (консоль + файл `app.logs`) | `config/settings.py:37-59`; логгер `main`, импортируется как объект (`dashboard/tasks.py:4`) |
| Конфигурация секретов | константы прямо в `settings.py` | `SECRET_KEY = ""` (`config/settings.py:6`), `TINKOFF_TOKEN = ""` (`config/settings.py:134`) |
| Инфраструктура | Docker Compose (БД + Redis) | `docker-compose.yml:1-19` |

**Несоответствие заявленного и фактического:** `README.md:22-23` позиционирует проект как
`investing` с API `/api/v1/shares`, что совпадает с кодом; при этом `README.md:1` и
`manage.py:2` называют проект `DjangoOld` — следы переименования шаблона.

---

## 2. Структура проекта

```
agent-deepseek/
├── manage.py                     точка входа CLI (manage.py:9, 18)
├── requirements.txt              40 зафиксированных зависимостей
├── HOMEWORK.md                   текст задания
├── README.md                     краткая инструкция запуска (БД, add_shares, celery beat/worker)
├── docker-compose.yml            postgres + redis для локального запуска
├── .gitignore                    исключения VCS (__pycache__, .venv, *.sqlite3, .env, *.log)
├── config/                       проектный пакет (настройки, URL, WSGI/ASGI, Celery)
│   ├── __init__.py               реэкспорт celery_app (config/__init__.py:1-3)
│   ├── settings.py               все настройки: приложения, БД, DRF, crispy, LOGGING, Celery
│   ├── urls.py                   корневой URLconf: admin/, dashboard, user
│   ├── celery.py                 экземпляр Celery + beat_schedule
│   ├── wsgi.py                   WSGI-приложение (для gunicorn/uwsgi)
│   └── asgi.py                   ASGI-приложение (не используется в проекте)
├── dashboard/                    основное приложение: справочник акций
│   ├── models.py                 модель Share
│   ├── views.py                  List/Detail/Create/Update/Delete + mixin авторизации
│   ├── urls.py                   маршруты app_name="dashboard"
│   ├── forms.py                  ShareModelForm (все поля модели)
│   ├── admin.py                  регистрация Share в админке
│   ├── apps.py                   AppConfig
│   ├── tasks.py                  Celery-задача update_last_price
│   ├── tests.py                  9 API-тестов (APITestCase)
│   ├── services/                 слой интеграции и визуализации
│   │   ├── market_data.py        get_last_data() — последняя цена из Tinkoff
│   │   └── graph.py              get_graph() — свечи за 180 дней → Plotly div
│   ├── management/commands/
│   │   └── add_shares.py         команда импорта справочника акций из Tinkoff
│   ├── migrations/               0001…0007 (эволюция схемы Share)
│   ├── api/                      REST API
│   │   ├── urls.py               подключает v1/
│   │   └── v1/
│   │       ├── urls.py           include(router.urls)
│   │       ├── router.py         DefaultRouter, ресурс shares
│   │       ├── views.py          ShareViewSet + ShareFilter
│   │       └── serializer.py     ShareSerializer
│   ├── static/dashboard/css/     bootstrap.min.css, sticky-footer-navbar.css
│   └── templates/dashboard/      base.html, list.html, detail.html, create.html, delete.html
└── user/                         приложение аутентификации
    ├── models.py                 НЕ модель: алиас get_user_model() (user/models.py:3)
    ├── forms.py                  RegistrationForm, AuthForm
    ├── views.py                  AuthView, RegistrationView, LogoutView
    ├── urls.py                   app_name="user": login/, registration/, logout/
    ├── apps.py                   AppConfig
    ├── migrations/               пустая (своих моделей нет)
    ├── static/user/css/          bootstrap.min.css, signin.css
    └── templates/user/           base.html, auth.html, registration.html
```

### 2.1 Назначение ключевых файлов

| Файл | Назначение |
|---|---|
| `manage.py` | CLI-обёртка Django; задаёт `config.settings` (`manage.py:9`) |
| `config/settings.py` | Единая конфигурация. Задаёт 11 приложений (`:13-26`), REST_FRAMEWORK с `LimitOffsetPagination`/`PAGE_SIZE=100` и `DjangoFilterBackend` по умолчанию (`:31-35`), LOGGING в консоль и `app.logs` (`:37-59`), PostgreSQL (`:91-104`), `STATIC_URL` (`:130`), `TINKOFF_TOKEN` (`:134`), параметры Celery и URL брокера (`:136-141`), `CELERY_TASK_ALWAYS_EAGER = False` (`:144`) |
| `config/urls.py` | Три точки монтирования: `admin/`, `""` → dashboard, `"user"` → user (`:5-7`) |
| `config/celery.py` | Создаёт `Celery("config")`, читает настройки с префиксом `CELERY` (`:9`), автообнаружение задач (`:11`), расписание Beat (`:13-18`) |
| `config/__init__.py` | Гарантирует инициализацию Celery при импорте пакета `config` (`:1`) |
| `dashboard/models.py` | Единственная доменная модель `Share` (`:4-21`) |
| `dashboard/views.py` | Весь HTML-контур: список, детальная с графиком, CRUD с проверкой авторизации |
| `dashboard/urls.py` | 5 HTML-маршрутов + точка монтирования API (`:14-19`) |
| `dashboard/services/market_data.py` | Запрос последней цены (`get_last_prices`) — единственное место, откуда Celery-задача получает цену |
| `dashboard/services/graph.py` | Запрос дневных свечей за 180 дней и сборка Plotly-графика |
| `dashboard/tasks.py` | Фоновая задача обновления цен и пересчёт флага `is_trend_high` |
| `dashboard/management/commands/add_shares.py` | Наполнение БД справочником акций (`instruments.shares()`) |
| `dashboard/api/v1/*` | Тонкий слой DRF: сериализатор + ModelViewSet + роутер |
| `dashboard/tests.py` | Контракт API (список/детальная/создание/изменение/удаление, коды 200/201/204/400/404) |
| `user/forms.py` | Валидация регистрации (совпадение паролей, уникальность e-mail) и формы входа |
| `user/views.py` | Ручные `View` с `@staticmethod`-обработчиками GET/POST; работа с `django.contrib.auth` |
| `user/models.py` | Своих моделей нет; `User = get_user_model()` — алиас на `auth.User` |

### 2.2 Связь `config` ↔ `dashboard` ↔ `user`

```
                        config/                         (проектный уровень)
        ┌───────────────────────────────────────────────────────────────┐
        │ settings.py   urls.py        celery.py                        │
        │   │ INSTALLED_APPS            │ beat_schedule                 │
        │   │ "dashboard","user"        │ "dashboard.tasks.update_..."  │
        └───┼───────────┼───────────────┼───────────────────────────────┘
            │           │               │
            │           ▼               │
            │   ROOT_URLCONF ───► path("",  include("dashboard.urls"))
            │                     path("user", include("user.urls"))
            │           │               │
    ┌───────▼───────────▼───────┐       │        ┌──────────────────────────┐
    │ dashboard/                │       │        │ user/                    │
    │  models.Share ◄───┐       │       │        │  forms (Auth/Registration)│
    │  views (CRUD)     │       │       │        │  views (login/reg/logout) │
    │  forms.ShareModelForm     │       │        │  urls app_name="user"     │
    │  api/v1 (DRF)     │       │       │        └────────────┬─────────────┘
    │  tasks ───────────┼───────┼───────┘                     │
    │  services/graph ──┘       │                             │
    └───────────────────────────┘                             │
                    ▲                                         │
                    └──── redirect("dashboard:index") ─────────┘
                          (user/views.py:24, 49, 64)
```

Три вида связей:

1. **`config` → `dashboard`/`user` (сверху вниз, только через настройки).**
   `config` ничего не импортирует из приложений: связь идёт через декларации в
   `INSTALLED_APPS` (`config/settings.py:22-23`), `ROOT_URLCONF` (`:71`), `TEMPLATES`
   с `APP_DIRS=True` (`:76`) — благодаря этому Django сам находит `templates/dashboard/`
   и `templates/user/`, а `TEMPLATES.DIRS=[]` (`:75`), т.е. все шаблоны живут внутри приложений.
   Celery-связь — строкой задачи `"dashboard.tasks.update_last_price"` (`config/celery.py:16`),
   а не импортом, поэтому beat не тянет код приложения на этапе загрузки.

2. **`dashboard` → `config` (обратная зависимость, высокая связность).**
   Приложение импортирует из `config` конкретные объекты:
   `from config.settings import TINKOFF_TOKEN, logger` (`dashboard/services/market_data.py:3`),
   `from config.settings import TINKOFF_TOKEN` (`dashboard/services/graph.py:8`,
   `dashboard/management/commands/add_shares.py:4`),
   `from config.settings import logger` (`dashboard/tasks.py:4`),
   `from config.celery import app` (`dashboard/tasks.py:1`).
   Это нарушает обычное направление зависимостей (приложение → фреймворк, а не → проект)
   и делает `dashboard` непригодным к повторному использованию вне `config`.

3. **`user` → `dashboard` (навигационная связь через URL-имена).**
   Прямых импортов нет; `user` ссылается только на имя маршрута
   `redirect("dashboard:index")` (`user/views.py:24, 49, 64`), а `dashboard/base.html:42`
   ссылается на `{% url 'user:auth' %}`, `base.html:39` — на `{% url 'user:logout' %}`.
   Функционально `user` — «поставщик» флага `request.user.is_authenticated`, который
   `dashboard` использует для показа CRUD-элементов (`list.html:9, 23, 41`) и который
   проверяется mixin'ом `IsUserAuthenticatedMixin` (`dashboard/views.py:11-17`).

Итого: `config` — композиционный корень; `dashboard` — доменное приложение (модель + UI + API + интеграция + задачи);
`user` — тонкая надстройка над `django.contrib.auth`, не имеющая собственных моделей.

---

## 3. Архитектура и взаимодействие компонентов

### 3.1 Общая схема

```
  Браузер ──HTTP──► WSGI (config/wsgi.py) ──► Middleware (settings.py:61-69)
                                                   │
                                                   ▼
                              ROOT_URLCONF config/urls.py
                      ┌────────────────────┬───────────────────┬──────────────┐
                      ▼                    ▼                   ▼              ▼
                 admin/            dashboard.urls        user.urls      dashboard.api
                                   "app_name=dashboard"  "app_name=user"  v1/router
                      │                    │                   │              │
                      │        ┌───────────┴──────────┐        │              ▼
                      │        ▼                      ▼        │        ShareViewSet
                      │   Views (HTML)            IsUserAuthenticatedMixin   (DRF)
                      │        │                      │        │              │
                      │        ▼                      ▼        │              ▼
                      │   Templates            redirect(index)│       ShareSerializer
                      │        │                               │              │
                      └────────┴───────────► ORM (Share.objects) ◄───────────┘
                                                   │
                                                   ▼
                                        PostgreSQL (psycopg2)

  Отдельные процессы:
  Celery Beat ──(redis broker, settings.py:141)──► Celery Worker
        └─ beat_schedule: update_last_price каждые 10 с (config/celery.py:13-18)
                                    │
                                    ▼
                     dashboard/tasks.py → services/market_data → Tinkoff Invest API (gRPC)
                                    │
                                    ▼
                          Share.objects.filter(...).update(...)  → PostgreSQL
```

### 3.2 Путь HTTP-запроса: от `urls.py` до БД

#### Сценарий A — `GET /` (список акций)

1. `config/urls.py:6` — `path("", include("dashboard.urls"))`: пустой префикс, запрос уходит в `dashboard.urls`.
2. `dashboard/urls.py:14` — `path("", ShareListView.as_view(), name="index")`.
3. Middleware-цепочка `config/settings.py:61-69` (Security → Session → Common → Csrf → Auth → Messages → XFrame).
   Анонимный пользователь получает `AnonymousUser` от `AuthenticationMiddleware`, CSRF для GET не проверяется.
4. `ShareListView` (`dashboard/views.py:20-26`): `model = Share`, `paginate_by = 100`, `ordering = ["name"]`.
   `ListView.get_queryset()` строит `Share.objects.all()` и применяет `order_by("name")`;
   `ListView.get_context_data()` добавляет `share_list` и `page_obj`.
5. Рендер `dashboard/templates/dashboard/list.html` (выбор шаблона — `dashboard/views.py:24`,
   поиск файла — через `APP_DIRS=True`, `config/settings.py:76`).
6. ORM выполняет: `SELECT ... FROM dashboard_share ORDER BY name ASC LIMIT 100` (+ `COUNT(*)` для пагинатора).
7. `psycopg2` (`requirements.txt (исх. ред.):27`) отправляет SQL в PostgreSQL `investing` на `localhost:5432`
   (`config/settings.py:97-103`).

#### Сценарий B — `GET /<pk>` (карточка акции, обращение к внешнему API)

1. `config/urls.py:6` → `dashboard/urls.py:15` — `path("<int:pk>", ShareDetailView.as_view(), name="detail")`.
   Конвертер `<int:pk>` не перехватывает `create`, `update/...`, `delete/...`, `api/`, поэтому
   порядок объявления безопасен.
2. `ShareDetailView.get` (`dashboard/views.py:29-38`) — обычный `View` с `@staticmethod`.
   **Проверки авторизации нет** (в отличие от CRUD-вьюх).
3. `Share.objects.get(id=pk)` (`dashboard/views.py:32`) → `SELECT ... WHERE id = %s`; при отсутствии записи
   выбрасывается `Share.DoesNotExist`, обработчика нет → HTTP 500.
4. `get_graph(share)` (`dashboard/views.py:37`) → `dashboard/services/graph.py:11-36`:
   - `Client(TINKOFF_TOKEN)` — открывается gRPC-канал к Tinkoff Invest API (`graph.py:12`);
   - `client.get_all_candles(figi=share.figi, from_=now()-timedelta(days=180), interval=CANDLE_INTERVAL_DAY)`
     (`graph.py:14-18`) — поток дневных свечей;
   - `plotly.offline.plot([...], output_type="div", ...)` (`graph.py:21-35`) — сериализация в HTML-фрагмент `<div>`.
5. Рендер `dashboard/templates/dashboard/detail.html`: `plot_div` вставляется с
   `{% autoescape off %}` (`detail.html:23-25`), поля `share.name`, `share.last_price`,
   `share.currency`, `share.updated_at` — `detail.html:11-13`.

#### Сценарий C — `GET|POST /create` (создание акции, защищённый маршрут)

1. `dashboard/urls.py:16` — `path("create", ShareCreateView.as_view(), name="create")`.
2. `IsUserAuthenticatedMixin.dispatch` (через `UserPassesTestMixin`, `dashboard/views.py:11-17`):
   `test_func()` возвращает `request.user.is_authenticated`; при `False` вызывается
   переопределённый `handle_no_permission()`, который делает `redirect("dashboard:index")`
   (а не redirect на страницу входа).
3. `GET`: `CreateView` создаёт `ShareModelForm` (`dashboard/forms.py:6-11`, `fields = "__all__"`)
   и рендерит `dashboard/templates/dashboard/create.html` через crispy (`create.html:8-19`).
4. `POST`: `CsrfViewMiddleware` проверяет `csrfmiddlewaretoken` (`create.html:14`).
5. `form.is_valid()` → валидация модели: обязательность `figi/isin/name/ticker/currency/uid`,
   `max_length` и `unique` для `figi`, `ticker`, `uid` (`dashboard/models.py:7-12`).
6. `form.save()` → `INSERT INTO dashboard_share (...) VALUES (...)`; `updated_at` заполняется
   `auto_now` (`models.py:17`).
7. `success_url = reverse_lazy("dashboard:index")` (`dashboard/views.py:46`) → HTTP 302 на `/`.

#### Сценарий D — `POST /api/v1/shares/` (REST)

1. `config/urls.py:6` → `dashboard/urls.py:19` — `path("api/", include("dashboard.api.urls"))`.
2. `dashboard/api/urls.py:4` — `path("v1/", include("dashboard.api.v1.urls"))`.
3. `dashboard/api/v1/urls.py:5` — `include(router.urls)`.
4. `dashboard/api/v1/router.py:5-6` — `DefaultRouter().register(r"shares", ShareViewSet)` →
   `/api/v1/shares/` (list/create), `/api/v1/shares/<pk>/` (retrieve/update/destroy).
5. `ShareViewSet` (`dashboard/api/v1/views.py:16-22`) — `ModelViewSet`, `queryset = Share.objects.all()`,
   `filter_backends = (OrderingFilter, DjangoFilterBackend, SearchFilter)`,
   `filterset_class = ShareFilter` (`name`, `ticker`), `ordering_fields = ["name", "ticker"]`,
   `search_fields = ["$name"]`.
6. `ShareSerializer` (`dashboard/api/v1/serializer.py:6-18`) — `ModelSerializer`, поля
   `id, figi, isin, name, ticker, currency, last_price, is_trend_high, updated_at` (`uid` не включён).
7. `ModelViewSet.create` → `serializer.is_valid()` → `serializer.save()` → `INSERT`.
   Ответ 201 с сериализованным объектом.
8. Пагинация — `LimitOffsetPagination`, `PAGE_SIZE=100` (`config/settings.py:31-35`), поэтому
   ответ списка имеет вид `{"count": N, "next": ..., "previous": ..., "results": [...]}`
   (это и проверяет `dashboard/tests.py:39`).

**Важно:** у `ShareViewSet` не заданы `permission_classes`/`authentication_classes`, значит действуют
дефолты DRF — `AllowAny`, без аутентификации. Т.е. API полностью открыт, хотя HTML-CRUD
защищён mixin'ом.

#### Сценарий E — фоновое обновление цен

1. `celery -A config beat` читает `config/urls.py`-независимый `config/celery.py:13-18`:
   задача `dashboard.tasks.update_last_price`, `schedule: 10.0` секунд.
2. Beat кладёт сообщение в Redis (`config/settings.py:141`).
3. Worker импортирует `dashboard/tasks.py:7` (`@app.task update_last_price`) и выполняет:
   - `Share.objects.all()` (`tasks.py:9`) — выборка всех акций;
   - для каждой: `get_last_data(share)` (`tasks.py:13`) →
     `Client(TINKOFF_TOKEN)` → `client.market_data.get_last_prices(figi=[share.figi])` →
     `last_prices.pop()` → `[price.units, price.time]` (`market_data.py:6-11`);
   - сравнение `share.last_price > last_price` → `is_trend_high` (`tasks.py:16-22`);
   - `Share.objects.filter(id=share.id).update(last_price=..., is_trend_high=...)` (`tasks.py:24-26`).
4. Исключения логируются через `logger` (`tasks.py:21, 28`) в `main` → консоль + `app.logs`
   (`config/settings.py:47-56`).

### 3.3 Где используется Celery

| Место | Роль |
|---|---|
| `config/celery.py:7-11` | Создание приложения, чтение `CELERY_*` из `settings.py` (`namespace="CELERY"`), `autodiscover_tasks()` |
| `config/celery.py:13-18` | Расписание Beat: одна периодическая задача `update_last_price`, период 10 с |
| `config/__init__.py:1` | Импорт `celery_app`, чтобы задачи регистрировались при старте Django |
| `dashboard/tasks.py:7` | Единственная задача — `update_last_price` |
| `config/settings.py:137-144` | Настройки: `CELERY_TIMEZONE="Europe/Moscow"`, `CELERY_TASK_TRACK_STARTED=True`, `CELERY_TASK_TIME_LIMIT=30*60`, `CELERY_BROKER_URL=redis://127.0.0.1:6379/0`, `CELERY_TASK_ALWAYS_EAGER=False` |
| `dashboard/tasks.py:1` | `from config.celery import app` — задача регистрируется на проектном экземпляре Celery |

Примечательно: **ни один HTTP-обработчик не ставит задачи в очередь**. Celery используется
исключительно как «внешний шедулер обновления цен», взаимодействия «запрос → задача» нет.
`CELERY_TASK_ALWAYS_EAGER = False` (`settings.py:144`) означает, что в тестах задачи тоже
не выполняются синхронно; тесты эту задачу не покрывают.

### 3.4 Как вызывается внешний API Tinkoff Invest

Три независимые точки интеграции, каждая со своим `Client`, каждое открытие — новый gRPC-канал:

| Функция | Метод API | Назначение | Файл:строки |
|---|---|---|---|
| `get_last_data(share)` | `market_data.get_last_prices(figi=[...])` | последняя цена по одной акции | `dashboard/services/market_data.py:6-11` |
| `get_graph(share)` | `get_all_candles(figi, from_, interval=CANDLE_INTERVAL_DAY)` | дневные свечи за 180 дней | `dashboard/services/graph.py:11-20` |
| `Command.handle` | `instruments.shares()` | полный справочник акций | `dashboard/management/commands/add_shares.py:12-22` |

Особенности:
- аутентификация — только токен из настроек: `Client(TINKOFF_TOKEN)` (`market_data.py:7`,
  `graph.py:12`, `add_shares.py:12`); токен задаётся константой `config/settings.py:134`;
- клиент используется как context manager (`with Client(...)`), т.е. канал закрывается после вызова;
- в `get_last_data` берётся `resp.price.units` — целая часть `Quotation`, дробная часть
  (`nano`) отбрасывается (`market_data.py:11`); аналогично `candle.close.units` в `graph.py:20`;
- обработки ошибок сети/quota в `get_graph` и `add_shares` нет — исключение дойдёт до пользователя
  (500); в `tasks.py` есть широкий `try/except` (`tasks.py:12, 27`).

---

## 4. Библиотеки и внешние зависимости

`requirements.txt` содержит 40 пакетов с жёсткой фиксацией версий (`==`).
Тип: **П** — прямая зависимость (импортируется в коде или указана в настройках),
**Т** — транзитивная (зависимость другой библиотеки), **D** — инструмент разработки.

| Пакет | Версия | Тип | Назначение / где используется |
|---|---|---|---|
| Django | 4.1.7 | П | Веб-фреймворк: ORM, URLconf, шаблоны, админка, auth (`config/settings.py:13-19`) |
| djangorestframework | 3.14.0 | П | REST API: `ModelViewSet`, `ModelSerializer`, `DefaultRouter`, `APITestCase` |
| django-filter | 22.1 | П | `FilterSet` для API (`dashboard/api/v1/views.py:10-13`) и `DEFAULT_FILTER_BACKENDS` (`config/settings.py:34`) |
| django-crispy-forms | 2.0 | П | Рендеринг форм (`{% load crispy_forms_tags %}`, `dashboard/templates/dashboard/create.html:8`) |
| crispy-bootstrap3 | 2022.1 | П | Шаблонный пакет Bootstrap 3 для crispy (`config/settings.py:28-29`) |
| celery | 5.2.7 | П | Фоновые задачи и Beat (`config/celery.py`, `dashboard/tasks.py`) |
| redis | 4.5.1 | П/Т | Python-клиент Redis; в проекте используется как брокер по URL (`config/settings.py:141`) |
| psycopg2-binary | 2.9.5 | П | Драйвер PostgreSQL (`config/settings.py:97`) |
| plotly | 5.13.1 | П | График цены в HTML (`dashboard/services/graph.py:3-4, 21-35`) |
| tinkoff-investments | 0.2.0b50 | П | Клиент Tinkoff Invest API, поставщик `tinkoff.invest` (`market_data.py:1`, `graph.py:5-6`, `add_shares.py:2`) |
| tinkoff | 0.1.1 | П | Устаревший клиент Tinkoff; конфликтует по namespace `tinkoff` с предыдущим (см. дефекты) |
| grpcio | 1.51.3 | Т | gRPC-транспорт для Tinkoff Invest API |
| protobuf | 3.20.3 | Т | Protobuf-сериализация сообщений gRPC |
| pydantic | 1.10.6 | Т | Валидация/модели данных в `tinkoff-investments` (v1 API) |
| cachetools | 5.3.0 | Т | Кэши (TTL/LRU) в `tinkoff-investments` |
| tenacity | 8.2.2 | Т | Повторные попытки (retry) в `tinkoff-investments` |
| python-dateutil | 2.8.2 | Т | Разбор дат в `tinkoff-investments` |
| pytz | 2022.7.1 | Т | Таймзоны (используется Django и `tinkoff`) |
| six | 1.16.0 | Т | Совместимость Py2/Py3 |
| asgiref | 3.6.0 | Т | ASGI/WSGI-мост Django |
| sqlparse | 0.4.3 | Т | Форматирование SQL в Django |
| amqp | 5.1.1 | Т | Протокол AMQP 0-9-1 (транспорт Kombu, альтернатива Redis из комментария `config/settings.py:140`) |
| kombu | 5.2.4 | Т | Абстракция обмена сообщениями Celery |
| billiard | 3.6.4.0 | Т | Форк `multiprocessing` для пула Celery |
| vine | 5.0.0 | Т | Promises/утилиты Celery |
| click | 8.1.3 | Т | CLI Celery (`celery -A config worker/beat`) |
| click-didyoumean | 0.3.0 | Т | Подсказки опечаток в CLI Celery |
| click-plugins | 1.1.1 | Т | Плагины CLI Celery |
| click-repl | 0.2.0 | Т | REPL-режим CLI Celery |
| prompt-toolkit | 3.0.38 | Т | Интерактивный ввод для `click-repl` |
| wcwidth | 0.2.6 | Т | Ширина символов для `prompt-toolkit` |
| async-timeout | 4.0.2 | Т | Таймауты asyncio (Redis-клиент) |
| typing_extensions | 4.5.0 | Т | Backport типов для зависимостей |
| black | 23.1.0 | D | Форматтер кода (в runtime-зависимостях — избыточно) |
| isort | 5.12.0 | D | Сортировка импортов (избыточно) |
| mypy-extensions | 1.0.0 | D | Типы для `black` / `mypy` |
| pathspec | 0.11.1 | D | gitignore-паттерны для `black` |
| platformdirs | 3.1.1 | D | Платформенные каталоги для `black` |
| packaging | 23.0 | D | Разбор версий (нужен `black`, `celery`) |
| tomli | 2.0.1 | D | Разбор TOML-конфигов (`black`/`isort`) на Python < 3.11 |

**Внешние сервисы (не Python-пакеты):**

| Сервис | Назначение | Конфигурация |
|---|---|---|
| PostgreSQL | основное хранилище | `config/settings.py:96-103`, `docker-compose.yml:3-14` |
| Redis | брокер Celery | `config/settings.py:141`, `docker-compose.yml:16-19` |
| Tinkoff Invest API (gRPC) | рыночные данные | `config/settings.py:134`, `dashboard/services/*` |
| CDN (plot.ly, code.jquery.com, cdnjs, stackpath) | JS/CSS фронтенда | `dashboard/templates/dashboard/base.html:10-24` |

---

## 5. Модель данных

### 5.1 Доменные модели приложения

**В приложении ровно одна модель — `Share`** (`dashboard/models.py:4-21`).
Модели `user` отсутствуют: `user/models.py:3` содержит не определение модели, а алиас
`User = get_user_model()` на стандартную `django.contrib.auth.models.User`.

#### `Share` (таблица `dashboard_share`) — «Акция»

| Поле | Тип Django | Параметры | Тип в PostgreSQL | verbose_name | Строка |
|---|---|---|---|---|---|
| `id` | `BigAutoField` | PK, auto | `bigint` | ID | `models.py` (неявно через `DEFAULT_AUTO_FIELD`, `config/settings.py:132`; в миграции — `0001_add_share.py:15-23`) |
| `figi` | `CharField(max_length=255)` | `unique=True`, NOT NULL | `varchar(255)` + UNIQUE | — | `models.py:7` |
| `isin` | `CharField(max_length=255)` | NOT NULL, **не unique** | `varchar(255)` | — | `models.py:8` |
| `name` | `CharField(max_length=255)` | NOT NULL | `varchar(255)` | «Наименование компании» | `models.py:9` |
| `ticker` | `CharField(max_length=10)` | `unique=True`, NOT NULL | `varchar(10)` + UNIQUE | «Тикер» | `models.py:10` |
| `currency` | `CharField(max_length=20)` | NOT NULL | `varchar(20)` | «Валюта» | `models.py:11` |
| `uid` | `CharField(max_length=255)` | `unique=True`, NOT NULL | `varchar(255)` + UNIQUE | — | `models.py:12` |
| `last_price` | `FloatField` | `null=True`, `blank=True` | `double precision` | «Текущая цена» | `models.py:13` |
| `is_trend_high` | `BooleanField` | `null=True`, `blank=True` | `boolean` | «Растет цена» | `models.py:14-16` |
| `updated_at` | `DateTimeField` | `auto_now=True`, `null=True`, `blank=True` | `timestamp with time zone` | — | `models.py:17` |

Метаданные (`models.py:19-21`): `verbose_name = "Акция"`, `verbose_name_plural = "Акции"`.
`Meta.ordering` **не задан** — сортировка `["name"]` задаётся только на уровне `ListView`
(`dashboard/views.py:26`).

Семантика полей:
- `figi` — идентификатор бумаги в Tinkoff (используется во всех запросах к API:
  `market_data.py:8`, `graph.py:15`);
- `uid` — внутренний UUID инструмента Tinkoff, добавлялся отдельной миграцией
  (`0003_add_uuid.py:12-17`), в API не отдаётся (отсутствует в `serializer.py:9-18`);
- `last_price` — цена, записанная Celery-задачей (`tasks.py:24-26`);
- `is_trend_high` — флаг «цена не упала относительно предыдущего замера», управляет цветом
  строки в UI (`list.html:35-40`);
- `updated_at` — `auto_now` (обновляется только при `save()`).

#### Связи

> **Важно:** приведённое ниже описывает **исходное** состояние проекта (до заданий №3–4).
> В задании №4 в модель данных добавлены внешние ключи — актуальная схема описана в разделе 8.

**Связей нет вообще:** ни `ForeignKey`, ни `ManyToManyField`, ни `OneToOneField`.
`Share` — изолированная таблица-справочник:

| Тип связи | Наличие | Подтверждение |
|---|---|---|
| FK (внешние ключи) | **отсутствуют** | `dashboard/models.py:4-21` — нет ни одного `ForeignKey`/`OneToOneField` |
| M2M (многие-ко-многим) | **отсутствуют** | `dashboard/models.py:4-21` — нет `ManyToManyField` |
| Связь `Share` ↔ `User` | **отсутствует** | у модели нет поля `user`/`owner`; список акций глобальный, один для всех пользователей (`views.py:23-26`) |
| Обратные связи (`related_name`) | **отсутствуют** | нечего связывать |

Практическое следствие: «добавить инструмент» означает изменение **общего** справочника,
доступного всем пользователям; понятия «мои акции» в модели данных нет.

### 5.2 Стандартные модели Django (создаются фреймворком)

Используются, но не объявлены в коде приложения (`INSTALLED_APPS`, `config/settings.py:14-19`):

| Модель | Приложение | Роль в проекте |
|---|---|---|
| `User` | `auth` | Пользователи регистрации/входа; `username` = e-mail (`user/forms.py:51`) |
| `Group`, `Permission` | `auth` | Не используются в коде (нет `permissions`/`groups`), но доступны через админку |
| `ContentType` | `contenttypes` | Инфраструктура разрешений и админки |
| `Session` | `sessions` | Сессии (middleware `config/settings.py:63`) |
| `LogEntry` | `admin` | История изменений в админке (`dashboard/admin.py:6-19`) |
| `Migration` | `migrations` | Служебная таблица применённых миграций |

`AUTH_USER_MODEL` не переопределён (`config/settings.py` не содержит этой настройки) —
используется стандартная `auth.User`.

### 5.3 Эволюция схемы (миграции)

| Миграция | Изменения |
|---|---|
| `0001_add_share.py:12-34` | Создание `Share`: `id`, `figi`, `isin`, `name`, `ticker`, `currency` |
| `0002_update_share.py:12-21` | `figi → unique`, `ticker → unique` |
| `0003_add_uuid.py:12-17` | Добавление `uid` (`unique`, `default=""`, `preserve_default=False`) |
| `0004_add_last_price.py:12-39` | Добавление `last_price`, `is_trend_high`; verbose_name для `currency`, `name`, `ticker` (в промежуточном состоянии — ошибочные «Валюта»/«Ти») |
| `0005_add_verbose_name.py:12-18` | Исправление `name` → «Наименование компании» |
| `0006_add_verbose_name.py:12-16` | Исправление `ticker` → «Тикер» |
| `0007_add_updated_at.py:12-16` | Добавление `updated_at` |

Итоговое состояние схемы совпадает с `models.py:4-21`. Замечание: поле `uid` вводилось
с `default=""` при `unique=True` (`0003_add_uuid.py:15`) — при наличии более одной строки
это привело бы к нарушению уникальности.

---

## 6. Механизмы обработки запросов и работы с БД

### 6.1 Типы обработчиков

| Механизм | Где | Особенности |
|---|---|---|
| Class-based views (HTML) | `dashboard/views.py:20-63` | `ListView`, `CreateView`, `UpdateView`, `DeleteView` — стандартные generic-вьюхи Django |
| «Ручной» `View` + `@staticmethod` | `dashboard/views.py:29-38`, `user/views.py:8-64` | `View.dispatch` вызывает `getattr(self, request.method.lower())(request, ...)`; статические методы работают, но лишают вьюху доступа к `self` (нельзя использовать `self.request`) |
| Миксин авторизации | `dashboard/views.py:11-17` | `UserPassesTestMixin` с переопределённым `handle_no_permission()` → `redirect("dashboard:index")` вместо редиректа на `/login/` |
| DRF ViewSet | `dashboard/api/v1/views.py:16-22` | `ModelViewSet` — 6 действий (list/create/retrieve/update/partial_update/destroy) одним классом |
| Management-команда | `dashboard/management/commands/add_shares.py:8-22` | `BaseCommand.handle`, запускается `python manage.py add_shares` |
| Celery-задача | `dashboard/tasks.py:7-28` | `@app.task`, запускается Beat'ом по расписанию |

### 6.2 Работа с ORM

Используемые конструкции:

| Конструкция | Место | SQL |
|---|---|---|
| `Model.objects.all()` | `dashboard/tasks.py:9`, `api/v1/views.py:18` | `SELECT * FROM dashboard_share` (в API — + `LIMIT/OFFSET`) |
| `ListView` + `ordering` | `dashboard/views.py:23-26` | `ORDER BY name ASC LIMIT 100 OFFSET ...` + `COUNT(*)` |
| `Model.objects.get(id=pk)` | `dashboard/views.py:32` | `SELECT ... WHERE id = %s LIMIT 21`; `DoesNotExist` не обрабатывается |
| `Model.objects.filter(id=...).update(...)` | `dashboard/tasks.py:24-26` | `UPDATE dashboard_share SET last_price=%s, is_trend_high=%s WHERE id = %s` — **без вызова `save()`**, поэтому `auto_now` не срабатывает |
| `Model.objects.get_or_create(**all_fields)` | `add_shares.py:15-22` | `SELECT` по всем 6 полям, при отсутствии — `INSERT` |
| `ModelForm` → `form.save()` | `dashboard/forms.py:6-11`, `views.py:41-55` | `INSERT`/`UPDATE` через `save()` (с `auto_now`) |
| `ModelSerializer` + `ModelViewSet` | `api/v1/serializer.py:6-18`, `views.py:16-22` | то же через DRF |
| `User.objects.create_user(...)` / `filter(email=...)` | `user/forms.py:39, 51` | `SELECT`/`INSERT` в `auth_user` |
| `authenticate()` / `login()` / `logout()` | `user/views.py:18, 23, 63` | чтение `auth_user`, запись/удаление сессии |

Соответствие модели и схемы: таблица `dashboard_share`, PK `id bigserial/bigint` (из `DEFAULT_AUTO_FIELD = BigAutoField`, `config/settings.py:132`), уникальные индексы по `figi`, `ticker`, `uid`.

### 6.3 Транзакции

- `ATOMIC_REQUESTS` **не включён** (`config/settings.py:91-104` — только `ENGINE/NAME/USER/PASSWORD/HOST/PORT`).
  Значит каждый запрос выполняется в autocommit-режиме; явных `transaction.atomic` в коде **нет**
  (ни одного `from django.db import transaction` в проекте).
- `tasks.py` изменяет записи по одной в цикле без общей транзакции (`tasks.py:11-28`):
  частичное обновление справочника является нормальным состоянием при падении worker'а.
- `add_shares.py:14-22` вставляет записи в цикле без транзакции: при ошибке на середине
  справочник остаётся частично загруженным.
- `get_or_create` не обёрнут в `atomic` вручную, но внутри использует `transaction.atomic`
  (поведение Django по умолчанию).

### 6.4 Фоновые задачи

| Аспект | Значение |
|---|---|
| Планировщик | Celery Beat, `config/celery.py:13-18` |
| Расписание | `{"add-every-5-min": {"task": "dashboard.tasks.update_last_price", "schedule": 10.0}}` — **ключ называет 5 минут, период равен 10 секундам** |
| Брокер | Redis `redis://127.0.0.1:6379/0` (`config/settings.py:141`) |
| Режим в тестах | `CELERY_TASK_ALWAYS_EAGER = False` (`config/settings.py:144`) |
| Таймзона | `CELERY_TIMEZONE = "Europe/Moscow"` (`config/settings.py:137`) при `TIME_ZONE = "UTC"` Django (`config/settings.py:124`) |
| Ограничение времени | `CELERY_TASK_TIME_LIMIT = 30*60` (`config/settings.py:139`) |
| Отслеживание | `CELERY_TASK_TRACK_STARTED = True` (`config/settings.py:138`) |
| Параллелизм внутри задачи | нет: цикл по всем акциям последовательно, с отдельным `Client` на каждую (`tasks.py:9-13`, `market_data.py:7`) |
| Идемпотентность | запись `last_price` идемпотентна; `is_trend_high` зависит от предыдущего значения, т.е. от порядка запусков |
| Обработка ошибок | широкие `try/except Exception` + логирование (`tasks.py:12, 20-22, 27-28`) — одна проблемная акция не прерывает остальные |

### 6.5 Обработка ошибок и коды ответов (фактически)

| Ситуация | Фактический результат | Причина |
|---|---|---|
| Несуществующий `pk` в HTML-карточке | **500** | `Share.objects.get()` без `get_object_or_404` (`views.py:32`) |
| Несуществующий `pk` в API | 404 | стандартное поведение DRF `ModelViewSet` |
| Аноним на `/create`, `/update/<pk>`, `/delete/<pk>` | 302 → `/` | `handle_no_permission` (`views.py:15-17`) |
| Аноним на `/` и `/<pk>` | 200 | авторизация не требуется |
| Ошибка Tinkoff API на карточке | 500 | нет `try/except` в `graph.py:11-36` |
| Пустой `email`/`password` в POST-входе | 500 (при отсутствии ключа) или сообщение об ошибке | прямое чтение `form.data[...]` (`user/views.py:19`) |
| Невалидный e-mail при регистрации | 500 | `form.errors["__all__"]` / `cleaned_data["email"]` (`user/views.py:54`, `user/forms.py:32`) |

### 6.6 Логирование

`LOGGING` (`config/settings.py:37-59`): единственный логгер `main`, уровень `INFO`,
два обработчика — `console` (`StreamHandler`) и `file` (`FileHandler`, файл `app.logs`
относительно рабочего каталога). Формат: `[{module} {asctime} {levelname}] {message}`.
Логгер импортируется как объект в модули: `from config.settings import logger`
(`dashboard/tasks.py:4`, `dashboard/services/market_data.py:3`).

События логирования: успешное получение цены (`market_data.py:10`, `INFO`),
ошибки в задаче (`tasks.py:21, 28`, `ERROR`). Логирование запросов/доступа не настроено.

### 6.7 Аутентификация и сессии

- Механизм — стандартный `django.contrib.auth`: `AuthenticationMiddleware`
  (`config/settings.py:66`) + `SessionMiddleware` (`:63`), сессии в БД (`django.contrib.sessions`).
- Пароли хранятся хешированными через `User.objects.create_user`
  (`user/forms.py:51` → `set_password`).
- Парольные валидаторы объявлены (`config/settings.py:106-119`), но при регистрации
  **не применяются**, т.к. `RegistrationForm` наследуется от `forms.Form`, а не от
  `UserCreationForm`/`SetPasswordForm` (`user/forms.py:8`).
- CSRF включён глобально (`config/settings.py:65`), токен вставляется в формы
  (`create.html:14`, `delete.html:10`, `auth.html:4`, `registration.html:5`).
- Выход выполняется GET-запросом (`user/views.py:61-64`, ссылка `dashboard/templates/dashboard/base.html:39`) —
  смена состояния без CSRF-токена.

---

## 7. Что изменено при модернизации (задание №3)

> Разделы 1–6 описывают **исходный** код. Ниже — дельта после модернизации.
> Полное обоснование, таблица версий и список исправленных дефектов — в `MODERNIZATION.md`.

### 7.1 Платформа и зависимости

| Область | Было | Стало |
|---|---|---|
| Python | 3.8–3.10 | 3.11+ (проверено на 3.12.14) |
| Django | 4.1.7 | 5.2.18 LTS |
| DRF / django-filter | 3.14.0 / 22.1 | 3.16.1 / 25.2 |
| Celery / redis | 5.2.7 / 4.5.1 | 5.5.3 / 6.4.0 |
| Драйвер БД | psycopg2-binary 2.9.5 | psycopg[binary] 3.3.6 |
| Plotly | 5.13.1 | 6.9.0 |
| Tinkoff SDK | `tinkoff` + `tinkoff-investments` в runtime | удалены из PyPI → опциональный `requirements-tinkoff.txt`, ленивый импорт |
| Фиксация версий | 40 пакетов, включая транзитивные | только прямые зависимости |

### 7.2 Конфигурация

| Настройка | Было | Стало |
|---|---|---|
| `SECRET_KEY` | `""` | переменная `DJANGO_SECRET_KEY`, dev-дефолт, запрет дефолта при `DEBUG=False` |
| `DEBUG` / `ALLOWED_HOSTS` | `True` / `[]` | `DJANGO_DEBUG` / список localhost + `DJANGO_ALLOWED_HOSTS` |
| `DATABASES` | жёстко PostgreSQL | SQLite по умолчанию, PostgreSQL при `DB_ENGINE=postgres` |
| `CELERY_BROKER_URL` | константа | переменная окружения |
| `TINKOFF_TOKEN` | `""` | переменная окружения |
| `STATIC_URL` | `"static/"` (без слэша) | `"/static/"` + `STATIC_ROOT` |
| Расписание Beat | ключ `add-every-5-min`, 10 с | ключ `update-last-price`, `PRICE_UPDATE_INTERVAL_SECONDS` (300 с) |
| Лог-файл | относительно CWD | `BASE_DIR / "app.logs"`, UTF-8 |
| Секреты | в коде | `.env.example`, только переменные окружения |

### 7.3 Код

| Модуль | Изменение |
|---|---|
| `dashboard/services/market_data.py` | ленивый импорт SDK, `quotation_to_float` (`units + nano/1e9`), защита от пустого ответа |
| `dashboard/services/graph.py` | ленивый импорт, точные цены, `include_plotlyjs=False`, легенда по тикеру |
| `dashboard/management/commands/add_shares.py` | `get_or_create` по `figi` + `defaults` (устранён `IntegrityError`) |
| `dashboard/tasks.py` | `save(update_fields=…)` вместо `.update()` (обновляется `updated_at`), явная обработка первого замера |
| `dashboard/views.py` | `get_object_or_404`, деградация карточки при недоступном Tinkoff API |
| `user/views.py`, `user/forms.py` | экземпляры форм вместо классов, `is_valid()`, безопасный разбор ошибок, нормализация e-mail, `validate_password` |
| шаблоны `detail.html`, `list.html` | `col-3`, блок ошибки графика, третье состояние индикатора (`None`) |
| `config/urls.py`, `config/celery.py`, `docker-compose.yml`, `.gitignore` | согласованность URL, расписание, том PostgreSQL, исключения VCS |

### 7.4 Результат проверки

`manage.py check` — без замечаний; `makemigrations --check` — изменений нет; `migrate` —
8 миграций применены; `runserver` поднялся и отдал `/` (200), `/api/v1/shares/` (200),
`/user/login/` (200, с `<input>`), `/admin/` (200), `/<pk>` (200 с сообщением о графике);
`manage.py test dashboard` — **33 теста, OK**.

---

## 8. Что добавлено в новой функциональности (задание №4)

> Реализовано направление «Виртуальный инвестиционный портфель» (п. 2 HOMEWORK.md).
> Требования — `FEATURE_REQUIREMENTS.md`, отчёт — `FEATURE_REPORT.md`.

### 8.1 Модель данных: было 1 модель, стало 4

| Модель | Назначение | Ключевые поля | Ограничения |
|---|---|---|---|
| `Share` | без изменений (справочник акций) | см. раздел 5.1 | `figi`, `ticker`, `uid` — UNIQUE |
| **`Portfolio`** (новая) | портфель пользователя | `owner` — FK → `auth.User` (CASCADE), `name` (100), `created_at`, `updated_at` | UNIQUE `(owner, name)` |
| **`Position`** (новая) | позиция по бумаге | `portfolio` — FK → `Portfolio` (CASCADE), `share` — FK → `Share` (PROTECT), `quantity` `Decimal(18,6)`, `avg_price` `Decimal(18,6)` | UNIQUE `(portfolio, share)`, CHECK `quantity >= 0` |
| **`Transaction`** (новая) | история операций | `portfolio` — FK (CASCADE), `share` — FK (PROTECT), `kind` (`buy`/`sell`), `quantity`, `price`, `realized_pnl` `Decimal(18,6)`, `executed_at`, `created_at` | сортировка `-executed_at, -id` |

**Появившиеся связи** (в исходной модели их не было вовсе):

```
auth.User 1 ──── N Portfolio 1 ──── N Position N ──── 1 Share
                        │
                        └──── N Transaction N ──── 1 Share
```

- `Portfolio.owner` → `auth.User`, `on_delete=CASCADE` (удаление пользователя удаляет портфели);
- `Position.portfolio` / `Transaction.portfolio` → `Portfolio`, `CASCADE`;
- `Position.share` / `Transaction.share` → `Share`, `PROTECT` (акцию нельзя удалить, пока по ней
  есть позиции или операции);
- M2M-связей по-прежнему нет.

Миграция: `dashboard/migrations/0008_portfolio_position_transaction_and_more.py`.

### 8.2 Новые слои

| Компонент | Файл | Содержание |
|---|---|---|
| Бизнес-логика | `dashboard/services/portfolio.py` | `execute_trade` (атомарная покупка/продажа, блокировка строки, средневзвешенная цена, реализованный P&L), `portfolio_summary` (стоимость, себестоимость, нереализованный/реализованный/суммарный P&L), `TradeError`, `to_decimal`, `share_price` |
| Сериализаторы | `dashboard/api/v1/portfolio_serializer.py` | `PortfolioSerializer`, `PositionSerializer`, `TransactionSerializer`, `TradeInputSerializer` |
| API | `dashboard/api/v1/portfolio_views.py` | `PortfolioViewSet` (`IsAuthenticated`, фильтр по владельцу) + действия `positions`, `transactions`, `summary`, `buy`, `sell` |
| Маршрут | `dashboard/api/v1/router.py` | `router.register(r"portfolios", …)` |
| Админка | `dashboard/admin.py` | `Portfolio` (+ inline позиций), `Position`, `Transaction` |
| Тесты | `dashboard/tests_portfolio.py` | 19 тестов |

### 8.3 Новые эндпоинты

`/api/v1/portfolios/` (CRUD) и действия `/{id}/positions/`, `/{id}/transactions/`,
`/{id}/summary/`, `/{id}/buy/`, `/{id}/sell/`. Все требуют аутентификации — в отличие от
публичного `/api/v1/shares/`, портфель является персональными данными.

### 8.4 Влияние на ранее описанное поведение

| Аспект из разделов 1–6 | Изменение |
|---|---|
| «Справочник акций глобальный, связи с пользователем нет» (раздел 5) | Появилась персональная сущность `Portfolio`, но сам `Share` по-прежнему не привязан к пользователю |
| «Транзакции в коде отсутствуют» (раздел 6.3) | В новом сервисе используются `@transaction.atomic` и `select_for_update` |
| «Celery не связан с HTTP-обработчиками» (раздел 3.3) | Не изменилось: портфель работает на уже сохранённых `last_price` |
| «Только один API-ресурс `shares`» (раздел 3.2) | Добавлен второй ресурс `portfolios` |
| Набор тестов (10) | 33 теста: 10 исходных + 4 регрессионных + 19 по портфелю и точности цен |
