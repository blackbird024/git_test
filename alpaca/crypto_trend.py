"""Estrategias diarias (no intradía) para cripto en Alpaca, solo compras.

Compara en datos diarios, con comisión incluida, contra comprar y mantener:
  * sma N:      mantener mientras el cierre esté sobre la media de N días; si no, efectivo.
  * cruce a/b:  mantener mientras la media de a días esté sobre la de b días.
  * donchian:   comprar al romper el máximo de 20 días, vender al perder el mínimo de 10.
  * rotación:   cada semana, mantener la cripto con mayor retorno a 30 días si es positivo.

En vivo se usa la más consistente del backtest: BTC, ETH y SOL a partes iguales,
cada una solo mientras su cierre diario esté sobre la media de 200 días.
Opera una vez al día; solo rebalancea si una posición se desvía más de un 20%.

Uso:
    python crypto_trend.py --backtest   # compara estrategias desde 2021
    python crypto_trend.py              # simulación de hoy
    python crypto_trend.py --execute    # envía las órdenes (cuenta PAPER)
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from alpaca_client import is_paper, trading_client
from notify import notify

FEE = 0.0025
SYMBOLS = ["BTC/USD", "ETH/USD", "SOL/USD"]
ALLOCATION_USD = 10_000   # capital total para cripto, repartido a partes iguales
SMA_DAYS = 200
DRIFT_TOLERANCE = 0.20
MIN_ORDER_USD = 50


def daily_closes(symbols, start=datetime(2021, 1, 1, tzinfo=timezone.utc)):
    request = CryptoBarsRequest(symbol_or_symbols=symbols, timeframe=TimeFrame.Day, start=start)
    df = CryptoHistoricalDataClient().get_crypto_bars(request).df.reset_index()
    closes = df.pivot(index="timestamp", columns="symbol", values="close")
    closes.index = closes.index.date
    return closes.dropna()


def run(closes, exposure):
    """exposure: DataFrame 0/1 por símbolo decidido con el cierre de ayer. Devuelve curva de capital."""
    returns = closes.pct_change().fillna(0)
    held = exposure.shift(1).fillna(0)          # se opera al día siguiente de la señal
    turnover = held.diff().abs().fillna(held.abs())
    daily = (held * returns).sum(axis=1) - FEE * turnover.sum(axis=1)
    return (1 + daily).cumprod(), int((turnover.sum(axis=1) > 0).sum())


def stats(curve):
    years = len(curve) / 365
    cagr = curve.iloc[-1] ** (1 / years) - 1
    dd = (curve / curve.cummax() - 1).min()
    return curve.iloc[-1] - 1, cagr, dd


def strategies(closes):
    out = {}
    for symbol in closes:
        c = closes[[symbol]]
        name = symbol.split("/")[0]
        out[f"{name} comprar y mantener"] = pd.DataFrame(1.0, index=c.index, columns=[symbol])
        for n in (20, 50, 100, 200):
            out[f"{name} sma {n}"] = (c > c.rolling(n).mean()).astype(float)
        for a, b in ((10, 50), (20, 100), (50, 200)):
            out[f"{name} cruce {a}/{b}"] = (c.rolling(a).mean() > c.rolling(b).mean()).astype(float)
        hi20, lo10 = c.rolling(20).max().shift(1), c.rolling(10).min().shift(1)
        state, pos = [], 0.0
        for price, h, l in zip(c[symbol], hi20[symbol], lo10[symbol]):
            if not np.isnan(h) and price > h:
                pos = 1.0
            elif not np.isnan(l) and price < l:
                pos = 0.0
            state.append(pos)
        out[f"{name} donchian 20/10"] = pd.DataFrame(state, index=c.index, columns=[symbol])

    # rotación semanal entre todas
    mom = closes.pct_change(30)
    weekly = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    current = None
    for i, day in enumerate(closes.index):
        if i % 7 == 0 and not mom.loc[day].isna().any():
            best = mom.loc[day].idxmax()
            current = best if mom.loc[day, best] > 0 else None
        if current:
            weekly.loc[day, current] = 1.0
    out["rotación 30d semanal"] = weekly
    return out


def backtest():
    closes = daily_closes(SYMBOLS)
    half = closes.index[len(closes) // 2]
    print(f"Datos diarios: {closes.index[0]} a {closes.index[-1]} ({len(closes)} días). "
          f"Comisión {FEE:.2%} por lado.\n")
    print(f"{'Estrategia':26}{'Total':>10}{'Anual':>9}{'DD máx':>9}{'Ops':>6}"
          f"{'1ª mitad':>10}{'2ª mitad':>10}")
    rows = []
    for name, exposure in strategies(closes).items():
        cols = exposure.columns
        curve, trades = run(closes[cols], exposure)
        total, cagr, dd = stats(curve)
        first = curve.loc[:half].iloc[-1] - 1
        second = curve.iloc[-1] / curve.loc[:half].iloc[-1] - 1
        rows.append((name, total, cagr, dd, trades, first, second))
    for name, total, cagr, dd, trades, first, second in rows:
        print(f"{name:26}{total:>10.0%}{cagr:>9.0%}{dd:>9.0%}{trades:>6}{first:>10.0%}{second:>10.0%}")


def run_live(execute):
    if not is_paper():
        sys.exit("Esta estrategia solo corre en la cuenta PAPER.")
    client = trading_client()
    closes = daily_closes(SYMBOLS, start=datetime.now(timezone.utc) - timedelta(days=SMA_DAYS * 2))
    today = datetime.now(timezone.utc).date()
    closes = closes[closes.index < today]  # solo días completos
    positions = {p.symbol: p for p in client.get_all_positions()}
    per_symbol = ALLOCATION_USD / len(SYMBOLS)

    print(f"Cripto tendencia (SMA {SMA_DAYS}), ${ALLOCATION_USD:,.0f} en total, "
          f"cierres hasta {closes.index[-1]}\n")
    print(f"{'Símbolo':9}{'Cierre':>12}{'SMA':>12}{'Tend.':>7}{'Objetivo':>11}{'Actual':>11}  Acción")
    orders = []
    for symbol in SYMBOLS:
        close = closes[symbol].iloc[-1]
        sma = closes[symbol].tail(SMA_DAYS).mean()
        up = close > sma
        target = per_symbol if up else 0.0
        pos = positions.get(symbol.replace("/", ""))
        current = float(pos.market_value) if pos else 0.0
        diff = target - current
        drifted = (target == 0 and current > 0) or (target > 0 and abs(diff) / target > DRIFT_TOLERANCE)
        action = "-"
        if drifted and abs(diff) >= MIN_ORDER_USD:
            if target == 0:
                orders.append((symbol, OrderSide.SELL, float(pos.qty), None))
                action = "vender todo"
            else:
                side = OrderSide.BUY if diff > 0 else OrderSide.SELL
                orders.append((symbol, side, None, round(abs(diff), 2)))
                action = f"{'comprar' if diff > 0 else 'vender'} ${abs(diff):,.2f}"
        print(f"{symbol:9}{close:>12,.2f}{sma:>12,.2f}{'▲' if up else '▼':>7}"
              f"{target:>11,.2f}{current:>11,.2f}  {action}")

    if not orders:
        print("\nSin cambios.")
        return
    if not execute:
        print("\nSimulación: usa --execute para enviar las órdenes.")
        return
    orders.sort(key=lambda o: o[1] != OrderSide.SELL)
    print()
    for symbol, side, qty, notional in orders:
        order = client.submit_order(MarketOrderRequest(
            symbol=symbol, side=side, qty=qty, notional=notional, time_in_force=TimeInForce.GTC))
        message = (f"Orden enviada: {side.value} {symbol} "
                   f"{qty if qty else f'${notional:,.2f}'}  estado: {order.status.value}")
        print(message)
        notify(f"[cripto] {message}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.backtest:
        backtest()
    else:
        run_live(args.execute)


if __name__ == "__main__":
    main()
