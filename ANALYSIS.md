# Анализ проекта Investing Demo

## Задание №1. Анализ исходного кода

### 1) Назначение приложения и используемый технологический стек
Investing Demo — веб-приложение для работы с акциями с интеграцией Tinkoff Invest API. Позволяет просматривать список акций, детальную карточку с графиком цен за 180 дней, добавлять/редактировать/удалять записи, получать актуальные цены через фоновые задачи Celery.

**Технологический стек:**
- Backend: Python, Django 4.1.7
- API: Django REST framework 3.14.0, django-filter 22.1
- UI: django-crispy-forms 2.0, crispy-bootstrap3 2022.1
- База данных: PostgreSQL (psycopg2-binary) с возможностью переключения на SQLite
- Фоновые задачи: Celery 5.2.7, Redis (broker), django-celery-beat совместимый подход через CELERY_BEAT_SCHEDULE
- Интеграция с биржей: tinkoff-investments 0.2.0b50 (tinkoff.invest), tinkoff 0.1.1
- Визуализация: plotly 5.13.1
- Прочее: pydantic, protobuf, grpcio

### 2) Структура проекта, основные компоненты и их назначение
- `config/` — конфигурация Django (settings, urls, wsgi/asgi, celery)
- `dashboard/` — основное приложение
  - `models.py` — модели данных
  - `views.py` — представления (CBV)
  - `forms.py` — формы
  - `urls.py` — маршруты dashboard
  - `tasks.py` — Celery задачи
  - `api/` — REST API (v1: router, views, serializers)
  - `services/` — бизнес-сервисы (market_data, graph)
  - `management/commands/` — кастомные команды (add_shares)
  - `migrations/` — миграции
- `user/` — приложение пользователей
- `templates/` — шаблоны

### 3) Архитектура приложения и взаимодействие компонентов
Монолитное MVT-приложение Django.
- Веб-слой: Django CBV + шаблоны. Часть операций защищена миксином авторизации.
- API-слой: DRF ViewSet с роутером, сериализаторами, фильтрацией/поиском/пагинацией.
- Сервисный слой: `services/market_data.py` (получение цен), `services/graph.py` (построение графика).
- Фоновый слой: Celery worker + beat периодически обновляют цены акций.
- Интеграция: прямая работа с Tinkoff Invest API через SDK.

Взаимодействие: HTTP-запрос -> URLconf -> View/Form/Serializer -> Model (ORM) -> БД. Фоновые задачи опрашивают Tinkoff API и обновляют Share.

### 4) Используемые библиотеки и внешние зависимости
См. `requirements.txt`: Django, DRF, django-filter, django-crispy-forms, crispy-bootstrap3, Celery, Redis, tinkoff-investments, plotly, psycopg2-binary, pydantic, protobuf, grpcio и др.

### 5) Модель данных
**Share** (основная сущность):
- figi (CharField, unique) — идентификатор инструмента
- isin (CharField)
- name (CharField, verbose_name "Наименование компании")
- ticker (CharField, unique, verbose_name "Тикер")
- currency (CharField, verbose_name "Валюта")
- uid (CharField, unique)
- last_price (FloatField, null/blank, verbose_name "Текущая цена")
- is_trend_high (BooleanField, null/blank, verbose_name "Растет цена")
- updated_at (DateTimeField, auto_now=True, null/blank)

Миграции показывают эволюцию модели (добавление uid, last_price, verbose_name, updated_at).

### 6) Механизмы обработки пользовательских запросов и взаимодействия с БД
- **Веб**: ListView/CreateView/UpdateView/DeleteView/View. Create/Update/Delete требуют авторизации через `IsUserAuthenticatedMixin`, при отсутствии прав редирект на `dashboard:index`.
- **ORM**: Django ORM, `get_or_create` при импорте акций, `filter().update()` при обновлении цен.
- **API**: DRF `ModelViewSet` для Share, `DefaultRouter`, фильтрация по name/ticker, поиск по name, сортировка, пагинация LimitOffsetPagination (page_size 100).
- **Фоновые задачи**: Celery task `update_last_price` обходит все акции, получает цену через Tinkoff API, рассчитывает флаг тренда, обновляет БД.
- **Сервисы**: `get_last_data()` получает последнюю цену, `get_graph()` строит график по дневным свечам за 180 дней через plotly.

## Задание №2. Восстановление функциональных требований

### Основные функциональные возможности (фактически реализованы)
**FR-001.** Просмотр списка акций. `ShareListView`, шаблон `list.html`, пагинация 100, сортировка по name.  
**FR-002.** Просмотр карточки акции с графиком. `ShareDetailView` + `get_graph()` (дневные свечи за 180 дней).  
**FR-003.** Добавление акции (только авторизованные). `ShareCreateView`, `ShareModelForm`.  
**FR-004.** Редактирование акции (только авторизованные). `ShareUpdateView`.  
**FR-005.** Удаление акции (только авторизованные). `ShareDeleteView`.  
**FR-006.** Загрузка списка акций из Tinkoff API. Команда `add_shares` использует `client.instruments.shares()` и `get_or_create`.  
**FR-007.** Периодическое обновление цен. Celery beat + `update_last_price` для всех акций.  
**FR-008.** Получение последней цены через Tinkoff API. `market_data.get_last_data()`.  
**FR-009.** Построение графика цен через Plotly. `services/graph.py`.  
**FR-010.** REST API для акций. DRF с сериализацией, фильтрацией, поиском, пагинацией.

### Бизнес-правила, проверки, ограничения
**BR-001.** Доступ к CRUD-операциям над акциями - только авторизованные пользователи. Иначе редирект на `dashboard:index`.  
**BR-002.** Уникальность: `figi`, `ticker`, `uid`.  
**BR-003.** Логика определения тренда: при наличии `share.last_price` и новой цены - если старая > новой, `is_trend_high=False`, иначе `True`. При ошибке сравнения `is_trend_high=True`.  
**BR-004.** Обновление цен идёт по всем акциям; ошибки логируются, выполнение продолжается.  
**BR-005.** График строится за 180 дней по дневным интервалам свечей.  
**BR-006.** Для работы с Tinkoff API требуется `TINKOFF_TOKEN`.  
**BR-007.** Импорт акций загружает все доступные инструменты типа shares.

### Неоднозначности, противоречия, возможные дефекты
- В `ShareDeleteView` комментарий "Удаление задачи" вместо "Удаление акции".
- В `market_data.get_last_data()` используется только `price.units`, игнорируется `nano` - возможна потеря точности.
- В `tasks.update_last_price()` сравнение может быть некорректным при None/разных типах; при ошибке логика установки `is_trend_high=True` неочевидна.
- В `graph.py` используется только `close.units`, нет обработки пустых данных/ошибок.
- Настройки: пустой `SECRET_KEY`, `DEBUG=True`, пустой `ALLOWED_HOSTS`, БД на Postgres, пустой `TINKOFF_TOKEN`.
- Одновременное наличие `tinkoff` и `tinkoff-investments` в requirements.
- Celery beat интервал 10 секунд.
- Логика "растет цена" (`is_trend_high`) при равенстве цен трактуется как True.
