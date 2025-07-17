
# 📈 IBKR Webhook-Based Trading Bot

This is a Flask-based trading bot that receives webhook signals (e.g., from TradingView) and places real-time orders on Interactive Brokers (IBKR) using the `ib_insync` API. It logs trades to a local SQLite database and supports TP (Take Profit) and SL (Stop Loss) orders.

---

## 🚀 Features

- ✅ Webhook-triggered entry and exit via `/webhook`
- ✅ IBKR Market + Limit order execution (forex, stocks)
- ✅ TP and SL order placement per trade
- ✅ Avoids re-entry after TP is hit
- ✅ Trade journaling in SQLite: tracks fills, status, profit
- ✅ Live dashboard via Flask (at `/`)
- ✅ Fully configurable via command-line

---

## 🧱 Project Structure

```

IBKR-Webhook-to-Order-Bot/
│
├── app.py                  # Main trading bot logic
├── trade\_state.db          # SQLite DB (auto-created)
├── templates/
│   └── index.html          # Dashboard UI
├── .env                    # API keys or secrets (ignored)
├── .gitignore              # Ignore files
└── README.md               # This file

````

---

## ⚙️ Requirements

- Python 3.9+
- TWS or IB Gateway (running in Paper or Live mode)
- Install dependencies:

```bash
pip install flask ib_insync
````

---

## 🔐 .env File (Optional)

Create a `.env` file to store sensitive config:

```
IB_HOST=127.0.0.1
IB_PORT=7497
IB_CLIENT_ID=1
```

---

## 🧪 Running the Bot

Start your bot with:

```bash
python app.py --flask-port 5001
```

You can configure port, IB host/port, and client ID using flags.

---

## 📡 Webhook Examples

### ✅ Open Trade

```json
{
  "action": "open",
  "symbol": "EUR/USD",
  "side": "buy",
  "quantity": 10000,
  "tp": 1.1150,
  "sl": 1.1050
}
```

### ❌ Close Trade

```json
{
  "action": "close",
  "symbol": "EUR/USD"
}
```

Send via `curl`:

```bash
curl -X POST http://127.0.0.1:5001/webhook \
-H "Content-Type: application/json" \
-d '{"action":"open", "symbol":"EUR/USD", "side":"buy", "quantity":10000, "tp":1.1150, "sl":1.1050}'
```

---

## 🧠 Re-Entry Protection

After a TP is hit, the bot **blocks new entries in the same direction** until manually overridden.

---

## 🛠 Development Notes

* All trades are stored in `trade_state.db`
* You can inspect the database using:

```bash
sqlite3 trade_state.db
SELECT * FROM trades ORDER BY id DESC;
```

---

## ✅ .gitignore Setup

Your `.gitignore` should include:

```gitignore
# Ignore sensitive or system files
.env
*.db
__pycache__/
.vscode/
*.pyc
```

---

## 📜 License

MIT License (Free to use, modify, and distribute)
