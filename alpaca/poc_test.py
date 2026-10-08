"""Perfil de volumen en NQ / MNQ: POC y área de valor de ayer (datos de 1 min con volumen, 2018 - oct 2026).

Perfil de la sesión 9:30-16:00 NY de ayer: volumen de cada vela de 1 min asignado a su cierre, en tramos de 5 puntos.
  POC   el tramo con más volumen.   Área de valor (VA): desde el POC se añade el tramo vecino con más volumen hasta
  llegar al 70 % del volumen. VAH / VAL = sus bordes.
Pruebas (hoy, sesión 9:30-16:00, velas de 5 min, cierre forzoso 16:00, una operación al día):
  A) POC de ayer: primer toque viniendo de un lado (9:35-15:00) → rebote o ruptura; stop 0,1 ATR (o 0,2); 1R / 2R.
  B) Regla del 80 %: si abre FUERA del área de valor de ayer y luego 1 o 2 velas de 30 min seguidas CIERRAN dentro,
     se opera hacia el otro lado del área (objetivo = el borde opuesto: VAL si abrió por encima, VAH si abrió por
     debajo). Stop: el extremo del día hasta la entrada · o 0,15 ATR. Entradas hasta las 13:00.
  C) Apertura respecto al área de valor: abre por encima del VAH → compra a las 9:35 (aceptación) o vende (rechazo);
     espejo por debajo del VAL. Stop 0,1 ATR, cierre 16:00.
ATR = media de 14 días del rango 9:30-16:00. Coste 1 punto (2 $/punto por MNQ).
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python poc_test.py
"""

import itertools

import numpy as np
import pandas as pd

import vwap_globex_8y as V


def profile(close, vol, step=5.0):
    b = np.floor(close / step).astype(np.int64)
    s = pd.Series(vol).groupby(b).sum().sort_index()
    bins, v = s.index.to_numpy(), s.to_numpy().astype(float)
    full = np.arange(bins.min(), bins.max() + 1)
    vv = np.zeros(len(full))
    vv[bins - bins.min()] = v
    p = int(vv.argmax())
    lo = hi = p
    tot, acc = vv.sum(), vv[p]
    while acc < 0.7 * tot and (lo > 0 or hi < len(vv) - 1):
        a = vv[lo - 1] if lo > 0 else -1
        c = vv[hi + 1] if hi < len(vv) - 1 else -1
        if c >= a:
            hi += 1
            acc += c
        else:
            lo -= 1
            acc += a
    poc = (full[p] + 0.5) * step
    return poc, full[lo] * step, (full[hi] + 1) * step


def exit_px(B, k0, s, sl, tg):
    for q in range(k0, len(B)):
        if (s == 1 and B[q, 2] <= sl) or (s == -1 and B[q, 1] >= sl):
            return min(sl, B[q, 0]) if s == 1 else max(sl, B[q, 0])
        if tg is not None and ((s == 1 and B[q, 1] >= tg) or (s == -1 and B[q, 2] <= tg)):
            return tg
    return B[-1, 3]


def stats(rows, prueba, var, T):
    if len(T) < 50:
        return
    y = np.array([a[0] for a in T])
    u = np.array([a[1] for a in T])
    d, v = u[y < 2023], u[y >= 2023]
    pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
    eq = np.cumsum(u)
    rows.append(dict(prueba=prueba, variante=var, ops_año=round(len(u) / 8.75), acierto=round((u > 0).mean(), 2),
                     dev=round(d.sum() / 5), pf_dev=pf(d), val=round(v.sum() / 3.75), pf_val=pf(v),
                     peor_racha=round((np.maximum.accumulate(eq) - eq).max()), años=f"{sum(u[y == k].sum() > 0 for k in range(2018, 2027))}/9"))


def main():
    pd.set_option("display.width", 250)
    m1 = V.load()
    m1.index = m1.index.tz_convert("America/New_York")
    hm1 = m1.index.hour * 60 + m1.index.minute
    r1 = m1[(hm1 >= 570) & (hm1 < 960)]
    days = []
    for d, g in r1.groupby(r1.index.normalize()):
        if len(g) < 380:
            continue
        b5 = g.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        if len(b5) != 78:
            continue
        days.append(dict(d=d, B=b5[["open", "high", "low", "close"]].to_numpy(), prof=profile(g.close.to_numpy(), g.volume.to_numpy()),
                         rng=g.high.max() - g.low.min()))
    atr = pd.Series([x["rng"] for x in days]).rolling(14).mean().shift(1).to_numpy()
    print("días", len(days), flush=True)
    rows = []
    cost = lambda s, px, e: (s * (px - e) - 1.0) * 2.0
    # A) POC de ayer
    for mode, sm, rr in itertools.product(("rebote", "ruptura"), (0.1, 0.2), (1.0, 2.0)):
        T = []
        for i in range(1, len(days)):
            if not np.isfinite(atr[i]):
                continue
            B, poc = days[i]["B"], days[i - 1]["prof"][0]
            for k in range(1, 67):
                if B[k, 2] <= poc <= B[k, 1]:
                    appr = 1 if B[k - 1, 3] > poc else -1 if B[k - 1, 3] < poc else 0
                    if appr == 0:
                        break
                    s = appr if mode == "rebote" else -appr
                    risk = sm * atr[i]
                    px = exit_px(B, k + 1, s, poc - s * risk, poc + s * rr * risk)
                    T.append((days[i]["d"].year, cost(s, px, poc)))
                    break
        stats(rows, "A) POC de ayer", f"{mode} · stop {sm} ATR · {rr:g}R", T)
    # B) regla del 80 %
    for conf, stopm in itertools.product((1, 2), ("extremo del día", "0,15 ATR")):
        T = []
        for i in range(1, len(days)):
            if not np.isfinite(atr[i]):
                continue
            B = days[i]["B"]
            _, val, vah = days[i - 1]["prof"]
            op = B[0, 0]
            if val <= op <= vah:
                continue
            s = -1 if op > vah else 1
            tg = val if s == -1 else vah
            inside = 0
            for j in range(6, 43, 6):          # cierres de las velas de 30 min hasta las 13:00
                cl = B[j - 1, 3]
                inside = inside + 1 if val < cl < vah else 0
                if inside >= conf:
                    e = B[j, 0]
                    sl = (B[:j, 1].max() if s == -1 else B[:j, 2].min()) if stopm == "extremo del día" else e - s * 0.15 * atr[i]
                    if s * (tg - e) <= 0 or s * (e - sl) <= 0:
                        break
                    px = exit_px(B, j, s, sl, tg)
                    T.append((days[i]["d"].year, cost(s, px, e)))
                    break
        stats(rows, "B) regla del 80 %", f"{conf} vela(s) de 30 min dentro · stop {stopm}", T)
    # C) apertura respecto al área de valor
    for mode in ("aceptación (a favor)", "rechazo (en contra)"):
        T = []
        for i in range(1, len(days)):
            if not np.isfinite(atr[i]):
                continue
            B = days[i]["B"]
            _, val, vah = days[i - 1]["prof"]
            op = B[0, 0]
            if val <= op <= vah:
                continue
            s = (1 if op > vah else -1) * (1 if mode.startswith("acept") else -1)
            e = B[1, 0]
            px = exit_px(B, 1, s, e - s * 0.1 * atr[i], None)
            T.append((days[i]["d"].year, cost(s, px, e)))
        stats(rows, "C) apertura fuera del área de valor", mode, T)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/poc_test.pkl")
    print(R.to_string(index=False))


if __name__ == "__main__":
    main()
