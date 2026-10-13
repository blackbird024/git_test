"""Reversión del ORB de 5 min (9:30-9:35 ET) CON CONFIRMACIÓN, como la opera edgeful (doble ruptura → el otro lado es el
objetivo). Reglas fijadas antes de ver resultados:
1. Rango 9:30-9:35 ET. Primera ruptura (1 tick fuera) desde las 9:35.
2. Confirmación de reversión: la primera vela (1 min o 5 min, variantes) que CIERRA de nuevo dentro del rango después de
   la ruptura → entrada a mercado en la apertura siguiente, en contra de la ruptura.
3. Stop: el extremo de la ruptura (máximo/mínimo alcanzado fuera del rango hasta la señal) ± 1 tick.
4. Objetivo: el otro lado del rango (variante "otro_lado") o 2R.
5. Señales hasta las 14:00 ET; salida 15:55 ET. Una operación al día. Costes base y alto. MGC (oro) y MNQ."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import load_days, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

A, LAST, EXK = 570, 840, 955


def signal(m, tk, tf, target):
    H, L, C = m[:, 1], m[:, 2], m[:, 3]
    if np.isnan(H[A:A + 5]).all():
        return None
    hi, lo = np.nanmax(H[A:A + 5]), np.nanmin(L[A:A + 5])
    if hi - lo <= 0:
        return None
    eps = tk * 1e-3
    up = np.nonzero(H[A + 5:LAST] >= hi + tk - eps)[0]
    dn = np.nonzero(L[A + 5:LAST] <= lo - tk + eps)[0]
    ku = up[0] + A + 5 if len(up) else None
    kd = dn[0] + A + 5 if len(dn) else None
    if (ku is None and kd is None) or (ku is not None and ku == kd):
        return None
    side, k = (1, ku) if kd is None or (ku is not None and ku < kd) else (-1, kd)
    ext = H[k] if side == 1 else L[k]
    j = k
    while j < LAST:
        b0 = j if tf == 1 else A + 5 + ((j - A - 5) // 5) * 5
        b1 = b0 + tf
        if b1 > LAST:
            return None
        seg_h, seg_l = H[max(b0, k):b1], L[max(b0, k):b1]
        if np.isnan(seg_h).all():
            j = b1
            continue
        ext = max(ext, np.nanmax(seg_h)) if side == 1 else min(ext, np.nanmin(seg_l))
        cc = C[b0:b1][~np.isnan(C[b0:b1])]
        if len(cc) and lo <= cc[-1] <= hi:
            stop = round((ext + side * tk) / tk) * tk
            if target == "otro_lado":
                return Order(-side, "market", b1, stop, lo if side == 1 else hi, EXK)
            return Order(-side, "market", b1, stop, None, EXK, target_r=2.0)
        j = b1
    return None


def main():
    per = periods("intradia", include_test=True)
    exp = new_experiment("orb5_reversion_confirmada")
    rows = []
    for sym in ("MGC", "MNQ"):
        D, _ = load_days(sym)
        for tf, tg, cn in itertools.product((1, 5), ("otro_lado", "2R"), ("base", "alto")):
            c = fut(sym, cn)
            fills = []
            for date, m in D:
                o = signal(m, c.tick, tf, tg)
                if o is not None:
                    f = simulate(date, m, EXK + 1, o, c)
                    if f is not None:
                        fills.append(f)
            t = trades_frame(fills, c)
            rows.append(dict(mercado=sym, confirmacion=f"cierre {tf} min", objetivo=tg, coste=cn,
                             llega_obj=(t.reason == "objetivo").mean(), **stats(t, per, c)))
        print(sym, "ok", flush=True)
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    pd.set_option("display.width", 260)
    print(r.drop(columns=["R_bruto"]).round(2).to_string(index=False))
    write_manifest(exp, experimento="reversión confirmada del ORB 5 min (MGC y MNQ)", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
