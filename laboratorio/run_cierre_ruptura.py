"""Pregunta del usuario: "¿espero al cierre de la vela que rompe?" Velas de 5 min 8:55, 14:25 y 15:25 Italia (2:55, 8:25
y 9:25 ET). MNQ. Reglas fijadas antes de ver resultados:
  ruptura    orden stop 1 tick fuera del rango (referencia, como el indicador)
  cierre1    la primera vela de 1 min que CIERRA fuera del rango → entrada a mercado en la apertura siguiente
  cierre5    la primera vela de 5 min (alineada al cierre del rango) que CIERRA fuera → entrada en la apertura siguiente
Stop a S = máx(R, 30 pts) del nivel roto (como el indicador; si al entrar el precio ya está más allá del objetivo se
cancela). Objetivo 0,75 R o 1 S. Plazo 3,5 h tras cerrar el rango. Coste base."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import load_days, setup, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest


def run(D, a, c, entry, tmode):
    tk = c.tick
    rnd = lambda x: round(x / tk) * tk
    fills = []
    for date, m in D:
        st = setup(m, a, 5, tk)
        if st is None or st == "mismo":
            continue
        hi, lo, R, _, k0, ex = st
        C = m[:, 3]
        if entry == "ruptura":
            side, kin, kind = st[3], k0, "stop"
        else:
            tf = 1 if entry == "cierre1" else 5
            side = None
            for b0 in range(a + 5, ex - tf, tf):
                cc = C[b0:b0 + tf][~np.isnan(C[b0:b0 + tf])]
                if len(cc) and (cc[-1] > hi or cc[-1] < lo):
                    side, kin, kind = (1 if cc[-1] > hi else -1), b0 + tf, "market"
                    break
            if side is None:
                continue
        edge = hi if side == 1 else lo
        S = max(R, 30.0)
        stop = rnd(edge - side * S - side * tk)
        tgt = rnd(edge + side * (0.75 * R if tmode == "0.75R" else S))
        if kind == "stop":
            o = Order(side, "stop", kin, stop, tgt, ex, level=rnd(edge + side * tk), k_last=kin + 1)
        else:
            o = Order(side, "market", kin, stop, tgt, ex)
        f = simulate(date, m, ex + 1, o, c)
        if f is not None:
            fills.append(f)
    return trades_frame(fills, c)


def main():
    D, _ = load_days("MNQ")
    per = periods("intradia", include_test=True)
    exp = new_experiment("cierre_vela_ruptura")
    rows = []
    c = fut("MNQ", "base")
    for (a, nm), tm, en in itertools.product(((175, "LONDRES 8:55"), (505, "DATO 14:25"), (565, "APERTURA 15:25")),
                                             ("0.75R", "1S"), ("ruptura", "cierre1", "cierre5")):
        t = run(D, a, c, en, tm)
        rows.append(dict(ventana=nm, objetivo=tm, entrada=en, ops_año=len(t) / 8.75,
                         entrada_vs_nivel_pts=np.nan, **stats(t, per, c)))
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    pd.set_option("display.width", 260)
    print(r[["ventana", "objetivo", "entrada", "ops_año", "dev", "val", "prueba", "neto_año", "acierto", "riesgo_med",
             "años_pos", "pasa"]].round(2).to_string(index=False))
    write_manifest(exp, experimento="entrada en la ruptura vs al cierre de la vela que rompe", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
