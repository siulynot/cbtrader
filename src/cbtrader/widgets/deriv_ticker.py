from __future__ import annotations
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static
from ..models import DataStore


class DerivTicker(Widget):
    DEFAULT_CSS = """
    DerivTicker {
        height: 3;
        background: #161b22;
        border-bottom: solid #30363d;
        layout: horizontal;
        padding: 0 2;
        align: left middle;
    }
    DerivTicker .product { color: #58a6ff; text-style: bold; width: auto; padding: 0 2; }
    DerivTicker .price   { color: white;   text-style: bold; width: auto; padding: 0 3; }
    DerivTicker .up      { color: #3fb950; width: auto; padding: 0 1; }
    DerivTicker .down    { color: #f85149; width: auto; padding: 0 1; }
    DerivTicker .dim     { color: #8b949e; width: auto; padding: 0 2; }
    DerivTicker .funding-pos { color: #3fb950; width: auto; padding: 0 1; }
    DerivTicker .funding-neg { color: #f85149; width: auto; padding: 0 1; }
    DerivTicker .conn    { width: auto; padding: 0 1; }
    """

    def __init__(self, store: DataStore, product_id: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._store      = store
        self._product_id = product_id

    def compose(self) -> ComposeResult:
        yield Static(self._product_id, classes="product")
        yield Static("", id="dt-price",    classes="price")
        yield Static("", id="dt-chg",      classes="dim")
        yield Static("", id="dt-funding",  classes="dim")
        yield Static("", id="dt-nextfund", classes="dim")
        yield Static("", id="dt-index",    classes="dim")
        yield Static("", id="dt-oi",       classes="dim")
        yield Static("", id="dt-vol",      classes="dim")
        yield Static("", id="dt-conn",     classes="conn")

    def refresh_data(self) -> None:
        t = self._store.ticker
        s = self._store

        conn     = "● LIVE" if s.connected else "○ connecting…"
        conn_cls = "up" if s.connected else "down"
        self.query_one("#dt-conn", Static).set_classes(conn_cls)
        self.query_one("#dt-conn").update(conn)

        if t.price == 0:
            return

        chg_pct = t.price_24h_pct
        chg_cls = "up" if chg_pct >= 0 else "down"
        chg_sym = "▲" if chg_pct >= 0 else "▼"
        self.query_one("#dt-price").update(f"${t.price:,.2f}")
        self.query_one("#dt-chg", Static).set_classes(chg_cls)
        self.query_one("#dt-chg").update(f"{chg_sym} {abs(chg_pct):.2f}%")

        fr_pct = s.funding_rate * 100
        fr_cls = "funding-pos" if fr_pct >= 0 else "funding-neg"
        self.query_one("#dt-funding", Static).set_classes(fr_cls)
        self.query_one("#dt-funding").update(f"Fr: {fr_pct:+.4f}%/hr")

        if s.next_funding:
            self.query_one("#dt-nextfund").update(f"Next: {s.next_funding[11:16]} UTC")

        if s.index_price > 0:
            self.query_one("#dt-index").update(f"Index: ${s.index_price:,.2f}")

        if s.open_interest > 0:
            oi_val = s.open_interest * t.price
            oi_str = f"${oi_val/1e9:.2f}B" if oi_val >= 1e9 else f"${oi_val/1e6:.0f}M"
            self.query_one("#dt-oi").update(f"OI: {oi_str}")

        if t.volume_24h > 0:
            vol_usd = t.volume_24h * t.price * s.contract_size
            vol_str = f"${vol_usd/1e9:.2f}B" if vol_usd >= 1e9 else f"${vol_usd/1e6:.1f}M"
            self.query_one("#dt-vol").update(f"Vol: {vol_str}")
