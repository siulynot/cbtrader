# cbtrader

A terminal trading interface for [Coinbase Advanced Trade](https://www.coinbase.com/advanced-trade), built with [Textual](https://textual.textualize.io/). Trade spot and BTC perpetual futures without leaving your terminal.

![Portfolio](docs/screenshots/portfolio.png)
![Spot BTC](docs/screenshots/spot.png)
![BTC Perp](docs/screenshots/perp.png)

---

## Features

- **Portfolio tab** — consolidated balance across spot and derivatives, session balance chart, crypto holdings with USD value and allocation
- **Spot BTC tab** — live candlestick chart (1m / 5m / 15m / 1h / 6h / 1D), real-time order book and trades, limit and market orders, USD / USDC toggle, open orders and order history
- **BTC Perp tab** — live derivatives chart, funding rate, next funding time, open interest, daily volume, long/short order form with leverage and margin preview, positions panel
- Single WebSocket connection for all products — no duplicate-connection issues
- All data streamed live via Coinbase Advanced Trade WebSocket

---

## Requirements

- Python 3.11+
- A [Coinbase Advanced Trade API key](https://www.coinbase.com/settings/api) with **view** and **trade** scopes
- A funded Coinbase account (spot) and/or a Coinbase FCM account (derivatives)

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/siulynot/cbtrader.git
cd cbtrader

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install the package in editable mode
pip install -e .
```

---

## Configuration

Copy the example config and fill in your credentials:

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml`:

```yaml
coinbase:
  api_key: "organizations/<org-id>/apiKeys/<key-id>"
  api_secret: |
    -----BEGIN EC PRIVATE KEY-----
    <your private key here>
    -----END EC PRIVATE KEY-----

trading:
  default_product: "BTC-USD"
  deriv_product: "BIP-20DEC30-CDE"
```

> **Where to get your API key:** Coinbase → Settings → API → New API Key.  
> Required scopes: `view`, `trade`.  
> `config.yaml` is listed in `.gitignore` and will never be committed.

### Derivatives setup

The default `deriv_product` is `BIP-20DEC30-CDE` — the Coinbase FCM BTC perpetual contract (1 contract = 0.01 BTC). This requires a [Coinbase FCM account](https://www.coinbase.com/derivatives). No INTX activation is needed.

To trade a different perpetual, replace `deriv_product` with any valid FCM product ID.

---

## Running

```bash
cbtrader
```

Or, without installing:

```bash
python -m cbtrader.main
```

---

## Usage

### Navigation

| Key | Action |
|-----|--------|
| `Tab` / click | Switch between Portfolio / Spot BTC / BTC Perp tabs |
| `q` | Quit |
| `r` | Force-refresh account data and order history |

### Portfolio tab

Displays your total balance (spot cash + crypto + derivatives CFM balance), a session balance chart that builds over time, and a breakdown of cash accounts and crypto holdings.

### Spot BTC tab

| Element | Interaction |
|---------|-------------|
| Timeframe buttons (1m … 1D) | Switch candlestick chart timeframe |
| Order book rows | Click a price to fill the Price field in the order form |
| BTC balance button | Click to fill the Size field with your full BTC balance |
| USD / USDC balance button | Click to fill the Size with the max BTC you can buy |
| USD / USDC toggle | Switch the quote currency for the order |
| Open Orders tab | Live open orders — click a row to cancel it |
| History tab | Filled and cancelled order history |

### BTC Perp tab

| Element | Interaction |
|---------|-------------|
| Buy Long / Sell Short | Toggle position direction |
| Limit / Market | Toggle order type |
| Avail button | Click to fill Size with the maximum contracts your balance supports |
| Size (Contracts) | Enter the number of contracts (1 contract = 0.01 BTC) |
| Leverage | Adjust leverage (1x – 50x); updates margin preview |
| Open Orders tab | Live open orders |
| History tab | Filled and cancelled order history |
| Positions tab | Current open positions with unrealized P&L |

---

## Project structure

```
cbtrader/
├── config.yaml.example     # copy to config.yaml and add your keys
├── pyproject.toml
└── src/cbtrader/
    ├── main.py             # entry point
    ├── app.py              # Textual app, tab layout, data orchestration
    ├── models.py           # DataStore, TickerData, Order, Position, …
    ├── api/
    │   ├── auth.py         # JWT (ES256) signing for Coinbase API
    │   ├── rest.py         # REST client (orders, candles, balances)
    │   └── feed.py         # WebSocket feed (single connection, multi-product)
    └── widgets/
        ├── ticker.py       # Spot ticker bar
        ├── deriv_ticker.py # Derivatives ticker bar (funding rate, OI, volume)
        ├── chart.py        # Candlestick chart (textual-plotext)
        ├── orderbook.py    # Live order book
        ├── trades.py       # Recent trades
        ├── orderform.py    # Spot order form
        ├── deriv_orderform.py  # Derivatives order form
        ├── balance.py      # Spot balance summary
        ├── deriv_balance.py    # Derivatives balance summary
        ├── openorders.py   # Open orders table
        ├── orderhistory.py # Order history table
        ├── positions.py    # Derivatives positions table
        └── portfolio.py    # Portfolio overview + session chart
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `textual` | TUI framework |
| `textual-plotext` | Plotext chart widget for Textual |
| `plotext` | Terminal charting |
| `websockets` | Coinbase Advanced Trade WebSocket |
| `PyJWT` + `cryptography` | ES256 JWT auth for Coinbase API |
| `requests` | REST API calls |
| `pyyaml` | Config file parsing |

---

## License

MIT
