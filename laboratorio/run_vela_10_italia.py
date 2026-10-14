"""Pregunta del usuario: "dame otra vela, por ejemplo la de las 10:00 hora de Italia" (= 4:00 ET la mayor parte del año;
a esa hora salen datos europeos). Velas de 5 min 9:55-10:00 y 10:00-10:05 Italia (3:55 y 4:00 ET) en MNQ y MGC.
Mismas reglas que el playbook (run_stop30.py): ruptura a favor con orden stop OCO; modos:
  orig      stop otro lado, objetivo 0,75 R      min30_R   stop mín. 30 pts (NQ), objetivo 0,75 R
  min30_1S  stop mín. 30 pts, objetivo 1 S (1:1)
Además, estadística gira/continúa (de run_rangos_multi_tf / run_oro_rangos). Coste base."""
import pandas as pd

from execution_costs.costs import fut
from rangos_lib import load_days, stats
from run_stop30 import run
from validation.runner import new_experiment, periods, write_manifest


def main():
    per = periods("intradia", include_test=True)
    exp = new_experiment("vela_10_italia")
    rows = []
    for sym, modes in (("MNQ", ("orig", "min30_R", "min30_1S")), ("MGC", ("orig",))):
        D, _ = load_days(sym)
        c = fut(sym, "base")
        for a, nm in ((235, "9:55-10:00"), (240, "10:00-10:05")):
            for md in modes:
                t = run(D, 5, a, c, md)
                rows.append(dict(mercado=sym, vela=nm, modo=md, ops_año=len(t) / 8.75, **stats(t, per, c)))
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    pd.set_option("display.width", 240)
    print(r[["mercado", "vela", "modo", "ops_año", "dev", "val", "prueba", "neto_año", "acierto", "riesgo_med",
             "años_pos", "pasa"]].round(2).to_string(index=False))
    o = pd.read_csv("experiments/20261013_182936_rangos_multi_tf/resumen.csv")
    g = pd.read_csv("experiments/20261013_184213_oro_rangos/fase1_resumen.csv")
    for a in (235, 240):
        x = o[(o.tf == 5) & (o.a == a)].iloc[0]
        y = g[(g.tf == 5) & (g.a == a)].iloc[0]
        print(f"{a}: NQ continúa {x.continua:.0f} / gira {x.gira:.0f} ({x.años_c}/{x.años_g} años) · "
              f"oro {y.continua:.0f} / {y.gira:.0f} ({y.años_c}/{y.años_g})")
    write_manifest(exp, experimento="vela de 5 min de las 10:00 Italia", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
