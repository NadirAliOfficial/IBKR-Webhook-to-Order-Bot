import logging
import argparse
import sqlite3
from flask import Flask, request, jsonify, render_template
from ib_insync import IB, Forex, Stock, MarketOrder, LimitOrder, util
from datetime import datetime
import asyncio

# --- 1. Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 2. Trade Journal Database (Your New Schema) ---
DB_FILE = 'trade_state.db'

def init_db():
    """Initializes the database with the new trade journal schema."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            symbol TEXT NOT NULL,
            signal TEXT NOT NULL,
            position_size REAL NOT NULL,
            entry_order_id INTEGER,
            tp_order_id INTEGER,
            entry_price REAL,
            exit_price REAL,
            tp_price REAL,
            tp_hit BOOLEAN DEFAULT 0,
            closed BOOLEAN DEFAULT 0,
            sl_price REAL,
            sl_order_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Trade Journal Database initialized.")

# --- NEW DATABASE HELPER FUNCTIONS ---
def log_new_trade(symbol, signal, size, entry_order_id, tp_price=None, tp_order_id=None, sl_price=None, sl_order_id=None):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO trades (symbol, signal, position_size, entry_order_id, tp_price, tp_order_id, sl_price, sl_order_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (symbol, signal, size, entry_order_id, tp_price, tp_order_id, sl_price, sl_order_id))
    conn.commit()
    conn.close()

def update_trade_on_fill(order_id, fill_price):
    """Updates a trade with its entry or exit price when a fill occurs."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    # Check if it's an entry fill
    cursor.execute("UPDATE trades SET entry_price = ? WHERE entry_order_id = ? AND closed = 0", (fill_price, order_id))
    # Check if it's a TP fill
    cursor.execute("UPDATE trades SET exit_price = ?, closed = 1, tp_hit = 1 WHERE tp_order_id = ? AND closed = 0", (fill_price, order_id))
    conn.commit()
    conn.close()

def close_trade_in_db(trade_id):
    """Marks a trade as closed when closed by a manual signal."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE trades SET closed = 1 WHERE id = ?", (trade_id,))
    conn.commit()
    conn.close()

def get_active_trade(symbol):
    """Finds the currently open trade for a symbol, if any."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE symbol = ? AND closed = 0 ORDER BY id DESC LIMIT 1", (symbol,))
    trade = cursor.fetchone()
    conn.close()
    return dict(trade) if trade else None

def get_last_closed_trade(symbol):
    """Finds the most recently closed trade for a symbol."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE symbol = ? AND closed = 1 ORDER BY id DESC LIMIT 1", (symbol,))
    trade = cursor.fetchone()
    conn.close()
    return dict(trade) if trade else None


# --- 3. Global Data & Main App ---
dashboard_data = {'status': 'Initializing...', 'account': {}, 'positions': []}
# (The old trade_log list is no longer needed, but we keep it for simple UI logging)
trade_log_ui = [] 

def main():
    # ... (Parser and args setup remains the same) ...
    parser = argparse.ArgumentParser(description='IBKR Stateful Trading Bot')
    parser.add_argument('--flask-host', default='0.0.0.0', help='Flask host')
    parser.add_argument('--flask-port', type=int, default=5001, help='Flask port')
    parser.add_argument('--ib-host', default='127.0.0.1', help='IB host')
    parser.add_argument('--ib-port', type=int, default=7497, help='IB port for TWS')
    parser.add_argument('--ib-client-id', type=int, default=1, help='IB client ID')
    args = parser.parse_args()

    init_db()
    app = Flask(__name__)
    ib = IB()

    async def update_dashboard_data():
        # ... (no changes needed here) ...
        global dashboard_data
        while ib.isConnected():
            try:
                account_values = ib.accountValues()
                dashboard_data['account'] = {item.tag: item.value for item in account_values if item.tag in ['NetLiquidation', 'TotalCashValue', 'BuyingPower', 'UnrealizedPnL', 'RealizedPnL']}
                positions = ib.positions()
                dashboard_data['positions'] = [{'symbol': p.contract.localSymbol, 'position': p.position, 'avgCost': round(p.avgCost, 2)} for p in positions]
                server_time = ib.reqCurrentTime()
                dashboard_data['status'] = f"Data successfully updated at {server_time.strftime('%Y-%m-%d %H:%M:%S')}"
                logger.info("Dashboard data refreshed.")
            except Exception as e:
                logger.error(f"Error refreshing dashboard data: {repr(e)}")
                dashboard_data['status'] = f"Error refreshing data: {repr(e)}"
            await asyncio.sleep(60)

    # --- 4. Re-architected Core Trading Logic ---
    def connect_ibkr():
        if not ib.isConnected():
            ib.connect(args.ib_host, args.ib_port, clientId=args.ib_client_id)

    # ** The NEW `open_position` function using the trade journal **
    def open_position(symbol: str, side: str, quantity: float, tp=None, sl=None):
        connect_ibkr()
        sym = symbol.replace('/', '').upper()

        # LOGIC 1: Avoid re-entry after TP
        last_closed = get_last_closed_trade(sym)
        if last_closed and last_closed.get('tp_hit') and last_closed.get('signal') == side:
            message = f"Re-entry for '{side}' on {sym} is blocked due to recent TP."
            logger.warning(message)
            trade_log_ui.append({'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'symbol': sym, 'action': "RE-ENTRY BLOCKED", 'details': message})
            return

        # LOGIC 2: One trade at a time & Reversals
        active_trade = get_active_trade(sym)
        if active_trade:
            if active_trade.get('signal') == side:
                logger.info(f"Signal '{side}' is same as active trade for {sym}. No action taken.")
                return
            else:
                logger.info(f"Signal '{side}' is opposite of active trade for {sym}. Reversing.")
                close_position(symbol) # This will close the active trade

        # Place the new entry order
        contract = Forex(sym) if '/' in symbol else Stock(sym, 'SMART', 'USD')
        action = 'BUY' if side == 'buy' else 'SELL'
        market_order_trade = ib.placeOrder(contract, MarketOrder(action, quantity))
        entry_order_id = market_order_trade.order.orderId
        trade_log_ui.append({'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'symbol': sym, 'action': f"Market Order ({action})", 'details': repr(market_order_trade)})
        
       # Place TP and get its ID
        tp_id = None
        if tp:
            tp_price = float(tp)
            exit_act = 'SELL' if side == 'buy' else 'BUY'
            tp_order_trade = ib.placeOrder(contract, LimitOrder(exit_act, quantity, tp_price))
            tp_id = tp_order_trade.order.orderId
            trade_log_ui.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': sym,
                'action': f"Take Profit ({exit_act})",
                'details': repr(tp_order_trade)
            })

        # Place SL and get its ID
        sl_id = None
        if sl:
            sl_price = float(sl)
            sl_act = 'SELL' if side == 'buy' else 'BUY'
            sl_order_trade = ib.placeOrder(contract, LimitOrder(sl_act, quantity, sl_price))
            sl_id = sl_order_trade.order.orderId
            trade_log_ui.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': sym,
                'action': f"Stop Loss ({sl_act})",
                'details': repr(sl_order_trade)
            })

        # Log the new trade with both TP and SL
        log_new_trade(sym, side, quantity, entry_order_id, tp, tp_id, sl, sl_id)


    # ** The NEW `close_position` function **
    def close_position(symbol: str):
        connect_ibkr()
        sym = symbol.replace('/', '').upper()
        active_trade = get_active_trade(sym)
        if not active_trade:
            logger.info(f"No active trade found for {sym} to close by signal.")
            return

        # Cancel TP order if exists
        tp_order_id = active_trade.get('tp_order_id')
        if tp_order_id:
            try:
                ib.cancelOrder(ib.orders()[tp_order_id])  # Or cancel by ID if needed
                logger.info(f"Cancelled TP order {tp_order_id}")
            except Exception as e:
                logger.warning(f"Failed to cancel TP order {tp_order_id}: {e}")

        # Close the position with a market order
        side = active_trade.get('signal')
        quantity = active_trade.get('position_size')
        action_to_close = 'SELL' if side == 'buy' else 'BUY'
        close_order_trade = ib.placeOrder(
            Forex(sym) if '/' in symbol else Stock(sym, 'SMART', 'USD'),
            MarketOrder(action_to_close, quantity)
        )

        close_trade_in_db(active_trade.get('id'))
        trade_log_ui.append({'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'symbol': sym, 'action': f"Close by Signal ({action_to_close})", 'details': repr(close_order_trade)})

    # --- 5. The Sentry & App Startup ---
    def onExecDetails(trade, fill):
        """Sentry that listens for all order fills to update the journal."""
        order_id = fill.execution.orderId
        fill_price = fill.execution.price
        logger.info(f"Fill detected for orderId {order_id} at price {fill_price}.")
        update_trade_on_fill(order_id, fill_price)

    # Flask routes
    @app.route('/')
    def index():
        return render_template('index.html', dashboard_data=dashboard_data, trade_log=trade_log_ui)
    
    @app.route('/webhook', methods=['POST'])
    def webhook():
        data = request.get_json(force=True)
        try:
            action = data.get('action')
            if action == 'open':
                open_position(data.get('symbol'), data.get('side'), data.get('quantity'), data.get('tp'), data.get('sl'))
            elif action == 'close':
                close_position(data.get('symbol'))
        except Exception as e:
            logger.error(f'Error processing webhook: {e}', exc_info=True)
            return jsonify({'status': 'error', 'msg': str(e)}), 500
        return jsonify({'status': 'success'}), 200

    def onConnected(*args):
        logger.info("IBKR Connection successful.")
        asyncio.create_task(update_dashboard_data())
    
    ib.execDetailsEvent += onExecDetails
    ib.connectedEvent += onConnected
    util.startLoop()
    connect_ibkr()
    app.run(host=args.flask_host, port=args.flask_port, debug=False)

if __name__ == '__main__':
    main()