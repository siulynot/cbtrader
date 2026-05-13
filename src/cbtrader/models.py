from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque
import threading


@dataclass
class TickerData:
    product_id:   str   = "BTC-USD"
    price:        float = 0.0
    price_24h_pct: float = 0.0
    volume_24h:   float = 0.0
    high_24h:     float = 0.0
    low_24h:      float = 0.0
    best_bid:     float = 0.0
    best_ask:     float = 0.0

    @property
    def spread(self) -> float:
        return self.best_ask - self.best_bid


@dataclass
class Trade:
    price: float
    size:  float
    side:  str    # "BUY" | "SELL"
    time:  str


@dataclass
class Order:
    order_id:     str
    side:         str
    order_type:   str
    product_id:   str
    base_size:    str
    limit_price:  str
    filled_size:  str
    status:       str
    created_at:   str
    avg_price:    str = ""
    filled_value: str = ""


@dataclass
class Balance:
    currency:  str
    available: float
    hold:      float

    @property
    def total(self) -> float:
        return self.available + self.hold


@dataclass
class FuturesBalance:
    buying_power:    float = 0.0
    cfm_balance:     float = 0.0
    initial_margin:  float = 0.0
    unrealized_pnl:  float = 0.0
    daily_pnl:       float = 0.0


@dataclass
class Position:
    product_id:     str
    side:           str    # "LONG" | "SHORT"
    contracts:      str
    avg_entry:      str
    unrealized_pnl: str
    daily_pnl:      str = ""


class OrderBook:
    """Thread-safe order book with sorted bid/ask dicts."""

    def __init__(self) -> None:
        self._lock  = threading.Lock()
        # bids: highest first (negate key for SortedDict ascending)
        self._bids: dict[float, float] = {}
        self._asks: dict[float, float] = {}

    def snapshot(self, bids: list[tuple[float, float]], asks: list[tuple[float, float]]) -> None:
        with self._lock:
            self._bids = dict(bids)
            self._asks = dict(asks)

    def update(self, side: str, price: float, qty: float) -> None:
        with self._lock:
            book = self._bids if side == "bid" else self._asks
            if qty == 0.0:
                book.pop(price, None)
            else:
                book[price] = qty

    def top(self, depth: int = 12) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
        """Returns (bids, asks) each as [(price, size)] sorted for display.
        Bids: highest first. Asks: lowest first."""
        with self._lock:
            bids = sorted(self._bids.items(), reverse=True)[:depth]
            asks = sorted(self._asks.items())[:depth]
        return bids, asks

    @property
    def mid(self) -> float:
        with self._lock:
            if not self._bids or not self._asks:
                return 0.0
            return (max(self._bids) + min(self._asks)) / 2


class DataStore:
    """Central shared state updated by WebSocket worker, read by widgets."""

    def __init__(self) -> None:
        self.ticker:    TickerData     = TickerData()
        self.orderbook: OrderBook      = OrderBook()
        self.trades:    deque[Trade]   = deque(maxlen=40)
        self.orders:    list[Order]    = []
        self.history:   list[Order]    = []
        self.balances:  dict[str, Balance] = {}
        self.connected: bool           = False
        self.error:     str            = ""
        # Derivatives extras (populated for perp store only)
        self.futures_balance: FuturesBalance = FuturesBalance()
        self.positions:       list[Position] = []
        self.funding_rate:    float = 0.0
        self.index_price:     float = 0.0
        self.next_funding:    str   = ""
        self.open_interest:   float = 0.0
        self.contract_size:   float = 0.01   # BTC-PERP-INTX: 1 contract = 0.01 BTC
        self.max_leverage:    float = 50.0
        self._lock = threading.Lock()

    def set_orders(self, orders: list[Order]) -> None:
        with self._lock:
            self.orders = orders

    def set_history(self, orders: list[Order]) -> None:
        with self._lock:
            self.history = orders

    def set_positions(self, positions: list[Position]) -> None:
        with self._lock:
            self.positions = positions

    def set_balances(self, balances: dict[str, Balance]) -> None:
        with self._lock:
            self.balances = dict(balances)

    def add_trade(self, trade: Trade) -> None:
        self.trades.appendleft(trade)
