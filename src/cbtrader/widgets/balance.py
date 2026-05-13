from __future__ import annotations
from rich.text import Text
from textual.widget import Widget
from textual.widgets import DataTable
from ..models import DataStore

_SHOW = ["BTC", "USD", "USDC", "ETH"]


class BalanceSummary(Widget):
    DEFAULT_CSS = """
    BalanceSummary {
        border: solid #30363d;
        height: auto;
        max-height: 12;
    }
    BalanceSummary DataTable { background: #0d1117; }
    """
    BORDER_TITLE = "Balance"

    def __init__(self, store: DataStore, **kwargs) -> None:
        super().__init__(**kwargs)
        self._store = store

    def compose(self):
        yield DataTable(show_header=True, cursor_type="none")

    def on_mount(self) -> None:
        t = self.query_one(DataTable)
        t.add_columns("Currency", "Available", "Hold")

    def refresh_data(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        balances = self._store.balances
        shown = [b for c, b in balances.items() if c in _SHOW and b.total > 0]
        others = [b for c, b in balances.items() if c not in _SHOW and b.total > 0]
        for b in shown + others[:3]:
            color = "#f0c000" if b.currency == "BTC" else "white"
            avail = f"{b.available:,.6f}" if b.currency == "BTC" else f"${b.available:,.2f}"
            hold  = f"{b.hold:,.6f}"       if b.currency == "BTC" else f"${b.hold:,.2f}"
            table.add_row(
                Text(b.currency, style=color),
                Text(avail),
                Text(hold, style="grey50"),
            )
