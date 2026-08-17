# IBKR Webhook-to-Order Bot

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![ib_insync](https://img.shields.io/badge/ib__insync-0.9.86+-brightgreen?style=flat)](https://github.com/erdewit/ib_insync)
[![License](https://img.shields.io/github/license/NadirAliOfficial/IBKR-Webhook-to-Order-Bot)](LICENSE)
[![Release](https://img.shields.io/github/v/release/NadirAliOfficial/IBKR-Webhook-to-Order-Bot)](https://github.com/NadirAliOfficial/IBKR-Webhook-to-Order-Bot/releases)

A stateful Flask-based trading bot that receives webhook signals (from TradingView or any alert source) and executes real-time orders on Interactive Brokers using `ib_insync`. Maintains a full trade journal in SQLite, supports TP/SL order management, and exposes a live dashboard and REST API.

---

## How It Works

```
TradingView Alert  ──►  POST /webhook  ──►  Signal Parser
                                                  │
                              ┌───────────────────┤
                              │                   │
                         open_position       close_position
                              │
                    ┌─────────┴──────────┐
                    │                    │
               Market Order          Limit Orders
               (Entry)               (TP + SL)
                    │
               Trade Journal (SQLite)
                    │
              onExecDetails sentry ──► fill prices tracked on execution
```

---

## Features

- **Webhook-triggered execution** — POST to `/webhook` to open or close positions
- **Webhook authentication** — `WEBHOOK_SECRET` env var; requests without matching `X-Webhook-Secret` header are rejected (401)
- **Stateful trade journal** — SQLite tracks entry/exit prices, TP hit, SL, order IDs, and close reason
- **Smart re-entry blocking** — if last trade closed via TP, same-direction signal is blocked until manually reset
- **Position reversal** — opposite signal on an open trade auto-closes and reverses
- **TP + SL order placement** — both limit orders placed alongside market entry
- **TP cancel on close** — open TP order is cancelled before placing the closing market order
- **Live dashboard** — Flask UI at `/` shows account data, open positions, and trade log
- **Health endpoint** — `GET /health` returns IBKR connection status and uptime (JSON)
- **Trades API** — `GET /api/trades` returns paginated trade journal as JSON
- **Input validation** — webhook payload validated before any order is placed (400 on bad input)

---

## Setup

### 1. Install dependencies

```bash
pip install flask ib_insync
```

### 2. Configure environment

```bash
export WEBHOOK_SECRET=your_secret_here   # optional but recommended
```

### 3. Start TWS or IB Gateway

Make sure TWS or IB Gateway is running with API access enabled:
- TWS Live: port `7496` | TWS Paper: port `7497`
- IB Gateway Live: port `4001` | IB Gateway Paper: port `4002`

### 4. Run the bot

```bash
python app.py --ib-port 7497 --flask-port 5001
```

---

## Webhook Payload

### Open a position

```json
{
  "action": "open",
  "symbol": "AAPL",
  "side": "buy",
  "quantity": 10,
  "tp": 195.50,
  "sl": 185.00
}
```

### Close a position

```json
{
  "action": "close",
  "symbol": "AAPL"
}
```

For Forex pairs, use slash notation: `"symbol": "EUR/USD"`.

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Live dashboard — account, positions, trade log |
| `/webhook` | POST | Receive and execute trading signals |
| `/health` | GET | IBKR connection status and uptime (JSON) |
| `/api/trades` | GET | Paginated trade journal (`?limit=50&offset=0`) |

---

## CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--flask-host` | `0.0.0.0` | Flask bind address |
| `--flask-port` | `5001` | Flask port |
| `--ib-host` | `127.0.0.1` | TWS/Gateway host |
| `--ib-port` | `7497` | TWS/Gateway API port |
| `--ib-client-id` | `1` | IBKR client ID |

---

## Project Structure

```
IBKR-Webhook-to-Order-Bot/
├── app.py              # Core bot — Flask routes, IBKR logic, trade journal
├── trade_state.db      # SQLite database (auto-created on first run)
├── templates/
│   └── index.html      # Dashboard UI
├── requirements.txt
└── README.md
```

---

## Developer

Built by **Nadir Ali Khan** — [TEAM NAK](https://github.com/NadirAliOfficial) | [Telegram](https://t.me/NAKBlockDev)
