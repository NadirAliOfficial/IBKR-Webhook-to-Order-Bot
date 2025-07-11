import logging
import argparse
from flask import Flask, request, jsonify
from ib_insync import IB, Forex, Stock, MarketOrder, LimitOrder, util

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Main entrypoint
def main():
    parser = argparse.ArgumentParser(description='IBKR Webhook-to-Order Bot')
    # Flask options
    parser.add_argument('--flask-host', default='0.0.0.0', help='Flask host')
    parser.add_argument('--flask-port', type=int, default=5000, help='Flask port')
    # IBKR connection options (TWS defaults)
    parser.add_argument('--ib-host', default='127.0.0.1', help='IB host')
    parser.add_argument('--ib-port', type=int, default=7497, help='IB port (7497 for TWS)')
    parser.add_argument('--ib-client-id', type=int, default=1, help='IB client ID')
    args = parser.parse_args()

    # Initialize Flask and IB
    app = Flask(__name__)
    ib = IB()

    # Start asyncio event loop in background thread
    util.startLoop()

    # Connect to IBKR
    def connect_ibkr():
        if not ib.isConnected():
            logger.info(f'Connecting to IB at {args.ib_host}:{args.ib_port}, clientId={args.ib_client_id}')
            ib.connect(args.ib_host, args.ib_port, clientId=args.ib_client_id)
    connect_ibkr()

    # Helpers
    def get_position(symbol: str):
        norm = symbol.replace('/', '').upper()
        for pos in ib.positions():
            if pos.contract.symbol == norm:
                return pos
        return None

    def open_position(symbol: str, side: str, quantity: float, tp=None):
        connect_ibkr()
        sym = symbol.replace('/', '').upper()
        contract = Forex(sym) if '/' in symbol else Stock(sym)
        # Reverse existing if opposite
        pos = get_position(symbol)
        if pos and pos.position != 0:
            curr = 'buy' if pos.position > 0 else 'sell'
            if curr == side:
                logger.info(f'Already {curr} {sym}; skipping')
                return
            logger.info(f'Reversing {sym}')
            ib.placeOrder(pos.contract, MarketOrder('SELL' if pos.position > 0 else 'BUY', abs(pos.position)))
            ib.sleep(1)
        # Place entry
        action = 'BUY' if side == 'buy' else 'SELL'
        ib.placeOrder(contract, MarketOrder(action, quantity))
        ib.sleep(1)
        logger.info(f'Placed {action} {quantity} {sym}')
        # Place TP limit
        if tp is not None:
            price = float(tp)
            exit_act = 'SELL' if side == 'buy' else 'BUY'
            ib.placeOrder(contract, LimitOrder(exit_act, quantity, price))
            logger.info(f'Placed TP limit at {price} {sym}')
        ib.sleep(1)

    def close_position(symbol: str):
        connect_ibkr()
        sym = symbol.replace('/', '').upper()
        pos = get_position(symbol)
        if not pos or pos.position == 0:
            logger.info(f'No open pos on {sym}')
            return
        act = 'SELL' if pos.position > 0 else 'BUY'
        ib.placeOrder(pos.contract, MarketOrder(act, abs(pos.position)))
        ib.sleep(1)
        logger.info(f'Closed {sym}')

    # Webhook endpoint
    @app.route('/webhook', methods=['POST'])
    def webhook():
        data = request.get_json(force=True)
        logger.info(f'Webhook received: {data}')
        symbol = data.get('symbol', '')
        action = data.get('action')
        side = data.get('side', '').lower()
        qty = data.get('quantity', 0)
        tp = data.get('tp')
        try:
            if action == 'open':
                open_position(symbol, side, qty, tp)
            elif action == 'close':
                close_position(symbol)
            else:
                logger.warning(f'Unknown action: {action}')
        except Exception as e:
            logger.error(f'Error processing webhook: {e}', exc_info=True)
            return jsonify({'status': 'error', 'msg': str(e)}), 500
        return jsonify({'status': 'success'}), 200

    # Start Flask server
    app.run(host=args.flask_host, port=args.flask_port)

if __name__ == '__main__':
    main()
