from __future__ import annotations
from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Label
from ..models import DataStore


class Positions(Widget):
    DEFAULT_CSS = """
    Positions {
        height: 100%;
        layout: vertical;
    }
    Positions DataTable { background: #0d1117; height: 1fr; }
    Positions Label     { color: #8b949e; height: 1; padding: 0 1; }
    """

    def __init__(self, store: DataStore, **kwargs) -> None:
        super().__init__(**kwargs)
        self._store = store

    def compose(self) -> ComposeResult:
        yield DataTable(id="pos-table", show_header=True, cursor_type="row")
        yield Label("", id="pos-status")

    def on_mount(self) -> None:
        t = self.query_one("#pos-table", DataTable)
        t.add_columns("Side", "Product", "Contracts", "Avg Entry", "Unr. PnL", "Daily PnL")

    def refresh_data(self) -> None:
        table     = self.query_one("#pos-table", DataTable)
        positions = self._store.positions
        table.clear()

        if not positions:
            self.query_one("#pos-status", Label).update("[dim]No open positions[/]")
            return

        self.query_one("#pos-status", Label).update("")
        for p in positions:
            side_color = "#3fb950" if p.side == "LONG" else "#f85149"
            try:
                pnl      = float(p.unrealized_pnl)
                pnl_str  = f"${pnl:+,.2f}"
                pnl_color = "#3fb950" if pnl >= 0 else "#f85149"
            except ValueError:
                pnl_str, pnl_color = p.unrealized_pnl, "white"

            try:
                dpnl      = float(p.daily_pnl)
                dpnl_str  = f"${dpnl:+,.2f}"
                dpnl_color = "#3fb950" if dpnl >= 0 else "#f85149"
            except ValueError:
                dpnl_str, dpnl_color = p.daily_pnl or "—", "white"

            try:
                entry_str = f"${float(p.avg_entry):,.2f}"
            except ValueError:
                entry_str = p.avg_entry or "—"

            table.add_row(
                Text(p.side,       style=side_color),
                Text(p.product_id, style="grey70"),
                Text(p.contracts),
                Text(entry_str),
                Text(pnl_str,  style=pnl_color),
                Text(dpnl_str, style=dpnl_color),
            )
