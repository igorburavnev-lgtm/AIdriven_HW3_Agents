# FEATURE_REPORT.md — Задание №4: «Виртуальный инвестиционный портфель»

## 1. Обоснование выбора: DRF API, а не HTML-интерфейс

В проекте действительно есть шаблоны, но только для CRUD справочника акций
(`dashboard/templates/dashboard/*.html`), и они одностраничные: список, карточка, форма,
подтверждение удаления. Для портфеля требуется другой набор экранов (список портфелей,
карточка с позициями, форма сделки, таблица истории, сводка P&L) — то есть **новый UI
«с нуля»**, а не переиспользование существующих шаблонов.

Решающие аргументы в пользу REST API:

| Критерий | DRF API | HTML UI |
|---|---|---|
| Соответствие существующей архитектуре | Проект уже имеет слой DRF (`/api/v1/shares/`), `rest_framework` в `INSTALLED_APPS`, 9 API-тестов | Потребовал бы 5–6 новых шаблонов и вьюх |
| Проверяемость | 17 автотестов проверяют поведение напрямую | Потребовались бы Selenium/интеграционные тесты вёрстки |
| Денежная логика | Операции покупки/продажи — это команды, а не формы; API выражает их явно (`buy`/`sell`) | Пришлось бы дублировать валидацию в формах |
| Границы изменений | Не затрагивает существующие вьюхи и их поведение | Риск регрессий в общем `base.html` и навигации |
| Трудоёмкость | 3 модуля | ~6 шаблонов + CSS + формы |

Итог: **основной интерфейс — REST API**; для администратора дополнительно расширена
Django-админка (просмотр портфелей, позиций и операций). Это даёт полноценный доступ
к функциональности без разработки нового публичного UI. Ограничение зафиксировано в разделе 6.

## 2. Что реализовано

### 2.1 Модель данных

| Модель | Назначение | Ключевые поля | Ограничения |
|---|---|---|---|
| `Portfolio` | Портфель пользователя | `owner` (FK → `auth.User`, CASCADE), `name`, `created_at`, `updated_at` | UNIQUE `(owner, name)` |
| `Position` | Текущая позиция по бумаге | `portfolio` (FK, CASCADE), `share` (FK → `Share`, PROTECT), `quantity` `Decimal(18,6)`, `avg_price` `Decimal(18,6)` | UNIQUE `(portfolio, share)`, CHECK `quantity >= 0` |
| `Transaction` | История операций | `portfolio`, `share`, `kind` (`buy`/`sell`), `quantity`, `price`, `realized_pnl`, `executed_at`, `created_at` | сортировка `-executed_at, -id` |

Связь с существующей моделью: `Position.share` и `Transaction.share` — внешние ключи на
`dashboard.Share` с `on_delete=PROTECT`, поэтому акцию нельзя удалить из справочника, пока
по ней есть позиции или операции. `Share` при этом не изменялась.

Миграция: `dashboard/migrations/0008_portfolio_position_transaction_and_more.py`
(создаёт три таблицы и три ограничения; `makemigrations --check` подтверждает отсутствие
незафиксированных изменений).

### 2.2 Бизнес-логика

Вынесена в `dashboard/services/portfolio.py`, без импортов DRF — переиспользуема и
тестируема отдельно:

- `execute_trade(portfolio, share, kind, quantity, price=None, executed_at=None)` —
  атомарная (`@transaction.atomic`) покупка/продажа с блокировкой строки позиции
  (`select_for_update`), пересчётом средневзвешенной цены при покупке и фиксацией
  реализованного результата при продаже;
- `portfolio_summary(portfolio)` — стоимость, себестоимость, нереализованный,
  реализованный и суммарный P&L, разбивка по позициям;
- `TradeError` — доменная ошибка, транслируемая в HTTP 400;
- `to_decimal` / `share_price` — безопасное преобразование чисел (через `str()`, чтобы
  не тащить двоичную погрешность float) и квантование до 6 знаков.

### 2.3 REST API

Базовый адрес: `/api/v1/portfolios/`. Все эндпоинты требуют аутентификации
(`IsAuthenticated`) и работают только с портфелями текущего пользователя.

| Метод | URL | Назначение | Ответ |
|---|---|---|---|
| GET | `/api/v1/portfolios/` | список своих портфелей | 200, `count/next/previous/results` |
| POST | `/api/v1/portfolios/` | создать портфель | 201 |
| GET | `/api/v1/portfolios/{id}/` | карточка портфеля | 200 / 404 |
| PATCH/PUT | `/api/v1/portfolios/{id}/` | переименовать | 200 |
| DELETE | `/api/v1/portfolios/{id}/` | удалить (каскадно) | 204 |
| GET | `/api/v1/portfolios/{id}/positions/` | текущие позиции с расчётами | 200 |
| GET | `/api/v1/portfolios/{id}/transactions/` | история операций | 200 (пагинация) |
| GET | `/api/v1/portfolios/{id}/summary/` | стоимость и P&L | 200 |
| POST | `/api/v1/portfolios/{id}/buy/` | виртуальная покупка | 201 |
| POST | `/api/v1/portfolios/{id}/sell/` | виртуальная продажа | 201 / 400 |

Пример покупки:

```http
POST /api/v1/portfolios/1/buy/
Content-Type: application/json

{"share": 1, "quantity": "10", "price": "100"}
```

```json
{
  "transaction": {"id": 1, "kind": "buy", "quantity": "10.000000", "price": "100.000000",
                  "realized_pnl": "0.000000", "ticker": "SBER"},
  "position":    {"id": 1, "ticker": "SBER", "quantity": "10.000000",
                  "avg_price": "100.000000", "current_price": 250.0,
                  "market_value": "2500.000000", "unrealized_pnl": "1500.000000"},
  "summary":     {"total_value": "2500.000000", "total_cost": "1000.000000",
                  "unrealized_pnl": "1500.000000", "realized_pnl": "0.000000",
                  "total_pnl": "1500.000000", "unpriced_positions": 0}
}
```

Пример отказа при продаже больше, чем есть:

```http
POST /api/v1/portfolios/1/sell/
{"share": 1, "quantity": "999"}
→ 400 {"detail": "Недостаточно бумаг SBER: в портфеле 5.000000, запрошено 999.000000"}
```

## 3. Добавленные и изменённые файлы

### 3.1 Добавленные

| Файл | Назначение |
|---|---|
| `dashboard/services/portfolio.py` | бизнес-логика портфеля (сделки, сводка) |
| `dashboard/api/v1/portfolio_serializer.py` | сериализаторы `Portfolio`, `Position`, `Transaction`, входных данных сделки |
| `dashboard/api/v1/portfolio_views.py` | `PortfolioViewSet` с действиями `positions`, `transactions`, `summary`, `buy`, `sell` |
| `dashboard/migrations/0008_portfolio_position_transaction_and_more.py` | миграция новых моделей и ограничений |
| `dashboard/tests_portfolio.py` | 19 тестов (17 API + 2 на точность цен) |
| `FEATURE_REQUIREMENTS.md` | проверяемые требования |
| `FEATURE_REPORT.md` | этот отчёт |

### 3.2 Изменённые

| Файл | Что изменено |
|---|---|
| `dashboard/models.py` | добавлены `Portfolio`, `Position`, `Transaction`; у `Share` добавлен `__str__` |
| `dashboard/admin.py` | регистрация новых моделей, inline позиций в карточке портфеля |
| `dashboard/api/v1/router.py` | регистрация `portfolios`, замена wildcard-импорта на явный |

Файлы, изменённые на этапе задания №3 (модернизация), перечислены в `MODERNIZATION.md`;
их поведение для существующего функционала не менялось — подтверждено 14 тестами
исходного функционала (10 исходных + 4 регрессионных).

## 4. Как проверялось

Окружение: CPython 3.12.14, Windows, SQLite; `Django 5.2.18`, `DRF 3.16.1`.

| Проверка | Команда | Результат |
|---|---|---|
| Системные проверки | `python manage.py check` | `System check identified no issues (0 silenced).` |
| Модели ↔ миграции | `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| Миграции | `python manage.py migrate` | `dashboard.0008_… OK` |
| Тесты | `python manage.py test dashboard` | **33 теста, OK** |

Состав тестов (`dashboard/tests_portfolio.py`):

| Тест | Что проверяет |
|---|---|
| `test_create_portfolio_assigns_current_user` | создание портфеля и автоматическая привязка владельца |
| `test_portfolio_list_is_scoped_to_owner` | изоляция списка портфелей |
| `test_duplicate_portfolio_name_is_rejected` | 400 при дубликате названия |
| `test_other_user_cannot_access_foreign_portfolio` | 404 на чужой портфель |
| `test_endpoints_require_authentication` | 401/403 для анонима |
| `test_buy_creates_position_with_market_price` | покупка по рыночной цене |
| `test_second_buy_recalculates_weighted_average_price` | средневзвешенная цена (100/200 → 150) |
| `test_buy_rejects_non_positive_quantity` | отказ при `quantity = 0` |
| `test_buy_without_price_and_without_market_data_is_rejected` | отказ при неизвестной цене |
| `test_sell_reduces_position_and_realizes_profit` | уменьшение позиции, `avg_price` неизменна, P&L = 200 |
| `test_selling_more_than_held_is_rejected` | **граничный случай**: продажа больше остатка → 400, состояние не изменилось |
| `test_selling_position_that_does_not_exist_is_rejected` | **граничный случай**: продажа без позиции → 400 |
| `test_full_sell_closes_position` | полная продажа удаляет позицию |
| `test_summary_computes_value_pnl_and_realized_result` | стоимость 3750, себестоимость 2250, нереализованный 1500, реализованный 500, итого 2000 |
| `test_summary_marks_positions_without_price` | позиция без цены исключена из итога и помечена |
| `test_transaction_history_lists_all_operations` | история из двух операций в обратном порядке |
| `test_positions_endpoint_returns_current_positions` | состав ответа `positions` |
| `QuotationPrecisionTests` (2) | `100.55` не превращается в `100` (регрессия DEF-23) |

Ручная проверка API (в дополнение к тестам) выполнялась на запущенном
`runserver`: `GET /` → 200, `GET /api/v1/shares/` → 200, `GET /user/login/` → 200,
`GET /admin/` → 200, `GET /1` → 200 с сообщением о недоступности графика.

## 5. Принятые решения по неоднозначностям

| Вопрос | Решение | Обоснование |
|---|---|---|
| Метод учёта при продаже | Средняя цена (average cost), `avg_price` не меняется при продаже | Простейший и наиболее прозрачный для виртуального портфеля; FIFO/LIFO потребовали бы хранить лоты |
| Округление | `Decimal(18,6)`, квантование `ROUND_HALF_EVEN` (по умолчанию `Decimal`) | Детерминированно и без ошибок float |
| Полная продажа | Позиция удаляется, история операций остаётся | Пустые строки-позиции засоряют список; история — отдельная сущность |
| Портфель без начального кэша | Кэш не моделируется; покупка не ограничена балансом | Направление «виртуальный портфель» в задании не требует денежного счёта |
| Несколько валют | Суммы не конвертируются; в сводке возвращается список `currencies` | Курсы валют вне объёма; лучше явно показать смешение, чем молча суммировать |
| Цена сделки | По умолчанию `Share.last_price`, можно передать явно | Позволяет моделировать сделки без зависимости от фонового обновления котировок |
| Публичность API портфелей | Только `IsAuthenticated` + фильтр по владельцу | В отличие от справочника акций, портфель — персональные данные |

## 6. Остающиеся ограничения

1. **Нет публичного HTML-интерфейса портфеля.** Функциональность доступна через API и
   админку. UI потребовал бы отдельных шаблонов; выбор обоснован в разделе 1.
2. **Кэш и комиссии не моделируются.** Баланс не ограничивает покупку; брокерские
   комиссии, налоги и дивиденды не учитываются.
3. **Одна валюта на итог.** `total_value`/`total_pnl` суммируют бумаги в разных валютах
   без конвертации; список валют возвращается в `currencies`. Для корректного итога нужен
   слой курсов.
4. **Котировки не в реальном времени.** Стоимость считается по `Share.last_price`,
   который обновляет Celery-задача; при отсутствии Redis/токена цена остаётся прежней.
5. **`select_for_update` не действует на SQLite.** На PostgreSQL блокировка строки
   работает; на SQLite конкурентные сделки не сериализуются. Тесты выполняются на SQLite.
6. **Дробные акции разрешены** (`Decimal(18,6)`), хотя у реальных брокеров лотность
   ограничена. Валидация лотности не реализована.
7. **Нет эндпоинта редактирования истории.** Операции неизменяемы (append-only);
   исправление ошибочной сделки не предусмотрено — можно удалить позицию или портфель.
8. **Наследуемые ограничения справочника.** `DEF-19` (`uid` при создании акции через API)
   и `DEF-32` (regex-поиск только на PostgreSQL) остаются, см. `MODERNIZATION.md` раздел 7.
