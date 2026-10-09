"""ORB «la vela habla» en distintos FUTUROS, comparado en R (múltiplos del riesgo) para que sean comparables. 2018 - oct 2026.

Regla: vela previa (5 min antes de la apertura) → primera vela de 5 min que cierra más allá de la previa → entrada;
si no, vela de 15 min sin rechazo → entrada; stop 10 % / 15 % del ATR (media de 14 días del rango de la sesión); cierre al
final de la sesión. Coste: 2 ticks por operación. Resultado en R (1 R = el riesgo de cada operación).
Sesión principal de cada mercado (hora NY): índices 9:30-16:00 · petróleo y gas 9:00-14:30 · metales 8:20-13:30 ·
bonos y euro 8:20-15:00.

Uso:
    python orb_mercados.py
"""

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).parent / ".lab_cache"
MERCADOS = {  # símbolo: (apertura, cierre en minutos NY, tick, $ por punto del micro, nombre del micro)
    "NQ": (570, 960, 0.25, 2, "MNQ"), "ES": (570, 960, 0.25, 5, "MES"), "RTY": (570, 960, 0.1, 5, "M2K"),
    "YM": (570, 960, 1.0, 0.5, "MYM"), "CL": (540, 870, 0.01, 100, "MCL"), "NG": (540, 870, 0.001, 1000, "MNG"),
    "GC": (500, 810, 0.1, 10, "MGC"), "SI": (500, 810, 0.005, 1000, "SIL"), "HG": (500, 810, 0.0005, 2500, "MHG"),
    "ZN": (500, 900, 0.015625, 1000, "ZN (sin micro)"), "6E": (500, 900, 0.00005, 12500, "M6E"),
}


def candle(B, n):
    o, c = B[0, 0], B[n - 1, 3]
    h, l = B[:n, 1].max(), B[:n, 2].min()
    if c == o:
        return None
    s = 1 if c > o else -1
    wick = (min(o, c) - l) if s == 1 else (h - max(o, c))
    return s, wick > abs(c - o)


def run(sym):
    a0, a1, tick, usd, micro = MERCADOS[sym]
    df = pickle.loads((CACHE / f"dbn_{sym}_5m.pkl").read_bytes())
    t = df.index
    hm = (t.hour * 60 + t.minute).to_numpy()
    arr = df[["open", "high", "low", "close"]].to_numpy()
    nbar = (a1 - a0) // 5
    days, prev_ok = [], []
    for d, idx in pd.Series(np.arange(len(df))).groupby(np.array(t.normalize().asi8)).indices.items():
        idx = np.asarray(idx)
        s = idx[(hm[idx] >= a0) & (hm[idx] < a1)]
        p = idx[hm[idx] == a0 - 5]
        if len(s) < nbar * 0.95 or len(p) != 1:
            continue
        days.append((pd.Timestamp(d), arr[s], arr[p[0]]))
    rng = pd.Series([B[:, 1].max() - B[:, 2].min() for _, B, _ in days])
    atr = rng.rolling(14).mean().shift(1).to_numpy()
    rows = []
    for (d, B, P), a in zip(days, atr):
        if not np.isfinite(a):
            continue
        c5, c15 = candle(B, 1), candle(B, 3)
        if c5 and ((c5[0] == 1 and B[0, 3] > P[1]) or (c5[0] == -1 and B[0, 3] < P[2])):
            n, s, k = 1, c5[0], 0.1
        elif c15 and not c15[1]:
            n, s, k = 3, c15[0], 0.15
        else:
            continue
        e = B[n, 0]
        risk = k * a
        sl = e - s * risk
        px = B[-1, 3]
        for q in range(n, len(B)):
            if (s == 1 and B[q, 2] <= sl) or (s == -1 and B[q, 1] >= sl):
                px = min(sl, B[q, 0]) if s == 1 else max(sl, B[q, 0])
                break
        r_mult = (s * (px - e) - 2 * tick) / risk
        rows.append((d.year, r_mult, risk * usd))
    return pd.DataFrame(rows, columns=["y", "R", "riesgo"]), micro


def main():
    pd.set_option("display.width", 250)
    out = {}
    for sym in MERCADOS:
        if not (CACHE / f"dbn_{sym}_5m.pkl").exists():
            continue
        R, micro = run(sym)
        d, v = R[R.y < 2023].R, R[R.y >= 2023].R
        pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
        eq = R.R.cumsum()
        out[sym] = {"micro": micro, "ops/año": round(len(R) / 8.75), "acierto": f"{(R.R > 0).mean():.0%}",
                    "R por op": round(R.R.mean(), 3), "R/año 18-22": round(d.sum() / 5, 1), "PF 18-22": pf(d),
                    "R/año 23-26": round(v.sum() / 3.75, 1), "PF 23-26": pf(v), "peor racha (R)": round((eq.cummax() - eq).max(), 1),
                    "años +": f"{(R.groupby('y').R.sum() > 0).sum()}/9", "riesgo típico 1 micro $": round(R.riesgo.tail(250).median())}
    T = pd.DataFrame(out).T.sort_values("R por op", ascending=False)
    T.to_pickle(CACHE / "orb_mercados.pkl")
    print(T.to_string())


if __name__ == "__main__":
    main()
