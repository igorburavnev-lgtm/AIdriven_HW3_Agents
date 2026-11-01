# FEATURE_REQUIREMENTS.md — виртуальный инвестиционный портфель

## Как я к этому пришёл

I started from the wording in `HOMEWORK.md` (пункт 2): «формировать персональные инвестиционные
портфели, моделировать операции покупки и продажи акций, учитывать количество и среднюю цену
приобретения, рассчитывать текущую стоимость портфеля, прибыль и убытки, а также просматривать
историю операций».

That sentence decomposes into five observable behaviours, so I turned each one into requirements I
could test rather than into prose. Three decisions shaped the whole design:

1. **Average price, not lots.** The task says «средняя цена приобретения», which is the average-cost
   method. It also means a sale must not change `avg_price` — only the quantity. That became an
   explicit requirement, because it is the kind of thing that silently breaks later.
2. **A trade is a command, not a document.** Buy/sell are actions with invariants ("can't sell more
   than you hold"), so they live in one atomic service function instead of being spread across a
   serializer and two view methods.
3. **History must survive.** Closing a position deletes the `Position` row, but `Transaction` rows
   stay, otherwise "просматривать историю операций" breaks exactly when it becomes interesting.

I also decided early that P&L has to be split into realised and unrealised. A single "profit" number
hides the difference between money already booked and money still exposed to the market.

## Область

**Входит:** персональные портфели; виртуальные покупка/продажа по бумагам из справочника `Share`;
учёт количества и средней цены; расчёт стоимости, реализованного и нереализованного P&L; история
операций; REST API + администрирование.

**Не входит:** реальные деньги и пополнение счёта, комиссии и налоги, конвертация валют,
котировки в реальном времени, публичный HTML-интерфейс портфеля (обоснование — `FEATURE_REPORT.md`,
раздел 2).

## Понятия

| Понятие | Определение |
|---|---|
| Портфель | именованный набор позиций, принадлежащий пользователю |
| Позиция | количество акций одного вида и средняя цена их приобретения |
| Операция | зафиксированный факт покупки или продажи |
| Средняя цена | средневзвешенная цена покупок; при продаже не меняется |
| Реализованный P&L | `(цена продажи − средняя цена) × количество` |
| Нереализованный P&L | `текущая стоимость − стоимость по средней цене` |

Денежные величины хранятся как `Decimal(18, 6)`.

## Требования

### Управление портфелями

**FR-P-01.** Аутентифицированный пользователь создаёт портфель запросом `POST /api/v1/portfolios/`
с полем `name`; владелец проставляется из `request.user` и в запросе не принимается.
→ `test_create_portfolio_assigns_current_user`

**FR-P-02.** `GET /api/v1/portfolios/` возвращает только портфели текущего пользователя
(формат `count/next/previous/results`).
→ `test_portfolio_list_is_scoped_to_owner`

**FR-P-03.** Обращение к портфелю другого пользователя возвращает **404**, а не 403: чужие
объекты не попадают в queryset.
→ `test_other_user_cannot_access_foreign_portfolio`

**FR-P-04.** Повторное имя портфеля у того же владельца возвращает **400** с понятным сообщением,
а не 500 от нарушения уникального индекса.
→ `test_duplicate_portfolio_name_is_rejected`

**FR-P-05.** `PATCH`/`PUT` переименовывают портфель, `DELETE` удаляет его вместе с позициями и
операциями (каскад).
→ схема миграции `0008` + `ModelViewSet`

**FR-P-06.** Любой эндпоинт `/api/v1/portfolios/…` без аутентификации возвращает **401/403**.
→ `test_endpoints_require_authentication`

### Покупка

**FR-P-07.** `POST /api/v1/portfolios/{id}/buy/` с `share` и `quantity` создаёт позицию, если её не
было; ответ **201** с `transaction`, `position`, `summary`.
→ `test_buy_creates_position_with_market_price`

**FR-P-08.** Повторная покупка суммирует количество и пересчитывает среднюю цену по формуле
`Σ(цена × кол-во) / Σ кол-во`; вторая позиция не создаётся. Пример: 10 по 100 + 10 по 200 = 20 по 150.
→ `test_second_buy_recalculates_weighted_average_price`

**FR-P-09.** Если `price` не передан, используется `Share.last_price`; явная цена имеет приоритет.
→ `test_buy_creates_position_with_market_price`, `test_second_buy_recalculates_weighted_average_price`

**FR-P-10.** Если цена неизвестна (нет `last_price` и не передана явно) — **400**, ничего не
создаётся.
→ `test_buy_without_price_and_without_market_data_is_rejected`

**FR-P-11.** `quantity ≤ 0` или нечисловое значение — **400**, состояние не меняется.
→ `test_buy_rejects_non_positive_quantity`

### Продажа

**FR-P-12.** Продажа уменьшает количество, но **не меняет** среднюю цену приобретения.
→ `test_sell_reduces_position_and_realizes_profit`

**FR-P-13.** Продажа больше остатка — **400** с указанием остатка; позиция и история не меняются.
→ `test_selling_more_than_held_is_rejected`

**FR-P-14.** Продажа бумаги, которой нет в портфеле, — **400** без создания операции.
→ `test_selling_position_that_does_not_exist_is_rejected`

**FR-P-15.** В операции сохраняется `realized_pnl = (цена − средняя цена) × количество`; значение
может быть отрицательным и возвращается в ответе и в истории.
→ `test_sell_reduces_position_and_realizes_profit`, `test_summary_computes_value_pnl_and_realized_result`

**FR-P-16.** Продажа всего остатка удаляет позицию; операции остаются в истории.
→ `test_full_sell_closes_position`

**FR-P-17.** Изменение позиции и запись операции выполняются в одной транзакции БД с блокировкой
строки позиции; отклонённая сделка не оставляет частичных изменений.
→ `test_selling_more_than_held_is_rejected` (после отказа 0 операций продажи)

### Стоимость и P&L

**FR-P-18.** `GET /api/v1/portfolios/{id}/summary/` возвращает `total_value` = Σ(кол-во × текущая
цена) и `total_cost` = Σ(кол-во × средняя цена).
→ `test_summary_computes_value_pnl_and_realized_result` (15 × 250 = 3750; 15 × 150 = 2250)

**FR-P-19.** `unrealized_pnl` = `total_value − total_cost`; по каждой позиции дополнительно
отдаются `market_value`, `unrealized_pnl`, `unrealized_pnl_percent`.
→ `test_summary_computes_value_pnl_and_realized_result` (1500)

**FR-P-20.** `realized_pnl` = сумма реализованных результатов по продажам; `total_pnl` =
`unrealized_pnl + realized_pnl`.
→ `test_summary_computes_value_pnl_and_realized_result` (500 и 2000)

**FR-P-21.** Позиция без цены не участвует в `total_value`, её `market_value` равен `null`, а
количество таких позиций возвращается в `unpriced_positions`.
→ `test_summary_marks_positions_without_price`

**FR-P-22.** `GET /api/v1/portfolios/{id}/positions/` отдаёт позиции с тикером, названием, валютой,
количеством, средней ценой, `cost_basis`, текущей ценой, стоимостью и нереализованным результатом.
→ `test_positions_endpoint_returns_current_positions`

### История

**FR-P-23.** `GET /api/v1/portfolios/{id}/transactions/` возвращает операции от новых к старым с
типом (`buy`/`sell`), подписью типа, тикером, количеством, ценой, `realized_pnl` и временем.
→ `test_transaction_history_lists_all_operations`

**FR-P-24.** Если в сделке передан `executed_at`, он сохраняется как время операции; иначе —
текущий момент.
→ `TradeInputSerializer` + `execute_trade`

### Данные

**FR-P-25.** `Portfolio`: `owner` (FK → `AUTH_USER_MODEL`, CASCADE), `name` (100), `created_at`,
`updated_at`; уникальность `(owner, name)`.

**FR-P-26.** `Position`: `portfolio` (FK, CASCADE), `share` (FK → `Share`, PROTECT), `quantity`
(≥ 0), `avg_price`, метки времени; уникальность `(portfolio, share)` и CHECK `quantity >= 0`.

**FR-P-27.** `Transaction`: `portfolio`, `share` (PROTECT), `kind`, `quantity`, `price`,
`realized_pnl`, `executed_at`, `created_at`; сортировка `-executed_at, -id`.

**FR-P-28.** Позиции и операции ссылаются на существующую модель `Share`; удалить акцию из
справочника, пока по ней есть позиции или операции, нельзя (`on_delete=PROTECT`).

**FR-P-29.** Портфели, позиции и операции доступны в Django-админке; в карточке портфеля позиции
показаны inline.

## Матрица «требование → тест»

| Требования | Тест |
|---|---|
| FR-P-01 … FR-P-06 | `test_create_portfolio_assigns_current_user`, `test_portfolio_list_is_scoped_to_owner`, `test_duplicate_portfolio_name_is_rejected`, `test_other_user_cannot_access_foreign_portfolio`, `test_endpoints_require_authentication` |
| FR-P-07 … FR-P-11 | `test_buy_creates_position_with_market_price`, `test_second_buy_recalculates_weighted_average_price`, `test_buy_rejects_non_positive_quantity`, `test_buy_without_price_and_without_market_data_is_rejected` |
| FR-P-12 … FR-P-17 | `test_sell_reduces_position_and_realizes_profit`, `test_selling_more_than_held_is_rejected`, `test_selling_position_that_does_not_exist_is_rejected`, `test_full_sell_closes_position` |
| FR-P-18 … FR-P-21 | `test_summary_computes_value_pnl_and_realized_result`, `test_summary_marks_positions_without_price` |
| FR-P-22, FR-P-23 | `test_positions_endpoint_returns_current_positions`, `test_transaction_history_lists_all_operations` |
| FR-P-24 … FR-P-29 | схема миграции + `manage.py check` / `makemigrations --check` |
