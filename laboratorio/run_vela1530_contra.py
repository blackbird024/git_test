"""Petición: vela de 5 min de 15:30 Italia (9:30-9:35 ET) A LA CONTRA, apostando a que gira, con entrada al cierre de una
vela de 1 min. Reglas fijadas antes de ver resultados (MNQ 2018-2026), dos lecturas:
  A) CONTRA DIRECTA: la primera vela de 1 min que CIERRA fuera del rango → entrada EN CONTRA a mercado en la apertura
     siguiente.
  B) RUPTURA FALLIDA: el precio rompe; la primera vela de 1 min que vuelve a CERRAR DENTRO del rango → entrada en contra
     de la ruptura (si rompió arriba, corto).
  Stop: extremo alcanzado por la ruptura ± 1 tick (variante: como mínimo a 30 pts de la entrada).
  Objetivo: el otro lado del rango, la mitad del rango, 1R o 2R.
  Plazo: 3,5 h desde las 9:35 ET (hasta 19:05 Italia). Una operación al día.
Selección: neto > 0 en dev Y val (coste base), n_val >= 30."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import load_days, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

A = 570
EX = A + 5 + 210


def run(D, c, modo, minstop, obj):
    tk = c.tick
    rnd = lambda x: round(x / tk) * tk
    fills = []
    for d, m in D:
        H, L, C = m[:, 1], m[:, 2], m[:, 3]
        if np.isnan(H[A:A + 5]).sum() > 2:
            continue
        hi, lo = np.nanmax(H[A:A + 5]), np.nanmin(L[A:A + 5])
        R = hi - lo
        if R <= 0:
            continue
        sig, rside, ext = None, 0, None
        for k in range(A + 5, EX - 1):
            if np.isnan(C[k]):
                continue
            if rside == 0:
                if H[k] > hi and L[k] < lo:
                    break
                if C[k] > hi or (modo == "fallida" and H[k] > hi):
                    rside, ext = 1, H[k]
                elif C[k] < lo or (modo == "fallida" and L[k] < lo):
                    rside, ext = -1, L[k]
                else:
                    continue
                if modo == "directa":
                    sig = (k + 1, -rside, ext)
                    break
                if lo <= C[k] <= hi:
                    sig = (k + 1, -rside, ext)
                    break
                continue
            ext = max(ext, H[k]) if rside == 1 else min(ext, L[k])
            if lo <= C[k] <= hi:
                sig = (k + 1, -rside, ext)
                break
        if sig is None:
            continue
        k, side, ext = sig
        ref = m[k, 0] if not np.isnan(m[k, 0]) else C[k - 1]
        stop = ext + tk if side == -1 else ext - tk
        if minstop and abs(stop - ref) < 30:
            stop = ref - side * 30
        stop = rnd(stop)
        if side * (ref - stop) <= 0:
            continue
        if obj in ("1R", "2R"):
            o = Order(side, "market", k, stop, None, EX, target_r=1.0 if obj == "1R" else 2.0)
        else:
            t = (lo if side == -1 else hi) if obj == "otro_lado" else (hi + lo) / 2
            if side * (t - ref) <= 0:
                continue
            o = Order(side, "market", k, stop, rnd(t), EX)
        f = simulate(d, m, EX + 1, o, c)
        if f is not None:
            fills.append(f)
    return trades_frame(fills, c)


def main():
    D, _ = load_days("MNQ")
    per = periods("intradia", include_test=True)
    c = fut("MNQ", "base")
    exp = new_experiment("vela1530_contra")
    rows = []
    for modo, ms, obj in itertools.product(("directa", "fallida"), (False, True), ("otro_lado", "mitad", "1R", "2R")):
        t = run(D, c, modo, ms, obj)
        g = t.gross_pts
        eq = t.pnl.cumsum()
        rows.append(dict(modo=modo, stop="extremo" + (" (mín 30)" if ms else ""), objetivo=obj, ops_año=len(t) / 8.75,
                         gana=(g > 0).mean(), gana_usd=t.pnl[t.pnl > 0].mean(), pierde_usd=t.pnl[t.pnl < 0].mean(),
                         stop_pts=t.risk_pts.median(), dd=(eq - eq.cummax()).min(), **stats(t, per, c)))
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="vela 15:30 Italia a la contra, entrada al cierre de 1 min", reglas=__doc__)
    pd.set_option("display.width", 280)
    print(r[["modo", "stop", "objetivo", "ops_año", "gana", "gana_usd", "pierde_usd", "stop_pts", "dev", "val",
             "prueba", "neto_año", "años_pos", "dd", "pasa"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
