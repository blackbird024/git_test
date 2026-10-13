"""Petición del usuario: objetivo de medio rango o 3/4 de rango (además de 1 rango, para comparar) en la ruptura A FAVOR
del rango de las velas que terminan a las 8:30 ET (dato macro, 14:30 Italia) y a las 9:30 ET (apertura NY, 15:30 Italia),
en 5, 15, 30 y 60 min. Mismas reglas que run_rangos_multi_tf.py (orden stop OCO 1 tick fuera, stop = otro lado del rango,
plazo máx(3,5 h, 2 × vela), si rompe los dos lados en el mismo minuto no se opera). Costes base, alto y alto + 4 ticks.
Ventanas elegidas A POSTERIORI (familia "dato/apertura" de los estudios anteriores): la prueba 2025-26 no es virgen."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from data.loaders import TICK, sessions
from execution_costs.costs import mnq
from run_orb_ventanas_edgeful import et_days
from run_rangos_multi_tf import setup
from validation.metrics import block_bootstrap_mean, trades_frame
from validation.runner import new_experiment, periods, split, write_manifest

WINS = [(5, 505), (15, 495), (30, 480), (60, 450), (5, 565), (15, 555), (30, 540), (60, 510)]


def main():
    D = et_days(sessions())
    per = periods("intradia", include_test=True)
    exp = new_experiment("rangos_objetivo_parcial")
    costs = {"base": mnq("base"), "alto": mnq("alto"), "alto+4": mnq("alto", extra_slip_ticks=4)}
    res = []
    for (dur, a), frac in itertools.product(WINS, (0.5, 0.75, 1.0)):
        fin = a + dur
        name = f"{dur} min {a // 60}:{a % 60:02d} ET ({(a // 60 + 6) % 24}:{a % 60:02d} Italia) → {'dato 8:30' if fin == 510 else 'apertura 9:30'}"
        for cn, c in costs.items():
            fills = []
            for date, m in D:
                st = setup(m, a, dur)
                if st is None or st == "mismo":
                    continue
                hi, lo, R, side, k, ex = st
                tgt = hi + frac * R if side == 1 else lo - frac * R
                o = Order(side, "stop", k, lo - TICK if side == 1 else hi + TICK, round(tgt / TICK) * TICK, ex,
                          level=hi + TICK if side == 1 else lo - TICK, k_last=k + 1)
                f = simulate(date, m, ex + 1, o, c)
                if f is not None:
                    fills.append(f)
            t = trades_frame(fills, c)
            sp = split(t, per)
            fm = t[t.date >= "2022-01-01"]
            lo_, hi_ = block_bootstrap_mean(fm.pnl.to_numpy())
            srt = fm.pnl.sort_values(ascending=False)
            res.append(dict(ventana=name, objetivo=f"{frac:g} rango", coste=cn, n=len(t),
                            dev=sp["desarrollo"].pnl.mean(), val=sp["validacion"].pnl.mean(),
                            prueba=sp["prueba"].pnl.mean(), ic90_FM=f"[{lo_:.1f}; {hi_:.1f}]",
                            top10=100 * srt[:10].sum() / fm.pnl.sum() if fm.pnl.sum() > 0 else np.nan,
                            neto_año=t.pnl.sum() / 8.75, acierto=(t.pnl > 0).mean(), riesgo_med=t.risk_usd.median(),
                            años_pos=int((t.groupby(t.date.dt.year).pnl.sum() > 0).sum()),
                            pasa=bool(sp["desarrollo"].pnl.mean() > 0 and sp["validacion"].pnl.mean() > 0)))
            if cn == "base":
                t.to_csv(exp / f"ops_{dur}_{a}_{frac}.csv.gz", index=False)
        print(name, frac, "ok", flush=True)
    r = pd.DataFrame(res)
    r.to_csv(exp / "resultados.csv", index=False)
    pd.set_option("display.width", 280, "display.max_rows", 200, "display.max_colwidth", 60)
    for cn in costs:
        print(f"\n== coste {cn} ==")
        print(r[r.coste == cn].drop(columns=["coste"]).round(2).to_string(index=False))
    write_manifest(exp, experimento="objetivo 0,5/0,75/1 rango en rangos que terminan en el dato o la apertura", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
