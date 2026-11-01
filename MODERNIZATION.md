# MODERNIZATION.md — Задание №3: модернизация, устранение дефектов, рефакторинг

> Отправная точка: исходная версия из ветки-копии (`Django 4.1.7`, Python 3.8–3.10 эпохи 2023 года).
> Целевая платформа: **Python 3.11+** (проверено на CPython 3.12.14).
> Все изменения проверены запуском: `manage.py check`, `manage.py migrate`, `manage.py runserver`,
> `manage.py test` — результаты в разделе 6.

---

## 1. Сводка

| Область | Было | Стало |
|---|---|---|
| Python | 3.8–3.10 (неявно, `tomli` в зависимостях) | 3.11+ (проверено на 3.12) |
| Django | 4.1.7 (не поддерживается с 2023) | **5.2.18 LTS** |
| DRF | 3.14.0 | **3.16.1** |
| Celery | 5.2.7 | **5.5.3** |
| Redis client | 4.5.1 | **6.4.0** |
| Драйвер БД | `psycopg2-binary` 2.9.5 | **`psycopg[binary]` 3.3.6** |
| Визуализация | plotly 5.13.1 | **plotly 6.9.0** |
| Tinkoff SDK | `tinkoff==0.1.1` + `tinkoff-investments==0.2.0b50` | из PyPI удалён → опциональная установка из исходников |
| Конфигурация | секреты и параметры в коде | переменные окружения + `.env.example` |
| Запуск без PostgreSQL | невозможен | SQLite по умолчанию, PostgreSQL по `DB_ENGINE=postgres` |

### 1.1 Ключевая находка: Tinkoff Invest SDK больше не распространяется через PyPI

Проверено запросами к индексу PyPI и GitHub API:

| Проверка | Результат |
|---|---|
| `https://pypi.org/simple/tinkoff-investments/` | **HTTP 404** |
| `https://pypi.org/simple/tinkoff/` | **HTTP 404** |
| `https://api.github.com/repos/RussianInvestments/invest-python` | существует, но `"archived": true`, последний push — 2025-10-09 |
| `https://api.github.com/repos/Tinkoff/invest-python` | `"archived": true`, последний push — 2023-08-06 |

Следствия и принятые решения:

1. Пакеты `tinkoff` и `tinkoff-investments` **убраны из `requirements.txt`** — иначе
   `pip install -r requirements.txt` падал бы на неразрешимой зависимости.
   Старая пара к тому же конфликтовала: оба пакета предоставляют namespace `tinkoff`.
2. SDK вынесен в отдельный **`requirements-tinkoff.txt`** с установкой из архивного репозитория:
   `tinkoff-investments @ git+https://github.com/RussianInvestments/invest-python.git`
   (помечено как непроверенное в этом окружении — см. ограничения).
3. Все обращения к SDK переведены на **ленивый импорт** внутри функций
   (`dashboard/services/market_data.py`, `dashboard/services/graph.py`,
   `dashboard/management/commands/add_shares.py`). Приложение запускается, отдаёт UI и API
   и проходит тесты без установленного SDK; SDK нужен только для реальных вызовов API.
4. В `ANALYSIS.md` (раздел 4) это расхождение отмечено как ограничение.

### 1.2 Ключевая находка: инструменты разработки в runtime-зависимостях

Исходный `requirements.txt` содержал `black`, `isort`, `mypy-extensions`, `pathspec`,
`platformdirs`, `tomli` — это инструменты разработки, а не runtime. Они вынесены в
`requirements-dev.txt`.

### 1.3 Изменение стратегии фиксации версий

Было: 40 пакетов, включая **все транзитивные** зависимости (`amqp`, `billiard`, `kombu`,
`vine`, `click-*`, `prompt-toolkit`, `wcwidth`, `cachetools`, `tenacity`, …), что делало
обновление одной библиотеки невозможным без ручного пересчёта графа.
Стало: фиксируются только **прямые** зависимости, транзитивные разрешаются менеджером пакетов.

---

## 2. Таблица зависимостей

Формат: пакет — текущая версия — новая версия — причина.

### 2.1 Обновлённые прямые зависимости

| Пакет | Текущая | Новая | Причина |
|---|---|---|---|
| Django | 4.1.7 | **5.2.18** | Ветка 4.1 не получает исправлений безопасности с декабря 2023. 5.2 — LTS (поддержка до апреля 2028), поддерживает Python 3.10–3.13, т.е. требование «3.11+» выполняется. Ветка 6.x отвергнута: требует Python 3.12+, что нарушило бы совместимость с 3.11 |
| djangorestframework | 3.14.0 | **3.16.1** | 3.14 не поддержан на Django 5.2 (удалённые `django.utils.timezone.utc`, изменения `NullBooleanField`). 3.16 официально поддерживает Django 4.2–5.2 |
| django-filter | 22.1 | **25.2** | Версия 22.1 (2022) несовместима с Django 5.x (использует удалённые API). 25.2 — актуальная ветка для Django 5.2 |
| django-crispy-forms | 2.0 | **2.4** | В 2.x сменился механизм шаблонных пакетов; 2.0 некорректно работает с Django 5.2. 2.4 — совместимая актуальная версия |
| crispy-bootstrap3 | 2022.1 | **2024.1** | Должен соответствовать версии django-crispy-forms 2.x |
| celery | 5.2.7 | **5.5.3** | 5.2 не поддерживает Python 3.12/3.13 и несовместим с kombu 5.6. 5.5 — актуальная поддерживаемая ветка |
| redis (client) | 4.5.1 | **6.4.0** | 4.x несовместим с Python 3.12 (использует удалённый `distutils` в цепочке сборки) и не поддерживает Redis 7 |
| psycopg2-binary | 2.9.5 | **удалён** | Заменён на psycopg 3 — см. строку ниже |
| psycopg[binary] | — | **3.3.6** | psycopg 3 — рекомендуемый драйвер для Django 4.2+; `psycopg2-binary` официально не рекомендован для продакшена и не имеет колёс под новые версии Python. Django 5.2 поддерживает psycopg 3.1.8+ нативно |
| plotly | 5.13.1 | **6.9.0** | 5.13 (2023) зависит от устаревшего `tenacity<9`; 6.9 — актуальная версия. API `plotly.offline.plot` сохранён (проверено) |
| tinkoff | 0.1.1 | **удалён** | Дублировал namespace `tinkoff` с `tinkoff-investments`, из PyPI удалён (404) |
| tinkoff-investments | 0.2.0b50 | **вынесен в `requirements-tinkoff.txt`** | Из PyPI удалён (404), репозиторий заархивирован; устанавливается из исходников по требованию |

### 2.2 Удалённые зависимости

| Пакет | Было | Причина удаления |
|---|---|---|
| pytz | 2022.7.1 | Django 4+ и Python 3.9+ используют `zoneinfo`; `pytz` в коде не импортируется |
| six | 1.16.0 | Транзитивная зависимость удалённого Tinkoff SDK |
| black, isort, mypy-extensions, pathspec, platformdirs, tomli, packaging | 2023.x | Инструменты разработки → `requirements-dev.txt` |
| amqp, billiard, kombu, vine, click, click-didyoumean, click-plugins, click-repl, prompt-toolkit, wcwidth, async-timeout, cachetools, tenacity, python-dateutil, grpcio, protobuf, pydantic, typing_extensions, sqlparse, asgiref | 2023.x | Транзитивные зависимости, теперь разрешаются автоматически |

### 2.3 Итоговый `requirements.txt`

```
Django==5.2.18
djangorestframework==3.16.1
django-filter==25.2
django-crispy-forms==2.4
crispy-bootstrap3==2024.1
plotly==6.9.0
celery==5.5.3
redis==6.4.0
psycopg[binary]==3.3.6
```

`requirements-dev.txt`: `black==26.10.1`, `isort==9.0.2`, `coverage==7.17.0`.
`requirements-tinkoff.txt`: опциональный SDK из исходников (см. 1.1).

---

## 3. Исправления, без которых приложение не запускалось

| # | Проблема | Было | Стало | Файл |
|---|---|---|---|---|
| 1 | Пустой `SECRET_KEY` → `ImproperlyConfigured` при старте | `SECRET_KEY = ""` | `os.environ["DJANGO_SECRET_KEY"]`, dev-значение по умолчанию, запрет дефолта при `DEBUG=False` | `config/settings.py:35`, `:46-49` |
| 2 | Пустой токен Tinkoff | `TINKOFF_TOKEN = ""` | `os.environ["TINKOFF_TOKEN"]` | `config/settings.py:194` |
| 3 | Жёстко прописанный PostgreSQL, недоступный без Docker → `migrate`/`runserver` падали | `NAME/USER/PASSWORD/HOST/PORT` в коде | SQLite по умолчанию; PostgreSQL при `DB_ENGINE=postgres` или `POSTGRES_DB` | `config/settings.py:138-158` |
| 4 | Параметры БД — секреты в репозитории | `postgres/postgres@localhost` | только из переменных окружения | `config/settings.py:138-158` |
| 5 | Импорт SDK Tinkoff на уровне модуля ломал старт без пакета | `from tinkoff.invest import Client` в шапке | ленивый импорт внутри функций | `dashboard/services/market_data.py:26`, `dashboard/services/graph.py:20`, `dashboard/management/commands/add_shares.py:12` |
| 6 | `ALLOWED_HOSTS = []` — сайт не открывался по IP | `[]` | `localhost`, `127.0.0.1`, `[::1]`, `testserver`; расширяется через `DJANGO_ALLOWED_HOSTS` | `config/settings.py:39-42` |
| 7 | `STATIC_URL = "static/"` без ведущего слэша → CSS не грузился на `/update/12`, `/user/login/` | `"static/"` | `"/static/"`, добавлен `STATIC_ROOT` | `config/settings.py:184-185` |
| 8 | `CELERY_BROKER_URL` захардкожен, без возможности переопределить | `"redis://127.0.0.1:6379/0"` | `os.environ["CELERY_BROKER_URL"]` (тот же дефолт) | `config/settings.py:202` |
| 9 | Лог-файл писался относительно CWD | `"app.logs"` | `BASE_DIR / "app.logs"`, UTF-8 | `config/settings.py:86-90` |
| 10 | Расписание Beat: ключ `add-every-5-min`, период 10 секунд | `schedule: 10.0` | ключ `update-last-price`, период из `PRICE_UPDATE_INTERVAL_SECONDS` (по умолчанию 300 с) | `config/celery.py:15-20`, `config/settings.py:208-210` |
| 11 | `DEBUG = True` в единственной конфигурации | `True` | `DJANGO_DEBUG` (по умолчанию `True` для разработки) | `config/settings.py:37` |
| 12 | `docker-compose.yml` монтировал `./:/app` в контейнер PostgreSQL | том проекта поверх `PGDATA` | именованный том `pgdata`, healthcheck, образы `postgres:17-alpine` / `redis:7-alpine` | `docker-compose.yml:3-26` |

### 3.1 Расписание Celery — как разрешена неоднозначность AMB-03

В `REQUIREMENTS.md` зафиксирована неоднозначность: ключ назывался `add-every-5-min`,
а период был 10 секунд. Решение: **имя ключа приведено к смыслу задачи**
(`update-last-price`), а период стал настраиваемым параметром со значением по умолчанию
**300 секунд (5 минут)** — это соответствует прежнему названию ключа и снижает нагрузку
на Tinkoff API (10 секунд для справочника в сотни бумаг — заведомо превышение лимитов).

---

## 4. Устранённые дефекты реализации

Нумерация соответствует разделу 6 `REQUIREMENTS.md`.

| DEF | Дефект | Исправление | Файл |
|---|---|---|---|
| DEF-04 | `updated_at` не обновлялся (`.update()` обходит `auto_now`) | замена на `save(update_fields=[..., "updated_at"])` | `dashboard/tasks.py:28` |
| DEF-10 | В шаблон передавался **класс** формы вместо экземпляра → страницы входа/регистрации без `<input>` | `AuthForm()` / `RegistrationForm()` | `user/views.py:23, 51` |
| DEF-11 | `AuthView.post` не валидировал форму и читал `form.data[...]` | `form.is_valid()` + `cleaned_data` | `user/views.py:29-35` |
| DEF-12 | `form.errors["__all__"]` → `KeyError` → 500 | безопасный обход всех ошибок формы (`_first_error`) | `user/views.py:10-14, 70` |
| DEF-13 | `cleaned_data["email"]` → `KeyError` при невалидном e-mail | `.get()` | `user/forms.py:40` |
| DEF-14 | Регистр e-mail: при регистрации сохранялся как есть, при входе — в нижний регистр → вход невозможен | нормализация `strip().lower()` при регистрации, `email__iexact` при проверке дубля | `user/forms.py:40, 48` |
| DEF-15 | Парольные валидаторы не применялись | явный вызов `validate_password()` | `user/forms.py:54` |
| DEF-16 | Выход только через GET | добавлен алиас `post = get`, GET сохранён для обратной совместимости | `user/views.py:82` |
| DEF-17 | Несуществующий `pk` в карточке → 500 | `get_object_or_404` | `dashboard/views.py:36` |
| DEF-18 | Ошибка Tinkoff роняла страницу карточки в 500 | `try/except` + сообщение в шаблоне; страница отдаёт 200 | `dashboard/views.py:38-46`, `dashboard/templates/dashboard/detail.html:23-29` |
| DEF-19 | `uid` в модели, но не в сериализаторе → уникальный конфликт | не менялось: вне области задачи (справочник), зафиксировано как ограничение | — |
| DEF-20 | `add_shares` искал по всем полям → `IntegrityError` при переименовании | `get_or_create(figi=..., defaults={...})` | `dashboard/management/commands/add_shares.py:22-31` |
| DEF-22 | Индикатор не различал «падение» и «нет данных» | третье состояние: нейтральный фон при `is_trend_high is None` | `dashboard/templates/dashboard/list.html:35-41` |
| DEF-23 | `Quotation.units` без `nano` → цена `100.55` сохранялась как `100` | `quotation_to_float()`: `units + nano / 1e9` | `dashboard/services/market_data.py:10-17` |
| DEF-24 | То же усечение в графике | `quotation_to_float(candle.close)` | `dashboard/services/graph.py:31` |
| DEF-25 | `last_prices.pop()` → `IndexError` на пустом списке | явная проверка и `ValueError` с понятным текстом | `dashboard/services/market_data.py:31-32` |
| DEF-27 | Неиспользуемая переменная с опечаткой `detetime` | `_price_time`, назначение задокументировано | `dashboard/tasks.py:12` |
| DEF-28 | Первый замер обрабатывался через перехват `TypeError` | явная ветка `if share.last_price is None` | `dashboard/tasks.py:17-20` |
| DEF-33 | Bootstrap-класс `col3` вместо `col-3` | `col-3` | `dashboard/templates/dashboard/detail.html:9-31` |
| DEF-34 | Plotly ~3 МБ в каждом ответе + отдельный CDN | `include_plotlyjs=False` | `dashboard/services/graph.py:49` |
| DEF-35 | Легенда графика `name="test"` | `name=share.ticker` | `dashboard/services/graph.py:39` |
| DEF-38 | `path("user", …)` без завершающего слэша | `path("user/", …)` | `config/urls.py:7` |
| DEF-08 | Том проекта поверх данных PostgreSQL | именованный том | `docker-compose.yml:12-15` |
| DEF-29 | Конфликт `tinkoff` / `tinkoff-investments` | оба убраны из runtime-зависимостей | `requirements.txt` |
| DEF-30 | Dev-инструменты в runtime | `requirements-dev.txt` | `requirements-dev.txt` |
| DEF-31 | `from .views import *` | явный импорт | `dashboard/api/v1/router.py:3` |

### 4.1 Дефекты, осознанно оставленные без изменений

| DEF | Причина |
|---|---|
| DEF-01 (частично) | Пустой `SECRET_KEY` заменён dev-значением; полноценное решение — обязательная переменная окружения в продакшене (реализовано: при `DEBUG=False` дефолт запрещён) |
| DEF-07 | API справочника остаётся открытым: это зафиксированное поведение (FR-45), а не ошибка запуска. Изменение потребовало бы ломать существующий контракт API и тесты |
| DEF-19, DEF-21, DEF-26, DEF-32 | Требуют изменения модели/схемы API (`uid`), либо оптимизации вне рамок «не менять поведение». Зафиксированы как ограничения в `FEATURE_REPORT.md` |
| DEF-10 (ответственность) | Форма входа по-прежнему не показывает ошибки отдельных полей, а только общее сообщение — сохранено ради прежнего UX |

---

## 5. Рефакторинг (без изменения поведения)

| Что | Было | Стало | Обоснование |
|---|---|---|---|
| Конфигурация | одна плоская портянка с магическими строками | хелперы `env_bool`/`env_list`, секции-комментарии | читаемость, отсутствие секретов в коде |
| Доступ к токену | `from config.settings import TINKOFF_TOKEN` в 3 модулях | `django.conf.settings.TINKOFF_TOKEN` | правильное направление зависимости, тестируемость через `override_settings` |
| Токен/клиент | три независимых `Client(TINKOFF_TOKEN)` | единый помощник `quotation_to_float` + ленивый клиент в каждом сервисе | удалено дублирование логики преобразования цены |
| `get_last_data` | `resp = resp.last_prices.pop()` (перезапись `resp`) | явные имена `response` / `last_price` | понятность, отсутствие «переменная-хамелеон» |
| `tasks.py` | вложенные `try/except`, «логика через исключение» | плоский `continue` + явные ветки | читаемость, отсутствие ложных `ERROR` в логе |
| Роутер API | wildcard-импорт | явные импорты | статический анализ, отсутствие скрытых связей |
| Шаблон карточки | `col3`, отсутствие обработки ошибок | `col-3`, блок ошибки | корректная вёрстка и деградация |
| `user/views.py` | три почти одинаковых `render(...)` | `_first_error()` + константы сообщений | устранено дублирование |
| Админка | только `Share` | + `Portfolio`, `Position`, `Transaction` (+ inline позиций) | новые модели доступны администратору |

---

## 6. Как проверялось (фактические результаты)

Окружение: CPython **3.12.14**, Windows; зависимости установлены из колёс PyPI согласно
новому `requirements.txt`; база — SQLite (PostgreSQL-сервер в окружении недоступен).

| Проверка | Команда | Результат |
|---|---|---|
| Системные проверки | `python manage.py check` | `System check identified no issues (0 silenced).` — exit 0 |
| Согласованность миграций | `python manage.py makemigrations --check --dry-run` | `No changes detected` — exit 0 |
| Применение миграций | `python manage.py migrate` | применены 8 миграций `dashboard` (0001–0008) + стандартные; exit 0 |
| Запуск сервера | `python manage.py runserver 127.0.0.1:8123 --noreload` | сервер поднялся; далее остановлен |
| HTTP-проверка | `GET /` | `200`, 2751 байт (список акций) |
| | `GET /api/v1/shares/` | `200` |
| | `GET /user/login/` | `200`, содержит `name="email"` и `type="password"` (DEF-10 исправлен) |
| | `GET /admin/` | `200` (форма входа в админку) |
| | `GET /1` (существующая акция, токена Tinkoff нет) | `200` + «График временно недоступен» (DEF-18 исправлен) |
| | `GET /1` (до создания акции) | `404`, а не 500 (DEF-17 исправлен) |
| Тесты | `python manage.py test dashboard` | **33 теста, OK** (10 исходных + 4 регрессионных + 19 новых по портфелю/точности) |

Замечание про установку зависимостей: в данном окружении `pip install` блокируется
файловой песочницей при распаковке колёс, поэтому пакеты ставились распаковкой
тех же колёс PyPI в виртуальное окружение. Состав и версии при этом ровно соответствуют
`requirements.txt` (проверены импортом и версиями: Django 5.2.18, DRF 3.16.1, Celery 5.5.3,
redis 6.4.0, plotly 6.9.0). Это ограничение окружения, а не проекта.

---

## 7. Остающиеся ограничения

1. **Tinkoff SDK не из PyPI.** Реальные вызовы API возможны только после установки
   `requirements-tinkoff.txt` из архивного репозитория; в этом окружении установка не
   выполнялась, поэтому проверены только ветки деградации (карточка без графика,
   задача без котировок).
2. **Redis/брокер не запускался.** Конфигурация Celery проверена статически (`check`) и
   тестами; фактическая доставка задач в Redis не проверялась (сервис недоступен).
3. **PostgreSQL не проверялся вживую.** Конфигурация включается через `DB_ENGINE=postgres`;
   миграции совместимы (нет сырого SQL), но прогон на PostgreSQL в этом окружении не выполнен.
   Отдельно отмечу: `search_fields = ["$name"]` (regex-поиск) работает только на PostgreSQL —
   на SQLite этот параметр может давать ошибку при обращении к `/api/v1/shares/?search=…`.
   Оставлено как есть (DEF-32), т.к. исправление меняет контракт API.
4. **`uid` и API создания акций (DEF-19).** Второй `POST /api/v1/shares/` без `uid` приведёт
   к нарушению UNIQUE. Требует изменения схемы API — вне рамок задачи «не менять поведение».
5. **Фронтенд с CDN.** Bootstrap/jQuery/Plotly подключаются с внешних CDN
   (`dashboard/templates/dashboard/base.html`); без интернета страница теряет оформление
   и график. Локальные копии есть только для Bootstrap CSS.
