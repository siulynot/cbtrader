from __future__ import annotations
import sys
from pathlib import Path

import yaml

from .api.feed import WebSocketFeed
from .api.rest import CoinbaseREST
from .app import CbTraderApp
from .models import DataStore


def _load_config(path: Path | None = None) -> dict:
    p = path or Path(__file__).parents[2] / "config.yaml"
    if not p.exists():
        sys.exit(f"config.yaml not found at {p}")
    with open(p) as f:
        return yaml.safe_load(f)


def main() -> None:
    cfg        = _load_config()
    cb_cfg     = cfg["coinbase"]
    key_name   = cb_cfg["api_key"]
    key_secret = cb_cfg["api_secret"]

    trading       = cfg.get("trading", {})
    spot_product  = trading.get("default_product", "BTC-USD")
    deriv_product = trading.get("deriv_product",   "BTC-PERP-INTX")

    rest = CoinbaseREST(key_name, key_secret)

    spot_store  = DataStore()
    deriv_store = DataStore()

    # Single WebSocket connection for all products → no concurrent-connection issues
    feed = WebSocketFeed(
        stores    = {spot_product: spot_store, deriv_product: deriv_store},
        key_name  = key_name,
        key_secret = key_secret,
    )

    app = CbTraderApp(
        rest,
        feed,
        spot_store, spot_product,
        deriv_store, deriv_product,
    )
    app.run()


if __name__ == "__main__":
    main()
