# ANALYSIS.md — анализ проекта «Investing Demo»

## 1. Назначение и технологический стек

`Investing Demo` — учебное Django-приложение, справочник акций Московской биржи с данными из
**Tinkoff Invest API**. Реализовано: просмотр списка бумаг, карточка с ценой и графиком за 180 дней,
CRUD справочника для авторизованных пользователей, REST API, регистрация/вход/выход, фоновая задача
обновления котировок, индикатор направления цены.

Приложения портфеля, сделок, списков наблюдения, истории цен и уведомлений в исходной версии не было;
внешний API использовался только на чтение (`get_last_prices`, `get_all_candles`,
`instruments.shares`).

Стек определяется по `requirements.txt`, `manage.py` и `config/settings.py`:

| Слой | Технология | Откуда видно |
|---|---|---|
| Язык | Python 3.x (исходно 3.8–3.10, в зависимостях был `tomli`) | `manage.py`, f-strings в сервисах |
| Фреймворк | Django 4.1.7, паттерн MVT, class-based views | `requirements.txt`, `INSTALLED_APPS`, `ROOT_URLCONF` |
| API | Django REST Framework 3.14 + django-filter | `rest_framework`, `django_filters` в `INSTALLED_APPS`, `ModelViewSet` |
| БД | PostgreSQL (`psycopg2-binary`) | `DATABASES` в `config/settings.py` |
| Задачи | Celery 5.2.7 + Redis | `config/celery.py`, `CELERY_BROKER_URL` |
| Внешний API | Tinkoff Invest (gRPC: `grpcio`, `protobuf`) | импорты `tinkoff.invest` в `dashboard/services/*` |
| Графики | Plotly 5.13.1 (`output_type="div"`) | `dashboard/services/graph.py` |
| Формы/UI | django-crispy-forms + crispy-bootstrap3, Bootstrap с CDN | `config/settings.py`, `dashboard/templates/**` |
| Точка входа | `manage.py` → `config.settings` | `manage.py` |

## 2. Структура проекта

```
manage.py                     CLI Django, задаёт config.settings
requirements.txt              40 пинов (прямые + транзитивные)
config/                       проектный пакет
  settings.py                 приложения, БД, DRF, crispy, LOGGING, Tinkoff-токен, Celery
  urls.py                     admin/, dashboard, user
  celery.py                   экземпляр Celery + beat_schedule
  wsgi.py, asgi.py            точки входа WSGI/ASGI
  __init__.py                 реэкспорт celery_app
dashboard/                    доменное приложение: справочник акций
  models.py                   Share
  views.py                    List/Detail/Create/Update/Delete + mixin авторизации
  urls.py                     app_name="dashboard"
  forms.py                    ShareModelForm (fields = "__all__")
  admin.py                    регистрация Share
  tasks.py                    update_last_price
  tests.py                    10 API-тестов
  services/market_data.py     get_last_data — последняя цена
  services/graph.py           get_graph — свечи 180 дней → Plotly div
  management/commands/add_shares.py   импорт справочника
  migrations/0001…0007        эволюция схемы Share
  api/v1/                     router, views (ShareViewSet), serializer
  templates/dashboard/        base, list, detail, create, delete
  static/dashboard/css/       bootstrap.min.css, sticky-footer-navbar.css
user/                         аутентификация
  models.py                   не модель, а алиас get_user_model()
  forms.py                    RegistrationForm, AuthForm
  views.py                    AuthView, RegistrationView, LogoutView
  urls.py                     login/, registration/, logout/
  templates/user/             base, auth, registration
```

Связи между пакетами:

- `config` — композиционный корень: объявляет приложения (`INSTALLED_APPS`), корневой URLconf и
  шаблонные каталоги (`APP_DIRS=True`). Из приложений он ничего не импортирует.
- `dashboard` → `config` (обратная зависимость): сервисы и задача импортируют `config.settings`
  (`TINKOFF_TOKEN`, `logger`) и `config.celery.app`. Формально это нарушает направление
  зависимостей, но так было задумано авторами.
- `user` → `dashboard` только через имя маршрута `dashboard:index`; обратно — через
  `request.user.is_authenticated` в шаблонах и mixin'е.

## 3. Архитектура и взаимодействие компонентов

Путь HTTP-запроса (сценарий «список акций»):

1. `config/urls.py` монтирует `dashboard.urls` на пустой префикс.
2. `dashboard/urls.py` сопоставляет `""` → `ShareListView`.
3. Middleware: security → session → common → csrf → auth → messages → clickjacking.
4. `ShareListView` (`ListView`) с `model = Share`, `paginate_by = 100`, `ordering = ["name"]`.
5. Шаблон `dashboard/list.html`; ORM выполняет `SELECT … ORDER BY name LIMIT 100` (+ `COUNT(*)`).
6. `psycopg2` → PostgreSQL `investing` на `localhost:5432`.

Карточка акции (`/<int:pk>`) дополнительно ходит во внешний API: `get_graph(share)` открывает
`Client(TINKOFF_TOKEN)`, тянет дневные свечи за 180 дней и превращает их в Plotly-`<div>`, который
вставляется в шаблон через `{% autoescape off %}`.

REST-путь: `config.urls` → `dashboard.urls` (`api/`) → `api/urls.py` (`v1/`) → `api/v1/urls.py`
(`router.urls`) → `ShareViewSet` → `ShareSerializer`. Пагинация `LimitOffsetPagination`, размер 100.

Celery используется отдельно от HTTP: Beat по расписанию ставит `dashboard.tasks.update_last_price`,
worker обходит все акции, запрашивает последнюю цену и пишет её в БД. Ни один HTTP-обработчик задачи
в очередь не ставит.

## 4. Зависимости

Прямые: `Django`, `djangorestframework`, `django-filter`, `django-crispy-forms`,
`crispy-bootstrap3`, `plotly`, `celery`, `redis`, `psycopg2-binary`, `tinkoff`,
`tinkoff-investments`. Остальные 29 записей — транзитивные (`kombu`, `billiard`, `vine`, `amqp`,
`click*`, `prompt-toolkit`, `wcwidth`, `asgiref`, `sqlparse`, `grpcio`, `protobuf`, `pydantic`,
`cachetools`, `tenacity`, `python-dateutil`, `pytz`, `six`, `async-timeout`, `typing_extensions`) и
инструменты разработки (`black`, `isort`, `mypy-extensions`, `pathspec`, `platformdirs`, `tomli`,
`packaging`).

Проблемы, видимые уже на этом этапе: пакеты `tinkoff` и `tinkoff-investments` делят один namespace
`tinkoff`; инструменты разработки попали в runtime; все транзитивные зависимости зафиксированы
вручную.

## 5. Модель данных

Единственная доменная модель — `Share` (таблица `dashboard_share`):

| Поле | Тип | Свойства |
|---|---|---|
| `id` | `BigAutoField` | PK |
| `figi` | `CharField(255)` | unique, NOT NULL |
| `isin` | `CharField(255)` | NOT NULL, без unique |
| `name` | `CharField(255)` | NOT NULL, verbose_name «Наименование компании» |
| `ticker` | `CharField(10)` | unique, NOT NULL, «Тикер» |
| `currency` | `CharField(20)` | NOT NULL, «Валюта» |
| `uid` | `CharField(255)` | unique, NOT NULL |
| `last_price` | `FloatField` | null/blank, «Текущая цена» |
| `is_trend_high` | `BooleanField` | null/blank, «Растет цена» |
| `updated_at` | `DateTimeField` | `auto_now=True`, null/blank |

`Meta`: `verbose_name = "Акция"`, без `ordering`.

**Связей нет:** ни `ForeignKey`, ни `ManyToManyField`, ни `OneToOneField`. Справочник глобальный —
понятия «мои акции» в модели данных нет. `user/models.py` — не модель, а алиас
`User = get_user_model()` на `django.contrib.auth.models.User`; собственных миграций у приложения
`user` нет.

Стандартные модели (`auth.User`, `Group`, `Permission`, `Session`, `ContentType`, `LogEntry`)
создаются фреймворком; `AUTH_USER_MODEL` не переопределён.

Миграции `0001`–`0007` последовательно добавляют поля и ограничения; итоговое состояние совпадает с
`models.py`.

## 6. Механизмы обработки запросов и работы с БД

Обработчики: generic CBV (`ListView`, `CreateView`, `UpdateView`, `DeleteView`), «ручные» `View` с
`@staticmethod` (`ShareDetailView`, `AuthView`, `RegistrationView`, `LogoutView`), `ModelViewSet` для
API, management-команда, Celery-задача.

Авторизация: `IsUserAuthenticatedMixin` (`UserPassesTestMixin`) закрывает create/update/delete;
у `handle_no_permission` переопределён на редирект на главную. Список и карточка — публичные.

ORM: `objects.all()`, `objects.get(id=…)`, `objects.filter(...).update(...)`,
`objects.get_or_create(**все_поля)`, `ModelForm.save()`, DRF `ModelSerializer`.

Транзакции: `ATOMIC_REQUESTS` не включён, явных `transaction.atomic` нет; задача и команда импорта
пишут по одной записи без общей транзакции.

Фоновые задачи: Beat с расписанием `10.0` секунд, брокер Redis, `CELERY_TASK_ALWAYS_EAGER = False`.
Задача перебирает все акции последовательно, открывая отдельный `Client` на каждую, и пишет
результат через `QuerySet.update()`.

Обработка ошибок: широкие `try/except` в задаче; в представлениях и сервисах обработки нет —
отсутствующий `pk` и недоступный внешний API дают HTTP 500.

Логирование: логгер `main`, консоль + файл `app.logs` (путь относительно CWD).

---

## 7. Что изменено

### 7.1 Платформа

| Область | Было | Стало |
|---|---|---|
| Python | 3.8–3.10 | 3.11+ (проверено на 3.12.14) |
| Django | 4.1.7 | 5.2.18 (LTS) |
| DRF / django-filter | 3.14.0 / 22.1 | 3.16.1 / 25.2 |
| Celery / redis | 5.2.7 / 4.5.1 | 5.5.3 / 6.4.0 |
| Драйвер БД | psycopg2-binary 2.9.5 | psycopg[binary] 3.3.6 |
| Plotly | 5.13.1 | 6.9.0 |
| Tinkoff SDK | два пакета в runtime, конфликт namespace | удалены из PyPI → `requirements-tinkoff.txt` + ленивый импорт |
| Состав requirements | 40 пинов, включая транзитивные и dev-инструменты | 9 прямых пинов + `requirements-dev.txt` |

### 7.2 Конфигурация

`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DATABASES`, `CELERY_BROKER_URL`, `TINKOFF_TOKEN` переехали
в переменные окружения (с dev-значениями по умолчанию и `.env.example`). SQLite стал БД по
умолчанию, PostgreSQL включается `DB_ENGINE=postgres`. `STATIC_URL` получил ведущий слэш, лог-файл
привязан к `BASE_DIR`, расписание Beat стало настраиваемым (по умолчанию 300 с вместо 10 с).
`docker-compose.yml` использует именованный том вместо монтирования проекта поверх `PGDATA`.

Причина, по которой эти правки стояли первыми: приложение вообще не запускалось — сначала
`ImproperlyConfigured` на драйвере PostgreSQL, затем `ModuleNotFoundError: tinkoff`.

### 7.3 Код

| Модуль | Изменение |
|---|---|
| `dashboard/services/market_data.py` | ленивый импорт SDK, `quotation_to_float` (`units + nano/1e9`), защита от пустого ответа |
| `dashboard/services/graph.py` | ленивый импорт, точные цены, `include_plotlyjs=False`, легенда по тикеру |
| `dashboard/management/commands/add_shares.py` | `get_or_create` по `figi` + `defaults` (устранён `IntegrityError`) |
| `dashboard/views.py` | `get_object_or_404`; карточка не падает при недоступном API |
| `dashboard/tasks.py` | `save(update_fields=…)` вместо `.update()` (обновляется `updated_at`), явная обработка первого замера |
| `user/views.py` | экземпляры форм вместо классов, `is_valid()`, безопасный разбор ошибок |
| `user/forms.py` | `.get()` вместо `[]`, нормализация e-mail, `validate_password` |
| `dashboard/templates/dashboard/*.html` | `col-3`, третье состояние индикатора, блок ошибки графика |
| `config/urls.py`, `config/celery.py`, `docker-compose.yml`, `.gitignore` | согласованность URL, расписание, том PostgreSQL, исключения VCS |

Подробный список с обоснованием — в `MODERNIZATION.md`.

### 7.4 Результат

`manage.py check` — без замечаний; `makemigrations --check` — изменений нет; `migrate` — применены
все миграции; `runserver` отдал `/`, `/api/v1/shares/`, `/user/login/`, `/admin/` со статусом 200;
`manage.py test dashboard` — **33 теста, OK**.

---

## 8. Что добавлено

### 8.1 Модель данных: было 1 модель, стало 4

| Модель | Назначение | Ключевые поля | Ограничения |
|---|---|---|---|
| `Share` | без изменений | см. раздел 5 | `figi`, `ticker`, `uid` — unique |
| **`Portfolio`** | портфель пользователя | `owner` (FK → `auth.User`, CASCADE), `name`, метки времени | UNIQUE `(owner, name)` |
| **`Position`** | позиция по бумаге | `portfolio` (FK, CASCADE), `share` (FK → `Share`, PROTECT), `quantity`, `avg_price` | UNIQUE `(portfolio, share)`, CHECK `quantity >= 0` |
| **`Transaction`** | история операций | `portfolio`, `share` (PROTECT), `kind`, `quantity`, `price`, `realized_pnl`, `executed_at` | сортировка `-executed_at, -id` |

**Появившиеся связи** (в исходной модели их не было вовсе):

```
auth.User 1 ─── N Portfolio 1 ─── N Position N ─── 1 Share
                        │
                        └──────── N Transaction N ─── 1 Share
```

`Position.share` и `Transaction.share` — `PROTECT`: пока по бумаге есть позиции или операции, удалить
её из справочника нельзя. M2M-связей по-прежнему нет.

### 8.2 Новые слои

| Компонент | Файл |
|---|---|
| Бизнес-логика (сделки, сводка, `TradeError`) | `dashboard/services/portfolio.py` |
| Сериализаторы | `dashboard/api/v1/portfolio_serializer.py` |
| `PortfolioViewSet` с действиями `positions`/`transactions`/`summary`/`buy`/`sell` | `dashboard/api/v1/portfolio_views.py` |
| Маршрут `/api/v1/portfolios/` | `dashboard/api/v1/router.py` |
| Админка (Portfolio + inline позиций, Position, Transaction) | `dashboard/admin.py` |
| Миграция | `dashboard/migrations/0008_portfolio_position_transaction_and_more.py` |
| Тесты (19) | `dashboard/tests_portfolio.py` |
| Документы | `FEATURE_REQUIREMENTS.md`, `FEATURE_REPORT.md`, `MODERNIZATION.md` |

### 8.3 Влияние на ранее описанное поведение

| Утверждение из разделов 1–6 | Что изменилось |
|---|---|
| «Справочник глобальный, связи с пользователем нет» | Появилась персональная сущность `Portfolio`; сам `Share` по-прежнему не привязан к пользователю |
| «Транзакций в коде нет» | В новом сервисе используются `transaction.atomic` и `select_for_update` |
| «Celery не связан с HTTP-обработчиками» | Не изменилось: портфель считает стоимость по уже сохранённым `last_price` |
| «Один API-ресурс — `shares`» | Добавлен второй ресурс — `portfolios` |
| «10 тестов» | 33 теста: 10 исходных + 4 регрессионных + 19 по портфелю и точности цен |
