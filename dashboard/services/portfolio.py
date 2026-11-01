"""Business logic of the virtual investment portfolio.

Deliberately free of DRF imports: the API, the admin and the tests all reuse it.
"""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from dashboard.models import Position, Share, Transaction

# Six decimal places, matching the DecimalField(decimal_places=6) columns.
QUANT = Decimal("0.000001")
ZERO = Decimal("0")


class TradeError(Exception):
    """Raised when a virtual trade would break a business rule."""


def to_decimal(value) -> Decimal:
    """Convert a number or string to a quantised Decimal.

    Going through ``str()`` avoids the binary-float noise of ``Decimal(0.1)``.
    """
    if value is None:
        raise TradeError("Значение не задано")
    try:
        return Decimal(str(value)).quantize(QUANT)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise TradeError(f"Некорректное числовое значение: {value!r}") from exc


def share_price(share: Share) -> Decimal | None:
    """Last known market price, or ``None`` when quotes were never loaded."""
    if share.last_price is None:
        return None
    return to_decimal(share.last_price)


def _resolve_price(share: Share, price) -> Decimal:
    value = to_decimal(price) if price is not None else share_price(share)
    if value is None:
        raise TradeError(
            f"Цена {share.ticker} неизвестна: укажите цену явно "
            f"или дождитесь обновления котировок"
        )
    if value <= 0:
        raise TradeError("Цена должна быть больше нуля")
    return value


def _check_quantity(quantity) -> Decimal:
    value = to_decimal(quantity)
    if value <= 0:
        raise TradeError("Количество должно быть больше нуля")
    return value


def _locked_position(portfolio, share):
    """Position row locked for the duration of the current transaction."""
    return (
        Position.objects.select_for_update()
        .filter(portfolio=portfolio, share=share)
        .first()
    )


@transaction.atomic
def execute_trade(
    *,
    portfolio,
    share: Share,
    kind: str,
    quantity,
    price=None,
    executed_at=None,
) -> Transaction:
    """Execute a virtual BUY or SELL and record it.

    BUY recalculates the weighted average purchase price; SELL reduces the
    position and realises the result, never selling more than is held.
    """
    quantity = _check_quantity(quantity)
    price = _resolve_price(share, price)
    executed_at = executed_at or timezone.now()

    if kind == Transaction.Kind.BUY:
        position = _locked_position(portfolio, share)
        if position is None:
            position = Position.objects.create(
                portfolio=portfolio, share=share, quantity=ZERO, avg_price=ZERO
            )
        new_quantity = position.quantity + quantity
        total_cost = position.avg_price * position.quantity + price * quantity
        position.quantity = new_quantity
        position.avg_price = (total_cost / new_quantity).quantize(QUANT)
        position.save(update_fields=["quantity", "avg_price", "updated_at"])
        realized_pnl = ZERO

    elif kind == Transaction.Kind.SELL:
        position = _locked_position(portfolio, share)
        if position is None or position.quantity <= ZERO:
            raise TradeError(f"В портфеле нет бумаг {share.ticker}")
        if quantity > position.quantity:
            raise TradeError(
                f"Недостаточно бумаг {share.ticker}: в портфеле {position.quantity}, "
                f"запрошено {quantity}"
            )
        realized_pnl = ((price - position.avg_price) * quantity).quantize(QUANT)
        position.quantity -= quantity
        if position.quantity == ZERO:
            # Closed position: drop the row, the history lives in Transaction.
            position.delete()
        else:
            position.save(update_fields=["quantity", "updated_at"])

    else:
        raise TradeError(f"Неизвестный тип операции: {kind}")

    return Transaction.objects.create(
        portfolio=portfolio,
        share=share,
        kind=kind,
        quantity=quantity,
        price=price,
        realized_pnl=realized_pnl,
        executed_at=executed_at,
    )


def portfolio_summary(portfolio) -> dict:
    """Current value, cost basis and P&L for a portfolio."""
    rows = []
    total_value = ZERO
    total_cost = ZERO
    unpriced = 0
    currencies = set()

    for position in portfolio.positions.select_related("share").all():
        price = share_price(position.share)
        cost = position.cost_basis
        row = {
            "position_id": position.id,
            "share_id": position.share_id,
            "ticker": position.share.ticker,
            "name": position.share.name,
            "currency": position.share.currency,
            "quantity": position.quantity,
            "avg_price": position.avg_price,
            "current_price": price,
            "cost_basis": cost,
            "market_value": None,
            "unrealized_pnl": None,
            "unrealized_pnl_percent": None,
        }
        total_cost += cost
        currencies.add(position.share.currency)

        if price is None:
            # No quote -> the position cannot be valued; exclude it from the
            # totals instead of silently pretending it is worth zero.
            unpriced += 1
        else:
            market_value = (price * position.quantity).quantize(QUANT)
            unrealized = market_value - cost
            row["market_value"] = market_value
            row["unrealized_pnl"] = unrealized
            row["unrealized_pnl_percent"] = (
                (unrealized / cost * 100).quantize(Decimal("0.01")) if cost else None
            )
            total_value += market_value

        rows.append(row)

    realized_pnl = (
        portfolio.transactions.filter(kind=Transaction.Kind.SELL).aggregate(
            total=Sum("realized_pnl")
        )["total"]
        or ZERO
    )
    unrealized_pnl = total_value - total_cost

    return {
        "portfolio_id": portfolio.id,
        "name": portfolio.name,
        "currencies": sorted(currencies),
        "positions": rows,
        "positions_count": len(rows),
        "unpriced_positions": unpriced,
        "total_value": total_value,
        "total_cost": total_cost,
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": realized_pnl,
        "total_pnl": unrealized_pnl + realized_pnl,
    }
