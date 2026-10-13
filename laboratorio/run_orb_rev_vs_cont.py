"""¿Qué se da más tras la primera ruptura del ORB de 15 min: reversión o continuación? (NQ 2018-2026, minuto a minuto)
Tras la primera ruptura (1 tick fuera), carrera hasta el plazo (3,5 h tras cerrar el rango, máx. 15:55 ET):
  continuación = llega a nivel roto + k × rango ; reversión = llega al otro lado del rango. Mismo minuto → "ambos".
k = 0,5 y 1 (con k = 1 las dos distancias desde el nivel roto son iguales)."""
import numpy as np
import pandas as pd

from data.loaders import sessions
from run_orb_ventanas_edgeful import et_days, first_breaks
from validation.runner import new_experiment, write_manifest

WINS = {"Londres 9:00 Italia (3:00 ET)": 180, "14:30 Italia (8:30 ET)": 510, "NY 15:30 Italia (9:30 ET)": 570}


def main():
    D = et_days(sessions())
    exp = new_experiment("orb_reversion_vs_continuacion")
    rows = []
    for name, a in WINS.items():
        ex = min(a + 15 + 210, 955)
        for date, m in D:
            r = first_breaks(m, a)
            if r is None:
                continue
            hi, lo, ku, kd = r
            R = hi - lo
            cand = [(k, s) for k, s in ((ku, 1), (kd, -1)) if k is not None and k < ex]
            if R <= 0 or not cand or (ku is not None and ku == kd):
                continue
            k, side = min(cand)
            H, L = m[:, 1], m[:, 2]
            edge, opp = (hi, lo) if side == 1 else (lo, hi)
            out = {}
            for kk in (0.5, 1.0):
                tgt = edge + side * kk * R
                res = "nada"
                for j in range(k, ex):
                    if np.isnan(H[j]):
                        continue
                    c = (H[j] >= tgt) if side == 1 else (L[j] <= tgt)
                    rv = (L[j] <= opp) if side == 1 else (H[j] >= opp)
                    if c and rv:
                        res = "ambos"; break
                    if c:
                        res = "continuacion"; break
                    if rv:
                        res = "reversion"; break
                out[kk] = res
            rows.append(dict(ventana=name, date=date, lado=side, cont05=out[0.5], cont1=out[1.0]))
    df = pd.DataFrame(rows)
    df.to_csv(exp / "carreras.csv.gz", index=False)
    pd.set_option("display.width", 200)
    for col, lab in (("cont1", "continuación = +1 rango"), ("cont05", "continuación = +0,5 rango")):
        print(f"\n{lab} vs reversión al otro lado (% de días con ruptura):")
        print((pd.crosstab(df.ventana, df[col], normalize="index") * 100).round(1).to_string())
    print("\nPor año (continuación +1 rango, % continuación / % reversión):")
    g = df.groupby(["ventana", df.date.dt.year]).cont1.agg(lambda s: f"{(s=='continuacion').mean()*100:.0f}/{(s=='reversion').mean()*100:.0f}")
    print(g.unstack().to_string())
    write_manifest(exp, experimento="reversión vs continuación tras la ruptura del ORB 15 min", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
