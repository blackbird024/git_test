"""Estrategia automática y replicable para cuentas de Alpaca.

La estrategia y las cuentas se definen en strategy_config.json, así la misma
lógica se aplica a varias cuentas. Las claves nunca van en el archivo: cada
cuenta indica los nombres de las variables de entorno que las contienen.

Reglas (parámetros en strategy_config.json):
  * Pesos objetivo por ETF; la suma no puede pasar del 100% y lo demás queda
    en efectivo.
  * Filtro de tendencia: un activo con trend_filter solo se mantiene si su
    cierre está por encima de la media móvil de sma_days días.
  * Solo rebalancea si una posición se desvía más de drift_tolerance
    (relativo) de su objetivo.
  * Freno de emergencia: si el equity cae max_drawdown bajo initial_capital,
    vende los activos con filtro de tendencia y no vuelve a comprarlos.
  * Las cuentas reales (paper: false) solo operan con --allow-live.

Uso:
    python auto_strategy.py                     # simulación en todas las cuentas
    python auto_strategy.py --execute           # envía órdenes
    python auto_strategy.py --account principal # solo una cuenta
    python auto_strategy.py --config otra.json  # otro archivo de configuración
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

DEFAULT_CONFIG = Path(__file__).with_name("strategy_config.json")


def load_config(path):
    config = json.loads(Path(path).read_text())
    total = sum(t["weight"] for t in config["strategy"]["targets"].values())
    if total > 1:
        sys.exit(f"Los pesos suman {total:.0%}; el máximo es 100%.")
    return config


def trends(data, symbols, sma_days):
    request = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=datetime.now(timezone.utc) - timedelta(days=sma_days * 1.6),
        feed=DataFeed.IEX,
    )
    bars = data.get_stock_bars(request).df
    result = {}
    for symbol in symbols:
        closes = bars.loc[symbol]["close"]
        if len(closes) < sma_days:
            sys.exit(f"{symbol}: solo hay {len(closes)} días de datos, se necesitan {sma_days}.")
        sma = closes.tail(sma_days).mean()
        result[symbol] = (closes.iloc[-1] > sma, closes.iloc[-1], sma)
    return result


def plan_orders(strategy, equity, positions, trend_data, kill_switch):
    orders, rows = [], []
    for symbol, target in strategy["targets"].items():
        up, price, sma = trend_data[symbol]
        weight = target["weight"]
        if target["trend_filter"] and (not up or kill_switch):
            weight = 0.0
        target_usd = equity * weight
        current_usd = float(positions[symbol].market_value) if symbol in positions else 0.0
        diff = target_usd - current_usd

        drifted = (target_usd == 0 and current_usd > 0) or (
            target_usd > 0 and abs(diff) / target_usd > strategy["drift_tolerance"])
        action = "-"
        if drifted and abs(diff) >= strategy["min_order_usd"]:
            if target_usd == 0:
                orders.append((symbol, OrderSide.SELL, float(positions[symbol].qty), None))
                action = "vender todo"
            else:
                side = OrderSide.BUY if diff > 0 else OrderSide.SELL
                orders.append((symbol, side, None, round(abs(diff), 2)))
                action = f"{'comprar' if diff > 0 else 'vender'} ${abs(diff):,.2f}"
        rows.append((symbol, price, sma, up, target_usd, current_usd, action))
    # ventas primero para liberar efectivo
    orders.sort(key=lambda o: o[1] != OrderSide.SELL)
    return orders, rows


def run_account(account, strategy, execute, allow_live):
    name = account["name"]
    print(f"=== Cuenta: {name} ({'PAPER' if account['paper'] else 'REAL'}) ===")
    key, secret = os.environ.get(account["key_env"]), os.environ.get(account["secret_env"])
    if not key or not secret:
        print(f"Sin claves ({account['key_env']} / {account['secret_env']}); se omite.\n")
        return
    if not account["paper"] and execute and not allow_live:
        print("Cuenta REAL: se necesita --allow-live para enviar órdenes; se simula.")
        execute = False

    client = TradingClient(key, secret, paper=account["paper"])
    data = StockHistoricalDataClient(key, secret)

    if not client.get_clock().is_open and execute:
        print("El mercado está cerrado; se simula en lugar de operar.")
        execute = False
    if client.get_orders():
        print("Hay órdenes abiertas; no se opera hasta que se ejecuten.\n")
        return

    equity = float(client.get_account().equity)
    positions = {p.symbol: p for p in client.get_all_positions()}
    kill_switch = equity < account["initial_capital"] * (1 - strategy["max_drawdown"])
    trend_data = trends(data, list(strategy["targets"]), strategy["sma_days"])
    orders, rows = plan_orders(strategy, equity, positions, trend_data, kill_switch)

    pnl = equity - account["initial_capital"]
    print(f"Equity: ${equity:,.2f}  P/L: ${pnl:+,.2f} ({pnl / account['initial_capital']:+.2%})"
          f"{'  ** FRENO DE EMERGENCIA ACTIVO **' if kill_switch else ''}")
    print(f"{'Símbolo':8}{'Precio':>10}{'SMA':>10}{'Tend.':>7}"
          f"{'Objetivo':>12}{'Actual':>12}  Acción")
    for symbol, price, sma, up, target_usd, current_usd, action in rows:
        print(f"{symbol:8}{price:>10.2f}{sma:>10.2f}{'▲' if up else '▼':>7}"
              f"{target_usd:>12,.2f}{current_usd:>12,.2f}  {action}")

    if not orders:
        print("Sin cambios: la cartera está dentro de la tolerancia.\n")
        return
    if not execute:
        print("Simulación: no se enviaron órdenes.\n")
        return
    for symbol, side, qty, notional in orders:
        order = client.submit_order(MarketOrderRequest(
            symbol=symbol, side=side, qty=qty, notional=notional,
            time_in_force=TimeInForce.DAY))
        print(f"Orden enviada: {side.value} {symbol} "
              f"{qty if qty else f'${notional:,.2f}'}  estado: {order.status.value}")
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--account", help="ejecutar solo esta cuenta")
    parser.add_argument("--execute", action="store_true", help="enviar órdenes")
    parser.add_argument("--allow-live", action="store_true", help="permitir cuentas reales")
    args = parser.parse_args()

    config = load_config(args.config)
    accounts = [a for a in config["accounts"] if not args.account or a["name"] == args.account]
    if not accounts:
        sys.exit(f"No existe la cuenta '{args.account}' en la configuración.")
    print(f"Estrategia: {config['strategy']['name']}\n")
    for account in accounts:
        run_account(account, config["strategy"], args.execute, args.allow_live)


if __name__ == "__main__":
    main()
