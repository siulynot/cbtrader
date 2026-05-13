from __future__ import annotations
from rich.text import Text
from textual.widget import Widget
from textual.app import ComposeResult
from textual.widgets import DataTable, Label
from ..models import DataStore


class OrderHistory(Widget):
    DEFAULT_CSS = """
    OrderHistory {
        height: 100%;
        layout: vertical;
    }
    OrderHistory DataTable { background: #0d1117; height: 1fr; }
    OrderHistory Label     { color: #8b949e; height: 1; padding: 0 1; }
    """

    def __init__(self, store: DataStore, **kwargs) -> None:
        super().__init__(**kwargs)
        self._store = store

    def compose(self) -> ComposeResult:
        yield DataTable(show_header=True, cursor_type="row")
        yield Label("", classes="oh-status")

    def on_mount(self) -> None:
        t = self.query_one(DataTable)
        t.add_columns("Side", "Product", "Type", "Avg Price", "Filled", "Value", "Status", "Date")

    def refresh_data(self) -> None:
        table  = self.query_one(DataTable)
        orders = self._store.history
        table.clear()

        if not orders:
            self.query_one(".oh-status", Label).update("[dim]No history — loads on first fetch[/]")
            return

        self.query_one(".oh-status", Label).update("")
        for o in orders:
            color = "#3fb950" if o.side == "BUY" else "#f85149"
            status_color = "#3fb950" if o.status == "FILLED" else "#8b949e"

            try:
                avg = f"${float(o.avg_price):,.2f}" if o.avg_price else "—"
            except (ValueError, TypeError):
                avg = o.avg_price or "—"
            try:
                val = f"${float(o.filled_value):,.2f}" if o.filled_value else "—"
            except (ValueError, TypeError):
                val = o.filled_value or "—"
            date = o.created_at[:10] if len(o.created_at) >= 10 else o.created_at

            table.add_row(
                Text(o.side,       style=color),
                Text(o.product_id, style="grey70"),
                Text(o.order_type, style="grey70"),
                Text(avg),
                Text(o.filled_size or "—"),
                Text(val),
                Text(o.status,     style=status_color),
                Text(date,         style="grey50"),
            )
