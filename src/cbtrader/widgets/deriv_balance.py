from __future__ import annotations
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable
from rich.text import Text
from ..models import DataStore


class DerivBalance(Widget):
    DEFAULT_CSS = """
    DerivBalance {
        border: solid #30363d;
        border-title-color: #8b949e;
        layout: vertical;
        height: auto;
    }
    DerivBalance DataTable {
        background: #0d1117;
        height: auto;
    }
    """
    BORDER_TITLE = "Futures Balance"

    def __init__(self, store: DataStore, **kwargs) -> None:
        super().__init__(**kwargs)
        self._store = store

    def compose(self) -> ComposeResult:
        yield DataTable(id="db-table", show_header=False, cursor_type="none")

    def on_mount(self) -> None:
        t = self.query_one("#db-table", DataTable)
        t.add_columns("Label", "Value")

    def refresh_data(self) -> None:
        fb   = self._store.futures_balance
        table = self.query_one("#db-table", DataTable)
        table.clear()

        def row(label: str, value: str, color: str = "white") -> None:
            table.add_row(
                Text(label, style="#8b949e"),
                Text(value, style=color),
            )

        row("Buying power",   f"${fb.buying_power:,.2f}")
        row("CFM balance",    f"${fb.cfm_balance:,.2f}")
        row("Initial margin", f"${fb.initial_margin:,.2f}")

        pnl_color = "#3fb950" if fb.unrealized_pnl >= 0 else "#f85149"
        pnl_str   = f"${fb.unrealized_pnl:+,.2f}"
        row("Unrealized PnL", pnl_str, pnl_color)

        dpnl_color = "#3fb950" if fb.daily_pnl >= 0 else "#f85149"
        row("Daily PnL",      f"${fb.daily_pnl:+,.2f}", dpnl_color)
