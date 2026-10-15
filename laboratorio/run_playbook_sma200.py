"""Petición: "incluiré el filtro de la SMA 200" en el playbook (DATO 5 min 8:25 ET obj 0,75 R; APERTURA 5 min 9:25 ET
obj 1 S; stop S = máx(rango, 30 pts); OCO stop 1 tick fuera; plazo 3,5 h). Reglas fijadas antes de ver resultados:
SMA 200 de cierres (1 min o 5 min), encadenada entre días (rejilla ET 0:00-16:00, incluye la noche), leída al cierre de
la vela del rango. Lado permitido = largo si cierre > SMA, corto si cierre < SMA.
  sin_filtro   referencia (playbook actual)
  primera      solo se opera si la PRIMERA ruptura va en el lado permitido (si no, no hay operación)
  solo_lado    solo se pone la orden del lado permitido (puede entrar aunque antes rompiera el otro lado)
Selección: neto > 0 en desarrollo Y validación (coste base), n_val >= 30, y mejor que sin filtro."""
import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import load_days, setup, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

WINS = {"DATO 14:25 Italia": (505, "R", 0.75), "APERTURA 15:25 Italia": (565, "S", 1.0)}


def smas(D):
    c = pd.Series(np.concatenate([m[:, 3] for _, m in D])).ffill()
    out = {}
    s1 = c.rolling(200).mean().to_numpy()
    c5 = c.iloc[4::5]
    s5 = pd.Series(np.nan, index=c.index)
    s5.iloc[4::5] = c5.rolling(200).mean().to_numpy()
    s5 = s5.ffill().to_numpy()
    n = D[0][1].shape[0]
    for i, (d, _) in enumerate(D):
        out[d] = (s1[i * n:(i + 1) * n], s5[i * n:(i + 1) * n])
    return out


def run(D, SM, a, base, frac, c, modo, tf):
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
        cl = C[a:a + 5][~np.isnan(C[a:a + 5])][-1]
        sma = SM[d][0 if tf == 1 else 1][a + 4]
        perm = 1 if cl > sma else -1
        if modo == "solo_lado":
            side = perm
            edge = hi if side == 1 else lo
            lvl = edge + side * tk
            hit = np.nonzero(H[a + 5:ex] >= lvl - 1e-9 if side == 1 else L[a + 5:ex] <= lvl + 1e-9)[0]
            if not len(hit):
                continue
            k = a + 5 + hit[0]
        else:
            st = setup(m, a, 5, tk)
            if st is None or st == "mismo":
                continue
            _, _, _, side, k, _ = st
            if modo == "primera" and side != perm:
                continue
            edge = hi if side == 1 else lo
        S = max(R, 30.0)
        dist = frac * (R if base == "R" else S)
        o = Order(side, "stop", k, rnd(edge - side * S - side * tk), rnd(edge + side * dist), ex,
                  level=rnd(edge + side * tk), k_last=k + 1)
        f = simulate(d, m, ex + 1, o, c)
        if f is not None:
            fills.append(f)
    return trades_frame(fills, c)


def main():
    D, _ = load_days("MNQ")
    SM = smas(D)
    per = periods("intradia", include_test=True)
    c = fut("MNQ", "base")
    exp = new_experiment("playbook_sma200")
    rows = []
    for w, (a, base, frac) in WINS.items():
        for modo, tf in [("sin_filtro", 1), ("primera", 1), ("solo_lado", 1), ("primera", 5), ("solo_lado", 5)]:
            t = run(D, SM, a, base, frac, c, modo, tf)
            g = t.gross_pts
            rows.append(dict(ventana=w, filtro="sin filtro" if modo == "sin_filtro" else f"SMA200 {tf} min · {modo}",
                             ops_año=len(t) / 8.75, gana=(g > 0).mean(), pierde=(g < 0).mean(), **stats(t, per, c)))
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="filtro SMA 200 en el playbook dato/apertura", reglas=__doc__)
    pd.set_option("display.width", 260)
    print(r[["ventana", "filtro", "ops_año", "gana", "pierde", "dev", "val", "prueba", "neto_año", "años_pos", "pasa"]]
          .round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
