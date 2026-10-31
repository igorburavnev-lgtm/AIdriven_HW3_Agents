from datetime import timedelta

from plotly.graph_objs import Scatter
from plotly.offline import plot
from tinkoff.invest import CandleInterval, Client
from tinkoff.invest.utils import now

from config.settings import TINKOFF_TOKEN


def get_graph(share):
    try:
        with Client(TINKOFF_TOKEN) as client:
            x_data, y_data = [], []
            candles = []
            try:
                candles = client.get_all_candles(
                    figi=share.figi,
                    from_=now() - timedelta(days=180),
                    interval=CandleInterval.CANDLE_INTERVAL_DAY,
                )
            except Exception:
                candles = []

            for candle in candles:
                try:
                    ctime = getattr(candle, "time", None)
                    if ctime is not None and hasattr(ctime, "date"):
                        x_data.append(ctime.date())
                    elif ctime is not None:
                        x_data.append(ctime)
                    else:
                        continue
                    close = getattr(candle, "close", None)
                    units = getattr(close, "units", None) if close is not None else None
                    nano = getattr(close, "nano", None) if close is not None else None
                    if units is not None and nano is not None:
                        try:
                            y_data.append(float(units) + float(nano) / 1e9)
                            continue
                        except Exception:
                            pass
                    if units is not None:
                        y_data.append(units)
                    elif close is not None and hasattr(close, "value"):
                        y_data.append(close.value)
                    else:
                        y_data.append(0)
                except Exception:
                    continue

        if not x_data:
            return None

        plot_div = plot(
            [
                Scatter(
                    x=x_data,
                    y=y_data,
                    mode="lines",
                    name=share.ticker or "price",
                    opacity=0.8,
                    marker_color="red",
                )
            ],
            output_type="div",
            show_link=False,
            link_text="",
        )
        return plot_div
    except Exception:
        return None

