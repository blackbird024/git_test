"""Petición: vela de 5 min de 15:25 Italia (9:25-9:30 ET). Suponer que la PRIMERA ruptura es falsa: cuando el precio
vuelve al rango, entrar EN CONTRA de esa ruptura con objetivo 1:0,5 y stop en el último máximo/mínimo de 1 min.
Reglas fijadas antes de ver resultados (MNQ 2018-2026):
  Primera ruptura: primera vela de 1 min (desde 9:30 ET) cuyo máximo supera el máximo de la vela + 1 tick (o el mínimo).
    Si en ese minuto rompe los dos lados, el primer lado se decide con los datos de 1 SEGUNDO
    (tools/download_nq_1s_doble_ruptura.py); si es el mismo segundo, el día no se opera.
  Vuelta al rango: primera vela de 1 min que CIERRA de nuevo al otro lado del nivel roto (por debajo del máximo si rompió
    arriba). Entrada a mercado en la apertura siguiente, EN CONTRA de la primera ruptura.
  Stop: el extremo alcanzado por la ruptura falsa (máximo de las velas de 1 min desde la ruptura) ± 1 tick.
  Objetivo: 0,5 R (pedido) y, para comparar, 1 R. R = distancia entrada-stop.
  Ventana de señal (variantes): hasta 30 min tras la ruptura, o todo el plazo (3,5 h desde 9:30 ET).
Selección: neto > 0 en dev Y val (coste base), n_val >= 30."""
import itertools
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import load_days, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

A = 565
EX = A + 5 + 210
RAW = Path(__file__).resolve().parents[1] / "vwap_lab" / "data" / "cache" / "NQ_1s_doble_ruptura.pkl"


def run(D, S1, c, objr, ventana):
    tk = c.tick
    rnd = lambda x: round(x / tk) * tk
    fills = []
    for d, m in D:
        H, L, C, O = m[:, 1], m[:, 2], m[:, 3], m[:, 0]
        if np.isnan(H[A:A + 5]).sum() > 2:
            continue
        hi, lo = np.nanmax(H[A:A + 5]), np.nanmin(L[A:A + 5])
        if hi <= lo:
            continue
        kb, bside = None, 0
        for k in range(A + 5, EX):
            if np.isnan(H[k]):
                continue
            up, dn = H[k] >= hi + tk, L[k] <= lo - tk
            if up and dn:
                if (d, A) not in S1 or S1[(d, A)][1] is None:
                    break
                s1 = S1[(d, A)][1]
                iu = np.nonzero(s1.high.to_numpy() >= hi + tk)[0]
                idn = np.nonzero(s1.low.to_numpy() <= lo - tk)[0]
                iu = iu[0] if len(iu) else 10 ** 9
                idn = idn[0] if len(idn) else 10 ** 9
                if iu == idn:
                    break
                kb, bside = k, (1 if iu < idn else -1)
                break
            if up or dn:
                kb, bside = k, (1 if up else -1)
                break
        if kb is None:
            continue
        lvl = hi if bside == 1 else lo
        ext = H[kb] if bside == 1 else L[kb]
        last = EX - 1 if ventana == "todo" else min(EX - 1, kb + 30)
        sig = None
        for k in range(kb, last):
            if np.isnan(C[k]):
                continue
            ext = max(ext, H[k]) if bside == 1 else min(ext, L[k])
            if (bside == 1 and C[k] < lvl) or (bside == -1 and C[k] > lvl):
                sig = k + 1
                break
        if sig is None:
            continue
        side = -bside
        stop = rnd(ext + tk) if side == -1 else rnd(ext - tk)
        o = Order(side, "market", sig, stop, None, EX, target_r=objr, tag="fake1525")
        f = simulate(d, m, EX + 1, o, c)
        if f is not None:
            fills.append(f)
    return trades_frame(fills, c)


def main():
    D, _ = load_days("MNQ")
    S1 = pickle.load(open(RAW, "rb"))
    per = periods("intradia", include_test=True)
    c = fut("MNQ", "base")
    exp = new_experiment("vela1525_ruptura_falsa")
    rows = []
    for objr, ven in itertools.product((0.5, 1.0), ("30min", "todo")):
        t = run(D, S1, c, objr, ven)
        g = t.gross_pts
        eq = t.pnl.cumsum()
        rows.append(dict(objetivo=f"1:{objr}", ventana=ven, ops_año=len(t) / 8.75, gana=(g > 0).mean(),
                         gana_usd=t.pnl[t.pnl > 0].mean(), pierde_usd=t.pnl[t.pnl < 0].mean(),
                         stop_pts=t.risk_pts.median(), dd=(eq - eq.cummax()).min(), **stats(t, per, c)))
        t.to_csv(exp / f"ops_{objr}_{ven}.csv.gz", index=False)
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="vela 15:25: primera ruptura falsa, entrada en contra al volver", reglas=__doc__)
    pd.set_option("display.width", 260)
    print(r[["objetivo", "ventana", "ops_año", "gana", "gana_usd", "pierde_usd", "stop_pts", "dev", "val", "prueba",
             "neto_año", "años_pos", "dd", "pasa"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
