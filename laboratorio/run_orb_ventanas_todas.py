"""Ampliación de run_orb_ventanas_edgeful.py a las 37 ventanas de 15 min (3:00-12:00 ET): doble ruptura en 3,5 h
(2018-2026) y estrategia "el otro lado es el objetivo" (entrada en contra en la primera ruptura, objetivo el otro lado,
stop 1 × rango; plazo 3,5 h tras cerrar el rango, como muy tarde 15:55 ET). Mismas reglas, fijadas antes."""
import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from data.loaders import sessions
from execution_costs.costs import mnq
from run_orb_ventanas_edgeful import NE, et_days, first_breaks
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, split, write_manifest


def main():
    S = sessions()
    D = et_days(S)
    per = periods("intradia", include_test=True)
    exp = new_experiment("orb_37_ventanas")
    c = mnq("base")
    rows = []
    for a in range(180, 721, 15):
        ex = min(a + 15 + 210, 955)
        fills, dbl, rngs, n = [], 0, [], 0
        for date, m in D:
            r = first_breaks(m, a)
            if r is None:
                continue
            hi, lo, ku, kd = r
            R = hi - lo
            if R <= 0:
                continue
            n += 1
            rngs.append(R)
            dbl += ku is not None and kd is not None and max(ku, kd) < a + 15 + 210
            cand = [(k, s) for k, s in ((ku, -1), (kd, 1)) if k is not None and k < ex]
            if not cand or (ku is not None and kd is not None and ku == kd):
                continue
            k, side = min(cand)
            ref = hi if side == -1 else lo
            f = simulate(date, m, ex + 1, Order(side, "market", k + 1, ref - side * R, lo if side == -1 else hi, ex), c)
            if f is not None:
                fills.append(f)
        t = trades_frame(fills, c)
        sp = split(t, per)
        rows.append(dict(ventana=f"{a // 60}:{a % 60:02d}", italia=f"{(a // 60 + 6) % 24}:{a % 60:02d}",
                         doble_3h5=dbl / n, rango_med_pts=np.median(rngs), n=len(t),
                         dev=sp["desarrollo"].pnl.mean(), val=sp["validacion"].pnl.mean(), prueba=sp["prueba"].pnl.mean(),
                         total=t.pnl.mean(), neto_año=t.pnl.sum() / 8.75, acierto=(t.pnl > 0).mean(),
                         R_bruto=(t.gross_pts * 2 / t.risk_usd).mean()))
        print(rows[-1]["ventana"], "ok", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(exp / "ventanas.csv", index=False)
    write_manifest(exp, experimento="37 ventanas ORB 15 min: doble ruptura y 'el otro lado es el objetivo'", reglas=__doc__)
    pd.set_option("display.width", 250, "display.max_rows", 100)
    df["3_periodos_+"] = (df.dev > 0) & (df.val > 0) & (df.prueba > 0)
    print(df.round({"doble_3h5": 3, "rango_med_pts": 1, "dev": 1, "val": 1, "prueba": 1, "total": 2, "neto_año": 0,
                    "acierto": 3, "R_bruto": 3}).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
