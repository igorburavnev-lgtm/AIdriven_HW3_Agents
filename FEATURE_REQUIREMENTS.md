# FEATURE_REQUIREMENTS.md — Виртуальный инвестиционный портфель

> Задание №4, направление 2 из `HOMEWORK.md`: «Виртуальный инвестиционный портфель».
> Документ содержит **проверяемые** требования: для каждого указан способ проверки
> (имя автотеста) и место реализации. Все 17 API-тестов и 2 теста точности находятся в
> `dashboard/tests_portfolio.py` и проходят (`python manage.py test dashboard` → 33 теста OK).

## 0. Область

**Входит в объём:**
- персональные портфели пользователя;
- моделирование покупки и продажи акций из существующего справочника `Share`;
- учёт количества и средней цены приобретения;
- расчёт текущей стоимости портфеля, прибыли и убытков (реализованных и нереализованных);
- история виртуальных операций;
- REST API (DRF) + админка.

**Не входит в объём (осознанно):**
- реальные деньги, пополнение/списание кэша, комиссии брокера, налоги;
- конвертация валют между позициями (портфель может содержать бумаги в разных валютах,
  суммы не приводятся к одной валюте — см. FR-P-20);
- котировки в реальном времени (используется `Share.last_price`, обновляемый Celery-задачей);
- графический UI портфеля (обоснование выбора API — в `FEATURE_REPORT.md`, раздел 1).

## 1. Понятия

| Понятие | Определение | Источник |
|---|---|---|
| Портфель | Именованный набор позиций, принадлежащий пользователю | `dashboard/models.py:32-56` |
| Позиция | Текущее количество акций одного вида и средняя цена их приобретения | `dashboard/models.py:59-109` |
| Операция | Зафиксированный факт покупки или продажи с ценой и количеством | `dashboard/models.py:112-163` |
| Средняя цена приобретения | Средневзвешенная цена всех покупок; при продаже не меняется | `dashboard/services/portfolio.py:61-96` |
| Реализованный P&L | Результат закрытой части позиции: `(цена продажи − средняя цена) × количество` | `dashboard/services/portfolio.py:112` |
| Нереализованный P&L | `текущая стоимость − стоимость по средней цене` | `dashboard/services/portfolio.py:182` |

Точность: количество и цены хранятся как `Decimal(18, 6)`; денежные результаты
квантуются до 6 знаков (`dashboard/services/portfolio.py:16`).

---

## 2. Управление портфелями

### FR-P-01. Создание портфеля
Аутентифицированный пользователь создаёт портфель запросом
`POST /api/v1/portfolios/` с полем `name`. Владелец проставляется автоматически из
`request.user`, поле `owner` в запросе не принимается.
- Проверка: `test_create_portfolio_assigns_current_user`
- Реализация: `dashboard/api/v1/portfolio_views.py:35-36`, `dashboard/api/v1/portfolio_serializer.py:9-18`

### FR-P-02. Список только собственных портфелей
`GET /api/v1/portfolios/` возвращает исключительно портфели текущего пользователя
(в формате `LimitOffsetPagination`: `count/next/previous/results`).
- Проверка: `test_portfolio_list_is_scoped_to_owner`
- Реализация: `dashboard/api/v1/portfolio_views.py:29-33`

### FR-P-03. Чужой портфель недоступен
Обращение к портфелю другого пользователя (`GET/PATCH/DELETE` и все действия)
возвращает **404**, а не 403: чужие объекты не попадают в queryset.
- Проверка: `test_other_user_cannot_access_foreign_portfolio`
- Реализация: `dashboard/api/v1/portfolio_views.py:29-33`

### FR-P-04. Уникальность названия в рамках владельца
Повторное создание портфеля с тем же `name` у того же пользователя возвращает **400**
с сообщением «Портфель с таким названием уже существует» (а не 500 от нарушения
уникального индекса).
- Проверка: `test_duplicate_portfolio_name_is_rejected`
- Реализация: `dashboard/api/v1/portfolio_serializer.py:20-31`, ограничение БД — `dashboard/models.py:49-53`

### FR-P-05. Изменение и удаление портфеля
`PATCH`/`PUT` изменяют название, `DELETE` удаляет портфель вместе с его позициями
и операциями (каскад).
- Реализация: `dashboard/api/v1/portfolio_views.py:18-36` (`ModelViewSet`), `dashboard/models.py:34-38` (`on_delete=CASCADE`)

### FR-P-06. Аутентификация обязательна
Любой эндпоинт `/api/v1/portfolios/…` без аутентификации возвращает **401 или 403**;
анонимный доступ к портфелям невозможен (в отличие от публичного справочника акций).
- Проверка: `test_endpoints_require_authentication`
- Реализация: `dashboard/api/v1/portfolio_views.py:27`

---

## 3. Покупка

### FR-P-07. Покупка создаёт позицию
`POST /api/v1/portfolios/{id}/buy/` с `share` и `quantity` создаёт позицию, если её не было:
`quantity` равна купленному количеству, `avg_price` — цене покупки. Ответ — **201**
с `transaction`, `position` и `summary`.
- Проверка: `test_buy_creates_position_with_market_price`
- Реализация: `dashboard/api/v1/portfolio_views.py:65-68, 74-102`, `dashboard/services/portfolio.py:61-96`

### FR-P-08. Повторная покупка пересчитывает среднюю цену
При покупке того же вида акций количество суммируется, средняя цена пересчитывается
по формуле `(Σ цена × количество) / Σ количество`; новая позиция не создаётся.
Пример: 10 шт. по 100 + 10 шт. по 200 → 20 шт. со средней ценой 150.
- Проверка: `test_second_buy_recalculates_weighted_average_price`
- Реализация: `dashboard/services/portfolio.py:88-95`

### FR-P-09. Цена по умолчанию — рыночная
Если `price` в запросе не передан, используется `Share.last_price` (последняя цена,
сохранённая фоновой задачей). Явно переданная цена имеет приоритет.
- Проверка: `test_buy_creates_position_with_market_price` (цена 100 из `last_price`), `test_second_buy_recalculates_weighted_average_price` (явные цены)
- Реализация: `dashboard/services/portfolio.py:42-50`

### FR-P-10. Покупка без известной цены отклоняется
Если цена не передана и `Share.last_price` пуст, запрос возвращает **400** с указанием
причины; позиция и операция не создаются.
- Проверка: `test_buy_without_price_and_without_market_data_is_rejected`
- Реализация: `dashboard/services/portfolio.py:44-48`

### FR-P-11. Неположительное количество отклоняется
`quantity ≤ 0` (в том числе `0`, отрицательное, нечисловое) возвращает **400**;
данные не меняются.
- Проверка: `test_buy_rejects_non_positive_quantity`; ограничение схемы —
  `serializers.DecimalField(min_value=0.000001)` (`dashboard/api/v1/portfolio_serializer.py:96-111`)
- Реализация: `dashboard/services/portfolio.py:53-57`

---

## 4. Продажа

### FR-P-12. Продажа уменьшает количество и не меняет среднюю цену
`POST /api/v1/portfolios/{id}/sell/` уменьшает `quantity` позиции на проданное количество;
`avg_price` остаётся прежней (метод средней цены, а не FIFO/LIFO).
- Проверка: `test_sell_reduces_position_and_realizes_profit`
- Реализация: `dashboard/services/portfolio.py:98-119`

### FR-P-13. Запрет продажи больше, чем есть
Если запрошенное количество превышает остаток позиции, возвращается **400**
с указанием остатка и запрошенного количества; позиция и история не изменяются,
операция не создаётся.
- Проверка: `test_selling_more_than_held_is_rejected`
- Реализация: `dashboard/services/portfolio.py:104-111`

### FR-P-14. Запрет продажи отсутствующей позиции
Продажа бумаги, которой нет в портфеле, возвращает **400** без создания операции.
- Проверка: `test_selling_position_that_does_not_exist_is_rejected`
- Реализация: `dashboard/services/portfolio.py:102-103`

### FR-P-15. Реализованный результат фиксируется в операции
При продаже в операции сохраняется `realized_pnl = (цена продажи − средняя цена) × количество`
(может быть отрицательным). Значение возвращается в ответе и в истории операций.
- Проверка: `test_sell_reduces_position_and_realizes_profit` (200 = (150−100)×4), `test_summary_computes_value_pnl_and_realized_result` (500)
- Реализация: `dashboard/services/portfolio.py:112`, `dashboard/models.py:140-145`

### FR-P-16. Полная продажа закрывает позицию
Если после продажи количество равно нулю, позиция удаляется (история операций сохраняется).
- Проверка: `test_full_sell_closes_position`
- Реализация: `dashboard/services/portfolio.py:114-118`

### FR-P-17. Атомарность операции
Запись операции и изменение позиции выполняются в одной транзакции БД
(`transaction.atomic`) с блокировкой строки позиции (`select_for_update`).
Отклонённая операция не оставляет частичных изменений.
- Проверка: `test_selling_more_than_held_is_rejected` (позиция 5 и 0 операций продажи после отказа)
- Реализация: `dashboard/services/portfolio.py:60-61, 82, 99`

---

## 5. Стоимость и прибыль/убыток

### FR-P-18. Текущая стоимость позиции и портфеля
`GET /api/v1/portfolios/{id}/summary/` возвращает `total_value` = Σ (`quantity` × текущая
цена) по всем позициям с известной ценой, и `total_cost` = Σ (`quantity` × `avg_price`).
- Проверка: `test_summary_computes_value_pnl_and_realized_result` (15 × 250 = 3750, 15 × 150 = 2250)
- Реализация: `dashboard/services/portfolio.py:134-196`

### FR-P-19. Нереализованный P&L
`unrealized_pnl` = `total_value − total_cost`; для каждой позиции дополнительно
отдаются `market_value`, `unrealized_pnl` и `unrealized_pnl_percent`.
- Проверка: `test_summary_computes_value_pnl_and_realized_result` (1500)
- Реализация: `dashboard/services/portfolio.py:166-174, 182-183`

### FR-P-20. Реализованный и суммарный P&L
`realized_pnl` = сумма `realized_pnl` всех операций продажи по портфелю;
`total_pnl` = `unrealized_pnl + realized_pnl`.
- Проверка: `test_summary_computes_value_pnl_and_realized_result` (500 и 2000)
- Реализация: `dashboard/services/portfolio.py:176-181, 194-195`

### FR-P-21. Позиции без цены не искажают итог
Если у бумаги нет `last_price`, её `market_value`/`unrealized_pnl` равны `null`,
она не входит в `total_value`, а её число возвращается в `unpriced_positions`.
- Проверка: `test_summary_marks_positions_without_price`
- Реализация: `dashboard/services/portfolio.py:161-164, 190`

### FR-P-22. Список позиций с расчётными полями
`GET /api/v1/portfolios/{id}/positions/` возвращает позиции с тикером, названием,
валютой, количеством, средней ценой, `cost_basis`, текущей ценой, стоимостью
и нереализованным результатом.
- Проверка: `test_positions_endpoint_returns_current_positions`
- Реализация: `dashboard/api/v1/portfolio_views.py:39-46`, `dashboard/api/v1/portfolio_serializer.py:35-73`

---

## 6. История операций

### FR-P-23. История в обратном хронологическом порядке
`GET /api/v1/portfolios/{id}/transactions/` возвращает операции портфеля от новых к старым,
с полями `kind` (`buy`/`sell`), `kind_display`, тикер, количество, цена, `realized_pnl`,
`executed_at`. История сохраняется после закрытия позиции.
- Проверка: `test_transaction_history_lists_all_operations`
- Реализация: `dashboard/api/v1/portfolio_views.py:47-57`, `dashboard/models.py:157-160` (`ordering`)

### FR-P-24. Произвольное время операции
Если в запросе покупки/продажи передан `executed_at`, он сохраняется как время операции;
иначе используется текущий момент.
- Реализация: `dashboard/api/v1/portfolio_serializer.py:108-111`, `dashboard/services/portfolio.py:66`

---

## 7. Данные и администрирование

### FR-P-25. Модель данных
- `Portfolio`: `owner` (FK → `AUTH_USER_MODEL`, CASCADE), `name` (100), `created_at`, `updated_at`;
  уникальность `(owner, name)`.
- `Position`: `portfolio` (FK, CASCADE), `share` (FK → `Share`, PROTECT), `quantity`
  (`Decimal 18,6` ≥ 0), `avg_price` (`Decimal 18,6`), `created_at`, `updated_at`;
  уникальность `(portfolio, share)`, CHECK `quantity >= 0`.
- `Transaction`: `portfolio` (FK), `share` (FK, PROTECT), `kind` (`buy`/`sell`),
  `quantity`, `price`, `realized_pnl`, `executed_at`, `created_at`.
- Реализация: `dashboard/models.py:32-163`; миграция — `dashboard/migrations/0008_portfolio_position_transaction_and_more.py`

### FR-P-26. Связь с существующей моделью `Share`
Позиции и операции ссылаются на `Share` по внешнему ключу с `on_delete=PROTECT`:
удаление акции из справочника невозможно, пока по ней есть позиции или операции.
- Проверка: схема миграции `0008`, `dashboard/models.py:66-71, 124-129`

### FR-P-27. Администрирование
Портфели, позиции и операции доступны в Django-админке; в карточке портфеля позиции
показаны inline.
- Реализация: `dashboard/admin.py:24-48`

### FR-P-28. Регистрация в API
Ресурс доступен по адресу `/api/v1/portfolios/`.
- Реализация: `dashboard/api/v1/router.py:8`

---

## 8. Матрица «требование → тест»

| Требование | Тест |
|---|---|
| FR-P-01 | `test_create_portfolio_assigns_current_user` |
| FR-P-02 | `test_portfolio_list_is_scoped_to_owner` |
| FR-P-03 | `test_other_user_cannot_access_foreign_portfolio` |
| FR-P-04 | `test_duplicate_portfolio_name_is_rejected` |
| FR-P-06 | `test_endpoints_require_authentication` |
| FR-P-07, FR-P-09 | `test_buy_creates_position_with_market_price` |
| FR-P-08, FR-P-09 | `test_second_buy_recalculates_weighted_average_price` |
| FR-P-10 | `test_buy_without_price_and_without_market_data_is_rejected` |
| FR-P-11 | `test_buy_rejects_non_positive_quantity` |
| FR-P-12, FR-P-15 | `test_sell_reduces_position_and_realizes_profit` |
| FR-P-13, FR-P-17 | `test_selling_more_than_held_is_rejected` |
| FR-P-14 | `test_selling_position_that_does_not_exist_is_rejected` |
| FR-P-16 | `test_full_sell_closes_position` |
| FR-P-18, FR-P-19, FR-P-20 | `test_summary_computes_value_pnl_and_realized_result` |
| FR-P-21 | `test_summary_marks_positions_without_price` |
| FR-P-22 | `test_positions_endpoint_returns_current_positions` |
| FR-P-23 | `test_transaction_history_lists_all_operations` |
| Точность цен (DEF-23) | `QuotationPrecisionTests.test_fractional_part_is_preserved`, `test_whole_numbers_stay_whole` |
| FR-P-05, FR-P-24, FR-P-25, FR-P-26, FR-P-27, FR-P-28 | проверяются схемой/кодом и системными проверками (`manage.py check`, `makemigrations --check`) |