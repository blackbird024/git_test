"""Petición: marcar el rango de 15:00 a 15:29 Italia (9:00-9:29 ET, 30 velas de 1 min, antes de la apertura) y, cuando
rompa, entrar A FAVOR con el stop al otro lado del rango. Reglas fijadas antes de ver resultados (MNQ 2018-2026):
  Entrada (variantes): RUPTURA = orden stop OCO 1 tick fuera (doble ruptura en el mismo minuto = no se opera);
                       CIERRE  = primera vela de 1 min que CIERRA fuera del rango → a mercado en la apertura siguiente.
  Stop: otro lado del rango ∓ 1 tick (variante: como mínimo a 30 pts del nivel roto).
  Objetivo: 0,5 R, 0,75 R o 1 R medido desde el nivel roto (R = tamaño del rango), o 1:1 respecto al stop.
  Plazo: hasta las 13:00 ET (19:00 Italia). Una operación al día.
Gana / pierde = resultado bruto en puntos. Selección: neto > 0 en dev Y val (coste base), n_val >= 30."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import load_days, setup, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

A, DUR, EX = 540, 30, 780


def run(D, c, entrada, minstop, obj):
    tk = c.tick
    rnd = lambda x: round(x / tk) * tk
    fills = []
    for d, m in D:
        H, L, C = m[:, 1], m[:, 2], m[:, 3]
        if np.isnan(H[A:A + DUR]).sum() > DUR / 2:
            continue
        hi, lo = np.nanmax(H[A:A + DUR]), np.nanmin(L[A:A + DUR])
        R = hi - lo
        if R <= 0:
            continue
        if entrada == "ruptura":
            st = setup(m, A, DUR, tk)
            if st is None or st == "mismo":
                continue
            _, _, _, side, k, _ = st
        else:
            cc = C[A + DUR:EX]
            out = np.nonzero((cc > hi) | (cc < lo))[0]
            if not len(out):
                continue
            k = A + DUR + out[0]
            side = 1 if C[k] > hi else -1
            k += 1
        edge = hi if side == 1 else lo
        S = max(R, minstop)
        stop = rnd(edge - side * S - side * tk)
        if obj == "1:1":
            o = Order(side, "stop" if entrada == "ruptura" else "market", k, stop, None, EX, target_r=1.0,
                      level=rnd(edge + side * tk), k_last=k + 1)
        else:
            o = Order(side, "stop" if entrada == "ruptura" else "market", k, stop, rnd(edge + side * obj * R), EX,
                      level=rnd(edge + side * tk), k_last=k + 1)
        f = simulate(d, m, EX + 1, o, c)
        if f is not None:
            fills.append(f)
    return trades_frame(fills, c)


def main():
    D, _ = load_days("MNQ")
    per = periods("intradia", include_test=True)
    c = fut("MNQ", "base")
    exp = new_experiment("rango_15_1529")
    rows = []
    rr = [np.nanmax(m[A:A + DUR, 1]) - np.nanmin(m[A:A + DUR, 2]) for _, m in D]
    print("rango mediano 15:00-15:29 Italia:", np.nanmedian(rr), "pts")
    for entrada, minstop, obj in itertools.product(("ruptura", "cierre"), (0.0, 30.0), (0.5, 0.75, 1.0, "1:1")):
        t = run(D, c, entrada, minstop, obj)
        g = t.gross_pts
        rows.append(dict(entrada=entrada, stop="otro lado" if minstop == 0 else "otro lado, mín 30", objetivo=
                         obj if obj == "1:1" else f"{obj} R", ops_año=len(t) / 8.75, gana=(g > 0).mean(),
                         pierde=(g < 0).mean(), gana_usd=2 * g[g > 0].mean(), pierde_usd=2 * g[g < 0].mean(),
                         **stats(t, per, c)))
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="rango 15:00-15:29 Italia, ruptura a favor", reglas=__doc__,
                   seleccionadas=r[r.pasa].index.tolist())
    pd.set_option("display.width", 280)
    print(r[["entrada", "stop", "objetivo", "ops_año", "gana", "pierde", "gana_usd", "pierde_usd", "dev", "val",
             "prueba", "neto_año", "años_pos", "pasa"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
