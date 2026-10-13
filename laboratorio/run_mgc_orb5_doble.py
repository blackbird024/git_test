"""Short de edgeful: "MGC 5 min ORB (9:30-9:35 ET), doble ruptura 101/128 = 78,9 % (25-feb-2026 a 24-ago-2026),
'the one setup that's held up for 2 years'". Reproducción y prueba como estrategia en oro (GC.v.0 como MGC).
Doble ruptura = se superan máximo y mínimo del rango (por mecha, 1 tick) entre 9:35 y 16:00 ET.
Estrategia "el otro lado es el objetivo" (reglas fijadas antes): en la primera ruptura se entra EN CONTRA a mercado en el
minuto siguiente; objetivo = el otro lado; stop = 1 rango más allá del nivel roto (y variante con stop mínimo 5 $ de
recorrido = 0,5 pts... no: variante con stop mínimo de 3 pts); salida 15:55 ET. Costes MGC base/alto."""
import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import load_days, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

A, TK = 570, 0.1


def main():
    D, excl = load_days("MGC")
    per = periods("intradia", include_test=True)
    exp = new_experiment("mgc_orb5_doble_ruptura")
    rows = []
    for date, m in D:
        H, L = m[:, 1], m[:, 2]
        if np.isnan(H[A:A + 5]).all():
            continue
        hi, lo = np.nanmax(H[A:A + 5]), np.nanmin(L[A:A + 5])
        up = np.nonzero(H[A + 5:960] >= hi + TK - 1e-9)[0]
        dn = np.nonzero(L[A + 5:960] <= lo - TK + 1e-9)[0]
        rows.append(dict(date=date, R=hi - lo, doble=len(up) > 0 and len(dn) > 0, alguna=len(up) > 0 or len(dn) > 0))
    f = pd.DataFrame(rows)
    f.to_csv(exp / "dias.csv.gz", index=False)
    w = f[(f.date >= "2026-02-25") & (f.date <= "2026-08-24")]
    print(f"Ventana del vídeo (25-feb a 24-ago-2026): {w.doble.sum()} de {len(w)} = {w.doble.mean() * 100:.1f} %  (edgeful: 101/128 = 78,9 %)")
    for lab_, d0 in (("últimos 2 años", "2024-10-02"), ("últimos 5 años", "2021-10-02"), ("2018-2026", "2018-01-01")):
        x = f[f.date >= d0]
        print(f"{lab_}: {x.doble.mean() * 100:.1f} % ({len(x)} días)")
    print("Por año:", (f.groupby(f.date.dt.year).doble.mean() * 100).round(1).to_dict())
    print(f"Rango mediano del ORB 5 min: {f.R.median():.1f} pts (= {f.R.median() * 10:.0f} $ por MGC)")

    res = []
    for minstop in (0.0, 3.0):
        for cn in ("base", "alto"):
            c = fut("MGC", cn)
            fills = []
            for date, m in D:
                H, L = m[:, 1], m[:, 2]
                if np.isnan(H[A:A + 5]).all():
                    continue
                hi, lo = np.nanmax(H[A:A + 5]), np.nanmin(L[A:A + 5])
                R = hi - lo
                if R <= 0:
                    continue
                up = np.nonzero(H[A + 5:955] >= hi + TK - 1e-9)[0]
                dn = np.nonzero(L[A + 5:955] <= lo - TK + 1e-9)[0]
                ku = up[0] + A + 5 if len(up) else None
                kd = dn[0] + A + 5 if len(dn) else None
                if (ku is None and kd is None) or (ku is not None and ku == kd):
                    continue
                side, k = (1, ku) if kd is None or (ku is not None and ku < kd) else (-1, kd)
                edge, opp = (hi, lo) if side == 1 else (lo, hi)
                S = max(R, minstop)
                o = Order(-side, "market", k + 1, round((edge + side * S) / TK) * TK, opp, 955)
                fl = simulate(date, m, 956, o, c)
                if fl is not None:
                    fills.append(fl)
            t = trades_frame(fills, c)
            res.append(dict(stop_minimo=minstop, coste=cn, llega_otro_lado=(t.reason == "objetivo").mean(),
                            **stats(t, per, c)))
    r = pd.DataFrame(res)
    r.to_csv(exp / "estrategia.csv", index=False)
    pd.set_option("display.width", 250)
    print("\nEstrategia 'en contra de la 1.ª ruptura, objetivo el otro lado' (MGC):")
    print(r.round(2).to_string(index=False))
    write_manifest(exp, experimento="short edgeful: MGC ORB 5 min doble ruptura", reglas=__doc__, exclusiones=excl)
    print("→", exp)


if __name__ == "__main__":
    main()
