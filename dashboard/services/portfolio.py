"""Business logic of the virtual investment portfolio.

Kept free of DRF imports so it can be reused by the API, the admin and the
management commands, and unit-tested on its own.
"""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from dashboard.models import Position, Share, Transaction

QUANT = Decimal("0.000001")
ZERO = Decimal("0")


class TradeError(Exception):
    """Raised when a virtual trade violates a business rule."""


def to_decimal(value) -> Decimal:
    """Convert a number/string to a quantized Decimal without binary float noise."""
    if value is None:
        raise TradeError("Значение не задано")
    try:
        # str() first: Decimal(0.1) would keep the float representation error.
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise TradeError(f"Некорректное числовое значение: {value!r}") from exc
    return result.quantize(QUANT)


def share_price(share: Share) -> Decimal | None:
    """Last known market price of a share, or ``None`` when it was never loaded."""
    if share.last_price is None:
        return None
    return to_decimal(share.last_price)


def _resolve_price(share: Share, price) -> Decimal:
    value = to_decimal(price) if price is not None else share_price(share)
    if value is None:
        raise TradeError(
            f"Цена {share.ticker} неизвестна: укажите цену явно или дождитесь обновления котировок"
        )
    if value <= 0:
        raise TradeError("Цена должна быть больше нуля")
    return value


def _check_quantity(quantity) -> Decimal:
    value = to_decimal(quantity)
    if value <= 0:
        raise TradeError("Количество должно быть больше нуля")
    return value


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
    """Execute a virtual BUY or SELL and return the recorded transaction.

    BUY recalculates the weighted average purchase price of the position.
    SELL reduces the position (realising P&L) and never allows selling more
    than is currently held.
    """
    quantity = _check_quantity(quantity)
    price = _resolve_price(share, price)
    executed_at = executed_at or timezone.now()

    if kind == Transaction.Kind.BUY:
        position = (
            Position.objects.select_for_update()
            .filter(portfolio=portfolio, share=share)
            .first()
        )
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
        position = (
            Position.objects.select_for_update()
            .filter(portfolio=portfolio, share=share)
            .first()
        )
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
            # Fully closed position: drop the row, the history stays in Transaction.
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
    """Aggregate current value, cost basis and P&L of a portfolio."""
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
