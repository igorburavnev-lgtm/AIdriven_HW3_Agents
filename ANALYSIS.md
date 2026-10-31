# Анализ проекта Investing Demo (задание №1)

## 1) Назначение и технологический стек
Приложение - демо для работы с акциями (интеграция с Tinkoff Invest API). Отображает список акций, карточку акции с графиком цен за последние 180 дней, позволяет добавлять/редактировать/удалять акции через веб-интерфейс, обновляет текущие цены через Celery.

Технологический стек:
- Язык/фреймворк: Python, Django 4.1.7
- API: Django REST Framework 3.14.0, django-filter 22.1
- Формы/UI: django-crispy-forms 2.0, crispy-bootstrap3 2022.1
- БД: PostgreSQL (psycopg2-binary 2.9.5). В настройках есть закомментированный SQLite.
- Очереди/планировщик: Celery 5.2.7, Redis (broker), celery beat
- Интеграция с биржей: tinkoff-investments 0.2.0b50, tinkoff 0.1.1
- Визуализация: plotly 5.13.1
- Прочее: pydantic 1.10.6, protobuf 3.20.3, grpcio 1.51.3

## 2) Структура проекта, компоненты, архитектура
Структура (основные модули):
- config/ - настройки проекта (settings, urls, celery, wsgi/asgi)
- dashboard/ - основная бизнес-логика
  - models.py - модель Share
  - views.py - представления (List/Create/Update/Delete/Detail)
  - forms.py - форма ShareModelForm
  - urls.py - роутинг dashboard
  - tasks.py - Celery задача update_last_price
  - admin.py, apps.py, tests.py
  - api/ - REST API (v1: router, serializer, views, urls)
  - services/ - интеграции (market_data.py, graph.py)
  - management/commands/add_shares.py - загрузка акций из Tinkoff API
  - migrations/ - миграции модели Share
- user/ - приложение пользователей (urls.py присутствует)
- manage.py, docker-compose.yml (Postgres), requirements.txt, README.md

Архитектура:
- Монолит Django (MVT). 
- Веб-часть через Django views (CBV) с миксином авторизации для создания/редактирования/удаления.
- REST API через DRF в dashboard/api/v1.
- Фоновая обработка через Celery + beat: периодическое обновление last_price для всех акций из Tinkoff API.
- Интеграция с Tinkoff Invest API через tinkoff-investments SDK. Получение списка инструментов (shares) и last_prices, построение графика по свечам.

Взаимодействие: пользователь через браузер -> Django views/templates -> модели; API -> DRF views/serializers; Celery worker/beat -> tasks -> services.market_data -> Tinkoff API -> обновление Share в БД. graph.py использует Tinkoff API для получения свечей и plotly для рендера графика.

## 3) Используемые библиотеки и зависимости
См. requirements.txt (ключевые: Django 4.1.7, DRF 3.14.0, celery 5.2.7, redis 4.5.1, tinkoff-investments 0.2.0b50, plotly 5.13.1, psycopg2-binary 2.9.5, crispy-forms/bootstrap3).

## 4) Модель данных
Модель Share (dashboard/models.py), миграции 0001-0007 отражают эволюцию:
- figi (CharField, unique)
- isin (CharField)
- name (CharField, verbose_name "Наименование компании") 
- ticker (CharField, unique, verbose_name "Тикер")
- currency (CharField, verbose_name "Валюта")
- uid (CharField, unique) - добавлено миграцией 0003
- last_price (FloatField, null/blank) - миграция 0004
- is_trend_high (BooleanField, null/blank, verbose_name "Растет цена") - добавлено позже
- updated_at (DateTimeField, auto_now=True, null/blank) - миграция 0007

Связей между моделями в текущем коде нет (только Share).

## 5) Механизмы обработки запросов и взаимодействия с БД
- Веб: CBV (ListView, CreateView, UpdateView, DeleteView, View). Create/Update/Delete защищены IsUserAuthenticatedMixin (только авторизованные). При отсутствии прав происходит редирект на "dashboard:index".
- Формы: ModelForm на всех полях Share.
- API: есть api urls (подключены в dashboard.urls и config.urls), используется DRF (роутер/серилизатор/views в dashboard/api/v1). ShareSerializer возвращает поля id, figi, isin, name, ticker, currency, last_price, is_trend_high, updated_at.
- БД: Django ORM. Обновление в задаче через Share.objects.filter(id=share.id).update(...). Создание через get_or_create в команде add_shares.
- Внешние вызовы: синхронные вызовы Tinkoff API в views/services/tasks/management командах (используют Client из tinkoff-investments).

# Восстановленные функциональные требования (задание №2)

Ниже - фактически реализованные требования с подтверждением в коде.

## Основные функциональные возможности
1. **Просмотр списка акций** (FR-001). Реализовано: ShareListView, шаблон dashboard/list.html, пагинация paginate_by=100, сортировка по name. Подтверждение: dashboard/views.py:20-27, dashboard/urls.py:14.
2. **Просмотр детальной карточки акции с графиком** (FR-002). ShareDetailView.get получает акцию по pk, рендерит dashboard/detail.html с plot_div = get_graph(share). Подтверждение: dashboard/views.py:29-38, dashboard/services/graph.py:11-36.
3. **Добавление акции** (FR-003). ShareCreateView (только авторизованные) с ShareModelForm, редирект на dashboard:index. Подтверждение: dashboard/views.py:41-47.
4. **Редактирование акции** (FR-004). ShareUpdateView (только авторизованные), модель Share, форма ShareModelForm. Подтверждение: dashboard/views.py:49-55.
5. **Удаление акции** (FR-005). ShareDeleteView (только авторизованные), редирект на dashboard:index (комментарий "Удаление задачи" некорректен). Подтверждение: dashboard/views.py:58-63.
6. **Загрузка списка акций из Tinkoff API** (FR-006). Management команда add_shares использует Client.instruments.shares() и создает записи через get_or_create по figi. Подтверждение: dashboard/management/commands/add_shares.py:8-24.
7. **Периодическое обновление цен акций** (FR-007). Celery задача update_last_price получает все Share, для каждой вызывает get_last_data, вычисляет is_trend_high (если last_price>new_price -> False иначе True, при ошибке -> True), обновляет last_price и is_trend_high. Расписание в beat - каждые 10 секунд. Подтверждение: dashboard/tasks.py:7-28, config/celery.py:13-18.
8. **Получение последней цены** (FR-008). Сервис get_last_data через Tinkoff Client.market_data.get_last_prices возвращает [resp.price.units, resp.time]. Подтверждение: dashboard/services/market_data.py:6-11.
9. **Построение графика цен** (FR-009). get_graph строит линейный график по дневным свечам за 180 дней (CANDLE_INTERVAL_DAY) через client.get_all_candles, использует plotly offline для div. Подтверждение: dashboard/services/graph.py:11-36.
10. **REST API для акций** (FR-010). DRF сериализация Share, фильтрация подключена, пагинация LimitOffsetPagination page_size 100. Подтверждение: config/settings.py:31-36, dashboard/api/v1/serializer.py:6-19.

## Бизнес-правила, проверки, ограничения
- Для доступа к созданию/редактированию/удалению требуется аутентификация (IsUserAuthenticatedMixin). Если не авторизован - редирект на "dashboard:index". (BR-001)
- Share.figi, Share.ticker, Share.uid уникальны. (BR-002)
- При обновлении цены: если известное share.last_price > полученная last_price -> is_trend_high = False, иначе True (т.е. "растет цена" трактуется как не падение/равно или выросло? Логика: если текущая сохраненная цена больше новой -> тренд не высокий/падает -> False, иначе True). При ошибке при сравнении is_trend_high устанавливается в True. (BR-003) 
- Обновление цен происходит для всех акций в БД по очереди; ошибки перехватываются и логируются, процесс продолжается. (BR-004)
- График строится за последние 180 дней по дневным свечам. (BR-005)
- Для работы с Tinkoff API требуется TINKOFF_TOKEN в настройках. (BR-006)
- Список акций загружается командой add_shares из всех доступных shares инструментах. (BR-007)

## Выявленные неоднозначности/противоречия/дефекты
- **Несоответствие комментария**: в ShareDeleteView комментарий "Удаление задачи" вместо "Удаление акции" (views.py:59).
- **Потенциальная проблема в get_last_data**: код делает `resp = resp.last_prices.pop()` и возвращает `[resp.price.units, resp.time]`. В tinkoff-investments API цена может быть представлена как Money (units/nano). Возврат только units может привести к неточности (отбрасывание nano). Также нет обработки пустого списка.
- **Проблема в tasks.update_last_price**: сравнение `share.last_price > last_price` - если last_price приходит как список/не число, либо если типы разные, возможно неожиданное поведение. Также share.last_price может быть None при первом обновлении - есть try/except, который выставляет is_trend_high=True при ошибке, что кажется произвольным.
- **Риск в graph.py**: используется `candle.close.units` - опять только units, без учета nano; при отсутствии данных может быть проблема. Также нет обработки ошибок.
- **Настройки**: SECRET_KEY пустой, DEBUG=True, ALLOWED_HOSTS пустой, БД настроена на Postgres локально, TINKOFF_TOKEN пустой. Для запуска в dev-окружении может потребоваться настройка. В settings закомментирован SQLite.
- **Зависимости**: в requirements.txt есть как tinkoff 0.1.1, так и tinkoff-investments 0.2.0b50 - возможно конфликт/избыточность; используются оба API стили? В коде используется tinkoff-investments (Client из tinkoff.invest).
- **Celery beat интервал** 10.0 секунд (очень частый для демо), CELERY_TASK_ALWAYS_EAGER=False.
- **API**: в dashboard/urls.py подключен "api/", в dashboard/api/v1 есть router/views/serializer - есть заготовка REST API, но полная структура может требовать настройки.
- **Логирование**: пишет в консоль и файл app.logs.
- **Модель**: verbose_name у is_trend_high "Растет цена" - не совсем точно отражает логику (при падении ставится False).
