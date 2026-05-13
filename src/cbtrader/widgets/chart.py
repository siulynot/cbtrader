from __future__ import annotations
import asyncio
from datetime import datetime

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Button, Static
from textual.containers import Horizontal
from textual_plotext import PlotextPlot

from ..api.rest import CoinbaseREST

_TIMEFRAMES = ["1m", "5m", "15m", "1h", "6h", "1D"]
_GRANULARITY = {
    "1m":  "ONE_MINUTE",
    "5m":  "FIVE_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "1h":  "ONE_HOUR",
    "6h":  "SIX_HOUR",
    "1D":  "ONE_DAY",
}
_CANDLE_LIMIT = {
    "1m": 100, "5m": 100, "15m": 80, "1h": 72, "6h": 60, "1D": 60,
}
# strftime format for building date strings passed to plotext
_STRFTIME = {
    "1m":  "%d/%m/%Y %H:%M:%S",
    "5m":  "%d/%m/%Y %H:%M:%S",
    "15m": "%d/%m/%Y %H:%M:%S",
    "1h":  "%d/%m/%Y %H:%M:%S",
    "6h":  "%d/%m/%Y %H:%M:%S",
    "1D":  "%d/%m/%Y",
}
# plotext date_form format (no % signs — plotext adds them via correct_form())
_PLT_FORM = {
    "1m":  "d/m/Y H:M:S",
    "5m":  "d/m/Y H:M:S",
    "15m": "d/m/Y H:M:S",
    "1h":  "d/m/Y H:M:S",
    "6h":  "d/m/Y H:M:S",
    "1D":  "d/m/Y",
}


class ChartPanel(Widget):
    DEFAULT_CSS = """
    ChartPanel {
        layout: vertical;
        border: solid #30363d;
        border-title-color: #8b949e;
    }
    ChartPanel #tf-bar {
        height: 3;
        background: #161b22;
        border-bottom: solid #30363d;
        layout: horizontal;
        padding: 0 1;
        align: left middle;
    }
    ChartPanel #tf-bar Button {
        height: 1;
        min-width: 5;
        background: #21262d;
        border: none;
        color: #8b949e;
        margin: 0 0 0 1;
    }
    ChartPanel #tf-bar Button.-active-tf {
        background: #1f6feb;
        color: white;
    }
    ChartPanel #chart-status {
        height: 1;
        color: #8b949e;
        padding: 0 1;
        text-align: right;
    }
    ChartPanel PlotextPlot {
        height: 1fr;
    }
    """
    BORDER_TITLE = "Chart"

    def __init__(self, rest: CoinbaseREST, product_id: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._rest       = rest
        self._product_id = product_id
        self._tf         = "1h"
        self._candles: list[dict] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="tf-bar"):
            for tf in _TIMEFRAMES:
                cls = "active-tf" if tf == self._tf else ""
                yield Button(tf, id=f"tf-{tf}", classes=cls)
        yield PlotextPlot(id="chart-plot")
        yield Static("", id="chart-status")

    def on_mount(self) -> None:
        self.run_worker(self._load_candles(), name="chart-init")
        self.set_interval(60.0, self._auto_refresh)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if not bid.startswith("tf-"):
            return
        tf = bid[3:]
        if tf not in _GRANULARITY:
            return
        # Update active button styling
        for t in _TIMEFRAMES:
            btn = self.query_one(f"#tf-{t}", Button)
            if t == tf:
                btn.add_class("active-tf")
            else:
                btn.remove_class("active-tf")
        self._tf = tf
        self.run_worker(self._load_candles(), name="chart-tf-change")

    def _auto_refresh(self) -> None:
        self.run_worker(self._load_candles(), name="chart-refresh")

    async def _load_candles(self) -> None:
        self.query_one("#chart-status", Static).update("[dim]Loading…[/]")
        try:
            gran  = _GRANULARITY[self._tf]
            limit = _CANDLE_LIMIT[self._tf]
            candles = await asyncio.to_thread(
                self._rest.get_candles, self._product_id, gran, limit
            )
            # Coinbase returns newest-first; sort oldest→newest
            self._candles = sorted(candles, key=lambda c: int(c.get("start", 0)))
            self._plot()
            self.query_one("#chart-status", Static).update(
                f"[dim]{self._product_id}  {self._tf}  {len(self._candles)} candles[/]"
            )
        except Exception as e:
            self.query_one("#chart-status", Static).update(f"[red]Chart error: {e}[/]")

    def _plot(self) -> None:
        if not self._candles:
            return

        strfmt  = _STRFTIME[self._tf]
        pltform = _PLT_FORM[self._tf]
        dates, opens, closes, highs, lows = [], [], [], [], []
        for c in self._candles:
            ts = int(c.get("start", 0))
            dates.append(datetime.utcfromtimestamp(ts).strftime(strfmt))
            opens.append(float(c.get("open", 0)))
            closes.append(float(c.get("close", 0)))
            highs.append(float(c.get("high", 0)))
            lows.append(float(c.get("low", 0)))

        plot = self.query_one("#chart-plot", PlotextPlot)
        plt  = plot.plt

        plt.clear_figure()
        plt.theme("dark")
        plt.date_form(pltform)
        plt.candlestick(
            dates,
            {"Open": opens, "Close": closes, "High": highs, "Low": lows},
            colors=["green+", "red+"],
        )
        plt.title(f"{self._product_id}  {self._tf}")
        plt.xlabel("")
        plt.xfrequency(max(1, len(dates) // 10))

        plot.refresh()
