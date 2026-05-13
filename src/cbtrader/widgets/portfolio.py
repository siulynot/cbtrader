from __future__ import annotations
import time
from collections import deque

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Static
from textual_plotext import PlotextPlot

from ..models import DataStore

_HISTORY_INTERVAL = 30   # seconds between balance snapshots
_HISTORY_MAX      = 300  # ~2.5 hours at 30s intervals


class PortfolioPanel(Widget):
    DEFAULT_CSS = """
    PortfolioPanel {
        layout: vertical;
        height: 1fr;
    }
    PortfolioPanel #port-header {
        height: 3;
        padding: 0 2;
    }
    PortfolioPanel #port-chart {
        height: 14;
        border-bottom: solid #30363d;
    }
    PortfolioPanel #port-tables {
        height: 1fr;
        layout: horizontal;
    }
    PortfolioPanel .port-col {
        width: 1fr;
        layout: vertical;
    }
    PortfolioPanel .port-col-right {
        border-left: solid #30363d;
    }
    PortfolioPanel .col-title {
        height: 1;
        color: #8b949e;
        padding: 0 1;
        background: #161b22;
    }
    PortfolioPanel DataTable {
        background: #0d1117;
        height: 1fr;
    }
    """
    BORDER_TITLE = "Portfolio"

    def __init__(self, spot_store: DataStore, deriv_store: DataStore, **kwargs) -> None:
        super().__init__(**kwargs)
        self._spot    = spot_store
        self._deriv   = deriv_store
        self._history: deque[tuple[float, float]] = deque(maxlen=_HISTORY_MAX)

    def compose(self) -> ComposeResult:
        yield Static("", id="port-header")
        yield PlotextPlot(id="port-chart")
        with Horizontal(id="port-tables"):
            with Vertical(classes="port-col"):
                yield Static("Cash & Derivatives", classes="col-title")
                yield DataTable(id="port-cash-dt", show_header=False, cursor_type="none")
            with Vertical(classes="port-col port-col-right"):
                yield Static("Crypto Holdings", classes="col-title")
                yield DataTable(id="port-crypto-dt", show_header=True, cursor_type="none")

    def on_mount(self) -> None:
        self.query_one("#port-cash-dt", DataTable).add_columns("Account", "Balance")
        self.query_one("#port-crypto-dt", DataTable).add_columns(
            "Asset", "Amount", "USD Value", "Alloc %"
        )

    def _compute(self) -> tuple[float, float, float, float]:
        """(total, cash_usd, crypto_usd, deriv_usd)."""
        btc_price = self._spot.ticker.price
        balances  = self._spot.balances
        fb        = self._deriv.futures_balance

        cash_usd = sum(
            b.total for c, b in balances.items() if c in ("USD", "USDC", "USDT")
        )
        crypto_usd = 0.0
        for cur, bal in balances.items():
            if cur in ("USD", "USDC", "USDT"):
                continue
            if cur == "BTC" and btc_price > 0:
                crypto_usd += bal.total * btc_price
        deriv_usd = fb.cfm_balance
        return cash_usd + crypto_usd + deriv_usd, cash_usd, crypto_usd, deriv_usd

    def refresh_data(self) -> None:
        total, cash_usd, crypto_usd, deriv_usd = self._compute()
        btc_price = self._spot.ticker.price
        balances  = self._spot.balances
        fb        = self._deriv.futures_balance
        now       = time.time()

        # Record balance snapshot at most every _HISTORY_INTERVAL seconds
        if total > 0 and (not self._history or now - self._history[-1][0] >= _HISTORY_INTERVAL):
            self._history.append((now, total))

        # ── Header ───────────────────────────────────────────────────────────
        parts = []
        if cash_usd:   parts.append(f"Cash ${cash_usd:,.0f}")
        if crypto_usd: parts.append(f"Crypto ${crypto_usd:,.0f}")
        if deriv_usd:  parts.append(f"Deriv ${deriv_usd:,.0f}")
        subline = "  |  ".join(parts) if parts else "loading…"
        self.query_one("#port-header", Static).update(
            f"[bold]Total Balance   [green]${total:,.2f}[/green][/bold]\n"
            f"[dim]{subline}[/dim]"
        )

        # ── Chart ─────────────────────────────────────────────────────────────
        plt = self.query_one("#port-chart", PlotextPlot).plt
        plt.clear_data()
        plt.clear_color()
        plt.theme("dark")
        plt.title("Session Balance (USD)")
        if len(self._history) >= 2:
            t0 = self._history[0][0]
            xs = [(t - t0) / 60 for t, _ in self._history]
            ys = [b for _, b in self._history]
            plt.plot(xs, ys, color="cyan+")
            plt.xlabel("minutes")
            mn, mx = min(ys), max(ys)
            pad = max((mx - mn) * 0.1, 10)
            plt.ylim(mn - pad, mx + pad)
        else:
            plt.plot([0], [total if total > 0 else 0], color="cyan+")
            plt.xlabel("Accumulating history…")
        self.query_one("#port-chart", PlotextPlot).refresh()

        # ── Cash & Derivatives table ──────────────────────────────────────────
        ct = self.query_one("#port-cash-dt", DataTable)
        ct.clear()
        for cur in ("USD", "USDC", "USDT"):
            bal = balances.get(cur)
            if bal and bal.total > 0:
                ct.add_row(
                    Text(cur, style="grey80"),
                    Text(f"${bal.total:,.2f}"),
                )
        ct.add_row(Text(""), Text(""))
        ct.add_row(Text("CFM Balance",  style="#58a6ff"), Text(f"${fb.cfm_balance:,.2f}"))
        ct.add_row(Text("Buying Power", style="grey70"),  Text(f"${fb.buying_power:,.2f}"))
        ct.add_row(Text("Init. Margin", style="grey70"),  Text(f"${fb.initial_margin:,.2f}"))
        pnl_s  = "#3fb950" if fb.unrealized_pnl >= 0 else "#f85149"
        dpnl_s = "#3fb950" if fb.daily_pnl       >= 0 else "#f85149"
        ct.add_row(Text("Unr. PnL",  style="grey70"), Text(f"${fb.unrealized_pnl:+,.2f}", style=pnl_s))
        ct.add_row(Text("Daily PnL", style="grey70"), Text(f"${fb.daily_pnl:+,.2f}",       style=dpnl_s))

        # ── Crypto holdings table ─────────────────────────────────────────────
        ht      = self.query_one("#port-crypto-dt", DataTable)
        ht.clear()
        total_nz = total if total > 0 else 1.0
        rows: list[tuple[str, float, float]] = []
        for cur, bal in balances.items():
            if cur in ("USD", "USDC", "USDT") or bal.total <= 0:
                continue
            usd_val = bal.total * btc_price if cur == "BTC" and btc_price > 0 else 0.0
            rows.append((cur, bal.total, usd_val))
        rows.sort(key=lambda r: -r[2])
        for cur, amount, usd_val in rows:
            alloc   = usd_val / total_nz * 100
            amt_str = f"{amount:.8f}".rstrip("0").rstrip(".")
            ht.add_row(
                Text(cur, style="white"),
                Text(amt_str,                     style="grey80"),
                Text(f"${usd_val:,.2f}" if usd_val > 0 else "—"),
                Text(f"{alloc:.1f}%",             style="grey60"),
            )
