"""Petición del usuario: las 57 velas de 15 min (0:00-14:00 ET) con ruptura a favor y objetivo 0,5 / 0,75 / 1 rango.
Mismas reglas que run_rangos_objetivo_parcial.py (orden stop OCO, stop = otro lado, plazo 3,5 h, mismo minuto = no se opera).
Coste base y alto. Regla: dev>0 y val>0 (base) → se mira la prueba."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from data.loaders import TICK, sessions
from execution_costs.costs import mnq
from run_orb_ventanas_edgeful import et_days
from run_rangos_multi_tf import setup
from validation.runner import new_experiment, periods, split, write_manifest
from validation.metrics import trades_frame


def main():
    D = et_days(sessions())
    per = periods("intradia", include_test=True)
    exp = new_experiment("rangos15_objetivos")
    rows = []
    for a in range(0, 841, 15):
        sts = [(date, m, setup(m, a, 15)) for date, m in D]
        sts = [(d, m, s) for d, m, s in sts if s is not None and s != "mismo"]
        for frac, cn in itertools.product((0.5, 0.75, 1.0), ("base", "alto")):
            c = mnq(cn)
            fills = []
            for date, m, (hi, lo, R, side, k, ex) in sts:
                tgt = hi + frac * R if side == 1 else lo - frac * R
                o = Order(side, "stop", k, lo - TICK if side == 1 else hi + TICK, round(tgt / TICK) * TICK, ex,
                          level=hi + TICK if side == 1 else lo - TICK, k_last=k + 1)
                f = simulate(date, m, ex + 1, o, c)
                if f is not None:
                    fills.append(f)
            t = trades_frame(fills, c)
            sp = split(t, per)
            rows.append(dict(ny=f"{a // 60}:{a % 60:02d}", italia=f"{(a // 60 + 6) % 24}:{a % 60:02d}",
                             objetivo=frac, coste=cn, n=len(t), dev=sp["desarrollo"].pnl.mean(),
                             val=sp["validacion"].pnl.mean(), prueba=sp["prueba"].pnl.mean(),
                             neto_año=t.pnl.sum() / 8.75, acierto=(t.pnl > 0).mean(),
                             años_pos=int((t.groupby(t.date.dt.year).pnl.sum() > 0).sum())))
        print(a, "ok", flush=True)
    r = pd.DataFrame(rows)
    r.to_csv(exp / "resultados.csv", index=False)
    b = r[r.coste == "base"].copy()
    b["pasa"] = (b.dev > 0) & (b.val > 0)
    b["tres_pos"] = b.pasa & (b.prueba > 0)
    pd.set_option("display.width", 220, "display.max_rows", 200)
    print("Ventanas/objetivos que pasan la regla (dev>0 y val>0), coste base:")
    print(b[b.pasa].round(2).to_string(index=False))
    a_ = r[r.coste == "alto"].set_index(["ny", "objetivo"])
    print("\nLas mismas con coste alto:")
    print(a_.loc[[(x, y) for x, y in zip(b[b.pasa].ny, b[b.pasa].objetivo)]].round(2).to_string())
    print("\nResumen por objetivo (coste base): nº de ventanas con neto>0 / 57, y con los 3 periodos > 0")
    print(b.groupby("objetivo").agg(neto_pos=("neto_año", lambda s: int((s > 0).sum())), tres_pos=("tres_pos", "sum"),
                                    neto_medio_año=("neto_año", "mean")).round(0).to_string())
    write_manifest(exp, experimento="57 velas de 15 min con objetivo 0,5/0,75/1 rango", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
