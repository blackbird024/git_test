"""Conexión básica con Alpaca Markets (paper trading por defecto).

Variables de entorno requeridas:
    APCA_API_KEY_ID      tu API key
    APCA_API_SECRET_KEY  tu API secret
Opcional:
    APCA_PAPER           "false" para usar la cuenta real (por defecto: true)

Uso:
    python alpaca_client.py                 # estado de cuenta y posiciones
    python alpaca_client.py quote AAPL      # última cotización
    python alpaca_client.py buy AAPL 1      # orden de compra a mercado
    python alpaca_client.py sell AAPL 1     # orden de venta a mercado
"""

import os
import sys

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest


def get_credentials():
    key = os.environ.get("APCA_API_KEY_ID")
    secret = os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        sys.exit("Faltan APCA_API_KEY_ID y/o APCA_API_SECRET_KEY en el entorno.")
    return key, secret


def is_paper():
    return os.environ.get("APCA_PAPER", "true").lower() != "false"


def trading_client():
    key, secret = get_credentials()
    return TradingClient(key, secret, paper=is_paper())


def data_client():
    key, secret = get_credentials()
    return StockHistoricalDataClient(key, secret)


def show_account():
    client = trading_client()
    account = client.get_account()
    clock = client.get_clock()
    print(f"Modo:            {'PAPER' if is_paper() else 'REAL'}")
    print(f"Estado:          {account.status}")
    print(f"Equity:          ${float(account.equity):,.2f}")
    print(f"Efectivo:        ${float(account.cash):,.2f}")
    print(f"Poder de compra: ${float(account.buying_power):,.2f}")
    print(f"Mercado abierto: {clock.is_open}")

    positions = client.get_all_positions()
    print(f"\nPosiciones ({len(positions)}):")
    for p in positions:
        print(f"  {p.symbol:6} {p.qty:>8} @ {float(p.avg_entry_price):,.2f}"
              f"  P/L: ${float(p.unrealized_pl):,.2f}")


def show_quote(symbol):
    request = StockLatestQuoteRequest(symbol_or_symbols=symbol.upper())
    quote = data_client().get_stock_latest_quote(request)[symbol.upper()]
    print(f"{symbol.upper()}  bid: {quote.bid_price}  ask: {quote.ask_price}"
          f"  ({quote.timestamp})")


def place_order(side, symbol, qty):
    if not is_paper():
        confirm = input(f"CUENTA REAL: {side.value} {qty} {symbol}. Escribe 'si': ")
        if confirm.strip().lower() != "si":
            sys.exit("Orden cancelada.")
    order = trading_client().submit_order(
        MarketOrderRequest(
            symbol=symbol.upper(),
            qty=qty,
            side=side,
            time_in_force=TimeInForce.DAY,
        )
    )
    print(f"Orden enviada: {order.id}  {order.side.value} {order.qty} "
          f"{order.symbol}  estado: {order.status.value}")


def main(argv):
    if not argv:
        show_account()
    elif argv[0] == "quote" and len(argv) == 2:
        show_quote(argv[1])
    elif argv[0] in ("buy", "sell") and len(argv) == 3:
        side = OrderSide.BUY if argv[0] == "buy" else OrderSide.SELL
        place_order(side, argv[1], float(argv[2]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
