"""Continuación de run_playbook_cierre_sma.py. Petición añadida: "si la vela es grande no ejecutas".
Misma entrada al CIERRE fuera del rango con filtro SMA 200 ("primera" o "solo lado", 1 o 5 min), y además se descarta la
señal si la vela que cierra fuera es GRANDE (fijado antes de ver resultados):
   grande_R   su tamaño (máximo − mínimo) es mayor que el rango de la vela de 5 min
   grande_S2  su tamaño es mayor que la mitad del stop (0,5 × S, ≈ 15 pts)
Si la vela es grande, no se opera ese día (con "solo lado" se sigue esperando otra vela que cierre fuera y no sea grande).
Mismos stops, objetivos y plazo. Selección: neto > 0 en dev Y val (coste base), n_val >= 30."""
import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import load_days, stats
from run_playbook_sma200 import smas
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

WINS = [("DATO 14:25", 505, "R", 0.75), ("APERTURA 15:25", 565, "S", 1.0), ("APERTURA 15:25", 565, "S", 0.7)]


def run(D, SM, a, base, frac, c, tf, filtro, grande):
    tk = c.tick
    rnd = lambda x: round(x / tk) * tk
    fills = []
    for d, m in D:
        H, L, C = m[:, 1], m[:, 2], m[:, 3]
        if np.isnan(H[a:a + 5]).sum() > 2:
            continue
        hi, lo = np.nanmax(H[a:a + 5]), np.nanmin(L[a:a + 5])
        R = hi - lo
        if R <= 0:
            continue
        ex = a + 5 + 210
        S = max(R, 30.0)
        lim = R if grande == "grande_R" else 0.5 * S
        sma = SM[d][0 if tf == 1 else 1]
        sig = None
        for kc in range(a + 5 + tf - 1, ex - 1, tf):
            sl = slice(kc - tf + 1, kc + 1)
            x = C[sl][~np.isnan(C[sl])]
            if not len(x):
                continue
            cl = x[-1]
            if lo <= cl <= hi:
                continue
            side = 1 if cl > hi else -1
            ok = (side == 1 and cl > sma[kc]) or (side == -1 and cl < sma[kc])
            big = np.nanmax(H[sl]) - np.nanmin(L[sl]) > lim
            if filtro == "primera" and (not ok or big):
                break
            if ok and not big:
                sig = (kc + 1, side)
                break
        if sig is None:
            continue
        k, side = sig
        edge = hi if side == 1 else lo
        o = Order(side, "market", k, rnd(edge - side * S - side * tk),
                  rnd(edge + side * frac * (R if base == "R" else S)), ex)
        f = simulate(d, m, ex + 1, o, c)
        if f is not None:
            fills.append(f)
    return trades_frame(fills, c)


def main():
    D, _ = load_days("MNQ")
    SM = smas(D)
    per = periods("intradia", include_test=True)
    c = fut("MNQ", "base")
    exp = new_experiment("playbook_cierre_sma200_vela_grande")
    rows = []
    for w, a, base, frac in WINS:
        for tf in (1, 5):
            for fl in ("primera", "solo_lado"):
                for gr in ("grande_R", "grande_S2"):
                    t = run(D, SM, a, base, frac, c, tf, fl, gr)
                    g = t.gross_pts
                    eq = t.pnl.cumsum()
                    rows.append(dict(ventana=w, objetivo=f"{frac} × {'rango' if base == 'R' else 'stop'}",
                                     entrada=f"cierre {tf} min · SMA {fl} · sin vela {gr}", ops_año=len(t) / 8.75,
                                     gana=(g > 0).mean(), gana_usd=t.pnl[t.pnl > 0].mean(),
                                     pierde_usd=t.pnl[t.pnl < 0].mean(), dd=(eq - eq.cummax()).min(),
                                     **stats(t, per, c)))
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="playbook: cierre fuera + SMA 200 + sin vela grande", reglas=__doc__)
    pd.set_option("display.width", 280, "display.max_colwidth", 50)
    print(r[["ventana", "objetivo", "entrada", "ops_año", "gana", "gana_usd", "pierde_usd", "dev", "val", "prueba",
             "neto_año", "años_pos", "dd", "pasa"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
