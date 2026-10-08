"""Simulación de la evaluación de Topstep (Trading Combine) con las estrategias probadas, 2018 - oct 2026.

Reglas usadas (cuenta de 50K, revisa las vigentes en tu panel de Topstep):
  objetivo +3.000 $ · Maximum Loss Limit 2.000 $ que sube con el máximo de saldo al CIERRE del día hasta quedarse
  en el saldo inicial · regla de consistencia: el mejor día debe ser < 50 % del beneficio total al aprobar ·
  todo cerrado antes de las 15:10 CT (16:10 NY), cosa que todas las estrategias cumplen.
Estrategias (resultado diario en $ con costes): NQ rango de ayer (1 MNQ) · NQ ORB 5 min (1 MNQ) ·
oro Londres rango NY de ayer, salida 14:25 Londres (1 MGC); y combinaciones.
Se empieza la evaluación cada día hábil desde 2018 y se cuenta: aprobada, suspendida, o sin decidir en 90 días.

Uso:
    python topstep_sim.py
"""

import numpy as np
import pandas as pd

import liquidez_ruptura_london as GL
from crt_backtest import load_5m
from nq_intraday_research import build_days
from orb_research import vela5


def pdr_series(stop=True):
    df = load_5m("NQ")
    t = df.index
    hm = (t.hour * 60 + t.minute).to_numpy()
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    g = (t + pd.Timedelta(hours=6)).normalize()
    groups = pd.Series(np.arange(len(df))).groupby(g).indices
    keys = sorted(groups)
    days = []
    for d in keys:
        idx = np.asarray(groups[d])
        rth = idx[(hm[idx] >= 570) & (hm[idx] < 960)]
        days.append(None if len(rth) != 78 else (d, rth, h[rth].max(), l[rth].min()))
    out = {}
    for i in range(1, len(days)):
        x, p = days[i], days[i - 1]
        if x is None or p is None:
            continue
        d, r, _, _ = x
        ph, pl = p[2], p[3]
        mid = (ph + pl) / 2 if stop else np.nan
        if not (pl <= o[r[0]] <= ph):
            continue
        for j, k in enumerate(r[:73]):
            if h[k] > ph:
                s, e = 1, max(ph, o[k])
            elif l[k] < pl:
                s, e = -1, min(pl, o[k])
            else:
                continue
            px = c[r[-1]]
            for q in r[j + 1:]:
                if (s == 1 and l[q] <= mid) or (s == -1 and h[q] >= mid):
                    px = min(mid, o[q]) if s == 1 else max(mid, o[q])
                    break
            out[pd.Timestamp(d).tz_localize(None).normalize()] = (s * (px - e) - 1) * 2
            break
    return pd.Series(out)


def orb5_series(stop=True):
    days = build_days("NQ")
    return pd.Series({pd.Timestamp(d).normalize(): p * 2 for d, p in vela5(days, frac=0.1 if stop else 1e6)})


def gold_series(stop=True):
    days, o, h, l, c = GL.build("GC")
    out = {}
    for x in days:
        R = GL.run([x], o, h, l, c, "ayer NY", 720, "otro lado" if stop else "sin stop", 1.0, "14:25 Lon", 0.3, 10.0)
        if len(R):
            out[x["d"].normalize()] = R.u.iloc[0]
    return pd.Series(out)


def combine(pnl, target=3000, mll=2000, max_days=90):
    dates = pnl.index
    res = []
    for s in range(len(dates) - 1):
        bal, peak, best, n = 0.0, 0.0, 0.0, 0
        out = "sin decidir"
        for d in dates[s:s + max_days]:
            v = pnl[d]
            bal += v
            best = max(best, v)
            n += 1
            floor = min(peak - mll, 0.0) if peak - mll < 0 else 0.0 - 0.0
            floor = min(peak, mll) - mll        # el límite sube con el máximo de cierre hasta el saldo inicial
            if bal <= floor:
                out = "suspendida"
                break
            peak = max(peak, bal)
            if bal >= target and best < 0.5 * bal:
                out = "aprobada"
                break
        res.append((out, n))
    R = pd.DataFrame(res, columns=["r", "dias"])
    return R


def main():
    s = {"NQ rango de ayer": pdr_series(), "NQ ORB 5 min": orb5_series(), "Oro Londres (salida 15:25)": gold_series()}
    idx = pd.bdate_range("2018-02-01", "2026-10-02")
    S = pd.DataFrame({k: v.reindex(idx).fillna(0.0) for k, v in s.items()})
    combos = {**{k: S[k] for k in S}, "Oro Londres + NQ rango de ayer": S.iloc[:, [0, 2]].sum(axis=1),
              "Oro Londres + NQ ORB 5 min": S.iloc[:, [1, 2]].sum(axis=1), "las tres": S.sum(axis=1)}
    rows = []
    for name, pnl in combos.items():
        R = combine(pnl)
        eq = pnl.cumsum()
        ap = R[R.r == "aprobada"]
        rows.append({"estrategia": name, "$/año": round(pnl.sum() / 8.67), "peor racha $": round((eq.cummax() - eq).max()),
                     "peor día $": round(pnl.min()), "aprobada": f"{(R.r == 'aprobada').mean():.0%}",
                     "suspendida": f"{(R.r == 'suspendida').mean():.0%}", "sin decidir (90 días)": f"{(R.r == 'sin decidir').mean():.0%}",
                     "días hasta aprobar (mediana)": int(ap.dias.median()) if len(ap) else None})
    pd.set_option("display.width", 220)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
