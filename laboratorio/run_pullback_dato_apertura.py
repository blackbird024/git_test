"""Pregunta del usuario: "¿y espero el pullback?" (y "la de 8:55": 2:55 ET, añadida después) en las velas de 5 min del dato (8:25 ET, 14:25 Italia) y de la apertura
(9:25 ET, 15:25 Italia). MNQ. Reglas fijadas antes de ver resultados:
  ruptura   orden stop 1 tick fuera del rango (como el indicador)
  pullback  tras la 1.ª ruptura, orden LÍMITE en el nivel roto (se llena si el precio vuelve a cruzarlo 1 tick); se
            cancela si antes toca el objetivo o el stop, o al plazo
  pullback_mitad  orden límite en la mitad del rango (pullback más profundo), mismas cancelaciones
Stop a S = máx(R, 30 pts) del nivel roto. Objetivo: 0,75 R (dato) y 1 S (apertura), más el otro de cada uno.
Plazo 3,5 h tras cerrar el rango. Coste base (y alto en el CSV)."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import lab, load_days, setup, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest


def run(D, a, c, entry, tmode):
    tk = c.tick
    rnd = lambda x: round(x / tk) * tk
    fills, señales = [], 0
    for date, m in D:
        st = setup(m, a, 5, tk)
        if st is None or st == "mismo":
            continue
        hi, lo, R, side, k, ex = st
        señales += 1
        edge = hi if side == 1 else lo
        S = max(R, 30.0)
        stop = rnd(edge - side * S - side * tk)
        tgt = rnd(edge + side * (0.75 * R if tmode == "0.75R" else S))
        if entry == "ruptura":
            o = Order(side, "stop", k, stop, tgt, ex, level=rnd(edge + side * tk), k_last=k + 1)
        else:
            lvl = edge if entry == "pullback" else rnd((hi + lo) / 2)
            H, L = m[k:ex, 1], m[k:ex, 2]
            hit = np.nonzero(H >= tgt if side == 1 else L <= tgt)[0]
            klast = k + (hit[0] if len(hit) else ex - k)
            if klast <= k + 1:
                continue
            o = Order(side, "limit", k + 1, stop, tgt, ex, level=lvl, k_last=klast)
        f = simulate(date, m, ex + 1, o, c)
        if f is not None:
            fills.append(f)
    return trades_frame(fills, c), señales


def main():
    D, _ = load_days("MNQ")
    per = periods("intradia", include_test=True)
    exp = new_experiment("pullback_dato_apertura")
    rows = []
    for (a, nm), tm, en, cn in itertools.product(((175, "LONDRES 8:55"), (505, "DATO 14:25"), (565, "APERTURA 15:25")), ("0.75R", "1S"),
                                                 ("ruptura", "pullback", "pullback_mitad"), ("base", "alto")):
        c = fut("MNQ", cn)
        t, n_sig = run(D, a, c, en, tm)
        rows.append(dict(ventana=nm, objetivo=tm, entrada=en, coste=cn, se_llena=len(t) / n_sig,
                         ops_año=len(t) / 8.75, **stats(t, per, c)))
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    pd.set_option("display.width", 260)
    print(r[r.coste == "base"][["ventana", "objetivo", "entrada", "se_llena", "ops_año", "dev", "val", "prueba",
                                "neto_año", "acierto", "riesgo_med", "años_pos", "pasa"]].round(2).to_string(index=False))
    write_manifest(exp, experimento="ruptura vs pullback en las velas del dato y la apertura", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
