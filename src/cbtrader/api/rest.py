from __future__ import annotations
import uuid
from typing import Any

import requests

from .auth import make_jwt

_BASE = "https://api.coinbase.com"
_TIMEOUT = 10


class CoinbaseREST:
    def __init__(self, key_name: str, key_secret: str) -> None:
        self._key   = key_name
        self._secret = key_secret
        self._session = requests.Session()

    def _headers(self, method: str, path: str) -> dict:
        token = make_jwt(self._key, self._secret, method, path)
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _get(self, path: str, params: dict | None = None) -> Any:
        r = self._session.get(
            f"{_BASE}{path}", headers=self._headers("GET", path),
            params=params, timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict) -> Any:
        r = self._session.post(
            f"{_BASE}{path}", headers=self._headers("POST", path),
            json=body, timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    def _delete(self, path: str, body: dict) -> Any:
        r = self._session.delete(
            f"{_BASE}{path}", headers=self._headers("DELETE", path),
            json=body, timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    # ── Accounts ──────────────────────────────────────────────────────────────

    def get_accounts(self) -> list[dict]:
        data = self._get("/api/v3/brokerage/accounts")
        return data.get("accounts", [])

    # ── Orders ────────────────────────────────────────────────────────────────

    # ── Derivatives ───────────────────────────────────────────────────────────

    def get_perp_info(self, product_id: str) -> dict:
        return self._get(f"/api/v3/brokerage/products/{product_id}")

    def get_futures_balance(self) -> dict:
        data = self._get("/api/v3/brokerage/cfm/balance_summary")
        return data.get("balance_summary", {})

    def get_futures_positions(self) -> list[dict]:
        data = self._get("/api/v3/brokerage/cfm/positions")
        return data.get("positions", [])

    # ── Orders ────────────────────────────────────────────────────────────────

    def get_order_history(self, product_id: str, limit: int = 50) -> list[dict]:
        filled = self._get(
            "/api/v3/brokerage/orders/historical/batch",
            params={"product_id": product_id, "order_status": "FILLED",
                    "limit": str(limit)},
        ).get("orders", [])
        cancelled = self._get(
            "/api/v3/brokerage/orders/historical/batch",
            params={"product_id": product_id, "order_status": "CANCELLED",
                    "limit": str(limit // 2)},
        ).get("orders", [])
        combined = filled + cancelled
        combined.sort(key=lambda o: o.get("created_time", ""), reverse=True)
        return combined[:limit]

    def get_open_orders(self, product_id: str) -> list[dict]:
        data = self._get(
            "/api/v3/brokerage/orders/historical/batch",
            params={"product_id": product_id, "order_status": "OPEN"},
        )
        return data.get("orders", [])

    def place_limit_order(
        self,
        product_id: str,
        side: str,           # "BUY" | "SELL"
        base_size: str,      # e.g. "0.001"
        limit_price: str,    # e.g. "80000"
        post_only: bool = False,
    ) -> dict:
        return self._post("/api/v3/brokerage/orders", {
            "client_order_id": str(uuid.uuid4()),
            "product_id": product_id,
            "side": side,
            "order_configuration": {
                "limit_limit_gtc": {
                    "base_size": base_size,
                    "limit_price": limit_price,
                    "post_only": post_only,
                }
            },
        })

    def place_market_buy(self, product_id: str, quote_size: str) -> dict:
        """Spot market buy with USD amount."""
        return self._post("/api/v3/brokerage/orders", {
            "client_order_id": str(uuid.uuid4()),
            "product_id": product_id,
            "side": "BUY",
            "order_configuration": {
                "market_market_ioc": {"quote_size": quote_size}
            },
        })

    def place_market_sell(self, product_id: str, base_size: str) -> dict:
        """Spot market sell with BTC amount."""
        return self._post("/api/v3/brokerage/orders", {
            "client_order_id": str(uuid.uuid4()),
            "product_id": product_id,
            "side": "SELL",
            "order_configuration": {
                "market_market_ioc": {"base_size": base_size}
            },
        })

    def place_market_order(self, product_id: str, side: str, base_size: str) -> dict:
        """Futures/perp market order with contract count as base_size."""
        return self._post("/api/v3/brokerage/orders", {
            "client_order_id": str(uuid.uuid4()),
            "product_id": product_id,
            "side": side,
            "order_configuration": {
                "market_market_ioc": {"base_size": base_size}
            },
        })

    def cancel_orders(self, order_ids: list[str]) -> dict:
        return self._post("/api/v3/brokerage/orders/batch_cancel", {
            "order_ids": order_ids
        })

    # ── Market data ───────────────────────────────────────────────────────────

    def get_candles(self, product_id: str, granularity: str, limit: int = 150) -> list[dict]:
        import time
        _SECS = {
            "ONE_MINUTE": 60, "FIVE_MINUTE": 300, "FIFTEEN_MINUTE": 900,
            "THIRTY_MINUTE": 1800, "ONE_HOUR": 3600, "TWO_HOUR": 7200,
            "SIX_HOUR": 21600, "ONE_DAY": 86400,
        }
        end   = int(time.time())
        start = end - _SECS.get(granularity, 3600) * limit
        data  = self._get(
            f"/api/v3/brokerage/products/{product_id}/candles",
            params={"start": str(start), "end": str(end),
                    "granularity": granularity, "limit": str(limit)},
        )
        return data.get("candles", [])
