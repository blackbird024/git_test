"""Vídeo de YouTube "stupid simple" (Casper): ORB de 5 min 9:30-9:35 ET + vela de 5 min que cierra fuera + retesteo
que toca el nivel y cierra fuera → entrada; stop en la mitad del rango (Fibonacci 0,5); objetivo 2R; "primeros 90 minutos".
Reglas fijadas antes de ver resultados (variantes donde el vídeo es ambiguo):
1. Rango = vela de 5 min 9:30-9:35 ET. Velas de 5 min alineadas a las 9:30.
2. Ruptura: vela de 5 min cuyo CUERPO entero queda fuera (apertura y cierre > máximo; variante "cierre": solo el cierre).
3. Retesteo: una vela POSTERIOR cuyo mínimo vuelve al nivel (<= máximo del rango, largos) y que CIERRA fuera (> máximo).
   Entrada a mercado en la apertura siguiente. Si antes una vela cierra DENTRO del rango, se anula y se espera una
   nueva ruptura.
4. Stop: mitad del rango ∓ 1 tick. Objetivo: 2R (desde la entrada real). Señales hasta las 11:00 ET (90 min);
   salida forzosa 15:55 ET (variante: 11:00 ET). Una operación al día. MNQ y MGC, costes base y alto.
Comparación: entrada directa al cierre de la vela de ruptura, sin retesteo (el vídeo dice que el retesteo duplica el acierto)."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import load_days, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

A, LAST = 570, 660


def bars5(m, k0, k1):
    out = []
    for k in range(k0, k1, 5):
        x = m[k:k + 5]
        ok = ~np.isnan(x[:, 0])
        if ok.any():
            y = x[ok]
            out.append((k, y[0, 0], y[:, 1].max(), y[:, 2].min(), y[-1, 3]))
    return out


def signal(m, tk, body, retest, exit_k):
    b = bars5(m, A, A + 5)
    if not b:
        return None
    _, _, hi, lo, _ = b[0]
    if hi <= lo:
        return None
    mid = (hi + lo) / 2
    side = 0
    for k, o, h, l, c in bars5(m, A + 5, LAST):
        if side == 0:
            up = (min(o, c) > hi) if body == "cuerpo" else c > hi
            dn = (max(o, c) < lo) if body == "cuerpo" else c < lo
            if up or dn:
                side = 1 if up else -1
                if not retest:
                    break
                continue
        else:
            if lo <= c <= hi:
                side = 0
                continue
            touch = (l <= hi) if side == 1 else (h >= lo)
            out = (c > hi) if side == 1 else (c < lo)
            if touch and out:
                break
    else:
        return None
    if side == 0:
        return None
    stop = round((mid - side * tk) / tk) * tk
    return Order(side, "market", k + 5, stop, None, exit_k, target_r=2.0)


def main():
    per = periods("intradia", include_test=True)
    exp = new_experiment("orb_retest_video")
    rows = []
    for sym in ("MNQ", "MGC"):
        D, _ = load_days(sym)
        for body, retest, ex, cn in itertools.product(("cuerpo", "cierre"), (True, False), (955, 660), ("base", "alto")):
            c = fut(sym, cn)
            fills = []
            for date, m in D:
                o = signal(m, c.tick, body, retest, ex)
                if o is not None:
                    f = simulate(date, m, ex + 1, o, c)
                    if f is not None:
                        fills.append(f)
            t = trades_frame(fills, c)
            rows.append(dict(mercado=sym, ruptura=body, retesteo=retest, salida="15:55" if ex == 955 else "11:00",
                             coste=cn, ops_año=len(t) / 8.75, **stats(t, per, c)))
        print(sym, "ok", flush=True)
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    pd.set_option("display.width", 260)
    print(r[r.coste == "base"][["mercado", "ruptura", "retesteo", "salida", "ops_año", "dev", "val", "prueba", "neto_año",
                                "acierto", "riesgo_med", "años_pos", "ic90_FM", "pasa"]].round(2).to_string(index=False))
    write_manifest(exp, experimento="ORB 5 min + cierre fuera + retesteo (vídeo 'stupid simple')", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
