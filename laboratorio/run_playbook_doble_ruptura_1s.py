"""Revisión del playbook con los días de DOBLE RUPTURA en el mismo minuto resueltos con datos de 1 SEGUNDO (NQ ohlcv-1s,
tools/download_nq_1s_doble_ruptura.py). Reglas del playbook sin cambios: OCO stop 1 tick fuera de la vela de 5 min
(8:25 ET DATO / 9:25 ET APERTURA), stop S = máx(rango, 30) desde el nivel roto, objetivo DATO 0,75 × rango, APERTURA
1 × S o 0,7 × S, plazo 3,5 h. En esos días:
  - lado = el nivel que el precio toca PRIMERO en las velas de 1 s (si los dos en el mismo segundo: caso peor, se toma
    el lado que acaba peor);
  - entrada = nivel (o apertura del segundo si salta más allá) + deslizamiento; gestión segundo a segundo durante los
    3 minutos descargados (stop primero si caben stop y objetivo en el mismo segundo; el objetivo exige 1 tick de cruce;
    en el segundo de entrada solo cuenta el stop), y después minuto a minuto como el simulador normal.
Resultado: el playbook completo (días normales + días de doble ruptura) por periodo."""
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from backtests.intraday import Fill, Order, simulate
from execution_costs.costs import fut
from rangos_lib import load_days, setup, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

RAW = Path(__file__).resolve().parents[1] / "vwap_lab" / "data" / "cache" / "NQ_1s_doble_ruptura.pkl"
WINS = [("DATO 14:25", 505, "R", 0.75), ("APERTURA 15:25 1:1", 565, "S", 1.0), ("APERTURA 15:25 1:0,7", 565, "S", 0.7)]


def resolver(d, m, a, k, s1, hi, lo, R, S, base, frac, c, side_forzado=None):
    tk, sl = c.tick, c.slip
    rnd = lambda x: round(x / tk) * tk
    ex = min(a + 5 + 210, 955)
    O, H, L = s1.open.to_numpy(), s1.high.to_numpy(), s1.low.to_numpy()
    up = np.nonzero(H >= hi + tk)[0]
    dn = np.nonzero(L <= lo - tk)[0]
    iu = up[0] if len(up) else 10 ** 9
    idn = dn[0] if len(dn) else 10 ** 9
    if side_forzado is not None:
        side, i0 = side_forzado, (iu if side_forzado == 1 else idn)
    elif iu == idn:
        return None
    else:
        side, i0 = (1, iu) if iu < idn else (-1, idn)
    if i0 >= 10 ** 9:
        return None
    edge = hi if side == 1 else lo
    lvl = rnd(edge + side * tk)
    entry = (max(lvl, O[i0]) if side == 1 else min(lvl, O[i0])) + side * sl
    stop = rnd(edge - side * S - side * tk)
    tgt = rnd(edge + side * frac * (R if base == "R" else S))
    risk = side * (entry - stop)
    mk = lambda xk, xp, why: Fill(d, side, k, entry, stop, tgt, xk, xp, why, risk, side * (xp - entry), "1s")
    for i in range(i0, len(O)):
        first = i == i0
        if side == 1:
            if not first and O[i] <= stop:
                return mk(k, O[i] - sl, "stop_hueco")
            if L[i] <= stop:
                return mk(k, stop - sl, "stop")
            if not first and (O[i] >= tgt or H[i] >= tgt + tk):
                return mk(k, max(O[i], tgt) if O[i] >= tgt else tgt, "objetivo")
        else:
            if not first and O[i] >= stop:
                return mk(k, O[i] + sl, "stop_hueco")
            if H[i] >= stop:
                return mk(k, stop + sl, "stop")
            if not first and (O[i] <= tgt or L[i] <= tgt - tk):
                return mk(k, min(O[i], tgt) if O[i] <= tgt else tgt, "objetivo")
    # sigue minuto a minuto desde el minuto siguiente a los 3 descargados
    k2 = k + 3
    MO, MH, ML = m[:, 0], m[:, 1], m[:, 2]
    for j in range(k2, ex):
        if np.isnan(MO[j]):
            continue
        if side == 1:
            if MO[j] <= stop:
                return mk(j, MO[j] - sl, "stop_hueco")
            if ML[j] <= stop:
                return mk(j, stop - sl, "stop")
            if MO[j] >= tgt:
                return mk(j, MO[j], "objetivo")
            if MH[j] >= tgt + tk:
                return mk(j, tgt, "objetivo")
        else:
            if MO[j] >= stop:
                return mk(j, MO[j] + sl, "stop_hueco")
            if MH[j] >= stop:
                return mk(j, stop + sl, "stop")
            if MO[j] <= tgt:
                return mk(j, MO[j], "objetivo")
            if ML[j] <= tgt - tk:
                return mk(j, tgt, "objetivo")
    j = ex
    while j < 960 and np.isnan(MO[j]):
        j += 1
    return mk(j, MO[j] - side * sl, "tiempo") if j < 960 else None


def main():
    D, _ = load_days("MNQ")
    S1 = pickle.load(open(RAW, "rb"))
    per = periods("intradia", include_test=True)
    c = fut("MNQ", "base")
    tk = c.tick
    rnd = lambda x: round(x / tk) * tk
    exp = new_experiment("playbook_doble_ruptura_1s")
    rows, n_amb = [], {}
    for w, a, base, frac in WINS:
        norm, dob = [], []
        amb = 0
        for d, m in D:
            st = setup(m, a, 5, tk)
            if st is None:
                continue
            H, L = m[:, 1], m[:, 2]
            hi, lo = np.nanmax(H[a:a + 5]), np.nanmin(L[a:a + 5])
            R = hi - lo
            S = max(R, 30.0)
            if st == "mismo":
                if (d, a) not in S1:
                    continue
                k, s1 = S1[(d, a)]
                if s1 is None or not len(s1):
                    continue
                f = resolver(d, m, a, k, s1, hi, lo, R, S, base, frac, c)
                if f is None:                       # mismo segundo: caso peor
                    amb += 1
                    fs = [x for x in (resolver(d, m, a, k, s1, hi, lo, R, S, base, frac, c, sd) for sd in (1, -1)) if x]
                    if not fs:
                        continue
                    f = min(fs, key=lambda x: x.gross_pts)
                dob.append(f)
            else:
                side, kk, ex = st[3], st[4], st[5]
                edge = hi if side == 1 else lo
                o = Order(side, "stop", kk, rnd(edge - side * S - side * tk),
                          rnd(edge + side * frac * (R if base == "R" else S)), ex, level=rnd(edge + side * tk),
                          k_last=kk + 1)
                f = simulate(d, m, ex + 1, o, c)
                if f is not None:
                    norm.append(f)
        n_amb[w] = amb
        for nombre, fl in (("solo días normales (antes)", norm), ("días doble ruptura (1 s)", dob),
                           ("TOTAL real", norm + dob)):
            t = trades_frame(fl, c).sort_values("date")
            g = t.gross_pts
            eq = t.pnl.cumsum()
            mo = t.groupby(t.date.dt.to_period("M")).pnl.sum()
            rows.append(dict(ventana=w, conjunto=nombre, ops_año=len(t) / 8.75, gana=(g > 0).mean(),
                             gana_usd=t.pnl[t.pnl > 0].mean(), pierde_usd=t.pnl[t.pnl < 0].mean(),
                             meses_pos=(mo > 0).mean(), dd=(eq - eq.cummax()).min(), **stats(t, per, c)))
            if nombre == "TOTAL real":
                t.to_csv(exp / f"ops_{w.replace(' ', '_').replace(':', '').replace(',', '')}.csv.gz", index=False)
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="playbook con días de doble ruptura resueltos con 1 s", reglas=__doc__,
                   ambiguos_mismo_segundo=n_amb)
    pd.set_option("display.width", 280)
    print("ambiguos (mismo segundo):", n_amb)
    print(r[["ventana", "conjunto", "ops_año", "gana", "gana_usd", "pierde_usd", "dev", "val", "prueba", "neto_año",
             "años_pos", "meses_pos", "dd", "pasa"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
