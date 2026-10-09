"""ORB «la vela habla» + batería de confluencias. NQ / MNQ, 2018 - oct 2026.

Señales: rompe la vela de 9:25 → entrada 9:35 (stop 10 % ATR); si no, vela de 15 min sin rechazo → 9:45 (15 % ATR).
Para cada confluencia se separan las señales en «a favor» / «en contra» (o grupos):
  hueco         apertura 9:30 vs cierre de ayer (16:00) en la dirección de la operación
  noche         precio de la señal vs apertura de Globex (18:00)
  medianoche    precio de la señal vs apertura de las 00:00 NY (idea AMD / ICT)
  ayer          dirección de la sesión de ayer (cierre vs apertura 9:30)
  rango ayer    la apertura está dentro / por encima / por debajo del rango de ayer (según la dirección)
  RSI 1h        RSI 14 de 1 h > 50 a favor / en contra
  VWAP          precio vs VWAP de la sesión Globex (desde 18:00)
  volatilidad   ATR de hoy vs media de 50 días (alta / baja)
  volumen       volumen de la primera vela vs media de 14 días (RVOL ≥ 1,2 / < 1,2)
  día           lunes … viernes
Coste 1 punto (2 $/punto por MNQ). Muchas pruebas a la vez: cuidado con los resultados que salgan por azar.

Uso:
    python orb_confluencias.py
"""

import numpy as np
import pandas as pd

import mezcla_filtros as M
import vwap_globex_8y as V
from crt_backtest import load_5m
from nq_intraday_research import build_days
from orb15_forma_vela import candle, trade
from orb_velas_30_60 import summary


def main():
    pd.set_option("display.width", 250)
    df = load_5m("NQ")
    t = df.index
    hm = (t.hour * 60 + t.minute).to_numpy()
    c = df.close.to_numpy()
    rsi = M.context(df)["RSI 1h"]
    gd = (t + pd.Timedelta(hours=6)).normalize()
    gopen = df.open.groupby(gd).transform("first").to_numpy()
    mid_open = pd.Series(np.where(hm == 0, df.open.to_numpy(), np.nan), index=t).groupby(t.normalize()).transform("max").to_numpy()
    pos = pd.Series(np.arange(len(t)), index=t)
    # VWAP Globex y volumen con datos de 1 min
    m1 = V.load()
    m1.index = m1.index.tz_convert("America/New_York")
    b5 = m1.resample("5min").agg({"high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    g5 = (b5.index + pd.Timedelta(hours=6)).normalize()
    typ = (b5.high + b5.low + b5.close) / 3
    vwap = ((typ * b5.volume).groupby(g5).cumsum() / b5.volume.groupby(g5).cumsum())
    vol930 = b5.volume[(b5.index.hour == 9) & (b5.index.minute == 30)]
    vol930.index = vol930.index.normalize().tz_localize(None)
    rvol = vol930 / vol930.rolling(14).mean().shift(1)
    pre = df[(t.hour == 9) & (t.minute == 25)]
    pre.index = pre.index.normalize().tz_localize(None)
    days = build_days("NQ")
    atr = pd.Series([x["atr"] for x in days])
    atr50 = atr.rolling(50).mean().to_numpy()
    rows = []
    for i, x in enumerate(days):
        d = pd.Timestamp(x["d"])
        if d not in pre.index or i == 0 or not np.isfinite(atr50[i]):
            continue
        ph, pl = pre.loc[d, ["high", "low"]]
        B, a = x["rth"], x["atr"]
        c5, c15 = candle(B, 1), candle(B, 3)
        if c5 and ((c5[0] == 1 and B[0, 3] > ph) or (c5[0] == -1 and B[0, 3] < pl)):
            n, s, k = 1, c5[0], 0.1
        elif c15 and not c15[2]:
            n, s, k = 3, c15[0], 0.15
        else:
            continue
        ts = (d + pd.Timedelta(minutes=570 + 5 * n)).tz_localize("America/New_York")
        j = pos.get(ts - pd.Timedelta(minutes=5))
        if j is None:
            continue
        px = B[n - 1, 3]
        f = lambda v: "a favor" if np.sign(v) == s else "en contra" if np.sign(v) == -s else "neutro"
        prev = days[i - 1]["rth"]
        op = B[0, 0]
        rng_pos = "dentro" if x["pl"] <= op <= x["ph"] else ("fuera a favor" if (op > x["ph"]) == (s == 1) else "fuera en contra")
        vw = vwap.asof(ts - pd.Timedelta(minutes=1)) if ts > vwap.index[0] else np.nan
        rows.append(dict(y=d.year, u=(trade(B, n, s, k * a) - 1) * 2,
                         hueco=f(op - x["pc"]), noche=f(px - gopen[j]), medianoche=f(px - mid_open[j]) if np.isfinite(mid_open[j]) else "neutro",
                         ayer=f(prev[-1, 3] - prev[0, 0]), rango_ayer=rng_pos, RSI_1h=f(rsi[j]) if np.isfinite(rsi[j]) else "neutro",
                         VWAP=f(px - vw) if np.isfinite(vw) else "neutro",
                         volatilidad="alta" if a > atr50[i] else "baja",
                         volumen=("RVOL ≥ 1,2" if rvol.get(d, np.nan) >= 1.2 else "RVOL < 1,2") if np.isfinite(rvol.get(d, np.nan)) else "sin dato",
                         dia=["lunes", "martes", "miércoles", "jueves", "viernes"][d.weekday()]))
    D = pd.DataFrame(rows)
    D.to_pickle(".lab_cache/orb_confluencias.pkl")
    print("TODAS:", summary(D).to_dict(), "\n")
    for col in ("hueco", "noche", "medianoche", "ayer", "rango_ayer", "RSI_1h", "VWAP", "volatilidad", "volumen", "dia"):
        g = D[D[col] != "neutro"].groupby(col).apply(summary, include_groups=False)
        print(f"── {col} ──\n{g.to_string()}\n")


if __name__ == "__main__":
    main()
