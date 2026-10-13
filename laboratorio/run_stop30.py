"""Petición del usuario: "los stops son muy chicos, busca 30 pts mínimo". MNQ, ruptura A FAVOR (orden stop OCO 1 tick
fuera del rango; mismo minuto en ambos lados = no se opera; plazo 3,5 h). Reglas fijadas antes de ver resultados:
  orig      stop = otro lado del rango, objetivo 0,75 R (referencia, sin cambios)
  filtro30  igual que orig, pero SOLO días con rango >= 30 puntos
  min30_R   stop a max(R, 30 pts) del nivel roto; objetivo 0,75 R (el del rango)
  min30_S   stop a S = max(R, 30 pts) del nivel roto; objetivo 0,75 S
  min30_1S  stop a S; objetivo 1 S
Ventanas: 5 min 8:25 y 9:25 ET (14:25/15:25 Italia), 15 min 8:15 y 9:15 ET, 30 min 8:00 ET. Costes base y alto."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import lab, load_days, setup, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

WINS = [(5, 505), (5, 565), (15, 495), (15, 555), (30, 480)]
MODES = ["orig", "filtro30", "min30_R", "min30_S", "min30_1S"]
MIN = 30.0


def run(D, dur, a, c, mode):
    tk = c.tick
    rnd = lambda x: round(x / tk) * tk
    fills = []
    for date, m in D:
        st = setup(m, a, dur, tk)
        if st is None or st == "mismo":
            continue
        hi, lo, R, side, k, ex = st
        if mode == "filtro30" and R < MIN:
            continue
        edge, opp = (hi, lo) if side == 1 else (lo, hi)
        S = R if mode in ("orig", "filtro30") else max(R, MIN)
        stop = rnd(edge - side * S - side * tk)
        tdist = {"orig": 0.75 * R, "filtro30": 0.75 * R, "min30_R": 0.75 * R, "min30_S": 0.75 * S, "min30_1S": S}[mode]
        o = Order(side, "stop", k, stop, rnd(edge + side * tdist), ex, level=rnd(edge + side * tk), k_last=k + 1)
        f = simulate(date, m, ex + 1, o, c)
        if f is not None:
            fills.append(f)
    return trades_frame(fills, c)


def main():
    D, _ = load_days("MNQ")
    per = periods("intradia", include_test=True)
    exp = new_experiment("stop_minimo_30")
    rows = []
    for (dur, a), mode in itertools.product(WINS, MODES):
        for cn in ("base", "alto"):
            c = fut("MNQ", cn)
            t = run(D, dur, a, c, mode)
            rows.append(dict(ventana=lab(dur, a), modo=mode, coste=cn, ops_año=len(t) / 8.75, **stats(t, per, c)))
        print(lab(dur, a), mode, "ok", flush=True)
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    pd.set_option("display.width", 260, "display.max_rows", 200)
    for cn in ("base", "alto"):
        print(f"\n== coste {cn} ==")
        print(r[r.coste == cn][["ventana", "modo", "ops_año", "dev", "val", "prueba", "ic90_FM", "neto_año", "acierto",
                                "riesgo_med", "top10", "años_pos", "pasa"]].round(2).to_string(index=False))
    write_manifest(exp, experimento="stop mínimo de 30 puntos en las rupturas del dato y la apertura", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
