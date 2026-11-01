"""Market data helpers backed by the Tinkoff Invest API."""

from django.conf import settings

from config.settings import logger

NANO_PER_UNIT = 1_000_000_000


def quotation_to_float(quotation) -> float:
    """Turn a Tinkoff ``Quotation`` into a float without losing the fraction.

    ``Quotation`` keeps the integer part in ``units`` and the fractional part in
    ``nano`` (1e-9). Reading only ``units`` — as the original code did — stored
    100.55 as 100.
    """
    return quotation.units + quotation.nano / NANO_PER_UNIT


def get_last_data(share):
    """Return ``[last_price, price_time]`` for ``share``.

    The SDK import is deferred on purpose: ``tinkoff-investments`` is no longer
    published on PyPI, so the web application must be able to import this module
    even when the package is absent. Only real API calls require it.
    """
    from tinkoff.invest import Client

    with Client(settings.TINKOFF_TOKEN) as client:
        response = client.market_data.get_last_prices(figi=[share.figi])

    if not response.last_prices:
        raise ValueError(f"Tinkoff API returned no last price for figi={share.figi}")

    last_price = response.last_prices[0]
    logger.info("Get last data for share with id %s", share.id)
    return [quotation_to_float(last_price.price), last_price.time]
