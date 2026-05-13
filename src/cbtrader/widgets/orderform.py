from __future__ import annotations
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Static
from textual.containers import Horizontal
from ..models import DataStore


class SubmitOrder(Message):
    def __init__(self, side: str, order_type: str, price: str, size: str,
                 product_id: str) -> None:
        super().__init__()
        self.side       = side
        self.order_type = order_type
        self.price      = price
        self.size       = size
        self.product_id = product_id


class OrderForm(Widget):
    DEFAULT_CSS = """
    OrderForm {
        border: solid #30363d;
        padding: 1 2;
        layout: vertical;
        height: auto;
    }
    OrderForm .side-row {
        layout: horizontal;
        height: 3;
        margin-bottom: 1;
    }
    OrderForm .type-row {
        layout: horizontal;
        height: 3;
        margin-bottom: 1;
    }
    OrderForm .curr-row {
        layout: horizontal;
        height: 3;
        margin-bottom: 1;
    }
    OrderForm Button {
        width: 1fr;
        min-width: 4;
    }
    OrderForm #btn-buy  { background: #1a4731; color: #3fb950; border: tall #3fb950; }
    OrderForm #btn-sell { background: #3d1a1a; color: #f85149; border: tall #f85149; }
    OrderForm #btn-buy.active  { background: #3fb950; color: #0d1117; text-style: bold; }
    OrderForm #btn-sell.active { background: #f85149; color: #0d1117; text-style: bold; }
    OrderForm #btn-limit, OrderForm #btn-market {
        background: #161b22; color: #8b949e; border: tall #30363d;
    }
    OrderForm #btn-limit.active, OrderForm #btn-market.active {
        background: #30363d; color: white; text-style: bold;
    }
    OrderForm #btn-usd, OrderForm #btn-usdc {
        background: #161b22; color: #8b949e; border: tall #30363d;
    }
    OrderForm #btn-usd.active, OrderForm #btn-usdc.active {
        background: #1f3a5f; color: #58a6ff; text-style: bold;
    }
    OrderForm #btn-btc-bal, OrderForm #btn-quote-bal {
        height: 1;
        background: transparent;
        border: none;
        text-style: none;
        margin-bottom: 0;
        width: 1fr;
        min-width: 4;
        text-align: left;
    }
    OrderForm #btn-btc-bal   { color: #f0c000; }
    OrderForm #btn-quote-bal { color: #58a6ff; }
    OrderForm #btn-btc-bal:hover,
    OrderForm #btn-quote-bal:hover { color: white; }
    OrderForm Input {
        margin-bottom: 1;
        border: tall #30363d;
        background: #161b22;
    }
    OrderForm .field-label {
        color: #8b949e;
        height: 1;
        margin-bottom: 0;
    }
    OrderForm #total-label { color: #8b949e; height: 1; }
    OrderForm #submit-btn  { margin-top: 1; height: 3; text-style: bold; }
    OrderForm #submit-btn.submit-buy  { background: #3fb950; color: #0d1117; }
    OrderForm #submit-btn.submit-sell { background: #f85149; color: #0d1117; }
    OrderForm #status-msg  { color: #8b949e; height: 1; text-align: center; }
    """
    BORDER_TITLE = "Order Form"

    def __init__(self, store: DataStore, product_id: str = "BTC-USD", **kwargs) -> None:
        super().__init__(**kwargs)
        self._store       = store
        self._base        = product_id.split("-")[0]   # "BTC"
        self._currency    = "USD"
        self._side        = "BUY"
        self._order_type  = "Limit"

    @property
    def _product_id(self) -> str:
        return f"{self._base}-{self._currency}"

    def compose(self) -> ComposeResult:
        with Horizontal(classes="side-row"):
            yield Button("Buy",  id="btn-buy",  classes="active")
            yield Button("Sell", id="btn-sell")
        with Horizontal(classes="type-row"):
            yield Button("Limit",  id="btn-limit",  classes="active")
            yield Button("Market", id="btn-market")
        with Horizontal(classes="curr-row"):
            yield Button("USD",  id="btn-usd",  classes="active")
            yield Button("USDC", id="btn-usdc")
        yield Button("BTC avail: —", id="btn-btc-bal")
        yield Button("Quote avail: —", id="btn-quote-bal")
        yield Label("Price (USD)", classes="field-label")
        yield Input(placeholder="0.00", id="inp-price", type="number")
        yield Label("Amount (BTC)", classes="field-label")
        yield Input(placeholder="0.00000000", id="inp-size", type="number")
        yield Static("Total: — USD", id="total-label")
        yield Button("Buy BTC", id="submit-btn", classes="submit-buy")
        yield Static("", id="status-msg")

    def on_mount(self) -> None:
        self._update_ui()
        self._fill_price_from_ticker()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-buy":
            self._side = "BUY"
        elif bid == "btn-sell":
            self._side = "SELL"
        elif bid == "btn-limit":
            self._order_type = "Limit"
        elif bid == "btn-market":
            self._order_type = "Market"
        elif bid == "btn-usd":
            self._currency = "USD"
        elif bid == "btn-usdc":
            self._currency = "USDC"
        elif bid == "btn-btc-bal":
            self._fill_size_from_btc()
            return
        elif bid == "btn-quote-bal":
            self._fill_size_from_quote()
            return
        elif bid == "submit-btn":
            self._submit()
            return
        self._update_ui()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._update_total()

    def set_price(self, price: float) -> None:
        self.query_one("#inp-price", Input).value = f"{price:.2f}"
        self._update_total()

    def _fill_size_from_btc(self) -> None:
        btc = self._store.balances.get("BTC")
        if btc and btc.available > 0:
            self.query_one("#inp-size", Input).value = f"{btc.available:.8f}"
            self._update_total()

    def _fill_size_from_quote(self) -> None:
        bal = self._store.balances.get(self._currency)
        price = self._store.ticker.price
        if bal and bal.available > 0 and price > 0:
            btc_qty = bal.available / price
            self.query_one("#inp-size", Input).value = f"{btc_qty:.8f}"
            self._update_total()

    def _fill_price_from_ticker(self) -> None:
        price_inp = self.query_one("#inp-price", Input)
        if not price_inp.value and self._store.ticker.price > 0:
            price_inp.value = f"{self._store.ticker.price:.2f}"
            self._update_total()

    def _update_ui(self) -> None:
        self.query_one("#btn-buy",    Button).set_class(self._side == "BUY",  "active")
        self.query_one("#btn-sell",   Button).set_class(self._side == "SELL", "active")
        self.query_one("#btn-limit",  Button).set_class(self._order_type == "Limit",  "active")
        self.query_one("#btn-market", Button).set_class(self._order_type == "Market", "active")
        self.query_one("#btn-usd",    Button).set_class(self._currency == "USD",  "active")
        self.query_one("#btn-usdc",   Button).set_class(self._currency == "USDC", "active")

        price_input = self.query_one("#inp-price", Input)
        price_input.disabled = self._order_type == "Market"

        submit = self.query_one("#submit-btn", Button)
        submit.label = f"{'Buy' if self._side == 'BUY' else 'Sell'} {self._base}"
        submit.set_class(self._side == "BUY",  "submit-buy")
        submit.set_class(self._side == "SELL", "submit-sell")

        self._update_btc_bal()
        self._update_quote_bal()
        self._update_total()

    def _update_btc_bal(self) -> None:
        btc = self._store.balances.get("BTC")
        if btc and btc.available > 0:
            label = f"BTC: {btc.available:.8f}  ← click to fill"
        else:
            label = "BTC: —"
        self.query_one("#btn-btc-bal", Button).label = label

    def _update_quote_bal(self) -> None:
        bal = self._store.balances.get(self._currency)
        if bal and bal.available > 0:
            label = f"{self._currency}: ${bal.available:,.2f}  ← click to fill"
        else:
            label = f"{self._currency}: —"
        self.query_one("#btn-quote-bal", Button).label = label

    def _update_total(self) -> None:
        try:
            price = float(self.query_one("#inp-price", Input).value or 0)
            size  = float(self.query_one("#inp-size",  Input).value or 0)
            total = price * size
            lbl   = f"Total: ${total:,.2f} {self._currency}" if total > 0 else "Total: —"
            self.query_one("#total-label").update(lbl)
        except ValueError:
            pass

    def _submit(self) -> None:
        price = self.query_one("#inp-price", Input).value.strip()
        size  = self.query_one("#inp-size",  Input).value.strip()
        if not size:
            self.query_one("#status-msg").update("[red]Enter a size[/]")
            return
        if self._order_type == "Limit" and not price:
            self.query_one("#status-msg").update("[red]Enter a price[/]")
            return
        self.query_one("#status-msg").update("[yellow]Submitting…[/]")
        self.post_message(SubmitOrder(
            self._side, self._order_type, price, size, self._product_id
        ))

    def refresh_data(self) -> None:
        self._update_btc_bal()
        self._update_quote_bal()
        self._fill_price_from_ticker()

    def show_result(self, ok: bool, msg: str) -> None:
        color = "green" if ok else "red"
        self.query_one("#status-msg").update(f"[{color}]{msg}[/]")
