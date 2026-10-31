from tinkoff.invest import Client

from config.settings import TINKOFF_TOKEN, logger


def get_last_data(share):
    try:
        with Client(TINKOFF_TOKEN) as client:
            resp = client.market_data.get_last_prices(figi=[share.figi])
            last_prices = getattr(resp, "last_prices", None)
            if not last_prices:
                raise ValueError("No last prices returned")
            price_obj = last_prices[0] if isinstance(last_prices, (list, tuple)) else last_prices
            price = getattr(price_obj, "price", None)
            units = getattr(price, "units", None) if price is not None else None
            nano = getattr(price, "nano", None) if price is not None else None
            value = units
            if units is not None and nano is not None:
                try:
                    value = float(units) + float(nano) / 1e9
                except Exception:
                    value = units
            elif units is None and price is not None and hasattr(price, "value"):
                value = price.value
            ts = getattr(price_obj, "time", None)
            logger.info(f"Get last data for share with id {share.id}")
            return [value, ts]
    except Exception as e:
        logger.error(e)
        raise

