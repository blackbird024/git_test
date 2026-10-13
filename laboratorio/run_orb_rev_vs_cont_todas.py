"""Reversión vs continuación tras la primera ruptura del rango de cada vela de 15 min, de 0:00 a 14:00 ET (6:00-20:00
Italia la mayor parte del año). Misma carrera que run_orb_rev_vs_cont.py con distancias iguales: continuación = nivel roto
+ 1 rango; reversión = otro lado del rango; plazo 3,5 h tras cerrar el rango (máx. 15:55 ET). NQ 2018-2026."""
import numpy as np
import pandas as pd

from data.loaders import sessions
from run_orb_ventanas_edgeful import et_days, first_breaks
from validation.runner import new_experiment, write_manifest


def race(m, a):
    ex = min(a + 15 + 210, 955)
    r = first_breaks(m, a)
    if r is None:
        return None
    hi, lo, ku, kd = r
    R = hi - lo
    cand = [(k, s) for k, s in ((ku, 1), (kd, -1)) if k is not None and k < ex]
    if R <= 0 or not cand or (ku is not None and ku == kd):
        return None
    k, side = min(cand)
    H, L = m[:, 1], m[:, 2]
    tgt = (hi + R) if side == 1 else (lo - R)
    opp = lo if side == 1 else hi
    for j in range(k, ex):
        if np.isnan(H[j]):
            continue
        c = (H[j] >= tgt) if side == 1 else (L[j] <= tgt)
        rv = (L[j] <= opp) if side == 1 else (H[j] >= opp)
        if c and rv:
            return "ambos"
        if c:
            return "continua"
        if rv:
            return "gira"
    return "nada"


def main():
    D = et_days(sessions())
    exp = new_experiment("orb15_gira_o_continua_todo_el_dia")
    rows = []
    for a in range(0, 841, 15):
        for date, m in D:
            r = race(m, a)
            if r is not None:
                rows.append(dict(a=a, date=date, res=r))
    df = pd.DataFrame(rows)
    df.to_csv(exp / "carreras.csv.gz", index=False)
    out = []
    for a, g in df.groupby("a"):
        y = g.groupby(g.date.dt.year).res.agg(lambda s: (s == "continua").mean() - (s == "gira").mean())
        out.append(dict(ny=f"{a // 60}:{a % 60:02d}", italia=f"{(a // 60 + 6) % 24}:{a % 60:02d}", dias=len(g),
                        continua=(g.res == "continua").mean() * 100, gira=(g.res == "gira").mean() * 100,
                        nada=(g.res == "nada").mean() * 100,
                        dif=((g.res == "continua").mean() - (g.res == "gira").mean()) * 100,
                        años_continua_gana=int((y > 0).sum()), años_gira_gana=int((y < 0).sum())))
    o = pd.DataFrame(out)
    o.to_csv(exp / "resumen.csv", index=False)
    pd.set_option("display.width", 200, "display.max_rows", 100)
    print(o.round(1).to_string(index=False))
    write_manifest(exp, experimento="gira o continúa tras la ruptura de cada vela de 15 min", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
