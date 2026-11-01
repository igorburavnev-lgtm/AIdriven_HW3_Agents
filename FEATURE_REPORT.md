# FEATURE_REPORT.md — виртуальный инвестиционный портфель

## 1. Что реализовано

### 1.1 Модель данных

Three new entities, all in the existing `dashboard` app so no new app had to be registered:

| Модель | Поля | Ограничения |
|---|---|---|
| `Portfolio` | `owner` (FK → `auth.User`, CASCADE), `name` (100), `created_at`, `updated_at` | UNIQUE `(owner, name)` |
| `Position` | `portfolio` (FK, CASCADE), `share` (FK → `Share`, PROTECT), `quantity` `Decimal(18,6)`, `avg_price` `Decimal(18,6)`, метки времени | UNIQUE `(portfolio, share)`, CHECK `quantity >= 0` |
| `Transaction` | `portfolio`, `share` (PROTECT), `kind` (`buy`/`sell`), `quantity`, `price`, `realized_pnl`, `executed_at`, `created_at` | сортировка `-executed_at, -id` |

`Share` was left untouched apart from a `__str__` helper. The relation to it is a real foreign key
with `on_delete=PROTECT`, so a share that is referenced by a position cannot be deleted from the
catalogue — that is the behaviour I wanted, and it is enforced by the database rather than by a view.

Migration: `dashboard/migrations/0008_portfolio_position_transaction_and_more.py`.

### 1.2 Бизнес-логика

`dashboard/services/portfolio.py`, no DRF imports:

- `execute_trade(...)` — atomic buy/sell with a row lock, weighted average on buy, realised result on
  sell;
- `portfolio_summary(portfolio)` — value, cost basis, unrealised/realised/total P&L, per-position rows;
- `TradeError` — domain error translated to HTTP 400 by the view;
- `to_decimal` / `share_price` — float-safe conversion and quantisation.

### 1.3 API

Base path `/api/v1/portfolios/`, authentication required, queryset always filtered by owner.

| Метод | URL | Назначение |
|---|---|---|
| GET/POST | `/api/v1/portfolios/` | список / создание |
| GET/PATCH/PUT/DELETE | `/api/v1/portfolios/{id}/` | карточка / переименование / удаление |
| GET | `/{id}/positions/` | позиции с расчётами |
| GET | `/{id}/transactions/` | история операций (с пагинацией) |
| GET | `/{id}/summary/` | стоимость и P&L |
| POST | `/{id}/buy/` | покупка |
| POST | `/{id}/sell/` | продажа |

A buy responds with the transaction, the resulting position and the whole summary, so the client
does not have to issue three requests to refresh a screen:

```json
{
  "transaction": {"id": 1, "kind": "buy", "quantity": "10.000000", "price": "100.000000", "realized_pnl": "0.000000"},
  "position":    {"id": 1, "ticker": "SBER", "quantity": "10.000000", "avg_price": "100.000000"},
  "summary":     {"total_value": "2500.000000", "total_cost": "1000.000000", "unrealized_pnl": "1500.000000", "realized_pnl": "0.000000", "total_pnl": "1500.000000"}
}
```

### 1.4 Админка и тесты

`Portfolio` (с inline-таблицей позиций), `Position` и `Transaction` зарегистрированы в
`dashboard/admin.py`. Тесты — `dashboard/tests_portfolio.py`, 19 штук.

---

## 2. Какие решения принимал и почему

### Решение 1: API вместо HTML-интерфейса

The project does have templates — but only five, and all of them are screens of the share CRUD
(`list`, `detail`, `create`, `delete`, `base`). A portfolio needs a different set: a portfolio list, a
portfolio card with positions, a trade form, a history table, a P&L summary. Not one of them could be
reused, so "we already have templates" would have meant writing a new UI anyway.

I chose DRF because the project already has a working API layer (`/api/v1/shares/`, `ModelViewSet`,
`django_filters`, nine API tests) and because trade operations are commands with invariants, which an
API expresses directly as `buy`/`sell` rather than as form submissions. I also get verifiable
behaviour: 17 API tests check the money logic exactly, whereas a UI would need browser tests to get
the same confidence. For administrators I still registered the models in the admin, so the feature is
reachable through a UI without a single new template.

### Решение 2: средняя цена и удаление закрытой позиции

The task says «средняя цена приобретения», so I implemented average cost rather than FIFO/LIFO lots.
That gives one non-obvious consequence: **a sale must not change `avg_price`**. I made it a separate
requirement (FR-P-12) and a dedicated assertion, because a "recompute average on sale" bug is easy to
introduce and hard to notice.

The second half of this decision is what to do when quantity reaches zero. I delete the `Position`
row and keep the `Transaction` rows. My hypothesis was that an empty position carries no information —
the history already records everything — and the tests confirm the history survives
(`test_full_sell_closes_position`, `test_transaction_history_lists_all_operations`).

### Решение 3: `Decimal`, не `float`

`Share.last_price` is a `FloatField`, so I had to decide whether to keep floats for money. I assumed
that repeated float arithmetic would drift (0.1 + 0.2 style), which would show up as a P&L ending in
…9999. So quantities and prices are `Decimal(18,6)`, and the conversion from the model goes through
`str()`:

```python
Decimal(str(share.last_price))   # not Decimal(share.last_price)
```

`Decimal(100.55)` would itself carry the binary representation error, while `Decimal("100.55")` is
exact. The summary test asserts exact values (`3750.000000`, `2250.000000`, `1500.000000`, `500.000000`,
`2000.000000`), and it passes — which is the evidence that this was worth doing.

### Проверка гипотезы про блокировки

`select_for_update()` does not work on SQLite the way it does on PostgreSQL. I suspected the tests
would fail with `NotSupportedError`. I ran them: SQLite simply ignores the lock, the statements stay
atomic through `transaction.atomic`, and all tests passed. So the code path is correct for PostgreSQL
(where the lock actually serialises concurrent trades) and harmless for SQLite — noted as a limitation
rather than worked around.

---

## 3. Как проверял

Environment: CPython 3.12.14, Windows, SQLite, Django 5.2.18, DRF 3.16.1.

| Проверка | Команда | Результат |
|---|---|---|
| Системные проверки | `python manage.py check` | `System check identified no issues (0 silenced).` |
| Дрейф миграций | `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| Миграции | `python manage.py migrate` | `dashboard.0008_… OK` |
| Тесты | `python manage.py test dashboard` | **33 теста, OK** |
| Сервер | `runserver` + probes | `/` 200, `/api/v1/shares/` 200, `/user/login/` 200, `/admin/` 200 |

Что именно покрывают 19 новых тестов:

| Тест | Проверяет |
|---|---|
| `test_create_portfolio_assigns_current_user` | владелец проставляется автоматически |
| `test_portfolio_list_is_scoped_to_owner` | список изолирован по владельцу |
| `test_duplicate_portfolio_name_is_rejected` | 400 на дубликат имени |
| `test_other_user_cannot_access_foreign_portfolio` | 404 на чужой портфель |
| `test_endpoints_require_authentication` | 401/403 для анонима |
| `test_buy_creates_position_with_market_price` | покупка по рыночной цене |
| `test_second_buy_recalculates_weighted_average_price` | средневзвешенная цена 100/200 → 150 |
| `test_buy_rejects_non_positive_quantity` | отказ на `quantity = 0` |
| `test_buy_without_price_and_without_market_data_is_rejected` | отказ без цены |
| `test_sell_reduces_position_and_realizes_profit` | количество −4, `avg_price` та же, P&L 200 |
| `test_selling_more_than_held_is_rejected` | **граничный случай**: продажа 10 из 5 → 400, состояние цело |
| `test_selling_position_that_does_not_exist_is_rejected` | **граничный случай**: нет позиции → 400 |
| `test_full_sell_closes_position` | полная продажа удаляет позицию, история остаётся |
| `test_summary_computes_value_pnl_and_realized_result` | 3750 / 2250 / 1500 / 500 / 2000 |
| `test_summary_marks_positions_without_price` | позиция без цены исключена из итога |
| `test_transaction_history_lists_all_operations` | две операции в обратном порядке |
| `test_positions_endpoint_returns_current_positions` | состав ответа позиций |
| `QuotationPrecisionTests` (2 теста) | `100.55` не превращается в `100` (регрессия из задания №3) |

---

## 4. Ограничения

1. **Нет публичного UI портфеля.** Доступ — через API и админку; обоснование в разделе 2.
2. **Кэш и комиссии не моделируются.** Баланс не ограничивает покупку; брокерские комиссии,
   налоги и дивиденды не учитываются.
3. **Валюта не конвертируется.** `total_value` складывает бумаги в разных валютах как есть; список
   валют возвращается в `currencies`. Корректный итог требует слоя курсов.
4. **Цены не в реальном времени.** Стоимость считается по `Share.last_price`, который обновляет
   Celery-задача; без Redis и токена цена остаётся прежней.
5. **`select_for_update` не сериализует сделки на SQLite** (см. раздел 2, «Проверка гипотезы»).
6. **Дробные акции разрешены** (`Decimal(18,6)`); лотность не проверяется.
7. **История неизменяема.** Исправить ошибочную сделку нельзя — можно удалить портфель.
8. **Наследуемые ограничения проекта:** `search_fields = ["$name"]` работает только на PostgreSQL;
   создание акции через API без `uid` может нарушить UNIQUE (см. `MODERNIZATION.md`, раздел 7).
