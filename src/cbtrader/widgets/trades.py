from __future__ import annotations
from rich.text import Text
from textual.widget import Widget
from textual.widgets import DataTable
from ..models import DataStore


class RecentTrades(Widget):
    DEFAULT_CSS = """
    RecentTrades {
        border: solid #30363d;
        height: 1fr;
    }
    RecentTrades DataTable {
        background: #0d1117;
    }
    """
    BORDER_TITLE = "Recent Trades"

    def __init__(self, store: DataStore, **kwargs) -> None:
        super().__init__(**kwargs)
        self._store = store

    def on_mount(self) -> None:
        t = self.query_one(DataTable)
        t.add_columns("Time", "Price (USD)", "Size (BTC)")
        t.show_header = True
        t.cursor_type = "none"

    def compose(self):
        yield DataTable()

    def refresh_data(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for trade in list(self._store.trades)[:20]:
            color = "#3fb950" if trade.side == "BUY" else "#f85149"
            arrow = "↑" if trade.side == "BUY" else "↓"
            time_str = trade.time[11:19] if len(trade.time) >= 19 else trade.time
            table.add_row(
                Text(time_str, style="grey50"),
                Text(f"{arrow} {trade.price:>10,.2f}", style=color),
                Text(f"{trade.size:.4f}", style=color),
            )
