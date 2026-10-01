"""Laboratorio de estrategias: compara muchas estrategias con los mismos datos y métricas.

Todas operan con 1x de exposición (100% del capital por operación), así los
resultados se pueden escalar: con 2x de apalancamiento, retorno y caídas se
duplican. Incluye un coste de COST por lado (spread + deslizamiento).

Métricas pensadas para cuentas de fondeo (prop firms):
  * Peor día: la mayor pérdida en un solo día (límite de pérdida diaria).
  * DD máx:   la mayor caída desde un máximo (límite de pérdida total).

Datos: velas de 1 minuto SIP (mercado completo) de los últimos 2 años para
las intradía, y velas diarias desde 2016 para las de varios días.

Uso:
    python strategy_lab.py                       # QQQ y GLD
    python strategy_lab.py --symbols QQQ SPY GLD
"""

import argparse
import pickle
from datetime import datetime, timedelta
from datetime import time as dtime
from pathlib import Path

import numpy as np
import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from alpaca_client import data_client
from vwap_intraday import NY

COST = 0.0002          # 0.02% por lado
INTRADAY_YEARS = 2
DAILY_START = datetime(2016, 1, 1)
CACHE = Path(__file__).with_name(".lab_cache")


# ---------------------------------------------------------------- datos

def _fetch(symbols, timeframe, start):
    end = datetime.now(NY) - timedelta(minutes=20)  # el plan gratuito no da SIP de los últimos 15 min
    request = StockBarsRequest(symbol_or_symbols=symbols, timeframe=timeframe,
                               start=start, end=end, feed=DataFeed.SIP)
    return data_client().get_stock_bars(request).df.reset_index()


def load(symbol, kind):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"{symbol}_{kind}_{datetime.now(NY):%Y%m%d}.pkl"
    if path.exists():
        df = pickle.loads(path.read_bytes())
    elif kind == "minute":
        df = _fetch([symbol], TimeFrame.Minute, datetime.now(NY) - timedelta(days=365 * INTRADAY_YEARS))
        df["ts"] = df["timestamp"].dt.tz_convert(NY)
        df = df[(df["ts"].dt.time >= dtime(9, 30)) & (df["ts"].dt.time < dtime(16, 0))]
        df["day"] = df["ts"].dt.date
        df["minute"] = (df["ts"].dt.hour - 9) * 60 + df["ts"].dt.minute - 30  # 0 = 9:30
        path.write_bytes(pickle.dumps(df))
    else:
        df = _fetch([symbol], TimeFrame.Day, DAILY_START)
        df["day"] = df["timestamp"].dt.tz_convert(NY).dt.date
        df = df.set_index("day")[["open", "high", "low", "close"]]
        path.write_bytes(pickle.dumps(df))

    if kind != "minute":
        return df
    days = [Day(d) for _, d in df.groupby("day") if len(d) >= 300]
    for prev, cur in zip(days, days[1:]):
        cur.prev_close = prev.c[-1]
    return days[1:]


class Day:
    """Velas de 1 minuto de una sesión como arrays de numpy."""

    def __init__(self, d):
        self.date = d["day"].iloc[0]
        self.m = d["minute"].to_numpy()
        self.o, self.h, self.l, self.c = (d[k].to_numpy() for k in ("open", "high", "low", "close"))
        tp = (self.h + self.l + self.c) / 3
        v = np.maximum(d["volume"].to_numpy(), 1)
        cv = np.cumsum(v)
        self.vwap = np.cumsum(tp * v) / cv
        self.vsd = np.sqrt(np.maximum(np.cumsum(tp * tp * v) / cv - self.vwap ** 2, 0))
        self.prev_close = None

    def idx(self, minute):
        """Índice de la primera vela en o después de `minute` (minutos desde las 9:30)."""
        i = np.searchsorted(self.m, minute)
        return min(i, len(self.m) - 1)


def trade(direction, entry, exit_price):
    """Retorno de una operación con 1x de exposición, con costes."""
    return direction * (exit_price / entry - 1) - 2 * COST


def run_with_stop(day, start, direction, entry, stop, end_minute=380, target=None, exit_fn=None):
    """Sigue la posición vela a vela desde `start`: stop, objetivo, salida opcional o cierre."""
    end = day.idx(end_minute)
    for i in range(start, end):
        if direction == 1 and day.l[i] <= stop:
            return trade(1, entry, min(stop, day.o[i]))
        if direction == -1 and day.h[i] >= stop:
            return trade(-1, entry, max(stop, day.o[i]))
        if target is not None and ((direction == 1 and day.h[i] >= target) or
                                   (direction == -1 and day.l[i] <= target)):
            return trade(direction, entry, target)
        if exit_fn and i + 1 < len(day.o) and exit_fn(i):
            return trade(direction, entry, day.o[i + 1])
    return trade(direction, entry, day.o[end] if end < len(day.o) else day.c[-1])


# ---------------------------------------------------------------- intradía
# Cada función recibe (días, índice del día) y devuelve la lista de retornos de ese día.

def vwap_reversion(days, k):
    """Reversión a la VWAP (la del EA de MT5): entra a 2σ, sale en la VWAP, stop 1.5σ más allá."""
    day, out = days[k], []
    i = day.idx(30)
    while i < day.idx(330) and len(out) < 3:
        vw, sd, close = day.vwap[i - 1], day.vsd[i - 1], day.c[i - 1]
        direction = 1 if close < vw - 2 * sd else -1 if close > vw + 2 * sd else 0
        if direction == 0 or sd <= 0:
            i += 1
            continue
        entry = day.o[i]
        stop = entry - direction * 1.5 * sd
        j, result = i, None
        while j < day.idx(380):
            if (direction == 1 and day.l[j] <= stop) or (direction == -1 and day.h[j] >= stop):
                fill = min(stop, day.o[j]) if direction == 1 else max(stop, day.o[j])
                result = trade(direction, entry, fill)
                break
            if j > i and ((direction == 1 and day.c[j - 1] >= day.vwap[j - 1]) or
                          (direction == -1 and day.c[j - 1] <= day.vwap[j - 1])):
                result = trade(direction, entry, day.o[j])
                break
            j += 1
        if result is None:
            result = trade(direction, entry, day.o[min(j, len(day.o) - 1)])
        out.append(result)
        i = j + 1
    return out


def opening_range_breakout(minutes):
    """Ruptura del rango de los primeros `minutes` minutos; stop en el medio; sale al cierre."""
    def strategy(days, k):
        day = days[k]
        end = day.idx(minutes)
        hi, lo = day.h[:end].max(), day.l[:end].min()
        mid = (hi + lo) / 2
        for i in range(end + 1, day.idx(330)):
            direction = 1 if day.c[i - 1] > hi else -1 if day.c[i - 1] < lo else 0
            if direction:
                entry = day.o[i]
                if (entry - mid) * direction <= 0:
                    return []
                return [run_with_stop(day, i, direction, entry, mid)]
        return []
    return strategy


def noise_breakout(days, k, lookback=14):
    """'Beat the Market' (Zarattini, Aziz y Barbon, 2024): bandas de ruido según la hora del día.

    La banda es el movimiento medio desde la apertura a cada hora en los últimos 14 días.
    Se revisa cada 30 minutos: si el precio sale de la banda, se entra en esa dirección;
    stop dinámico en la banda o la VWAP; todo se cierra al final del día.
    """
    if k < lookback:
        return []
    day = days[k]
    checkpoints = range(30, 390, 30)
    sigma = {}
    for cp in checkpoints:
        moves = []
        for past in days[k - lookback:k]:
            j = past.idx(cp)
            moves.append(abs(past.c[j] / past.o[0] - 1))
        sigma[cp] = np.mean(moves)
    upper_ref = max(day.o[0], day.prev_close)
    lower_ref = min(day.o[0], day.prev_close)

    position, entry, out = 0, 0.0, []
    for cp in checkpoints:
        i = day.idx(cp)
        if i >= len(day.c) - 1:
            break
        price = day.c[i - 1]
        upper, lower = upper_ref * (1 + sigma[cp]), lower_ref * (1 - sigma[cp])
        # salida con stop dinámico
        if position == 1 and price < max(upper, day.vwap[i - 1]):
            out.append(trade(1, entry, day.o[i]))
            position = 0
        elif position == -1 and price > min(lower, day.vwap[i - 1]):
            out.append(trade(-1, entry, day.o[i]))
            position = 0
        if position == 0:
            if price > upper:
                position, entry = 1, day.o[i]
            elif price < lower:
                position, entry = -1, day.o[i]
    if position:
        out.append(trade(position, entry, day.c[-1]))
    return out


def gap_fade(days, k):
    """Cierre del hueco: si abre entre 0.3% y 1.5% lejos del cierre anterior, apuesta a que vuelve.

    Objetivo en el cierre anterior, stop a 1x el tamaño del hueco más allá, salida a las 12:00.
    """
    day = days[k]
    gap = day.o[0] / day.prev_close - 1
    if not 0.003 <= abs(gap) <= 0.015:
        return []
    direction = -1 if gap > 0 else 1
    i = day.idx(5)
    entry = day.o[i]
    stop = entry * (1 - direction * abs(gap))
    return [run_with_stop(day, i, direction, entry, stop, end_minute=150, target=day.prev_close)]


def gap_and_go(days, k):
    """Continuación del hueco: si abre >0.3% lejos y los primeros 15 min siguen esa dirección."""
    day = days[k]
    gap = day.o[0] / day.prev_close - 1
    if abs(gap) < 0.003:
        return []
    direction = 1 if gap > 0 else -1
    i = day.idx(15)
    if (day.c[i - 1] - day.o[0]) * direction <= 0:
        return []
    entry = day.o[i]
    stop = day.l[:i].min() if direction == 1 else day.h[:i].max()
    return [run_with_stop(day, i, direction, entry, stop)]


def late_momentum(days, k):
    """Momentum de la última media hora (Gao, Han, Li y Zhou, 2018).

    Si el mercado sube desde el cierre anterior hasta las 15:30, compra para la última media hora;
    si baja, vende en corto.
    """
    day = days[k]
    i = day.idx(360)
    ret = day.c[i - 1] / day.prev_close - 1
    if abs(ret) < 0.001:
        return []
    direction = 1 if ret > 0 else -1
    return [trade(direction, day.o[i], day.c[-1])]


def vwap_trend_pullback(days, k):
    """Seguimiento de tendencia: tras la primera hora, si el precio está del lado de una VWAP
    con pendiente a favor, entra cuando retrocede a tocar la VWAP. Stop a 1σ, sale al cierre."""
    day = days[k]
    for i in range(day.idx(60), day.idx(330)):
        vw, sd = day.vwap[i - 1], day.vsd[i - 1]
        slope = vw - day.vwap[max(i - 31, 0)]
        if sd <= 0:
            continue
        if slope > 0 and day.l[i - 1] <= vw < day.c[i - 1]:
            return [run_with_stop(day, i, 1, day.o[i], vw - sd)]
        if slope < 0 and day.h[i - 1] >= vw > day.c[i - 1]:
            return [run_with_stop(day, i, -1, day.o[i], vw + sd)]
    return []


INTRADAY = {
    "VWAP reversión (EA)": vwap_reversion,
    "Ruptura rango 30m": opening_range_breakout(30),
    "Ruptura rango 60m": opening_range_breakout(60),
    "Bandas de ruido": noise_breakout,
    "Cierre de hueco": gap_fade,
    "Continuación hueco": gap_and_go,
    "Momentum 15:30": late_momentum,
    "Retroceso a VWAP": vwap_trend_pullback,
}


# ---------------------------------------------------------------- varios días
# Cada función recibe el DataFrame diario y devuelve retornos diarios (Serie) con 1x.

def rsi(series, n):
    delta = series.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / down)


def from_positions(df, position, entry="close"):
    """Retorno diario de mantener `position` (decidida al cierre) durante el día siguiente."""
    ret = df["close"].pct_change().fillna(0)
    held = position.shift(1).fillna(0)
    costs = held.diff().abs().fillna(held.abs()) * COST
    return held * ret - costs


def buy_and_hold(df):
    return from_positions(df, pd.Series(1.0, index=df.index))


def trend_sma200(df):
    return from_positions(df, (df["close"] > df["close"].rolling(200).mean()).astype(float))


def rsi2(df):
    """RSI(2) de Connors: compra con RSI(2) < 10 en tendencia alcista; vende al cerrar sobre la media de 5."""
    c = df["close"]
    r2, sma200, sma5 = rsi(c, 2), c.rolling(200).mean(), c.rolling(5).mean()
    pos, state = [], 0.0
    for price, r, s200, s5 in zip(c, r2, sma200, sma5):
        if state == 0 and r < 10 and price > s200:
            state = 1.0
        elif state == 1 and price > s5:
            state = 0.0
        pos.append(state)
    return from_positions(df, pd.Series(pos, index=df.index))


def ibs(df):
    """Fuerza de la vela (IBS): compra al cierre si cerró cerca del mínimo; vende al cierre siguiente."""
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    value = (df["close"] - df["low"]) / rng
    return from_positions(df, (value < 0.2).astype(float))


def overnight(df):
    """Comprar al cierre y vender a la apertura siguiente (en CFDs habría que sumar el swap)."""
    ret = df["open"] / df["close"].shift(1) - 1
    return (ret - 2 * COST).fillna(0)


DAILY = {
    "Comprar y mantener": buy_and_hold,
    "Tendencia SMA 200": trend_sma200,
    "RSI(2) Connors": rsi2,
    "IBS < 0.2": ibs,
    "Solo de noche": overnight,
}


# ---------------------------------------------------------------- informe

def metrics(daily):
    """daily: Serie de retornos por día (0 en días sin operación)."""
    curve = (1 + daily).cumprod()
    years = len(daily) / 252
    cagr = curve.iloc[-1] ** (1 / years) - 1
    dd = (curve / curve.cummax() - 1).min()
    half = len(daily) // 2
    first = (1 + daily.iloc[:half]).prod() - 1
    second = (1 + daily.iloc[half:]).prod() - 1
    return cagr, dd, daily.min(), first, second


def header(title):
    print(f"\n{title}")
    print(f"{'Estrategia':22}{'Ops':>6}{'Gan.':>6}{'F.benef.':>9}{'Anual':>8}{'DD máx':>8}"
          f"{'Peor día':>9}{'1ª mitad':>9}{'2ª mitad':>9}")


def row(name, trades, daily):
    trades = np.array(trades)
    wins = (trades > 0).mean() if len(trades) else 0
    gross_loss = -trades[trades < 0].sum()
    pf = trades[trades > 0].sum() / gross_loss if gross_loss > 0 else float("inf")
    cagr, dd, worst, first, second = metrics(daily)
    print(f"{name:22}{len(trades):>6}{wins:>6.0%}{pf:>9.2f}{cagr:>8.1%}{dd:>8.1%}"
          f"{worst:>9.2%}{first:>9.1%}{second:>9.1%}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--symbols", nargs="+", default=["QQQ", "GLD"])
    args = parser.parse_args()

    for symbol in [s.upper() for s in args.symbols]:
        days = load(symbol, "minute")
        header(f"=== {symbol} intradía: {days[0].date} a {days[-1].date} ({len(days)} días), "
               f"coste {COST:.2%} por lado ===")
        for name, fn in INTRADAY.items():
            per_day = [fn(days, k) for k in range(len(days))]
            daily = pd.Series([sum(t) for t in per_day], index=[d.date for d in days])
            row(name, [t for ts in per_day for t in ts], daily)

        df = load(symbol, "daily")
        header(f"=== {symbol} varios días: {df.index[0]} a {df.index[-1]} "
               f"(Ops y Gan. cuentan días invertido) ===")
        for name, fn in DAILY.items():
            daily = fn(df)
            position_changes = daily[daily != 0]
            row(name, position_changes.to_numpy(), daily)


if __name__ == "__main__":
    main()
