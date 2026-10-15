"""Petición: "buscaré beneficio 1:0,7" en el playbook. Mismas reglas (vela 5 min 8:25 y 9:25 ET, OCO stop 1 tick fuera,
stop S = máx(rango, 30 pts) desde el nivel roto, plazo 3,5 h) con objetivo = 0,7 × S, comparado con los objetivos actuales
(DATO 0,75 × rango; APERTURA 1 × S). Selección: neto > 0 en dev Y val (coste base), n_val >= 30."""
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import load_days, setup, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest


def run(D, a, base, frac, c):
    tk = c.tick
    rnd = lambda x: round(x / tk) * tk
    fills = []
    for d, m in D:
        st = setup(m, a, 5, tk)
        if st is None or st == "mismo":
            continue
        hi, lo, R, side, k, ex = st
        edge = hi if side == 1 else lo
        S = max(R, 30.0)
        o = Order(side, "stop", k, rnd(edge - side * S - side * tk), rnd(edge + side * frac * (R if base == "R" else S)),
                  ex, level=rnd(edge + side * tk), k_last=k + 1)
        f = simulate(d, m, ex + 1, o, c)
        if f is not None:
            fills.append(f)
    return trades_frame(fills, c)


def main():
    D, _ = load_days("MNQ")
    per = periods("intradia", include_test=True)
    c = fut("MNQ", "base")
    exp = new_experiment("playbook_objetivo_07")
    rows = []
    for w, a, actual in (("DATO 14:25", 505, ("R", 0.75)), ("APERTURA 15:25", 565, ("S", 1.0))):
        for nombre, (base, frac) in (("actual " + f"{actual[1]} × {'rango' if actual[0] == 'R' else 'stop'}", actual),
                                     ("0,7 × stop (1:0,7)", ("S", 0.7))):
            t = run(D, a, base, frac, c)
            g = t.gross_pts
            mo = t.groupby(t.date.dt.to_period("M")).pnl.sum()
            eq = t.pnl.cumsum()
            rows.append(dict(ventana=w, objetivo=nombre, ops_año=len(t) / 8.75, gana=(g > 0).mean(),
                             gana_usd=t.pnl[t.pnl > 0].mean(), pierde_usd=t.pnl[t.pnl < 0].mean(),
                             meses_pos=(mo > 0).mean(), dd_max=(eq - eq.cummax()).min(), **stats(t, per, c)))
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="playbook con objetivo 0,7 × stop", reglas=__doc__)
    pd.set_option("display.width", 260)
    print(r[["ventana", "objetivo", "ops_año", "gana", "gana_usd", "pierde_usd", "dev", "val", "prueba", "neto_año",
             "años_pos", "meses_pos", "dd_max", "pasa"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
