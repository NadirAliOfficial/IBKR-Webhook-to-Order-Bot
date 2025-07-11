# IBKR-Webhook-to-Order-Bot
- Connects to IB Gateway / TWS via ib_insync - Enforces “one trade at a time” per symbol (no pyramiding) - Reverses position on opposite-side open signals - Attaches a TP limit order when provided - Closes existing position on “close” signals
