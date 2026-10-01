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
"""

import argparse
from datetime import datetime, timedelta

from vwap_intraday import CLOSE_ALL, LAST_ENTRY, NY, SESSION_OPEN, minute_bars, position_size

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


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backtest", type=int, metavar="DÍAS", required=True)
    parser.add_argument("--symbols", nargs="+", default=["GLD"])
    args = parser.parse_args()
    backtest(args.backtest, [s.upper() for s in args.symbols])


if __name__ == "__main__":
    main()
