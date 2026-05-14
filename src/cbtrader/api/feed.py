from __future__ import annotations
import asyncio
import json
import logging

import websockets

from .auth import make_jwt
from ..models import DataStore, Trade, TickerData

_WS_URL = "wss://advanced-trade-ws.coinbase.com"
log = logging.getLogger(__name__)


class WebSocketFeed:
    """Single WebSocket connection routing data to multiple per-product stores."""

    def __init__(self, stores: dict[str, DataStore],
                 key_name: str, key_secret: str) -> None:
        self._stores   = stores          # {"BTC-USD": spot_store, "BTC-PERP-INTX": deriv_store}
        self._products = list(stores.keys())
        self._key      = key_name
        self._secret   = key_secret

    async def run(self) -> None:
        while True:
            try:
                await self._connect()
            except Exception as e:
                for s in self._stores.values():
                    s.connected = False
                    s.error     = str(e)[:80]
                await asyncio.sleep(3)

    async def _connect(self) -> None:
        async with websockets.connect(
            _WS_URL, ping_interval=20, ping_timeout=30,
            max_size=10 * 1024 * 1024,
        ) as ws:
            for s in self._stores.values():
                s.connected = True
                s.error     = ""

            token = make_jwt(self._key, self._secret)
            for channel in ("ticker", "level2", "market_trades", "user"):
                await ws.send(json.dumps({
                    "type":        "subscribe",
                    "product_ids": self._products,
                    "channel":     channel,
                    "jwt":         token,
                }))

            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if msg.get("type") == "error":
                    for s in self._stores.values():
                        s.error = msg.get("message", "WS error")[:80]
                    continue

                channel = msg.get("channel", "")
                try:
                    if channel == "ticker":
                        self._handle_ticker(msg)
                    elif channel == "l2_data":
                        self._handle_l2(msg)
                    elif channel == "market_trades":
                        self._handle_trades(msg)
                    elif channel == "user":
                        self._handle_user(msg)
                except Exception as e:
                    log.warning("handler error [%s]: %s", channel, e)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _handle_ticker(self, msg: dict) -> None:
        for event in msg.get("events", []):
            for t in event.get("tickers", []):
                pid   = t.get("product_id", "")
                store = self._stores.get(pid)
                if store is None:
                    continue
                store.ticker = TickerData(
                    product_id    = pid,
                    price         = float(t.get("price", 0) or 0),
                    price_24h_pct = float(t.get("price_percent_chg_24_h", 0) or 0),
                    volume_24h    = float(t.get("volume_24_h", 0) or 0),
                    high_24h      = float(t.get("high_24_h", 0) or 0),
                    low_24h       = float(t.get("low_24_h", 0) or 0),
                    best_bid      = float(t.get("best_bid", 0) or 0),
                    best_ask      = float(t.get("best_ask", 0) or 0),
                )
                # Futures-only fields pushed on the ticker channel
                fr = t.get("funding_rate")
                if fr is not None:
                    try:
                        store.funding_rate = float(fr)
                    except (ValueError, TypeError):
                        pass
                nf = t.get("next_funding_time") or t.get("funding_time")
                if nf:
                    store.next_funding = str(nf)[:19]

    def _handle_l2(self, msg: dict) -> None:
        for event in msg.get("events", []):
            pid   = event.get("product_id", "")
            store = self._stores.get(pid)
            if store is None:
                continue
            ev_type = event.get("type")
            updates = event.get("updates", [])
            if ev_type == "snapshot":
                bids = [(float(u["price_level"]), float(u["new_quantity"]))
                        for u in updates if u["side"] == "bid"]
                asks = [(float(u["price_level"]), float(u["new_quantity"]))
                        for u in updates if u["side"] == "offer"]
                store.orderbook.snapshot(bids, asks)
            else:
                for u in updates:
                    store.orderbook.update(
                        "bid" if u["side"] == "bid" else "ask",
                        float(u["price_level"]),
                        float(u["new_quantity"]),
                    )

    def _handle_trades(self, msg: dict) -> None:
        for event in msg.get("events", []):
            for t in event.get("trades", []):
                pid   = t.get("product_id", "")
                store = self._stores.get(pid)
                if store is None:
                    continue
                store.add_trade(Trade(
                    price = float(t.get("price", 0) or 0),
                    size  = float(t.get("size", 0) or 0),
                    side  = t.get("side", ""),
                    time  = t.get("time", "")[:19],
                ))

    def _handle_user(self, msg: dict) -> None:
        from ..models import Order
        for event in msg.get("events", []):
            # Group orders by product_id and update each store
            by_product: dict[str, list] = {}
            for o in event.get("orders", []):
                status = o.get("status", "")
                if status not in ("OPEN", "PENDING"):
                    continue
                pid = o.get("product_id", "")
                by_product.setdefault(pid, []).append(o)

            # Collect new orders per store; a store may service multiple products
            # (e.g. spot_store handles both BTC-USD market data and BTC-USDC orders)
            store_orders: dict[int, tuple] = {}
            for pid, raw_orders in by_product.items():
                store = self._stores.get(pid)
                if store is None:
                    continue
                sid = id(store)
                if sid not in store_orders:
                    store_orders[sid] = (store, [])
                bucket = store_orders[sid][1]
                for o in raw_orders:
                    cfg = o.get("order_configuration", {})
                    llg = cfg.get("limit_limit_gtc", cfg.get("limit_limit_gtd", {}))
                    bucket.append(Order(
                        order_id    = o.get("order_id", ""),
                        side        = o.get("order_side", ""),
                        order_type  = o.get("order_type", ""),
                        product_id  = pid,
                        base_size   = llg.get("base_size", o.get("base_size", "")),
                        limit_price = llg.get("limit_price", ""),
                        filled_size = o.get("filled_size", "0"),
                        status      = status,
                        created_at  = o.get("creation_time", "")[:19],
                    ))

            for store, orders in store_orders.values():
                store.set_orders(orders)
