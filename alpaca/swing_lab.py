"""Laboratorio de swing trading: operaciones de días a semanas, con velas diarias desde 2016.

Todas son solo de compra, se deciden con el cierre y se ejecutan al cierre del
mismo día (en MT5 o con órdenes al cierre). Exposición 1x y coste de COST por lado.

Uso:
    python swing_lab.py                               # QQQ SPY IWM GLD
    python swing_lab.py --symbols QQQ SPY DIA IWM GLD TLT
"""

import argparse

import numpy as np
import pandas as pd

import strategy_lab as lab
from strategy_lab import load, rsi

COST = 0.0002


def atr(df, n=14):
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1)
    return tr.max(axis=1).rolling(n).mean()


def stateful(df, enter, leave):
    """Posición 0/1: entra cuando `enter` es cierto, sale cuando `leave` es cierto."""
    pos, state = [], 0.0
    for e, l in zip(enter.fillna(False), leave.fillna(False)):
        if state == 0 and e:
            state = 1.0
        elif state == 1 and l:
            state = 0.0
        pos.append(state)
    return pd.Series(pos, index=df.index)


def with_time_stop(df, enter, leave, max_days):
    """Como `stateful`, pero sale también tras `max_days` días."""
    pos, state, held = [], 0.0, 0
    for e, l in zip(enter.fillna(False), leave.fillna(False)):
        if state == 0 and e:
            state, held = 1.0, 0
        elif state == 1:
            held += 1
            if l or held >= max_days:
                state = 0.0
        pos.append(state)
    return pd.Series(pos, index=df.index)


# ---------------------------------------------------------------- estrategias
# Cada una recibe el DataFrame diario y devuelve la posición (0/1) al cierre de cada día.

def rsi2(df):
    """Connors RSI(2): compra con RSI(2) < 10 sobre la media de 200; sale al cerrar sobre la media de 5."""
    c = df["close"]
    return stateful(df, (rsi(c, 2) < 10) & (c > c.rolling(200).mean()), c > c.rolling(5).mean())


def cumulative_rsi(df):
    """Connors: suma de RSI(2) de los últimos 2 días < 35 en tendencia; sale con RSI(2) > 65."""
    c = df["close"]
    r = rsi(c, 2)
    return stateful(df, (r.rolling(2).sum() < 35) & (c > c.rolling(200).mean()), r > 65)


def double_sevens(df):
    """Connors 'Double 7s': compra en mínimo de 7 días sobre la media de 200; vende en máximo de 7 días."""
    c = df["close"]
    return stateful(df, (c <= c.rolling(7).min()) & (c > c.rolling(200).mean()), c >= c.rolling(7).max())


def ibs(df):
    """IBS: compra si cierra en el 20% inferior del rango del día; vende si cierra en el 20% superior."""
    value = (df["close"] - df["low"]) / (df["high"] - df["low"]).replace(0, np.nan)
    return stateful(df, value < 0.2, value > 0.8)


def ibs_trend(df):
    """IBS solo en tendencia alcista (sobre la media de 200)."""
    c = df["close"]
    value = (c - df["low"]) / (df["high"] - df["low"]).replace(0, np.nan)
    return stateful(df, (value < 0.2) & (c > c.rolling(200).mean()), value > 0.8)


def bollinger(df):
    """Bollinger: compra al cerrar bajo la banda inferior (20, 2) en tendencia; sale en la media de 20."""
    c = df["close"]
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    return stateful(df, (c < mid - 2 * sd) & (c > c.rolling(200).mean()), c > mid)


def three_down(df):
    """Tres cierres a la baja seguidos en tendencia alcista; sale en el primer cierre al alza o a los 5 días."""
    c = df["close"]
    down = c < c.shift(1)
    enter = down & down.shift(1) & down.shift(2) & (c > c.rolling(200).mean())
    return with_time_stop(df, enter, c > c.shift(1), 5)


def atr_pullback(df):
    """Retroceso de 2 ATR bajo la media exponencial de 20 en tendencia; sale al recuperar la media o 10 días."""
    c = df["close"]
    ema = c.ewm(span=20, adjust=False).mean()
    enter = (c < ema - 2 * atr(df)) & (c > c.rolling(200).mean())
    return with_time_stop(df, enter, c > ema, 10)


def donchian(df):
    """Tortugas: compra al romper el máximo de 20 días; vende al perder el mínimo de 10."""
    c = df["close"]
    return stateful(df, c > c.rolling(20).max().shift(1), c < c.rolling(10).min().shift(1))


def macd_trend(df):
    """MACD (12, 26, 9) por encima de su señal y precio sobre la media de 200."""
    c = df["close"]
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    return ((macd > macd.ewm(span=9, adjust=False).mean()) & (c > c.rolling(200).mean())).astype(float)


def trend_sma200(df):
    c = df["close"]
    return (c > c.rolling(200).mean()).astype(float)


def buy_and_hold(df):
    return pd.Series(1.0, index=df.index)


STRATEGIES = {
    "Comprar y mantener": buy_and_hold,
    "Tendencia SMA 200": trend_sma200,
    "RSI(2) Connors": rsi2,
    "RSI(2) acumulado": cumulative_rsi,
    "Double 7s": double_sevens,
    "IBS": ibs,
    "IBS + tendencia": ibs_trend,
    "Bollinger 20/2": bollinger,
    "3 días a la baja": three_down,
    "Retroceso 2 ATR": atr_pullback,
    "Donchian 20/10": donchian,
    "MACD + tendencia": macd_trend,
}


# ---------------------------------------------------------------- evaluación

def evaluate(df, position):
    ret = df["close"].pct_change().fillna(0)
    held = position.shift(1).fillna(0)
    changes = held.diff().abs().fillna(held.abs())
    daily = held * ret - changes * COST

    # operaciones: tramos seguidos con posición
    trades, durations, current, days = [], [], 1.0, 0
    for h, r, ch in zip(held, ret, changes):
        if h:
            current *= 1 + r - ch * COST
            days += 1
        elif days:
            trades.append(current * (1 - COST) - 1)
            durations.append(days)
            current, days = 1.0, 0
    if days:
        trades.append(current - 1)
        durations.append(days)
    return daily, np.array(trades), np.array(durations), held.mean()


def report(symbols):
    summary = {}
    for symbol in symbols:
        df = load(symbol, "daily")
        print(f"\n=== {symbol}: {df.index[0]} a {df.index[-1]} ({len(df)} días), coste {COST:.2%} por lado ===")
        print(f"{'Estrategia':20}{'Ops':>5}{'Gan.':>6}{'F.ben.':>7}{'Días':>6}{'Expos.':>7}"
              f"{'Anual':>8}{'DD máx':>8}{'Peor día':>9}{'Ret/DD':>7}{'1ª mitad':>9}{'2ª mitad':>9}")
        for name, fn in STRATEGIES.items():
            daily, trades, durations, exposure = evaluate(df, fn(df))
            cagr, dd, worst, first, second = lab.metrics(daily)
            gross_loss = -trades[trades < 0].sum()
            pf = trades[trades > 0].sum() / gross_loss if gross_loss > 0 else float("inf")
            ratio = cagr / -dd if dd < 0 else float("inf")
            summary.setdefault(name, []).append((cagr, dd, ratio, first > 0 and second > 0))
            print(f"{name:20}{len(trades):>5}{(trades > 0).mean():>6.0%}{pf:>7.2f}"
                  f"{durations.mean():>6.1f}{exposure:>7.0%}{cagr:>8.1%}{dd:>8.1%}{worst:>9.2%}"
                  f"{ratio:>7.2f}{first:>9.1%}{second:>9.1%}")

    print(f"\n=== Resumen en {len(symbols)} activos ===")
    print(f"{'Estrategia':20}{'Anual medio':>12}{'DD medio':>10}{'Ret/DD medio':>13}{'Positiva en ambas mitades':>27}")
    for name, rows in summary.items():
        cagr, dd, ratio, both = zip(*rows)
        print(f"{name:20}{np.mean(cagr):>12.1%}{np.mean(dd):>10.1%}{np.mean(ratio):>13.2f}"
              f"{f'{sum(both)}/{len(both)}':>27}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--symbols", nargs="+", default=["QQQ", "SPY", "IWM", "GLD"])
    args = parser.parse_args()
    report([s.upper() for s in args.symbols])


if __name__ == "__main__":
    main()
