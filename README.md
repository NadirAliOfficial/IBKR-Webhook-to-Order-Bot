# IBKR Webhook-to-Order Bot

This Python project provides a Flask-based webhook receiver that converts TradingView alerts into interactive orders on Interactive Brokers (TWS or IB Gateway) using the `ib_insync` library.

---

## Features

* Listens for HTTP POST requests at `/webhook` endpoint
* Parses JSON payload with fields: `symbol`, `action`, `side`, `quantity`, and optional `tp` (take-profit)
* Opens or closes positions on IBKR (Forex or Stock contracts)
* Ensures only one position per symbol at a time, reversing if an opposite trade is requested
* Places market orders for entry and limit orders for take-profit
* Runs an asyncio event loop alongside Flask to support `ib_insync` in a multi-threaded environment

---

## Requirements

* Python 3.8+ (tested on 3.9)
* TWS (Trader Workstation) or IB Gateway running locally
* `pip` package manager

---

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/ibkr-webhook-bot.git
   cd ibkr-webhook-bot
   ```

2. (Optional) Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # macOS/Linux
   .\.venv\Scripts\activate  # Windows
   ```

3. Install dependencies:

   ```bash
   pip install flask ib_insync
   ```

---

## Configuration & Usage

### Running the Bot

By default, the bot connects to TWS on `127.0.0.1:7497` (client ID 1) and serves HTTP on `0.0.0.0:5000`.

Start the bot with:

```bash
python bot.py \
  --ib-host 127.0.0.1 \
  --ib-port 7497 \
  --ib-client-id 1 \
  --flask-host 0.0.0.0 \
  --flask-port 5000
```

You can override any parameter:

* `--ib-port 4002` for IB Gateway
* Different client IDs, hosts, or ports as needed

### Webhook Payload

Send a POST request with JSON body:

| Field      | Type   | Required     | Description                                 |
| ---------- | ------ | ------------ | ------------------------------------------- |
| `symbol`   | string | Yes          | `EUR/USD` or stock ticker, case-insensitive |
| `action`   | string | Yes          | `open` or `close`                           |
| `side`     | string | Yes for open | `buy` or `sell`                             |
| `quantity` | number | Yes          | Number of units/contracts                   |
| `tp`       | number | No           | Price for take-profit limit order           |

Example (open position):

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EUR/USD","side":"buy","action":"open","quantity":1,"tp":1.12345}'
```

Example (close position):

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EUR/USD","action":"close"}'
```

---

## Logging

* Uses Python's `logging` module at `INFO` level
* Prints connection steps, order placement details, and errors to console

---

## Production Considerations

* Replace Flask's built-in dev server with a production server (e.g., Gunicorn)
* Use HTTPS and authentication for the webhook endpoint
* Implement retry logic and persistent state if needed
* Add monitoring and alerting for errors or disconnects

---

## License

MIT License • © 2025 Team NAK
