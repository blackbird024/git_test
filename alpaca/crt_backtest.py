"""Backtest de la estrategia CRT multi-temporalidad (4H ubicación, 1H condición, 5m ejecución).

Reglas (del vídeo):
  1. 4H: la vela de 4 horas de referencia, ya cerrada, marca CRT alto y CRT bajo.
  2. 1H: el precio rompe un extremo (alcista: rompe el CRT bajo; bajista: el alto) y una
     vela de 1 hora CIERRA de vuelta dentro del rango -> condición.
  3. 5m: tras la condición, se espera un cambio de estado (CISD): una vela de 5 minutos cierra
     por encima de la apertura de la última secuencia de velas bajistas (alcista), o por debajo
     de la apertura de la última secuencia de velas alcistas (bajista). Entrada a mercado.
  4. Stop más allá del extremo de esa secuencia/movimiento. Objetivo 2R (o el extremo opuesto
     del rango en la variante "rango"). Si no se toca nada, se cierra al final de la ventana.
  Una operación por día como máximo.

Datos: QQQ (velas de 1 minuto SIP con horario extendido, desde las 4:00 NY) y BTC/ETH (24 h).
Para QQQ no hay datos de 1:00-5:00 NY, así que se usan las velas de 4H de 5:00-9:00 y 9:00-13:00.

Uso:
    python crt_backtest.py
"""

import pickle
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from alpaca_client import data_client

NY = "America/New_York"
CACHE = Path(__file__).with_name(".lab_cache")
YEARS = 2


def load_5m(symbol):
    """Velas de 5 minutos (hora de Nueva York). NQ, ES y GC vienen de Databento (futuros CME, 24 h)."""
    CACHE.mkdir(exist_ok=True)
    if symbol in ("NQ", "ES", "GC"):
        return pickle.loads((CACHE / f"dbn_{symbol}_5m.pkl").read_bytes())
    path = CACHE / f"crt_{symbol.replace('/', '')}_{datetime.now():%Y%m%d}.pkl"
    if path.exists():
        return pickle.loads(path.read_bytes())
    start = datetime.now(timezone.utc) - timedelta(days=365 * YEARS)
    end = datetime.now(timezone.utc) - timedelta(minutes=20)
    if "/" in symbol:
        req = CryptoBarsRequest(symbol_or_symbols=[symbol], timeframe=TimeFrame(5, TimeFrameUnit.Minute),
                                start=start, end=end)
        df = CryptoHistoricalDataClient().get_crypto_bars(req).df
    else:
        req = StockBarsRequest(symbol_or_symbols=[symbol], timeframe=TimeFrame(5, TimeFrameUnit.Minute),
                               start=start, end=end, feed=DataFeed.SIP)
        df = data_client().get_stock_bars(req).df
    df = df.reset_index().set_index("timestamp").sort_index()[["open", "high", "low", "close"]]
    df.index = df.index.tz_convert(NY)
    path.write_bytes(pickle.dumps(df))
    return df


def run_day(day5, crt_start, crt_hours, cond_end, entry_end, exit_time, target_mode, cost):
    """Una sesión. Horas en NY (decimales). Devuelve el resultado en R o None si no hay operación."""
    hour = day5.index.hour + day5.index.minute / 60
    crt = day5[(hour >= crt_start) & (hour < crt_start + crt_hours)]
    if len(crt) < crt_hours * 12 * 0.6:
        return None
    hi, lo = crt["high"].max(), crt["low"].min()
    after = day5[(hour >= crt_start + crt_hours) & (hour < exit_time)]
    if after.empty:
        return None

    # 1H: condición = cierre horario de vuelta dentro tras romper un extremo
    h1 = after[["open", "high", "low", "close"]].resample("1h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    ran_low = ran_high = False
    direction, cond_time = 0, None
    for t, c in h1.iterrows():
        if t.hour + t.minute / 60 >= cond_end:
            break
        ran_low |= c["low"] < lo
        ran_high |= c["high"] > hi
        if ran_low and lo < c["close"] < hi:
            direction, cond_time = 1, t + pd.Timedelta(hours=1)
            break
        if ran_high and lo < c["close"] < hi:
            direction, cond_time = -1, t + pd.Timedelta(hours=1)
            break
    if not direction:
        return None

    # 5m: CISD después de la condición
    m5 = after[after.index >= cond_time]
    o, h, l, c = (m5[k].to_numpy() for k in ("open", "high", "low", "close"))
    hours5 = m5.index.hour + m5.index.minute / 60
    seq_start = None   # inicio de la última secuencia de velas contrarias
    for i in range(len(m5)):
        if hours5[i] >= entry_end:
            return None
        against = c[i] < o[i] if direction == 1 else c[i] > o[i]
        if against:
            if seq_start is None or not (c[i - 1] < o[i - 1] if direction == 1 else c[i - 1] > o[i - 1]):
                seq_start = i
            continue
        if seq_start is None:
            continue
        level = o[seq_start]
        if (direction == 1 and c[i] > level) or (direction == -1 and c[i] < level):
            entry = c[i]
            stop = l[seq_start:i + 1].min() if direction == 1 else h[seq_start:i + 1].max()
            risk = abs(entry - stop)
            if risk <= 0:
                return None
            if target_mode == "2R":
                target = entry + direction * 2 * risk
            else:                                   # extremo opuesto del rango CRT
                target = hi if direction == 1 else lo
                if (target - entry) * direction <= 0:
                    return None
            # gestión desde la vela siguiente
            for j in range(i + 1, len(m5)):
                if (direction == 1 and l[j] <= stop) or (direction == -1 and h[j] >= stop):
                    exit_px = stop
                    break
                if (direction == 1 and h[j] >= target) or (direction == -1 and l[j] <= target):
                    exit_px = target
                    break
            else:
                exit_px = c[-1]
            gross = direction * (exit_px - entry) / risk
            return gross - 2 * cost * entry / risk     # costes expresados en R
    return None


def report(name, results):
    r = pd.Series([x for x in results if x is not None])
    if r.empty:
        print(f"  {name:48} sin operaciones")
        return
    curve = r.cumsum()
    dd = (curve - curve.cummax()).min()
    half = len(r) // 2
    pf = r[r > 0].sum() / -r[r < 0].sum() if (r < 0).any() else np.inf
    print(f"  {name:48}{len(r):>5}{(r > 0).mean():>7.0%}{r.mean():>+8.2f}{r.sum():>+8.1f}"
          f"{pf:>7.2f}{dd:>8.1f}{r.iloc[:half].sum():>+8.1f}{r.iloc[half:].sum():>+8.1f}")


def main():
    variants = [
        # nombre, símbolo, vela CRT inicio, condición hasta, entrada hasta, salida, coste por lado
        ("QQQ  vela 5:00-9:00", "QQQ", 5, 14, 15, 15.9, 0.00005),
        ("QQQ  vela 9:00-13:00", "QQQ", 9, 15, 15.5, 15.9, 0.00005),
        ("BTC  vela 1:00-5:00 (vídeo)", "BTC/USD", 1, 12, 13, 16, 0.0005),
        ("ETH  vela 1:00-5:00 (vídeo)", "ETH/USD", 1, 12, 13, 16, 0.0005),
    ]
    print(f"\n  {'Variante':48}{'Ops':>5}{'Gan.':>7}{'R med':>8}{'R tot':>8}{'F.ben':>7}{'DD (R)':>8}"
          f"{'1ª mit':>8}{'2ª mit':>8}")
    for name, symbol, start, cond_end, entry_end, exit_time, cost in variants:
        df = load_5m(symbol)
        days = [g for _, g in df.groupby(df.index.date)]
        for mode in ("2R", "rango"):
            res = [run_day(d, start, 4, cond_end, entry_end, exit_time, mode, cost) for d in days]
            report(f"{name}, objetivo {mode}", res)
    print("\n  R med = resultado medio por operación en R (veces el riesgo). DD = peor racha en R.")


if __name__ == "__main__":
    main()
