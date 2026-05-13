from __future__ import annotations
from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Label
from ..models import DataStore


class CancelOrder(Message):
    def __init__(self, order_id: str) -> None:
        super().__init__()
        self.order_id = order_id


class OpenOrders(Widget):
    DEFAULT_CSS = """
    OpenOrders {
        border: solid #30363d;
        height: 100%;
        layout: vertical;
    }
    OpenOrders Label { color: #8b949e; height: 1; padding: 0 1; }
    OpenOrders DataTable { background: #0d1117; height: 1fr; }
    """
    BORDER_TITLE = "Open Orders  (click row to cancel)"

    def __init__(self, store: DataStore, **kwargs) -> None:
        super().__init__(**kwargs)
        self._store    = store
        self._order_ids: list[str] = []

    def compose(self) -> ComposeResult:
        yield DataTable(show_header=True, cursor_type="row")
        yield Label("", classes="oo-status")

    def on_mount(self) -> None:
        t = self.query_one(DataTable)
        t.add_columns("Side", "Type", "Price", "Size", "Filled", "Status", "Created")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            idx = list(event.data_table.rows.keys()).index(event.row_key)
            if idx < len(self._order_ids):
                self.post_message(CancelOrder(self._order_ids[idx]))
        except (ValueError, IndexError):
            pass

    def refresh_data(self) -> None:
        table  = self.query_one(DataTable)
        orders = self._store.orders
        table.clear()
        self._order_ids = []

        if not orders:
            self.query_one(".oo-status", Label).update("[dim]No open orders[/]")
            return

        self.query_one(".oo-status", Label).update("")
        for o in orders:
            self._order_ids.append(o.order_id)
            color = "#3fb950" if o.side == "BUY" else "#f85149"
            price_str = f"${float(o.limit_price or 0):,.2f}" if o.limit_price else "MKT"
            created   = o.created_at[11:19] if len(o.created_at) >= 19 else o.created_at
            table.add_row(
                Text(o.side, style=color),
                Text(o.order_type),
                Text(price_str),
                Text(o.base_size),
                Text(o.filled_size),
                Text(o.status, style="grey50"),
                Text(created, style="grey50"),
            )
