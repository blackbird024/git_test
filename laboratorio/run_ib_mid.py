"""Initial Balance (IB) mid pullback (vídeo de YouTube, "A+ setup"), traducido a reglas mecánicas para MNQ.
Reglas fijadas ANTES de ver resultados:

1. IB = máximo y mínimo de 9:30 a 10:30 ET (velas de 5 min 9:30…10:25). IB mid = punto medio.
2. "Movimiento direccional" en la primera hora: |cierre de 10:25-10:30 − apertura 9:30| >= 0,5 × rango del IB.
   Dirección = signo de ese movimiento. Si no hay movimiento direccional, no se opera.
3. Desde las 10:30 (IB ya fijado; el vídeo dice que así lo hace "la mayoría de las veces") se espera un retroceso al
   IB mid: vela de 5 min cuyo mínimo (largos) llega al mid (<= mid + 2 ticks) y que CIERRA por encima del mid.
   Variante "con mecha": además la mecha inferior es >= 40 % del rango de la vela (rechazo).
   Si antes de la señal una vela cierra por debajo del mínimo del IB (largos), el día se cancela.
4. Entrada en la apertura de la vela siguiente (señales hasta las 15:00). Stop: mínimo de la vela de señal − 1 tick.
5. Objetivo: el extremo del IB a favor (máximo del IB para largos) o 2R. Cierre forzoso 15:55. Una operación por día.
La entrada "por momentum" del vídeo es discrecional y no se modela.
"""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, run
from data.loaders import TICK, bars5, sessions
from execution_costs.costs import mnq
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest


def ib_mid(s, ctx, wick=True, target="ib", dir_min=0.5, wick_min=0.4):
    b = bars5(s)
    if len(b) < 20 or np.isnan(b[:12]).any():
        return None
    ibh, ibl = b[:12, 1].max(), b[:12, 2].min()
    rng = ibh - ibl
    if rng <= 0:
        return None
    mv = b[11, 3] - b[0, 0]
    if abs(mv) < dir_min * rng:
        return None
    side = 1 if mv > 0 else -1
    mid = (ibh + ibl) / 2
    for i in range(12, len(b)):
        if 5 * (i + 1) >= 330:
            return None
        o, h, l, c = b[i]
        if np.isnan(c):
            continue
        if (side == 1 and c < ibl) or (side == -1 and c > ibh):
            return None
        if side == 1:
            touch = l <= mid + 2 * TICK and c > mid
            wk = (min(o, c) - l) >= wick_min * (h - l) if h > l else False
        else:
            touch = h >= mid - 2 * TICK and c < mid
            wk = (h - max(o, c)) >= wick_min * (h - l) if h > l else False
        if touch and (wk or not wick):
            stop = l - TICK if side == 1 else h + TICK
            if target == "ib":
                return Order(side, "market", 5 * (i + 1), stop, ibh if side == 1 else ibl, 385, tag="ib_mid")
            return Order(side, "market", 5 * (i + 1), stop, None, 385, target_r=2.0, tag="ib_mid")
    return None


def main():
    S = sessions()
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    variants = {f"{'con' if w else 'sin'} mecha, objetivo {t}": dict(wick=w, target=t)
                for w, t in itertools.product((True, False), ("ib", "2R"))}
    exp = new_experiment("ib_mid_pullback")
    rows = []
    for name, p in variants.items():
        for scen in ("bajo", "base", "alto"):
            c = mnq(scen)
            t = trades_frame(run(S, ib_mid, c, **p), c)
            if scen == "base":
                t.to_csv(exp / f"ops_{''.join(ch if ch.isalnum() else '_' for ch in name)}.csv.gz", index=False)
            for k, tp in split(t, per).items():
                rows.append(dict(variante=name, coste=scen, periodo=k, **summary(tp, cals[k])))
            o = t[t.date >= "2022-01-01"]
            lo, hi = block_bootstrap_mean(o.pnl.to_numpy())
            rows.append(dict(variante=name, coste=scen, periodo="FM 2022-2026", n=len(o), esperanza=o.pnl.mean(),
                             pf=o.pnl[o.pnl > 0].sum() / -o.pnl[o.pnl < 0].sum(), acierto=(o.pnl > 0).mean(),
                             R_medio=o.R.mean(), R_bruto=(o.gross_pts * 2 / o.risk_usd).mean(), ic90_bajo=lo, ic90_alto=hi,
                             riesgo_mediano=o.risk_usd.median()))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="IB mid pullback (vídeo)", reglas=__doc__,
                   periodos={k: [str(a.date()), str(b.date())] for k, (a, b) in per.items()})
    pd.set_option("display.width", 260, "display.max_rows", 200)
    b = res[res.coste == "base"]
    print(b[["variante", "periodo", "n", "ops_año", "neto_año", "pf", "esperanza", "acierto", "R_medio", "R_bruto",
             "ic90_bajo", "ic90_alto", "dd_max", "riesgo_mediano"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
