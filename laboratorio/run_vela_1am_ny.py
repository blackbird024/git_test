"""Petición: probar la vela de 1:00 a 1:15 NY (7:00-7:15 Italia), 15 min, MNQ 2018-2026. Reglas fijadas antes:
  Carrera: tras la primera ruptura, ¿llega antes a +1 rango más allá (continúa) o al otro lado (gira)? (plazo 3,5 h)
  A FAVOR: OCO stop 1 tick fuera; stop = otro lado (o mínimo 15 pts / 30 pts desde el nivel roto); objetivo 0,5 / 0,75 /
    1 × rango desde el nivel roto, o 1:1 respecto al stop.
  EN CONTRA: en la ruptura, a mercado en contra; objetivo el otro lado; stop a 1 rango más allá.
  Plazo 3,5 h (hasta 4:45 NY = 10:45 Italia). Días con doble ruptura en el mismo minuto: CASO PEOR (se simulan los dos
  lados y se cuenta el peor), para no inflar el resultado como pasó con el playbook.
Selección: neto > 0 en dev Y val (coste base), n_val >= 30."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import load_days, race, setup, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

A, DUR = 60, 15


def run(D, c, modo, minstop, obj):
    tk = c.tick
    rnd = lambda x: round(x / tk) * tk
    fills = []
    for d, m in D:
        st = setup(m, A, DUR, tk)
        if st is None:
            continue
        H, L = m[:, 1], m[:, 2]
        hi, lo = np.nanmax(H[A:A + DUR]), np.nanmin(L[A:A + DUR])
        R = hi - lo
        ex = min(A + DUR + 210, 955)
        if st == "mismo":
            k = A + DUR + np.nonzero((H[A + DUR:ex] >= hi + tk) | (L[A + DUR:ex] <= lo - tk))[0][0]
            lados = [(1, k), (-1, k)]
        else:
            lados = [(st[3], st[4])]
        opts = []
        for side, k in lados:
            edge, opp = (hi, lo) if side == 1 else (lo, hi)
            if modo == "favor":
                S = max(R, minstop)
                stop = rnd(edge - side * S - side * tk)
                if obj == "1:1":
                    o = Order(side, "stop", k, stop, None, ex, level=rnd(edge + side * tk), k_last=k + 1, target_r=1.0)
                else:
                    o = Order(side, "stop", k, stop, rnd(edge + side * obj * R), ex, level=rnd(edge + side * tk),
                              k_last=k + 1)
            else:
                o = Order(-side, "market", k + 1, rnd(edge + side * R), opp, ex)
            f = simulate(d, m, ex + 1, o, c)
            if f is not None:
                opts.append(f)
        if opts:
            fills.append(min(opts, key=lambda f: f.gross_pts))
    return trades_frame(fills, c)


def main():
    D, _ = load_days("MNQ")
    per = periods("intradia", include_test=True)
    c = fut("MNQ", "base")
    exp = new_experiment("vela_1am_ny")
    res, rr = [], []
    for d, m in D:
        st = setup(m, A, DUR, c.tick)
        if st is None:
            continue
        rr.append(np.nanmax(m[A:A + DUR, 1]) - np.nanmin(m[A:A + DUR, 2]))
        res.append("mismo" if st == "mismo" else race(m, st))
    res = pd.Series(res)
    print(f"rango mediano {np.median(rr):.1f} pts · días {len(res)} · continúa {(res == 'continua').mean():.0%} · "
          f"gira {(res == 'gira').mean():.0%} · ninguno {(res == 'nada').mean():.0%} · doble mismo minuto {(res == 'mismo').mean():.1%}")
    rows = []
    vs = [("favor", ms, ob) for ms in (0.0, 15.0, 30.0) for ob in (0.5, 0.75, 1.0, "1:1")] + [("contra", 0.0, None)]
    for modo, ms, ob in vs:
        t = run(D, c, modo, ms, ob)
        g = t.gross_pts
        eq = t.pnl.cumsum()
        rows.append(dict(modo=modo, stop="otro lado" if ms == 0 else f"mín {ms:.0f}", objetivo=str(ob),
                         ops_año=len(t) / 8.75, gana=(g > 0).mean(), gana_usd=t.pnl[t.pnl > 0].mean(),
                         pierde_usd=t.pnl[t.pnl < 0].mean(), dd=(eq - eq.cummax()).min(), **stats(t, per, c)))
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="vela 15 min 1:00 NY (7:00 Italia)", reglas=__doc__)
    pd.set_option("display.width", 260)
    print(r[["modo", "stop", "objetivo", "ops_año", "gana", "gana_usd", "pierde_usd", "dev", "val", "prueba",
             "neto_año", "años_pos", "dd", "pasa"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
