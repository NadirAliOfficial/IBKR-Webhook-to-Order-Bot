
import logging
import traceback

from flask import Flask, request, jsonify
from ib_insync import IB, Forex, MarketOrder, LimitOrder, util

# Start ib_insync asyncio loop
util.startLoop()

# ——— Configuration ———
IB_HOST      = '127.0.0.1'   # IBKR TWS/Gateway host
IB_PORT      = 7497          # API port (4001=paper, 7497=live)
IB_CLIENT_ID = 1             # unique client ID
FLASK_PORT   = 5001          # Flask server port

# ——— Logging Setup ———
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ——— IBKR Connection ———
ib = IB()
ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
logger.info(f"Connected to IBKR at {IB_HOST}:{IB_PORT} (client {IB_CLIENT_ID})")

# Track open TP orders for cancellation
outstanding_tps = {}

# ——— Helper Functions ———
def qualify_forex(symbol: str):
    """
    Build and qualify a Forex contract for 'EURUSD'-style symbols.
    """
    logger.info(f"Qualifying Forex contract for {symbol}")
    if len(symbol) != 6:
        raise ValueError(f"Invalid Forex symbol: {symbol}")

    base = symbol[:3]
    quote = symbol[3:]

    from ib_insync import Contract
    contract = Contract()
    contract.symbol = base
    contract.secType = 'CASH'
    contract.exchange = 'IDEALPRO'
    contract.currency = quote

    qualified = ib.qualifyContracts(contract)

    if not qualified:
        logger.warning(f"IDEALPRO failed for {symbol}, trying SMART")
        contract.exchange = 'SMART'
        qualified = ib.qualifyContracts(contract)

    if not qualified:
        raise RuntimeError(f"Could not qualify Forex contract for {symbol}")

    logger.info(f"Qualified {symbol} on exchange {qualified[0].exchange}")
    return qualified[0]




def get_position(symbol: str) -> float:
    """
    Return current open position size for given Forex symbol.
    """
    for pos in ib.positions():
        if pos.contract.symbol == symbol:
            return pos.position
    return 0.0


def close_position(symbol: str):
    """
    Close any open position for this symbol and cancel its TP.
    """
    size = get_position(symbol)
    if size == 0.0:
        logger.info(f"No position to close for {symbol}")
        return
    contract = qualify_forex(symbol)
    side = 'SELL' if size > 0 else 'BUY'
    ib.placeOrder(contract, MarketOrder(side, abs(size)))
    logger.info(f"Closed {symbol}: {side} {abs(size)}")
    tp = outstanding_tps.pop(symbol, None)
    if tp:
        ib.cancelOrder(tp)
        logger.info(f"Canceled TP for {symbol}")


def open_position(symbol: str, side: str, qty: float, tp: float = None):
    """
    Open or reverse a Forex position:
      1. Reverse opposite side if open
      2. Avoid pyramiding
      3. Place market order + optional TP limit
    """
    current = get_position(symbol)
    want_long = side.lower() == 'buy'
    contract = qualify_forex(symbol)

    # Reverse if opposite side exists
    if current != 0.0 and ((current > 0) != want_long):
        logger.info(f"Reversing existing position for {symbol}")
        close_position(symbol)

    # Refresh position and avoid pyramiding
    current = get_position(symbol)
    if (want_long and current > 0) or (not want_long and current < 0):
        logger.info(f"Skipping pyramiding for {symbol} (current={current})")
        return

    # Market order
    action = 'BUY' if want_long else 'SELL'
    ib.placeOrder(contract, MarketOrder(action, qty))
    logger.info(f"Placed market {action} {qty} {symbol}")

    # Take-profit limit
    if tp is not None:
        tp_action = 'SELL' if want_long else 'BUY'
        tp_order = ib.placeOrder(contract, LimitOrder(tp_action, qty, tp))
        outstanding_tps[symbol] = tp_order
        logger.info(f"Set TP for {symbol}: {tp_action} {qty}@{tp}")

# ——— Flask App ———
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    logger.info(f"Webhook received: {data}")
    try:
        symbol   = data['symbol']
        action   = data['action']
        side     = data['side']
        qty      = float(data.get('quantity', 1))
        tp_val   = float(data['tp']) if data.get('tp') else None

        if action == 'open':
            open_position(symbol, side, qty, tp_val)
        elif action == 'close':
            close_position(symbol)
        else:
            raise ValueError(f"Unknown action: {action}")

        return jsonify(status='ok', data=data), 200
    except Exception:
        tb = traceback.format_exc()
        logger.error(tb)
        return jsonify(status='error', error=tb), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=FLASK_PORT)
