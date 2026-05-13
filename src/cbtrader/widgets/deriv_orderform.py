from __future__ import annotations
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Static
from textual.containers import Horizontal
from ..models import DataStore
from .orderform import SubmitOrder   # reuse same message


class DerivOrderForm(Widget):
    DEFAULT_CSS = """
    DerivOrderForm {
        border: solid #30363d;
        padding: 1 2;
        layout: vertical;
        height: auto;
    }
    DerivOrderForm .side-row, DerivOrderForm .type-row {
        layout: horizontal;
        height: 3;
        margin-bottom: 1;
    }
    DerivOrderForm Button {
        width: 1fr;
        min-width: 4;
    }
    DerivOrderForm #btn-long  { background: #1a4731; color: #3fb950; border: tall #3fb950; }
    DerivOrderForm #btn-short { background: #3d1a1a; color: #f85149; border: tall #f85149; }
    DerivOrderForm #btn-long.active  { background: #3fb950; color: #0d1117; text-style: bold; }
    DerivOrderForm #btn-short.active { background: #f85149; color: #0d1117; text-style: bold; }
    DerivOrderForm #btn-dlimit, DerivOrderForm #btn-dmarket {
        background: #161b22; color: #8b949e; border: tall #30363d;
    }
    DerivOrderForm #btn-dlimit.active, DerivOrderForm #btn-dmarket.active {
        background: #30363d; color: white; text-style: bold;
    }
    DerivOrderForm #btn-pos-bal {
        height: 1; background: transparent; border: none;
        color: #58a6ff; text-style: none; margin-bottom: 1;
        width: 1fr; min-width: 4; text-align: left;
    }
    DerivOrderForm #btn-pos-bal:hover { color: white; }
    DerivOrderForm Input {
        margin-bottom: 1;
        border: tall #30363d;
        background: #161b22;
    }
    DerivOrderForm .field-label  { color: #8b949e; height: 1; margin-bottom: 0; }
    DerivOrderForm .info-row     { color: #8b949e; height: 1; margin-bottom: 0; }
    DerivOrderForm #dsubmit-btn  { margin-top: 1; height: 3; text-style: bold; }
    DerivOrderForm #dsubmit-btn.submit-long  { background: #3fb950; color: #0d1117; }
    DerivOrderForm #dsubmit-btn.submit-short { background: #f85149; color: #0d1117; }
    DerivOrderForm #dstatus-msg  { color: #8b949e; height: 1; text-align: center; }
    """
    BORDER_TITLE = "Order Form"

    def __init__(self, store: DataStore, product_id: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._store      = store
        self._product_id = product_id
        self._side       = "LONG"
        self._order_type = "Limit"
        self._leverage   = 1.0

    def compose(self) -> ComposeResult:
        with Horizontal(classes="side-row"):
            yield Button("Buy Long",  id="btn-long",  classes="active")
            yield Button("Sell Short", id="btn-short")
        with Horizontal(classes="type-row"):
            yield Button("Limit",  id="btn-dlimit",  classes="active")
            yield Button("Market", id="btn-dmarket")
        yield Button("Available: —", id="btn-pos-bal")
        yield Label("Price (USD)", classes="field-label")
        yield Input(placeholder="0.00", id="dinp-price", type="number")
        yield Label("Size (Contracts)", classes="field-label")
        yield Input(placeholder="1", id="dinp-size", type="number")
        yield Label("Leverage", classes="field-label")
        yield Input(value="1", id="dinp-lev", type="number")
        yield Static("Notional: —", id="dnotional",  classes="info-row")
        yield Static("Margin:   —", id="dmargin",    classes="info-row")
        yield Static("Funding:  —", id="dfunding",   classes="info-row")
        yield Button("Buy Long BTC", id="dsubmit-btn", classes="submit-long")
        yield Static("", id="dstatus-msg")

    def on_mount(self) -> None:
        self._update_ui()
        self._fill_price_from_ticker()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-long":
            self._side = "LONG"
        elif bid == "btn-short":
            self._side = "SHORT"
        elif bid == "btn-dlimit":
            self._order_type = "Limit"
        elif bid == "btn-dmarket":
            self._order_type = "Market"
        elif bid == "btn-pos-bal":
            self._fill_from_balance()
            return
        elif bid == "dsubmit-btn":
            self._submit()
            return
        self._update_ui()

    def on_input_changed(self, _: Input.Changed) -> None:
        self._update_info()

    def set_price(self, price: float) -> None:
        self.query_one("#dinp-price", Input).value = f"{price:.2f}"
        self._update_info()

    def _fill_price_from_ticker(self) -> None:
        inp = self.query_one("#dinp-price", Input)
        if not inp.value and self._store.ticker.price > 0:
            inp.value = f"{self._store.ticker.price:.2f}"
            self._update_info()

    def _fill_from_balance(self) -> None:
        fb            = self._store.futures_balance
        price         = self._store.ticker.price
        lev           = self._leverage
        contract_size = self._store.contract_size
        if fb.buying_power > 0 and price > 0 and lev > 0 and contract_size > 0:
            max_contracts = (fb.buying_power * lev) / (price * contract_size)
            self.query_one("#dinp-size", Input).value = f"{max_contracts:.2f}"
            self._update_info()

    def _update_ui(self) -> None:
        self.query_one("#btn-long",    Button).set_class(self._side == "LONG",  "active")
        self.query_one("#btn-short",   Button).set_class(self._side == "SHORT", "active")
        self.query_one("#btn-dlimit",  Button).set_class(self._order_type == "Limit",  "active")
        self.query_one("#btn-dmarket", Button).set_class(self._order_type == "Market", "active")

        self.query_one("#dinp-price", Input).disabled = self._order_type == "Market"

        submit = self.query_one("#dsubmit-btn", Button)
        if self._side == "LONG":
            submit.label = "Buy Long BTC"
            submit.set_class(True,  "submit-long")
            submit.set_class(False, "submit-short")
        else:
            submit.label = "Sell Short BTC"
            submit.set_class(False, "submit-long")
            submit.set_class(True,  "submit-short")

        self._update_avail()
        self._update_info()

    def _update_avail(self) -> None:
        fb  = self._store.futures_balance
        lbl = f"Avail: ${fb.buying_power:,.2f}  ← click to fill"
        self.query_one("#btn-pos-bal", Button).label = lbl

    def _update_info(self) -> None:
        try:
            price         = float(self.query_one("#dinp-price", Input).value or 0)
            contracts     = float(self.query_one("#dinp-size",  Input).value or 0)
            lev_s         = self.query_one("#dinp-lev", Input).value or "1"
            self._leverage = max(1.0, min(float(lev_s), self._store.max_leverage))
        except ValueError:
            return

        contract_size = self._store.contract_size
        notional = price * contracts * contract_size
        margin   = notional / self._leverage if self._leverage > 0 else 0.0
        fr_pct   = self._store.funding_rate * 100

        btc_size = contracts * contract_size
        self.query_one("#dnotional").update(
            f"Notional: {contracts:.2f} contracts = {btc_size:.4f} BTC  ${notional:,.2f}"
            if notional > 0 else "Notional: —"
        )
        self.query_one("#dmargin").update(
            f"Margin ({self._leverage:.0f}x): ${margin:,.2f}" if margin > 0 else "Margin: —"
        )
        self.query_one("#dfunding").update(
            f"Funding: {fr_pct:+.4f}%/hr" if self._store.funding_rate else "Funding: —"
        )

    def _submit(self) -> None:
        price = self.query_one("#dinp-price", Input).value.strip()
        size  = self.query_one("#dinp-size",  Input).value.strip()
        if not size:
            self.query_one("#dstatus-msg").update("[red]Enter size[/]")
            return
        if self._order_type == "Limit" and not price:
            self.query_one("#dstatus-msg").update("[red]Enter price[/]")
            return
        api_side = "BUY" if self._side == "LONG" else "SELL"
        self.query_one("#dstatus-msg").update("[yellow]Submitting…[/]")
        self.post_message(SubmitOrder(api_side, self._order_type, price, size,
                                     self._product_id))

    def refresh_data(self) -> None:
        self._update_avail()
        self._fill_price_from_ticker()

    def show_result(self, ok: bool, msg: str) -> None:
        color = "green" if ok else "red"
        self.query_one("#dstatus-msg").update(f"[{color}]{msg}[/]")
