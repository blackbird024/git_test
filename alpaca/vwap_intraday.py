"""Estrategia intradía de reversión a la VWAP para Alpaca (cuenta PAPER).

Misma lógica que el EA de MT5 (mt5/VwapReversion.mq5):
  * Calcula la VWAP de la sesión y su desviación estándar con velas de 1 minuto.
  * Compra si una vela cierra entry_bands desviaciones por debajo de la VWAP;
    vende en corto si cierra entry_bands por encima.
  * Sale al volver a la VWAP, en el stop-loss (stop_bands desviaciones más
    allá de la entrada) o a la hora de cierre forzoso. Nada queda abierto
    de un día para otro.
  * Riesgo por operación, máximo de operaciones al día y pérdida diaria máxima.

Usa QQQM (Nasdaq-100) e IAU (oro) para no mezclarse con las posiciones de
largo plazo de auto_strategy.py, que usa QQQ y GLD.

Uso:
    python vwap_intraday.py --backtest 90   # prueba con los últimos 90 días
    python vwap_intraday.py --live          # opera hasta el cierre del mercado
    python vwap_intraday.py --backtest 90 --symbols QQQ GLD
"""

import argparse
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import time as dtime
from zoneinfo import ZoneInfo

from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest, StopLossRequest
from alpaca.trading.enums import QueryOrderStatus

from alpaca_client import data_client, is_paper, trading_client

NY = ZoneInfo("America/New_York")
SYMBOLS = ["QQQM", "IAU"]
SESSION_OPEN = dtime(9, 30)
WARMUP_MINUTES = 30
LAST_ENTRY = dtime(15, 0)
CLOSE_ALL = dtime(15, 50)
ENTRY_BANDS = 2.0
STOP_BANDS = 1.5
RISK_PER_TRADE = 0.005      # 0.5% del equity
MAX_POSITION_PCT = 0.25     # tope de exposición por símbolo
MAX_TRADES_PER_DAY = 3      # por símbolo
MAX_DAILY_LOSS = 0.02       # 2% del equity al inicio del día


@dataclass
class Signal:
    vwap: float
    sd: float
    close: float


def session_signal(day_bars):
    """VWAP y desviación con las velas cerradas de la sesión (DataFrame de un día)."""
    tp = (day_bars["high"] + day_bars["low"] + day_bars["close"]) / 3
    vol = day_bars["volume"].clip(lower=1)
    vwap = (tp * vol).sum() / vol.sum()
    variance = (tp * tp * vol).sum() / vol.sum() - vwap * vwap
    sd = math.sqrt(variance) if variance > 0 else 0.0
    return Signal(vwap, sd, float(day_bars["close"].iloc[-1]))


def entry_side(sig):
    if sig.sd <= 0:
        return None
    if sig.close < sig.vwap - ENTRY_BANDS * sig.sd:
        return OrderSide.BUY
    if sig.close > sig.vwap + ENTRY_BANDS * sig.sd:
        return OrderSide.SELL
    return None


def position_size(equity, price, stop_distance):
    if stop_distance <= 0:
        return 0
    by_risk = equity * RISK_PER_TRADE / stop_distance
    by_cap = equity * MAX_POSITION_PCT / price
    return int(min(by_risk, by_cap))


def minute_bars(symbols, start, end=None):
    request = StockBarsRequest(symbol_or_symbols=symbols, timeframe=TimeFrame.Minute,
                               start=start, end=end, feed=DataFeed.IEX)
    df = data_client().get_stock_bars(request).df
    df = df.reset_index()
    df["ts"] = df["timestamp"].dt.tz_convert(NY)
    df = df[(df["ts"].dt.time >= SESSION_OPEN) & (df["ts"].dt.time < dtime(16, 0))]
    df["day"] = df["ts"].dt.date
    return df


# ---------------------------------------------------------------- backtest

def backtest(days, symbols, equity=100_000):
    start = datetime.now(NY) - timedelta(days=days)
    print(f"Descargando velas de 1 minuto desde {start:%Y-%m-%d}...")
    df = minute_bars(symbols, start)
    trades = []
    for symbol in symbols:
        sdf = df[df["symbol"] == symbol]
        for day, day_df in sdf.groupby("day"):
            trades.extend(backtest_day(symbol, day_df.reset_index(drop=True), equity))

    if not trades:
        print("Sin operaciones en el periodo.")
        return
    print(f"\n{'Símbolo':8}{'Ops':>6}{'Ganadas':>9}{'P/L':>12}{'P/L medio':>12}")
    for symbol in symbols:
        st = [t for t in trades if t["symbol"] == symbol]
        if st:
            pnl = sum(t["pnl"] for t in st)
            wins = sum(t["pnl"] > 0 for t in st)
            print(f"{symbol:8}{len(st):>6}{wins / len(st):>9.0%}{pnl:>12,.2f}{pnl / len(st):>12,.2f}")

    trades.sort(key=lambda t: t["exit_time"])
    curve, peak, max_dd = 0.0, 0.0, 0.0
    for t in trades:
        curve += t["pnl"]
        peak = max(peak, curve)
        max_dd = max(max_dd, peak - curve)
    reasons = {}
    for t in trades:
        reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    print(f"\nTotal: {len(trades)} operaciones, P/L ${curve:,.2f} "
          f"({curve / equity:+.2%} sobre ${equity:,.0f}), drawdown máximo ${max_dd:,.2f}")
    print("Salidas: " + ", ".join(f"{k}: {v}" for k, v in reasons.items()))


def backtest_day(symbol, bars, equity):
    trades, position = [], None
    warmup_end = (datetime.combine(bars["day"][0], SESSION_OPEN) + timedelta(minutes=WARMUP_MINUTES)).time()
    for i in range(1, len(bars)):
        bar = bars.iloc[i]
        t = bar["ts"].time()
        sig = session_signal(bars.iloc[:i])  # solo velas cerradas antes de esta

        if position:
            side, qty, entry, stop, entry_time = position
            exit_price, reason = None, None
            # stop dentro de esta vela
            if side == OrderSide.BUY and bar["low"] <= stop:
                exit_price, reason = min(stop, bar["open"]), "stop"
            elif side == OrderSide.SELL and bar["high"] >= stop:
                exit_price, reason = max(stop, bar["open"]), "stop"
            # la vela anterior cerró en la VWAP: salir a la apertura de esta
            elif (side == OrderSide.BUY and sig.close >= sig.vwap) or \
                 (side == OrderSide.SELL and sig.close <= sig.vwap):
                exit_price, reason = bar["open"], "vwap"
            elif t >= CLOSE_ALL:
                exit_price, reason = bar["open"], "cierre"
            if exit_price is not None:
                direction = 1 if side == OrderSide.BUY else -1
                trades.append({"symbol": symbol, "pnl": direction * qty * (exit_price - entry),
                               "reason": reason, "exit_time": bar["ts"]})
                position = None
            continue

        if len(trades) >= MAX_TRADES_PER_DAY or t < warmup_end or t >= LAST_ENTRY:
            continue
        if sum(tr["pnl"] for tr in trades) <= -equity * MAX_DAILY_LOSS:
            continue
        side = entry_side(sig)
        if side:
            entry = bar["open"]
            stop_distance = STOP_BANDS * sig.sd
            qty = position_size(equity, entry, stop_distance)
            if qty > 0:
                stop = entry - stop_distance if side == OrderSide.BUY else entry + stop_distance
                position = (side, qty, entry, stop, bar["ts"])

    if position:  # sin datos al final: cerrar al último precio
        side, qty, entry, _, _ = position
        direction = 1 if side == OrderSide.BUY else -1
        last = bars.iloc[-1]
        trades.append({"symbol": symbol, "pnl": direction * qty * (last["close"] - entry),
                       "reason": "cierre", "exit_time": last["ts"]})
    return trades


# ---------------------------------------------------------------- en vivo

def close_symbol(client, symbol):
    open_orders = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol]))
    for order in open_orders:
        client.cancel_order_by_id(order.id)
    client.close_position(symbol)


def live(symbols):
    if not is_paper():
        sys.exit("La estrategia intradía solo corre en la cuenta PAPER.")
    client = trading_client()
    start_equity = float(client.get_account().equity)
    trades_today = {s: 0 for s in symbols}
    print(f"Inicio: equity ${start_equity:,.2f}. Símbolos: {', '.join(symbols)}")

    while True:
        now = datetime.now(NY)
        if not client.get_clock().is_open or now.time() >= CLOSE_ALL:
            for p in client.get_all_positions():
                if p.symbol in symbols:
                    close_symbol(client, p.symbol)
                    print(f"{now:%H:%M} cierre forzoso de {p.symbol}")
            break

        today_open = datetime.combine(now.date(), SESSION_OPEN, NY)
        bars = minute_bars(symbols, today_open)
        current_minute = now.replace(second=0, microsecond=0)
        equity = float(client.get_account().equity)
        loss_limit_hit = equity - start_equity <= -start_equity * MAX_DAILY_LOSS
        positions = {p.symbol: p for p in client.get_all_positions()}

        for symbol in symbols:
            sbars = bars[(bars["symbol"] == symbol) & (bars["ts"] < current_minute)]
            if len(sbars) < 2:
                continue
            sig = session_signal(sbars)
            pos = positions.get(symbol)
            if pos:
                is_long = float(pos.qty) > 0
                if loss_limit_hit or (is_long and sig.close >= sig.vwap) or \
                        (not is_long and sig.close <= sig.vwap):
                    close_symbol(client, symbol)
                    print(f"{now:%H:%M} {symbol}: salida (VWAP {sig.vwap:.2f}, "
                          f"P/L ${float(pos.unrealized_pl):,.2f})")
                continue

            warmup_end = today_open + timedelta(minutes=WARMUP_MINUTES)
            if loss_limit_hit or trades_today[symbol] >= MAX_TRADES_PER_DAY or \
                    now < warmup_end or now.time() >= LAST_ENTRY:
                continue
            side = entry_side(sig)
            if not side:
                continue
            stop_distance = STOP_BANDS * sig.sd
            qty = position_size(equity, sig.close, stop_distance)
            if qty <= 0:
                continue
            stop = sig.close - stop_distance if side == OrderSide.BUY else sig.close + stop_distance
            client.submit_order(MarketOrderRequest(
                symbol=symbol, qty=qty, side=side, time_in_force=TimeInForce.DAY,
                order_class=OrderClass.OTO, stop_loss=StopLossRequest(stop_price=round(stop, 2))))
            trades_today[symbol] += 1
            print(f"{now:%H:%M} {symbol}: {side.value} {qty} @ ~{sig.close:.2f} "
                  f"(VWAP {sig.vwap:.2f}, stop {stop:.2f})")

        time.sleep(60 - datetime.now().second + 2)

    pnl = float(client.get_account().equity) - start_equity
    print(f"Fin del día. Resultado de la cuenta: ${pnl:+,.2f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backtest", type=int, metavar="DÍAS")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--symbols", nargs="+", default=SYMBOLS)
    args = parser.parse_args()
    symbols = [s.upper() for s in args.symbols]
    if args.backtest:
        backtest(args.backtest, symbols)
    else:
        live(symbols)


if __name__ == "__main__":
    main()
