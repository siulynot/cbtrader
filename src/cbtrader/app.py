from __future__ import annotations
import asyncio

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, TabbedContent, TabPane

from .api.feed import WebSocketFeed
from .api.rest import CoinbaseREST
from .models import Balance, DataStore, FuturesBalance, Order, Position
from .widgets.balance import BalanceSummary
from .widgets.chart import ChartPanel
from .widgets.deriv_balance import DerivBalance
from .widgets.deriv_orderform import DerivOrderForm
from .widgets.deriv_ticker import DerivTicker
from .widgets.openorders import CancelOrder, OpenOrders
from .widgets.orderbook import OrderBook, PriceSelected
from .widgets.orderform import OrderForm, SubmitOrder
from .widgets.orderhistory import OrderHistory
from .widgets.portfolio import PortfolioPanel
from .widgets.positions import Positions
from .widgets.ticker import TickerBar
from .widgets.trades import RecentTrades


class CbTraderApp(App):
    TITLE = "cbtrader"
    CSS = """
    Screen { background: #0d1117; layout: vertical; }

    /* ── shared main layout ─────────────────────────── */
    .main-area {
        layout: horizontal;
        height: 1fr;
    }
    .left-col  { width: 2fr; layout: vertical; }
    .center-col {
        width: 1fr; layout: vertical;
        border-left: solid #30363d;
        border-right: solid #30363d;
    }
    .right-col { width: 34; layout: vertical; }
    .bottom-area {
        height: 16;
        border-top: solid #30363d;
    }
    .bottom-area TabbedContent { height: 1fr; }
    .bottom-area TabPane       { padding: 0; height: 1fr; }

    /* ── chart / orderbook / trades proportions ─────── */
    .chart-panel  { height: 1fr; }
    .ob-panel     { height: 2fr; }
    .trades-panel { height: 1fr; }

    /* ── outer market tabs ──────────────────────────── */
    #market-tabs { height: 1fr; }
    #market-tabs TabPane { padding: 0; height: 1fr; layout: vertical; }
    """
    BINDINGS = [("q", "quit", "Quit"), ("r", "refresh_acct", "Refresh")]

    def __init__(self,
                 rest: CoinbaseREST,
                 feed: WebSocketFeed,
                 spot_store: DataStore, spot_product: str,
                 order_product: str,
                 deriv_store: DataStore, deriv_product: str,
                 ) -> None:
        super().__init__()
        self._rest           = rest
        self._feed           = feed
        self._spot_store     = spot_store
        self._spot_product   = spot_product
        self._order_product  = order_product   # pair used for open orders / history
        self._deriv_store    = deriv_store
        self._deriv_product  = deriv_product

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        ss = self._spot_store
        ds = self._deriv_store

        with TabbedContent(id="market-tabs"):

            # ── Portfolio tab ─────────────────────────────────────────────────
            with TabPane("◈  Portfolio", id="tab-portfolio"):
                yield PortfolioPanel(self._spot_store, self._deriv_store,
                                     id="p-portfolio")

            # ── Spot tab ──────────────────────────────────────────────────────
            with TabPane("◆  Spot BTC", id="tab-spot"):
                yield TickerBar(ss, id="s-ticker")
                with Horizontal(classes="main-area"):
                    with Vertical(classes="left-col"):
                        yield ChartPanel(self._rest, self._spot_product,
                                         id="s-chart", classes="chart-panel")
                    with Vertical(classes="center-col"):
                        yield OrderBook(ss, depth=10, id="s-ob",
                                        classes="ob-panel")
                        yield RecentTrades(ss, id="s-trades",
                                           classes="trades-panel")
                    with Vertical(classes="right-col"):
                        yield OrderForm(ss, self._spot_product, id="s-form")
                        yield BalanceSummary(ss, id="s-balance")
                with Vertical(classes="bottom-area"):
                    with TabbedContent():
                        with TabPane("Open Orders", id="s-tab-open"):
                            yield OpenOrders(ss, id="s-open-orders")
                        with TabPane("History", id="s-tab-hist"):
                            yield OrderHistory(ss, id="s-history")

            # ── Derivatives tab ───────────────────────────────────────────────
            with TabPane("⬡  BTC Perp", id="tab-deriv"):
                yield DerivTicker(ds, self._deriv_product, id="d-ticker")
                with Horizontal(classes="main-area"):
                    with Vertical(classes="left-col"):
                        yield ChartPanel(self._rest, self._deriv_product,
                                         id="d-chart", classes="chart-panel")
                    with Vertical(classes="center-col"):
                        yield OrderBook(ds, depth=10, id="d-ob",
                                        classes="ob-panel")
                        yield RecentTrades(ds, id="d-trades",
                                           classes="trades-panel")
                    with Vertical(classes="right-col"):
                        yield DerivOrderForm(ds, self._deriv_product, id="d-form")
                        yield DerivBalance(ds, id="d-balance")
                with Vertical(classes="bottom-area"):
                    with TabbedContent():
                        with TabPane("Open Orders", id="d-tab-open"):
                            yield OpenOrders(ds, id="d-open-orders")
                        with TabPane("History", id="d-tab-hist"):
                            yield OrderHistory(ds, id="d-history")
                        with TabPane("Positions", id="d-tab-pos"):
                            yield Positions(ds, id="d-positions")

        yield Footer()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self.run_worker(self._feed.run(), exclusive=True, name="ws-feed")

        self.set_interval(0.2,  self._tick_fast)
        self.set_interval(2.0,  self._tick_slow)
        self.set_interval(30.0, self._fetch_spot_account)
        self.set_interval(10.0, self._fetch_spot_orders)
        self.set_interval(60.0, self._fetch_spot_history)
        self.set_interval(15.0, self._fetch_deriv_data)
        self.set_interval(60.0, self._fetch_deriv_history)

        self.run_worker(self._async_fetch_spot_account(), name="s-acct-init")
        self.run_worker(self._async_fetch_spot_orders(),  name="s-orders-init")
        self.run_worker(self._async_fetch_spot_history(), name="s-hist-init")
        self.run_worker(self._async_fetch_deriv_data(),   name="d-data-init")
        self.run_worker(self._async_fetch_deriv_history(), name="d-hist-init")

    # ── Ticks ─────────────────────────────────────────────────────────────────

    def _tick_fast(self) -> None:
        self.query_one("#s-ticker", TickerBar).refresh_data()
        self.query_one("#s-ob",     OrderBook).refresh_data()
        self.query_one("#d-ticker", DerivTicker).refresh_data()
        self.query_one("#d-ob",     OrderBook).refresh_data()

    def _tick_slow(self) -> None:
        _refresh = [
            ("#s-trades",      RecentTrades),
            ("#s-form",        OrderForm),
            ("#s-balance",     BalanceSummary),
            ("#s-open-orders", OpenOrders),
            ("#s-history",     OrderHistory),
            ("#d-trades",      RecentTrades),
            ("#d-form",        DerivOrderForm),
            ("#d-balance",     DerivBalance),
            ("#d-open-orders", OpenOrders),
            ("#d-history",     OrderHistory),
            ("#d-positions",   Positions),
            ("#p-portfolio",   PortfolioPanel),
        ]
        for wid_id, wtype in _refresh:
            try:
                self.query_one(wid_id, wtype).refresh_data()
            except Exception:
                pass

    # ── Spot fetchers ─────────────────────────────────────────────────────────

    def _fetch_spot_account(self) -> None:
        self.run_worker(self._async_fetch_spot_account(), name="s-acct")

    def _fetch_spot_orders(self) -> None:
        self.run_worker(self._async_fetch_spot_orders(), name="s-orders")

    def _fetch_spot_history(self) -> None:
        self.run_worker(self._async_fetch_spot_history(), name="s-hist")

    async def _async_fetch_spot_account(self) -> None:
        try:
            accounts = await asyncio.to_thread(self._rest.get_accounts)
            balances: dict[str, Balance] = {}
            for a in accounts:
                cur   = a.get("currency", "")
                avail = float(a.get("available_balance", {}).get("value", 0) or 0)
                hold  = float(a.get("hold", {}).get("value", 0) or 0)
                if cur and (avail + hold) > 0:
                    balances[cur] = Balance(currency=cur, available=avail, hold=hold)
            self._spot_store.set_balances(balances)
        except Exception as e:
            self._spot_store.error = f"Account error: {e}"

    async def _async_fetch_spot_orders(self) -> None:
        try:
            raw = await asyncio.to_thread(self._rest.get_open_orders, self._order_product)
            self._spot_store.set_orders(self._parse_orders(raw))
        except Exception as e:
            self._spot_store.error = f"Orders error: {e}"

    async def _async_fetch_spot_history(self) -> None:
        try:
            raw = await asyncio.to_thread(self._rest.get_order_history, self._order_product)
            self._spot_store.set_history(self._parse_orders(raw, include_fill=True))
        except Exception as e:
            self._spot_store.error = f"History error: {e}"

    # ── Derivatives fetchers ──────────────────────────────────────────────────

    def _fetch_deriv_data(self) -> None:
        self.run_worker(self._async_fetch_deriv_data(), name="d-data")

    def _fetch_deriv_history(self) -> None:
        self.run_worker(self._async_fetch_deriv_history(), name="d-hist")

    async def _async_fetch_deriv_data(self) -> None:
        try:
            info, fb_raw, pos_raw = await asyncio.gather(
                asyncio.to_thread(self._rest.get_perp_info, self._deriv_product),
                asyncio.to_thread(self._rest.get_futures_balance),
                asyncio.to_thread(self._rest.get_futures_positions),
            )
            # Perp info — funding_rate/open_interest may be in perpetual_details (INTX)
            # or directly on future_product_details (FCM BIP products)
            fpd = info.get("future_product_details", {})
            pd  = fpd.get("perpetual_details") or {}
            def _fval(key: str) -> float:
                return float(pd.get(key) or fpd.get(key) or 0)
            self._deriv_store.funding_rate  = _fval("funding_rate")
            self._deriv_store.open_interest = _fval("open_interest")
            self._deriv_store.index_price   = float(fpd.get("index_price") or 0)
            self._deriv_store.max_leverage  = float(pd.get("max_leverage") or 50)
            # contract_size: use API value only if it looks like BTC (≤1), else keep 0.01
            api_cs = float(fpd.get("contract_size") or 0)
            if 0 < api_cs <= 1:
                self._deriv_store.contract_size = api_cs
            nt = pd.get("funding_time") or fpd.get("funding_time") or ""
            self._deriv_store.next_funding  = nt[:19] if nt else ""

            # Futures balance
            def fv(d: dict, key: str) -> float:
                return float(d.get(key, {}).get("value", 0) or 0)
            self._deriv_store.futures_balance = FuturesBalance(
                buying_power   = fv(fb_raw, "futures_buying_power"),
                cfm_balance    = fv(fb_raw, "cfm_usd_balance"),
                initial_margin = fv(fb_raw, "initial_margin"),
                unrealized_pnl = fv(fb_raw, "unrealized_pnl"),
                daily_pnl      = fv(fb_raw, "daily_realized_pnl"),
            )

            # Positions
            positions = []
            for p in pos_raw:
                ev = p.get("entry_vwap", {})
                positions.append(Position(
                    product_id     = p.get("product_id", ""),
                    side           = p.get("side", ""),
                    contracts      = p.get("number_of_contracts", ""),
                    avg_entry      = ev.get("price", {}).get("value", "") if isinstance(ev, dict) else "",
                    unrealized_pnl = p.get("unrealized_pnl", "0"),
                    daily_pnl      = p.get("daily_realized_pnl", "0"),
                ))
            self._deriv_store.set_positions(positions)

            # Open orders for deriv
            raw_orders = await asyncio.to_thread(
                self._rest.get_open_orders, self._deriv_product
            )
            self._deriv_store.set_orders(self._parse_orders(raw_orders))
        except Exception as e:
            self._deriv_store.error = f"Deriv error: {e}"

    async def _async_fetch_deriv_history(self) -> None:
        try:
            raw = await asyncio.to_thread(self._rest.get_order_history, self._deriv_product)
            self._deriv_store.set_history(self._parse_orders(raw, include_fill=True))
        except Exception as e:
            self._deriv_store.error = f"Deriv history error: {e}"

    # ── Order parsing helper ──────────────────────────────────────────────────

    @staticmethod
    def _parse_orders(raw: list[dict], include_fill: bool = False) -> list[Order]:
        orders = []
        for o in raw:
            cfg = o.get("order_configuration") or {}
            llg = cfg.get("limit_limit_gtc") or cfg.get("limit_limit_gtd") or {}
            mkt = cfg.get("market_market_ioc") or {}
            base_size = (
                llg.get("base_size")
                or mkt.get("base_size")
                or o.get("base_size", "")
            )
            created = (o.get("created_time") or "")
            orders.append(Order(
                order_id     = o.get("order_id", ""),
                side         = o.get("side", ""),
                order_type   = o.get("order_type", ""),
                product_id   = o.get("product_id", ""),
                base_size    = base_size,
                limit_price  = llg.get("limit_price", ""),
                filled_size  = str(o.get("filled_size") or "0"),
                status       = o.get("status", ""),
                created_at   = created[:19],
                avg_price    = str(o.get("average_filled_price") or "") if include_fill else "",
                filled_value = str(o.get("filled_value") or "")        if include_fill else "",
            ))
        return orders

    # ── Message handlers ──────────────────────────────────────────────────────

    def on_price_selected(self, msg: PriceSelected) -> None:
        for wid in ("#s-form", "#d-form"):
            try:
                self.query_one(wid).set_price(msg.price)   # type: ignore[union-attr]
            except Exception:
                pass

    def on_submit_order(self, msg: SubmitOrder) -> None:
        self.run_worker(
            self._async_place_order(msg.side, msg.order_type, msg.price,
                                    msg.size, msg.product_id),
            name="place-order",
        )

    async def _async_place_order(
        self, side: str, order_type: str, price: str, size: str, product_id: str
    ) -> None:
        is_deriv = product_id == self._deriv_product
        form_id  = "#d-form" if is_deriv else "#s-form"
        try:
            form = self.query_one(form_id)
        except Exception:
            return
        try:
            if order_type == "Limit":
                result = await asyncio.to_thread(
                    self._rest.place_limit_order, product_id, side, size, price,
                )
            elif is_deriv:
                # Futures market orders always use base_size (contract count)
                result = await asyncio.to_thread(
                    self._rest.place_market_order, product_id, side, size,
                )
            elif side == "BUY":
                # Spot market buy: spend USD amount
                try:
                    usd_total = str(round(float(price) * float(size), 2))
                except Exception:
                    usd_total = size
                result = await asyncio.to_thread(
                    self._rest.place_market_buy, product_id, usd_total,
                )
            else:
                result = await asyncio.to_thread(
                    self._rest.place_market_sell, product_id, size,
                )
            success = result.get("success", False)
            oid = (result.get("order_id")
                   or result.get("success_response", {}).get("order_id", ""))
            msg_str = (f"OK #{oid[:8]}" if success
                       else result.get("error_response", {}).get("message", "error")[:40])
            form.show_result(success, msg_str)    # type: ignore[union-attr]
            if success:
                await asyncio.sleep(1)
                if is_deriv:
                    await self._async_fetch_deriv_data()
                    await self._async_fetch_deriv_history()
                else:
                    await self._async_fetch_spot_account()
                    await self._async_fetch_spot_history()
        except Exception as e:
            form.show_result(False, str(e)[:50])  # type: ignore[union-attr]

    def on_cancel_order(self, msg: CancelOrder) -> None:
        self.run_worker(self._async_cancel(msg.order_id), name="cancel-order")

    async def _async_cancel(self, order_id: str) -> None:
        try:
            await asyncio.to_thread(self._rest.cancel_orders, [order_id])
            # Remove from both stores in case cancel comes from either tab
            for store, wid in ((self._spot_store, "#s-open-orders"),
                               (self._deriv_store, "#d-open-orders")):
                store.orders = [o for o in store.orders if o.order_id != order_id]
                self.query_one(wid, OpenOrders).refresh_data()
        except Exception as e:
            self._spot_store.error = str(e)[:60]

    def action_refresh_acct(self) -> None:
        self.run_worker(self._async_fetch_spot_account(),  name="s-acct-manual")
        self.run_worker(self._async_fetch_spot_history(),  name="s-hist-manual")
        self.run_worker(self._async_fetch_deriv_data(),    name="d-data-manual")
        self.run_worker(self._async_fetch_deriv_history(), name="d-hist-manual")
