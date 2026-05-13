from __future__ import annotations
from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Static
from ..models import DataStore


class PriceSelected(Message):
    def __init__(self, price: float) -> None:
        super().__init__()
        self.price = price


class OrderBook(Widget):
    DEFAULT_CSS = """
    OrderBook {
        layout: vertical;
        border: solid #30363d;
        border-title-color: #8b949e;
    }
    OrderBook .ob-title {
        height: 1;
        background: #161b22;
        color: #8b949e;
        text-align: center;
        padding: 0 1;
    }
    OrderBook .mid-row {
        height: 1;
        background: #1f2937;
        text-align: center;
        color: #f0c000;
        text-style: bold;
    }
    OrderBook DataTable {
        height: 1fr;
        background: #0d1117;
    }
    """
    BORDER_TITLE = "Order Book"

    def __init__(self, store: DataStore, depth: int = 12, **kwargs) -> None:
        super().__init__(**kwargs)
        self._store = store
        self._depth = depth

    def compose(self) -> ComposeResult:
        yield Static("Price (USD)          Size (BTC)     Total", classes="ob-title")
        yield DataTable(id="ob-asks", show_header=False, cursor_type="row")
        yield Static("", id="ob-mid", classes="mid-row")
        yield DataTable(id="ob-bids", show_header=False, cursor_type="row")

    def on_mount(self) -> None:
        for tid in ("ob-asks", "ob-bids"):
            t = self.query_one(f"#{tid}", DataTable)
            t.add_columns("price", "size", "total")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = event.data_table
        row   = table.get_row(event.row_key)
        try:
            price_str = str(row[0]).replace(",", "").strip()
            price = float(price_str)
            self.post_message(PriceSelected(price))
        except (ValueError, IndexError):
            pass

    def refresh_data(self) -> None:
        bids, asks = self._store.orderbook.top(self._depth)
        mid = self._store.orderbook.mid

        ask_table = self.query_one("#ob-asks", DataTable)
        bid_table = self.query_one("#ob-bids", DataTable)

        RED   = "#f85149"
        GREEN = "#3fb950"
        DIM   = "grey50"

        # Asks: lowest at bottom → build reversed
        ask_table.clear()
        cum = 0.0
        rows_ask = []
        for price, size in sorted(asks):
            cum += size
            rows_ask.append((price, size, cum))
        for price, size, total in reversed(rows_ask):
            ask_table.add_row(
                Text(f"{price:>12,.2f}", style=RED),
                Text(f"{size:>10.4f}",  style=RED),
                Text(f"{total:>10.4f}", style=DIM),
            )

        # Mid price
        if mid:
            spread_bps = (asks[0][0] - bids[0][0]) / mid * 10_000 if bids and asks else 0
            self.query_one("#ob-mid").update(
                f"  ${mid:,.2f}   spread {spread_bps:.1f} bps"
            )

        # Bids
        bid_table.clear()
        cum = 0.0
        for price, size in bids:
            cum += size
            bid_table.add_row(
                Text(f"{price:>12,.2f}", style=GREEN),
                Text(f"{size:>10.4f}",  style=GREEN),
                Text(f"{cum:>10.4f}",   style=DIM),
            )
