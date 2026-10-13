"""Números para el playbook: combinación DATO (5 min 8:25 ET, objetivo 0,75 R) + APERTURA (5 min 9:25 ET, objetivo 1 S),
stop mínimo 30 pts, coste base, 1 MNQ (reglas de run_stop30.py). Curva diaria, rachas, meses, caída máxima y una
simulación tipo Topstep con remuestreo de días (colchón 993 $ = balance 50.555 − suelo 49.561,70; objetivo +3.000 $
desde el inicio de la cuenta: con el balance actual faltan ~2.445 $). No es una predicción: es el backtest remuestreado."""
import numpy as np
import pandas as pd

from execution_costs.costs import fut
from rangos_lib import load_days
from run_stop30 import run
from validation.runner import new_experiment, write_manifest


def main():
    D, _ = load_days("MNQ")
    c = fut("MNQ", "base")
    import run_stop30 as rs
    tD = rs.run(D, 5, 505, c, "min30_R")
    tA = rs.run(D, 5, 565, c, "min30_1S")
    tD["setup"], tA["setup"] = "DATO", "APERTURA"
    t = pd.concat([tD, tA]).sort_values("date")
    exp = new_experiment("playbook_numeros")
    t.to_csv(exp / "ops.csv.gz", index=False)
    days = pd.DatetimeIndex(sorted({d for d, _ in D}))
    dp = t.groupby("date").pnl.sum().reindex(days, fill_value=0.0)
    eq = dp.cumsum()
    dd = (eq.cummax() - eq).max()
    mon = dp.resample("ME").sum()
    yr = dp.resample("YE").sum()
    lose = (t.pnl < 0).astype(int).to_numpy()
    run_, best = 0, 0
    for x in lose:
        run_ = run_ + 1 if x else 0
        best = max(best, run_)
    out = dict(ops=len(t), ops_año=len(t) / 8.75, neto_total=t.pnl.sum(), neto_año=t.pnl.sum() / 8.75,
               acierto=(t.pnl > 0).mean(), gan_media=t.pnl[t.pnl > 0].mean(), perd_media=t.pnl[t.pnl < 0].mean(),
               peor_dia=dp.min(), mejor_dia=dp.max(), dd_max=dd, racha_perdedora_max=best,
               meses_pos=(mon > 0).mean(), peor_mes=mon.min(), mejor_mes=mon.max(), neto_mes_medio=mon.mean(),
               dias_con_op=(dp != 0).mean())
    print({k: round(v, 3) for k, v in out.items()})
    print("Por año:", yr.round(0).to_dict())
    print("Por setup:", t.groupby("setup").pnl.agg(["count", "sum", "mean"]).round(1).to_dict())
    # Topstep: remuestreo de días hábiles (bloques de 5 días) — prob. de llegar a +objetivo antes de perder el colchón
    rng = np.random.default_rng(7)
    arr = dp.to_numpy()
    res = []
    for mnq in (1, 2, 3, 4):
        for obj, colchon in ((2445.0, 993.3), (3000.0, 2000.0)):
            ok = fail = 0
            dias = []
            for _ in range(4000):
                pnl, d = 0.0, 0
                while True:
                    s = rng.integers(0, len(arr) - 5)
                    for x in arr[s:s + 5]:
                        pnl += x * mnq
                        d += 1
                        if pnl >= obj or pnl <= -colchon or d > 500:
                            break
                    if pnl >= obj or pnl <= -colchon or d > 500:
                        break
                if pnl >= obj:
                    ok += 1
                    dias.append(d)
                elif pnl <= -colchon:
                    fail += 1
            res.append(dict(mnq=mnq, objetivo=obj, colchon=colchon, aprueba=ok / 4000, pierde=fail / 4000,
                            dias_medianos=float(np.median(dias)) if dias else np.nan))
    r = pd.DataFrame(res)
    r.to_csv(exp / "topstep_sim.csv", index=False)
    print(r.round(3).to_string(index=False))
    pd.Series(out).to_csv(exp / "resumen.csv")
    write_manifest(exp, experimento="números del playbook (DATO + APERTURA)", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
