"""Access to market data provided by the Tinkoff Invest API."""

from django.conf import settings

from config.settings import logger

NANO = 1_000_000_000


def quotation_to_float(quotation) -> float:
    """Convert a Tinkoff ``Quotation`` to a float without losing fractions.

    ``Quotation`` stores the whole part in ``units`` and the fractional part in
    ``nano`` (1e-9). Reading only ``units`` (the previous behaviour) truncated
    prices such as 100.55 to 100.
    """
    return quotation.units + quotation.nano / NANO


def get_last_data(share):
    """Return ``[last_price, price_time]`` for ``share`` from the Tinkoff API.

    The SDK is imported lazily so that Django can start (and be tested) in
    environments where the optional Tinkoff dependency is not installed.
    """
    from tinkoff.invest import Client

    with Client(settings.TINKOFF_TOKEN) as client:
        response = client.market_data.get_last_prices(figi=[share.figi])

    if not response.last_prices:
        raise ValueError(f"Tinkoff API returned no prices for figi={share.figi}")

    last_price = response.last_prices[0]
    logger.info("Get last data for share with id %s", share.id)
    return [quotation_to_float(last_price.price), last_price.time]
