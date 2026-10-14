"""Petición: "la mejor estrategia para London session, fácil y sencilla, con probabilidad de ganar y de perder".
MNQ, ventanas de Londres (hora de Italia = ET + 6): vela de 5 min 8:00, 8:55, 9:00 y vela de 15 min 8:00, 9:00.
Reglas fijadas antes de ver resultados (ruptura A FAVOR con orden stop OCO 1 tick fuera; doble ruptura en el mismo
minuto = no se opera; plazo 3,5 h desde el cierre de la vela):
  stop S = máx(rango, M) desde el nivel roto, M ∈ {15, 30} puntos
  objetivo ∈ {0,5 S, 1 S}
Además "GIRO": en la ruptura, entrada EN CONTRA a mercado, objetivo el otro lado del rango, stop a 1 rango más allá.
Probabilidades: gana = la operación termina en positivo (bruto, en puntos); pierde = termina en negativo.
Selección (protocolo): esperanza neta > 0 en desarrollo Y validación (coste base), n_val >= 30."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import lab, load_days, run_strategy, setup, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

WINS = [(5, 120), (5, 175), (5, 180), (15, 120), (15, 180)]


def run(D, dur, a, c, M, frac):
    tk = c.tick
    rnd = lambda x: round(x / tk) * tk
    fills = []
    for date, m in D:
        st = setup(m, a, dur, tk)
        if st is None or st == "mismo":
            continue
        hi, lo, R, side, k, ex = st
        edge = hi if side == 1 else lo
        S = max(R, M)
        o = Order(side, "stop", k, rnd(edge - side * S - side * tk), rnd(edge + side * frac * S), ex,
                  level=rnd(edge + side * tk), k_last=k + 1)
        f = simulate(date, m, ex + 1, o, c)
        if f is not None:
            fills.append(f)
    return trades_frame(fills, c)


def probs(t):
    g = t.gross_pts
    yrs = t.groupby(t.date.dt.year).gross_pts.sum()
    return dict(gana=(g > 0).mean(), pierde=(g < 0).mean(), gana_pts=g[g > 0].mean(), pierde_pts=g[g < 0].mean(),
                media_pts=g.mean(), años_pos_bruto=int((yrs > 0).sum()), n_años=len(yrs))


def main():
    D, _ = load_days("MNQ")
    per = periods("intradia", include_test=True)
    c = fut("MNQ", "base")
    exp = new_experiment("londres_simple_probabilidades")
    rows = []
    for (dur, a) in WINS:
        for M, frac in itertools.product((15, 30), (0.5, 1.0)):
            t = run(D, dur, a, c, M, frac)
            rows.append(dict(ventana=lab(dur, a), modo=f"FAVOR stop mín {M}, obj {frac} S", ops_año=len(t) / 8.75,
                             **probs(t), **stats(t, per, c)))
        t = run_strategy(D, dur, a, c, mode="contra")
        rows.append(dict(ventana=lab(dur, a), modo="GIRO obj otro lado, stop 1 rango", ops_año=len(t) / 8.75,
                         **probs(t), **stats(t, per, c)))
        print(lab(dur, a), "ok", flush=True)
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="Londres simple: probabilidad de ganar/perder", reglas=__doc__)
    pd.set_option("display.width", 280, "display.max_rows", 200)
    print(r[["ventana", "modo", "ops_año", "gana", "pierde", "gana_pts", "pierde_pts", "media_pts", "años_pos_bruto",
             "dev", "val", "prueba", "años_pos", "pasa"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
