"""Petición: en el playbook, ESPERAR A QUE LA VELA CIERRE fuera del rango y operar SOLO a favor de la SMA 200.
Velas del rango: 5 min 8:25 ET (DATO, 14:25 Italia) y 9:25 ET (APERTURA, 15:25 Italia). Reglas fijadas antes de ver
resultados (MNQ 2018-2026):
  Cierre: primera vela (de 1 min o de 5 min, variantes) que CIERRA fuera del rango → entrada a mercado en la apertura
          siguiente. Plazo para la señal y la operación: 3,5 h.
  SMA 200 (1 min o 5 min, la misma temporalidad que la vela de cierre), leída en la vela de la señal:
     sin filtro · "primera" (si el primer cierre fuera va contra la SMA, no se opera) · "solo lado" (se espera al primer
     cierre fuera EN el lado de la SMA).
  Stop: S = máx(rango, 30 pts) desde el nivel roto. Objetivo desde el nivel roto: DATO 0,75 × rango; APERTURA 1 × S o 0,7 × S.
  Referencia: el playbook actual (orden stop en la ruptura, sin filtro).
Selección: neto > 0 en dev Y val (coste base), n_val >= 30."""
import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import load_days, setup, stats
from run_playbook_sma200 import smas
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

WINS = [("DATO 14:25", 505, "R", 0.75), ("APERTURA 15:25", 565, "S", 1.0), ("APERTURA 15:25", 565, "S", 0.7)]


def run(D, SM, a, base, frac, c, entrada, tf, filtro):
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
        if entrada == "ruptura":
            st = setup(m, a, 5, tk)
            if st is None or st == "mismo":
                continue
            _, _, _, side, k, _ = st
            edge = hi if side == 1 else lo
            o = Order(side, "stop", k, rnd(edge - side * S - side * tk),
                      rnd(edge + side * frac * (R if base == "R" else S)), ex, level=rnd(edge + side * tk), k_last=k + 1)
        else:
            sma = SM[d][0 if tf == 1 else 1]
            sig = None
            for kc in range(a + 5 + tf - 1, ex - 1, tf):        # minuto de cierre de cada vela
                x = C[kc - tf + 1:kc + 1]
                x = x[~np.isnan(x)]
                if not len(x):
                    continue
                cl = x[-1]
                if lo <= cl <= hi:
                    continue
                side = 1 if cl > hi else -1
                ok = filtro == "sin" or (side == 1 and cl > sma[kc]) or (side == -1 and cl < sma[kc])
                if filtro == "primera" and not ok:
                    break
                if ok:
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
    exp = new_experiment("playbook_cierre_sma200")
    rows = []
    for w, a, base, frac in WINS:
        vs = [("ruptura", 1, "sin")] + [("cierre", tf, fl) for tf in (1, 5) for fl in ("sin", "primera", "solo_lado")]
        for entrada, tf, fl in vs:
            t = run(D, SM, a, base, frac, c, entrada, tf, fl)
            g = t.gross_pts
            eq = t.pnl.cumsum()
            rows.append(dict(ventana=w, objetivo=f"{frac} × {'rango' if base == 'R' else 'stop'}",
                             entrada="orden stop en la ruptura (actual)" if entrada == "ruptura" else
                             f"cierre vela {tf} min · SMA200 {fl}", ops_año=len(t) / 8.75, gana=(g > 0).mean(),
                             gana_usd=t.pnl[t.pnl > 0].mean(), pierde_usd=t.pnl[t.pnl < 0].mean(),
                             dd=(eq - eq.cummax()).min(), **stats(t, per, c)))
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="playbook: entrada al cierre fuera del rango + filtro SMA 200", reglas=__doc__)
    pd.set_option("display.width", 280, "display.max_colwidth", 45)
    print(r[["ventana", "objetivo", "entrada", "ops_año", "gana", "gana_usd", "pierde_usd", "dev", "val", "prueba",
             "neto_año", "años_pos", "dd", "pasa"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
