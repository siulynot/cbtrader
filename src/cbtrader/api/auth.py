from __future__ import annotations
import secrets
import time

import jwt
from cryptography.hazmat.primitives.serialization import load_pem_private_key

_BASE_REST = "https://api.coinbase.com"
_BASE_WS   = "wss://advanced-trade-ws.coinbase.com"


def _load_key(pem_str: str):
    pem = pem_str.replace("\\n", "\n").encode()
    return load_pem_private_key(pem, password=None)


def make_jwt(key_name: str, key_secret: str, method: str = "", path: str = "") -> str:
    """JWT for REST (method+path required) or WebSocket (leave both empty)."""
    private_key = _load_key(key_secret)
    now = int(time.time())
    payload: dict = {
        "sub": key_name,
        "iss": "coinbase-cloud",
        "nbf": now,
        "exp": now + 120,
    }
    if method and path:
        payload["uri"] = f"{method} api.coinbase.com{path}"
    headers = {"kid": key_name, "nonce": secrets.token_hex(10)}
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)
