from __future__ import annotations
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static
from ..models import DataStore


class TickerBar(Widget):
    DEFAULT_CSS = """
    TickerBar {
        height: 3;
        background: #161b22;
        border-bottom: solid #30363d;
        layout: horizontal;
        padding: 0 2;
        align: left middle;
    }
    TickerBar .product { color: white; text-style: bold; width: auto; padding: 0 2; }
    TickerBar .price   { color: white; text-style: bold; width: auto; padding: 0 3; }
    TickerBar .up      { color: #3fb950; width: auto; padding: 0 1; }
    TickerBar .down    { color: #f85149; width: auto; padding: 0 1; }
    TickerBar .dim     { color: #8b949e; width: auto; padding: 0 2; }
    TickerBar .conn    { width: auto; padding: 0 1; }
    """

    def __init__(self, store: DataStore, **kwargs) -> None:
        super().__init__(**kwargs)
        self._store = store

    def compose(self) -> ComposeResult:
        yield Static("BTC-USD ★", classes="product")
        yield Static("", id="tb-price",  classes="price")
        yield Static("", id="tb-chg",    classes="dim")
        yield Static("", id="tb-vol",    classes="dim")
        yield Static("", id="tb-high",   classes="dim")
        yield Static("", id="tb-low",    classes="dim")
        yield Static("", id="tb-conn",   classes="conn")

    def refresh_data(self) -> None:
        t = self._store.ticker

        # Connection status always shown, regardless of whether price is in yet
        conn     = "● LIVE" if self._store.connected else "○ connecting…"
        conn_cls = "up" if self._store.connected else "down"
        self.query_one("#tb-conn", Static).set_classes(conn_cls)
        self.query_one("#tb-conn").update(conn)

        if t.price == 0:
            return

        chg_pct = t.price_24h_pct
        chg_cls = "up" if chg_pct >= 0 else "down"
        chg_sym = "▲" if chg_pct >= 0 else "▼"

        self.query_one("#tb-price").update(f"${t.price:,.2f}")
        self.query_one("#tb-chg", Static).set_classes(chg_cls)
        self.query_one("#tb-chg").update(f"{chg_sym} {abs(chg_pct):.2f}%")
        vol_usd = t.volume_24h * t.price
        vol_str = f"${vol_usd/1e9:.2f}B" if vol_usd >= 1e9 else f"${vol_usd/1e6:.0f}M"
        self.query_one("#tb-vol").update(f"24h Vol: {vol_str}")
        self.query_one("#tb-high").update(f"H: ${t.high_24h:,.2f}")
        self.query_one("#tb-low").update(f"L: ${t.low_24h:,.2f}")
