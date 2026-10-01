"""Ruptura del rango de apertura (Opening Range Breakout) intradía.

Estrategia de seguimiento de tendencia, pensada para instrumentos que tienden
a seguir su movimiento (como el oro) en lugar de volver a la media:
  * Marca el máximo y el mínimo de los primeros `range_minutes` de la sesión.
  * Compra si una vela cierra por encima del máximo; vende en corto si cierra
    por debajo del mínimo. Una operación por día.
  * Stop-loss en el lado opuesto del rango (o en su punto medio).
  * Objetivo en `target_r` veces el riesgo, o mantener hasta el cierre forzoso.

Uso:
    python orb_intraday.py --backtest 180 --symbols GLD   # compara variantes
    python orb_intraday.py --live                         # opera GLD hasta el cierre
"""

import argparse
import sys
import time
from datetime import datetime, timedelta

from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest

from alpaca_client import is_paper, trading_client
from vwap_intraday import (CLOSE_ALL, LAST_ENTRY, NY, SESSION_OPEN, close_symbol, entries_today,
                           intraday_pnl, minute_bars, position_size)

# variante que opera en vivo: fue positiva en las dos mitades del backtest de 180 días
LIVE_SYMBOL = "GLD"
LIVE_RANGE_MINUTES = 60

# (minutos de rango, stop, objetivo en R; None = mantener hasta el cierre)
VARIANTS = [
    (15, "opuesto", 2.0), (15, "medio", 2.0), (15, "medio", None),
    (30, "opuesto", 2.0), (30, "medio", 2.0), (30, "medio", None),
    (60, "opuesto", 2.0), (60, "medio", 2.0), (60, "medio", None),
]


def backtest_day(bars, range_minutes, stop_mode, target_r, equity):
    range_end = (datetime.combine(bars["day"].iloc[0], SESSION_OPEN)
                 + timedelta(minutes=range_minutes)).time()
    times = bars["ts"].dt.time
    opening = bars[times < range_end]
    rest = bars[times >= range_end].reset_index(drop=True)
    if len(opening) < range_minutes * 0.5 or len(rest) < 2:
        return None
    hi, lo = opening["high"].max(), opening["low"].min()
    mid = (hi + lo) / 2

    for i in range(1, len(rest)):
        prev, bar = rest.iloc[i - 1], rest.iloc[i]
        if bar["ts"].time() >= LAST_ENTRY:
            return None
        if prev["close"] > hi:
            direction, stop = 1, (lo if stop_mode == "opuesto" else mid)
        elif prev["close"] < lo:
            direction, stop = -1, (hi if stop_mode == "opuesto" else mid)
        else:
            continue
        entry = bar["open"]
        risk = abs(entry - stop)
        if risk <= 0 or (entry - stop) * direction <= 0:
            return None
        qty = position_size(equity, entry, risk)
        target = entry + direction * target_r * risk if target_r else None
        return simulate_exit(rest.iloc[i:], direction, qty, entry, stop, target)
    return None


def simulate_exit(bars, direction, qty, entry, stop, target):
    for _, bar in bars.iterrows():
        if bar["ts"].time() >= CLOSE_ALL:
            return direction * qty * (bar["open"] - entry), "cierre"
        # el stop se evalúa antes que el objetivo: supuesto conservador
        if (direction == 1 and bar["low"] <= stop) or (direction == -1 and bar["high"] >= stop):
            fill = min(stop, bar["open"]) if direction == 1 else max(stop, bar["open"])
            return direction * qty * (fill - entry), "stop"
        if target and ((direction == 1 and bar["high"] >= target) or
                       (direction == -1 and bar["low"] <= target)):
            return direction * qty * (target - entry), "objetivo"
    last = bars.iloc[-1]
    return direction * qty * (last["close"] - entry), "cierre"


def backtest(days, symbols, equity=100_000):
    start = datetime.now(NY) - timedelta(days=days)
    print(f"Descargando velas de 1 minuto desde {start:%Y-%m-%d}...")
    df = minute_bars(symbols, start)
    for symbol in symbols:
        sdf = df[df["symbol"] == symbol]
        days_list = [d.reset_index(drop=True) for _, d in sdf.groupby("day")]
        print(f"\n{symbol}: {len(days_list)} sesiones")
        print(f"{'Rango':>6} {'Stop':>8} {'Objetivo':>9}{'Ops':>6}{'Ganadas':>9}"
              f"{'P/L':>11}{'DD máx':>10}")
        for range_minutes, stop_mode, target_r in VARIANTS:
            results = [r for r in (backtest_day(d, range_minutes, stop_mode, target_r, equity)
                                   for d in days_list) if r]
            if not results:
                continue
            pnls = [r[0] for r in results]
            curve = peak = max_dd = 0.0
            for p in pnls:
                curve += p
                peak = max(peak, curve)
                max_dd = max(max_dd, peak - curve)
            wins = sum(p > 0 for p in pnls) / len(pnls)
            target_label = f"{target_r}R" if target_r else "cierre"
            print(f"{range_minutes:>5}m {stop_mode:>8} {target_label:>9}{len(pnls):>6}"
                  f"{wins:>9.0%}{sum(pnls):>11,.2f}{max_dd:>10,.2f}")


def live(symbol=LIVE_SYMBOL, range_minutes=LIVE_RANGE_MINUTES):
    if not is_paper():
        sys.exit("La estrategia intradía solo corre en la cuenta PAPER.")
    client = trading_client()
    print(f"ORB en vivo: {symbol}, rango de {range_minutes} min, stop en el medio, "
          f"salida a las {CLOSE_ALL:%H:%M}", flush=True)
    announced = False

    while True:
        now = datetime.now(NY)
        today_open = datetime.combine(now.date(), SESSION_OPEN, NY)
        positions = {p.symbol: p for p in client.get_all_positions()}

        if not client.get_clock().is_open or now.time() >= CLOSE_ALL:
            if symbol in positions:
                close_symbol(client, symbol)
                print(f"{now:%H:%M} cierre forzoso de {symbol}", flush=True)
            break

        range_end = today_open + timedelta(minutes=range_minutes)
        if now >= range_end and symbol not in positions and \
                entries_today(client, symbol, today_open) == 0 and now.time() < LAST_ENTRY:
            bars = minute_bars([symbol], today_open)
            current_minute = now.replace(second=0, microsecond=0)
            opening = bars[bars["ts"] < range_end]
            closed = bars[(bars["ts"] >= range_end) & (bars["ts"] < current_minute)]
            if len(opening) >= range_minutes * 0.5 and len(closed):
                hi, lo = opening["high"].max(), opening["low"].min()
                mid = (hi + lo) / 2
                if not announced:
                    print(f"{now:%H:%M} rango: {lo:.2f} - {hi:.2f} (stop en {mid:.2f})", flush=True)
                    announced = True
                last = float(closed["close"].iloc[-1])
                side = OrderSide.BUY if last > hi else OrderSide.SELL if last < lo else None
                if side:
                    equity = float(client.get_account().equity)
                    qty = position_size(equity, last, abs(last - mid))
                    if qty > 0:
                        client.submit_order(MarketOrderRequest(
                            symbol=symbol, qty=qty, side=side, time_in_force=TimeInForce.DAY,
                            order_class=OrderClass.OTO,
                            stop_loss=StopLossRequest(stop_price=round(mid, 2))))
                        print(f"{now:%H:%M} {symbol}: {side.value} {qty} @ ~{last:.2f} "
                              f"(stop {mid:.2f})", flush=True)

        if now.minute % 15 == 0:
            pnl = intraday_pnl(client, [symbol], today_open)
            print(f"{now:%H:%M} sigue activo. P/L intradía {symbol}: ${pnl:+,.2f}", flush=True)
        time.sleep(60 - datetime.now().second + 2)

    today_open = datetime.combine(datetime.now(NY).date(), SESSION_OPEN, NY)
    print(f"Fin del día. Resultado {symbol}: ${intraday_pnl(client, [symbol], today_open):+,.2f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backtest", type=int, metavar="DÍAS")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--symbols", nargs="+", default=["GLD"])
    args = parser.parse_args()
    if args.live:
        live()
    else:
        backtest(args.backtest, [s.upper() for s in args.symbols])


if __name__ == "__main__":
    main()
