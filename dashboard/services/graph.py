"""Builds the price chart displayed on the share detail page."""

from datetime import timedelta

from django.conf import settings
from plotly.graph_objs import Scatter
from plotly.offline import plot

from dashboard.services.market_data import quotation_to_float

CHART_DAYS = 180


def get_graph(share):
    """Return a Plotly ``<div>`` with daily candles of the last 180 days."""
    # Deferred import: the Tinkoff SDK is optional at start-up time.
    from tinkoff.invest import CandleInterval, Client
    from tinkoff.invest.utils import now

    x_data, y_data = [], []
    with Client(settings.TINKOFF_TOKEN) as client:
        for candle in client.get_all_candles(
            figi=share.figi,
            from_=now() - timedelta(days=CHART_DAYS),
            interval=CandleInterval.CANDLE_INTERVAL_DAY,
        ):
            x_data.append(candle.time.date())
            y_data.append(quotation_to_float(candle.close))

    return plot(
        [
            Scatter(
                x=x_data,
                y=y_data,
                mode="lines",
                name=share.ticker,
                opacity=0.8,
                marker_color="red",
            )
        ],
        output_type="div",
        show_link=False,
        link_text="",
        # base.html already loads plotly.js from the CDN; embedding a second
        # ~3 MB copy in every response was pure waste.
        include_plotlyjs=False,
    )
