"""Backtest de estrategias intradía en cripto (Alpaca, solo compras).

Diferencias con acciones: el mercado no cierra (la "sesión" es el día UTC),
Alpaca no permite cortos en cripto y cobra comisión (~0.25% por operación
como taker), que se incluye en los resultados.

Estrategias:
  * vwap: reversión a la VWAP del día (compra bajo la banda inferior, sale en la VWAP).
  * orb:  ruptura al alza del rango de los primeros 60 minutos desde `inicio`.
Todas cierran la posición antes de terminar el día UTC.

Uso:
    python crypto_intraday.py --backtest 180 --symbols BTC/USD ETH/USD
"""

import argparse
from datetime import datetime, timedelta, timezone

import numpy as np
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

FEE = 0.0025             # comisión por lado (taker)
RISK_PER_TRADE = 0.005
MAX_POSITION_PCT = 0.25
MAX_TRADES_PER_DAY = 3
BAR_MINUTES = 5
DAY_END_MIN = 23 * 60 + 50   # cierre forzoso 23:50 UTC


def load_bars(symbols, days):
    request = CryptoBarsRequest(symbol_or_symbols=symbols,
                                timeframe=TimeFrame(BAR_MINUTES, TimeFrameUnit.Minute),
                                start=datetime.now(timezone.utc) - timedelta(days=days))
    df = CryptoHistoricalDataClient().get_crypto_bars(request).df.reset_index()
    df["day"] = df["timestamp"].dt.date
    df["minute"] = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute
    return df


def size(equity, price, risk):
    if risk <= 0:
        return 0.0
    return min(equity * RISK_PER_TRADE / risk, equity * MAX_POSITION_PCT / price)


def close_trade(qty, entry, exit_price):
    return qty * (exit_price - entry) - FEE * qty * (entry + exit_price)


def vwap_day(d, equity, entry_bands=2.0, stop_bands=1.5, warmup_min=120, last_entry_min=22 * 60):
    o, h, l, c, v, m = (d[k].to_numpy() for k in ("open", "high", "low", "close", "volume", "minute"))
    tp = (h + l + c) / 3
    v = np.maximum(v, 1e-9)
    cv, cpv, cp2v = np.cumsum(v), np.cumsum(tp * v), np.cumsum(tp * tp * v)
    trades, pos = [], None
    for i in range(1, len(d)):
        vwap = cpv[i - 1] / cv[i - 1]  # solo velas cerradas
        sd = np.sqrt(max(cp2v[i - 1] / cv[i - 1] - vwap * vwap, 0))
        prev_close = c[i - 1]
        if pos:
            qty, entry, stop = pos
            if l[i] <= stop:
                trades.append((close_trade(qty, entry, min(stop, o[i])), "stop"))
                pos = None
            elif prev_close >= vwap:
                trades.append((close_trade(qty, entry, o[i]), "vwap"))
                pos = None
            elif m[i] >= DAY_END_MIN:
                trades.append((close_trade(qty, entry, o[i]), "cierre"))
                pos = None
            continue
        if len(trades) >= MAX_TRADES_PER_DAY or m[i] < warmup_min or m[i] >= last_entry_min:
            continue
        if sd > 0 and prev_close < vwap - entry_bands * sd:
            risk = stop_bands * sd
            pos = (size(equity, o[i], risk), o[i], o[i] - risk)
    if pos:
        trades.append((close_trade(pos[0], pos[1], c[-1]), "cierre"))
    return trades


def orb_day(d, equity, start_min, range_min=60, stop="medio"):
    o, h, l, c, m = (d[k].to_numpy() for k in ("open", "high", "low", "close", "minute"))
    in_range = (m >= start_min) & (m < start_min + range_min)
    if in_range.sum() < range_min / BAR_MINUTES * 0.5:
        return []
    hi, lo = h[in_range].max(), l[in_range].min()
    stop_price = (hi + lo) / 2 if stop == "medio" else lo
    after = np.nonzero(m >= start_min + range_min)[0]
    for i in after[1:]:
        if m[i] >= DAY_END_MIN - 60:
            return []
        if c[i - 1] > hi:
            entry = o[i]
            if entry <= stop_price:
                return []
            qty = size(equity, entry, entry - stop_price)
            for j in range(i, len(d)):
                if l[j] <= stop_price:
                    return [(close_trade(qty, entry, min(stop_price, o[j])), "stop")]
                if m[j] >= DAY_END_MIN:
                    return [(close_trade(qty, entry, o[j]), "cierre")]
            return [(close_trade(qty, entry, c[-1]), "cierre")]
    return []


STRATEGIES = {
    "vwap 2.0σ":           lambda d, eq: vwap_day(d, eq),
    "vwap 3.0σ":           lambda d, eq: vwap_day(d, eq, entry_bands=3.0),
    "orb 00:00 UTC":       lambda d, eq: orb_day(d, eq, start_min=0),
    "orb 13:30 UTC (NY)":  lambda d, eq: orb_day(d, eq, start_min=13 * 60 + 30),
}


def summarize(pnls):
    curve = peak = max_dd = 0.0
    for p in pnls:
        curve += p
        peak = max(peak, curve)
        max_dd = max(max_dd, peak - curve)
    return curve, max_dd


def backtest(days, symbols, equity=100_000):
    print(f"Descargando velas de {BAR_MINUTES} minutos de {days} días...")
    df = load_bars(symbols, days)
    for symbol in symbols:
        day_frames = [d.reset_index(drop=True) for _, d in df[df["symbol"] == symbol].groupby("day")]
        half = len(day_frames) // 2
        print(f"\n{symbol}: {len(day_frames)} días (comisión {FEE:.2%} por lado incluida)")
        print(f"{'Estrategia':20}{'Ops':>6}{'Ganadas':>9}{'P/L':>11}{'DD máx':>10}"
              f"{'1ª mitad':>11}{'2ª mitad':>11}")
        for name, fn in STRATEGIES.items():
            per_day = [fn(d, equity) for d in day_frames]
            pnls = [p for t in per_day for p, _ in t]
            if not pnls:
                continue
            total, max_dd = summarize(pnls)
            first = sum(p for t in per_day[:half] for p, _ in t)
            second = sum(p for t in per_day[half:] for p, _ in t)
            wins = sum(p > 0 for p in pnls) / len(pnls)
            print(f"{name:20}{len(pnls):>6}{wins:>9.0%}{total:>11,.2f}{max_dd:>10,.2f}"
                  f"{first:>11,.2f}{second:>11,.2f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backtest", type=int, metavar="DÍAS", required=True)
    parser.add_argument("--symbols", nargs="+", default=["BTC/USD", "ETH/USD"])
    args = parser.parse_args()
    backtest(args.backtest, args.symbols)


if __name__ == "__main__":
    main()
