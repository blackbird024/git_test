"""IBS swing trading en Alpaca (cuenta PAPER): QQQ y GLD.

Misma estrategia que el EA de MT5 (mt5/IbsSwing.mq5), la mejor del laboratorio de swing:
  * Unos minutos antes del cierre mira dónde está el precio dentro del rango de hoy:
    IBS = (precio - mínimo) / (máximo - mínimo).
  * IBS < 0.2 y sin posición: compra ALLOCATION_USD.
  * IBS > 0.8 con posición: vende todo.
QQQ y GLD no están en auto_strategy.py, así que no se mezcla con el largo plazo.

Se ejecuta una vez al día entre las 15:50 y las 16:00 de Nueva York.

Uso:
    python ibs_swing.py             # muestra el IBS y lo que haría
    python ibs_swing.py --execute   # envía las órdenes (solo dentro del horario)
"""

import argparse
import sys
from datetime import datetime
from datetime import time as dtime

from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from alpaca_client import is_paper, trading_client
from vwap_intraday import NY, SESSION_OPEN, minute_bars

SYMBOLS = ["QQQ", "GLD"]
ALLOCATION_USD = 10_000
ENTRY_IBS = 0.20
EXIT_IBS = 0.80
WINDOW = (dtime(15, 50), dtime(16, 0))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not is_paper():
        sys.exit("Esta estrategia solo corre en la cuenta PAPER.")

    client = trading_client()
    now = datetime.now(NY)
    in_window = client.get_clock().is_open and WINDOW[0] <= now.time() < WINDOW[1]
    execute = args.execute and in_window
    if args.execute and not in_window:
        print("Fuera del horario de decisión (15:50-16:00 NY con mercado abierto): solo se simula.")

    bars = minute_bars(SYMBOLS, datetime.combine(now.date(), SESSION_OPEN, NY))
    positions = {p.symbol: p for p in client.get_all_positions()}
    print(f"{now:%Y-%m-%d %H:%M} NY\n")
    print(f"{'Símbolo':8}{'Precio':>10}{'Mínimo':>10}{'Máximo':>10}{'IBS':>7}  Posición  Acción")
    for symbol in SYMBOLS:
        sbars = bars[bars["symbol"] == symbol]
        if len(sbars) < 100:
            print(f"{symbol:8} sin datos suficientes de hoy ({len(sbars)} velas)")
            continue
        high, low, price = sbars["high"].max(), sbars["low"].min(), float(sbars["close"].iloc[-1])
        ibs = (price - low) / (high - low) if high > low else 0.5
        pos = positions.get(symbol)

        action, order = "-", None
        if pos and ibs > EXIT_IBS:
            action = "vender todo"
            order = MarketOrderRequest(symbol=symbol, qty=float(pos.qty), side=OrderSide.SELL,
                                       time_in_force=TimeInForce.DAY)
        elif not pos and ibs < ENTRY_IBS:
            action = f"comprar ${ALLOCATION_USD:,.0f}"
            order = MarketOrderRequest(symbol=symbol, notional=ALLOCATION_USD, side=OrderSide.BUY,
                                       time_in_force=TimeInForce.DAY)
        held = f"{float(pos.qty):.3f}" if pos else "ninguna"
        print(f"{symbol:8}{price:>10.2f}{low:>10.2f}{high:>10.2f}{ibs:>7.2f}  {held:>8}  {action}")
        if order and execute:
            sent = client.submit_order(order)
            print(f"         orden enviada: {sent.side.value} {symbol}  estado: {sent.status.value}")
    if not execute:
        print("\nSimulación: no se enviaron órdenes.")


if __name__ == "__main__":
    main()
