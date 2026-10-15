"""Guía "ORB El Autómata" (Los Autómatas): ORB en MNQ, velas de 5 min, hora de NY. Reglas de la guía:
  rango con velas de 1 min (1:00-1:15 NY, o 9:15-9:30 NY); esperar una vela de 5 min que CIERRE fuera del rango y sea
  A FAVOR (alcista para largo, bajista para corto); entrar al cierre de esa vela; stop en la MECHA de la vela de ruptura
  o en el LADO OPUESTO del rango (+ buffer); objetivo en múltiplos de R; omite la operación si el stop supera el máximo
  permitido; una operación por sesión; cierre obligatorio a una hora.
Lo que la guía no dice (los ajustes "son parte de la membresía") se fija ANTES de ver resultados:
  buffer de ruptura 0; buffer de stop 1 tick; objetivo 0,5 / 1 / 1,5 / 2 R; stop máximo: sin límite o 30 pts;
  horas: 1 AM → entradas hasta 4:00 NY y cierre 5:00 NY; NY 9:15 → entradas hasta 11:30 y cierre 12:30.
  Entrada en la apertura del minuto siguiente al cierre de la vela (≈ su cierre) con deslizamiento.
Se mide en 8 años (2018-2026) y además en el último año y los últimos 90 días (los periodos de la guía).
Selección: neto > 0 en dev Y val (coste base), n_val >= 30."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import load_days, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

SES = {"1 AM (1:00-1:15)": (60, 75, 240, 300), "NY (9:15-9:30)": (555, 570, 690, 750)}


def run(D, c, ses, stop_modo, objr, maxstop):
    a0, a1, last, cierre = SES[ses]
    tk = c.tick
    rnd = lambda x: round(x / tk) * tk
    fills = []
    for d, m in D:
        O, H, L, C = m[:, 0], m[:, 1], m[:, 2], m[:, 3]
        if np.isnan(H[a0:a1]).sum() > (a1 - a0) / 2:
            continue
        hi, lo = np.nanmax(H[a0:a1]), np.nanmin(L[a0:a1])
        if hi <= lo:
            continue
        for b in range(a1, last, 5):
            x = slice(b, b + 5)
            ok = ~np.isnan(C[x])
            if not ok.any():
                continue
            o5, c5 = O[x][ok][0], C[x][ok][-1]
            h5, l5 = np.nanmax(H[x]), np.nanmin(L[x])
            side = 1 if (c5 > hi and c5 > o5) else -1 if (c5 < lo and c5 < o5) else 0
            if side == 0:
                continue
            if stop_modo == "mecha":
                stop = l5 - tk if side == 1 else h5 + tk
            else:
                stop = lo - tk if side == 1 else hi + tk
            if maxstop and abs(c5 - stop) > maxstop:
                break                                   # se omite la operación (sin rearme)
            o = Order(side, "market", b + 5, rnd(stop), None, cierre, target_r=objr, tag="automata")
            f = simulate(d, m, cierre + 1, o, c)
            if f is not None:
                fills.append(f)
            break
    return trades_frame(fills, c)


def main():
    D, _ = load_days("MNQ")
    per = periods("intradia", include_test=True)
    c = fut("MNQ", "base")
    exp = new_experiment("orb_automata")
    rows = []
    fin = D[-1][0]
    for ses, sm, objr, mx in itertools.product(SES, ("mecha", "opuesto"), (0.5, 1.0, 1.5, 2.0), (0, 30)):
        t = trades_frame([], c) if False else run(D, c, ses, sm, objr, mx)
        g = t.gross_pts
        eq = t.pnl.cumsum()
        u1 = t[t.date > fin - pd.Timedelta(days=365)]
        u90 = t[t.date > fin - pd.Timedelta(days=90)]
        rows.append(dict(sesion=ses, stop=sm, objetivo=f"{objr} R", stop_max=mx or "sin", ops_año=len(t) / 8.75,
                         gana=(g > 0).mean(), gana_usd=t.pnl[t.pnl > 0].mean(), pierde_usd=t.pnl[t.pnl < 0].mean(),
                         stop_pts=t.risk_pts.median(), dd=(eq - eq.cummax()).min(),
                         ultimo_año=u1.pnl.sum(), gana_1a=(u1.gross_pts > 0).mean(),
                         ult_90d=u90.pnl.sum(), n_90d=len(u90), gana_90d=(u90.gross_pts > 0).mean(),
                         **stats(t, per, c)))
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="ORB El Autómata (guía pública)", reglas=__doc__)
    pd.set_option("display.width", 320)
    print(r[["sesion", "stop", "objetivo", "stop_max", "ops_año", "gana", "gana_usd", "pierde_usd", "stop_pts", "dev",
             "val", "prueba", "neto_año", "años_pos", "dd", "ultimo_año", "gana_1a", "ult_90d", "n_90d", "gana_90d",
             "pasa"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
