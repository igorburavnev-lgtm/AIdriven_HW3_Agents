# REQUIREMENTS.md — восстановленные функциональные требования (прогон `agent-cursor-mimic`)
Всего **36 требований** в 5 группах.

---

## 1. Просмотр справочника акций

**FR-C-01.** `GET /` отдаёт HTML-страницу со списком всех акций из БД.
→ `dashboard/urls.py:14`, `dashboard/views.py:22`

**FR-C-02.** Список упорядочен по наименованию компании.
→ `dashboard/views.py:28` (`ordering = ["name"]`)

**FR-C-03.** Список постраничный, по 100 записей на страницу.
→ `dashboard/views.py:27` (`paginate_by = 100`)

**FR-C-04.** В шаблоне есть навигация по страницам: ссылки на предыдущую/следующую и на каждую
страницу, текущая выделена.
→ `dashboard/templates/dashboard/list.html:63-80`

**FR-C-05.** Если акций нет, вместо таблицы выводится «Акций еще нет».
→ `dashboard/templates/dashboard/list.html:15, 83-85`

**FR-C-06.** Тикер в строке — ссылка на карточку акции `/<id>`.
→ `dashboard/templates/dashboard/list.html:32`, `dashboard/urls.py:15`

**FR-C-07.** Цена выводится в виде «значение валюта»; ячейка окрашена: зелёная при `is_trend_high = True`,
розовая при `False`, нейтральная при `NULL`.
→ `dashboard/templates/dashboard/list.html:35-41`, `dashboard/models.py:19`

**FR-C-08.** Карточка `GET /<int:pk>` показывает наименование, текущую цену с валютой и время
последнего обновления записи.
→ `dashboard/urls.py:15`, `dashboard/views.py:31-35`, `dashboard/templates/dashboard/detail.html:11-13`

**FR-C-09.** Карточка строит график цен закрытия по дневным свечам за последние 180 дней.
→ `dashboard/views.py:39`, `dashboard/services/graph.py:11, 14, 24`

**FR-C-10.** График — линейный, красный, с прозрачностью 0.8, легенда по тикеру, без ссылки на plot.ly,
Plotly.js подключается извне (не встраивается в ответ).
→ `dashboard/services/graph.py:36, 46`

**FR-C-11.** HTML графика вставляется в страницу без экранирования.
→ `dashboard/templates/dashboard/detail.html:23-26`

**FR-C-12.** Если данные рынка недоступны, карточка всё равно открывается (HTTP 200) и показывает
сообщение вместо графика.
→ `dashboard/views.py:39-47`, `dashboard/templates/dashboard/detail.html:28`

**FR-C-13.** Просмотр списка и карточки не требует аутентификации; скрываются только элементы управления.
→ `dashboard/views.py:22-45`, `dashboard/templates/dashboard/list.html:9-13`

**FR-C-14.** Запрос несуществующей акции возвращает 404, а не серверную ошибку.
→ `dashboard/views.py:37` (`get_object_or_404`)

## 2. Управление справочником (только аутентифицированные)

**FR-C-15.** Кнопка «Добавить» и колонка «Управление» отображаются только аутентифицированному
пользователю.
→ `dashboard/templates/dashboard/list.html:9-13, 23-25, 41-50`

**FR-C-16.** `GET /create` для анонима перенаправляет на главную, не открывая форму.
→ `dashboard/urls.py:16`, `dashboard/views.py:13-19, 56`

**FR-C-17.** Форма создания строится по модели и включает все редактируемые поля, выводится crispy-разметкой.
→ `dashboard/forms.py:6-11`, `dashboard/templates/dashboard/create.html:16`

**FR-C-18.** Успешное создание сохраняет запись и перенаправляет на главную.
→ `dashboard/views.py:56-62`

**FR-C-19.** `GET /update/<pk>` доступен только аутентифицированным и использует ту же форму и шаблон,
что и создание.
→ `dashboard/urls.py:17`, `dashboard/views.py:64-70`

**FR-C-20.** `GET /delete/<pk>` показывает подтверждение с названием инструмента; `POST` удаляет запись
и перенаправляет на главную.
→ `dashboard/urls.py:18`, `dashboard/views.py:73-78`, `dashboard/templates/dashboard/delete.html:10-11`

**FR-C-21.** Все формы защищены CSRF-токеном.
→ `dashboard/templates/dashboard/create.html:14`, `dashboard/templates/dashboard/delete.html:10`,
`user/templates/user/auth.html:4`, `user/templates/user/registration.html:5`

## 3. Регистрация, вход, выход

**FR-C-22.** Форма регистрации содержит обязательные `email`, `password1`, `password2`.
→ `user/forms.py:15-36`

**FR-C-23.** Пароли должны совпадать, иначе выводится «Введенные пароли не совпадают».
→ `user/forms.py:37-45`

**FR-C-24.** E-mail должен быть уникальным (проверка без учёта регистра).
→ `user/forms.py:49`

**FR-C-25.** Пароль проверяется штатными валидаторами Django.
→ `user/forms.py:3, 54`

**FR-C-26.** Успешная регистрация создаёт пользователя (`username = email`, e-mail нормализован к нижнему
регистру), сразу выполняет вход и перенаправляет на главную.
→ `user/forms.py:64`, `user/views.py:58-69`

**FR-C-27.** При ошибке валидации страница регистрации показывается повторно с текстом первой ошибки.
→ `user/views.py:10-14, 76`

**FR-C-28.** `GET /user/login/` и `GET /user/registration/` отдают формы с полями ввода.
→ `user/urls.py:8-9`, `user/views.py:22, 52`

**FR-C-29.** Вход выполняется по e-mail и паролю; e-mail приводится к нижнему регистру.
→ `user/views.py:28-36`

**FR-C-30.** Успешный вход создаёт сессию и перенаправляет на главную; неуспешный — повторно показывает
форму с сообщением «Неверный логин или пароль! Повторите попытку.».
→ `user/views.py:31-45`

**FR-C-31.** `GET /user/logout/` завершает сессию и перенаправляет на главную; тот же обработчик доступен
по POST.
→ `user/urls.py:10`, `user/views.py:80-88`

**FR-C-32.** В шапке приложения для аутентифицированного пользователя выводятся приветствие с e-mail и
кнопка «Выход», для анонима — кнопка «Войти».
→ `dashboard/templates/dashboard/base.html:37-43`

## 4. REST API

**FR-C-33.** API доступен по `/api/v1/`; ресурс акций — `/api/v1/shares/` и `/api/v1/shares/<pk>/`.
→ `config/urls.py:6`, `dashboard/urls.py:19`, `dashboard/api/v1/router.py:7`

**FR-C-34.** Список отдаётся с пагинацией `LimitOffsetPagination` (размер 100) в формате
`count/next/previous/results`.
→ `config/settings.py:70-72`

**FR-C-35.** Элемент акции содержит `id, figi, isin, name, ticker, currency, last_price, is_trend_high,
updated_at`; поле `uid` не отдаётся.
→ `dashboard/api/v1/serializer.py:6-18`

**FR-C-36.** Поддерживается фильтрация по `name` и `ticker`, сортировка по `name`/`ticker` (`ordering`) и
поиск по `name` (`search`).
→ `dashboard/api/v1/views.py:10-22`

**FR-C-37.** API выполняет CRUD без аутентификации: список, чтение, создание, изменение, удаление возвращают
200/201/204, ошибки валидации — 400, отсутствующая запись — 404.
→ `dashboard/api/v1/views.py:16`, `dashboard/tests.py:8-122`

**FR-C-38.** Доступны портфельные эндпоинты `/api/v1/portfolios/` (см. `FEATURE_REQUIREMENTS.md`, FR-P-01…FR-P-29).
→ `dashboard/api/v1/router.py:8`

## 5. Данные, импорт, фоновые задачи, администрирование

**FR-C-39.** Акция хранится в модели `Share`: `figi` (уникальный), `isin`, `name`, `ticker` (уникальный),
`currency`, `uid` (уникальный), `last_price` (может быть пустым), `is_trend_high` (может быть пустым),
`updated_at` (автозаполнение).
→ `dashboard/models.py:9-29`

**FR-C-40.** Команда `python manage.py add_shares` загружает справочник из Tinkoff Invest API и создаёт
недостающие записи, сопоставляя их по `figi`.
→ `dashboard/management/commands/add_shares.py:7-32`

**FR-C-41.** Celery Beat периодически запускает `update_last_price`; период задаётся настройкой
`PRICE_UPDATE_INTERVAL_SECONDS` (по умолчанию 300 с).
→ `config/celery.py:15-20`, `config/settings.py:207-210`

**FR-C-42.** Задача перебирает все акции, получает последнюю цену по `figi` и сохраняет её вместе с флагом
`is_trend_high`; при первой загрузке флаг считается «ростом»; ошибка по одной бумаге логируется и не
прерывает обработку остальных.
→ `dashboard/tasks.py:8-30`, `dashboard/services/market_data.py:20-37`

**FR-C-43.** Токен Tinkoff и прочие секреты берутся из переменных окружения, а не из кода.
→ `config/settings.py:199`

**FR-C-44.** Справочник акций доступен в Django-админке: список, поиск по `figi/isin/name/ticker`, форма
с восемью полями.
→ `config/urls.py:5`, `dashboard/admin.py:6-20`

**FR-C-45.** События логируются в консоль и в файл `app.logs` рядом с проектом.
→ `config/settings.py:74-95`

---

## Выявленные неоднозначности и дефекты

Подробный разбор — в `MODERNIZATION.md` (разделы 2 и 4). Кратко:

- **Неоднозначность:** расписание Beat в исходном коде называлось `add-every-5-min`, но выполнялось раз в
  10 секунд — какое значение задумано, однозначно не восстановить; принято 300 с с возможностью настройки.
- **Неоднозначность:** `is_trend_high` в исходном коде выставлялся в «истину» и при равенстве цен — трактовка
  «цена не упала» вместо «цена растёт».
- **Дефект:** `?search=` использует PostgreSQL-синтаксис регулярного выражения (`search_fields = ["$name"]`),
  на SQLite поиск не работает — оставлено осознанно, исправление меняет контракт API.
- **Дефект:** создание акции через API без `uid` может нарушить уникальный индекс (в сериализаторе поля нет) —
  требует изменения схемы API, поэтому не исправлялось в рамках задания №3.
