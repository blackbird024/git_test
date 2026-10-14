"""Pregunta del usuario: "¿mejor que mire el oro en Londres?". Mismas familias que run_londres_busqueda.py (MNQ),
aplicadas al oro (GC 1 min como MGC), reloj de Italia 0:00-22:00, más la ruptura de velas de 5 min de Londres.
Como el oro pasó de ~1.300 a más de 3.000 $, las distancias fijas se escalan con el precio: unidad U = 0,15 % del
precio a las 9:00 (≈ 2 pts en 2018, ≈ 5 pts en 2025; equivale a los 30 pts del NQ respecto al rango de Londres).
  MOMENTO   a favor / en contra del movimiento de Asia (0:00 → 8:59); stop U; objetivo 1:1 o solo tiempo.
  TRAMPA    barrida de Asia 0-9 / Asia 2-6 / máximo-mínimo del día anterior y cierre de 5 min de nuevo dentro → en
            contra; stop extremo ± 1 tick (mínimo U/3); objetivo mitad del rango (Asia), 1R o 2R.
  HUECO     |apertura 9:00 − cierre 22:00 del día anterior| >= 2U/3: relleno o sigue (1:1).
  RUPTURA   vela de 5 min 8:00 / 8:55 / 9:00 Italia; OCO stop 1 tick fuera; stop S = máx(rango, U/2 o U);
            objetivo 0,5 S o 1 S; plazo 3,5 h.
Señales 9:00-11:00 (salvo RUPTURA), cierre 12:00 o 14:20. Selección: neto > 0 en dev Y val (coste base), n_val >= 30."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import fut
from rangos_lib import FILES, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

N, K0, K1 = 1320, 540, 660


def oro_dias():
    df = pd.read_pickle(FILES["MGC"])
    df.index = df.index.tz_convert("Europe/Rome")
    arr = df[["open", "high", "low", "close", "volume"]].to_numpy()
    ins = df["instrument_id"].to_numpy()
    t = df.index
    mins = (t.hour * 60 + t.minute).to_numpy()
    out, prev = [], None
    for d, idx in pd.Series(np.arange(len(df)), index=pd.Index(t.date)).groupby(level=0):
        d = pd.Timestamp(d)
        ii = idx.to_numpy()
        ii = ii[mins[ii] < N]
        if d.weekday() >= 5 or len(ii) == 0:
            continue
        m = np.full((N, 5), np.nan)
        m[mins[ii]] = arr[ii]
        di = np.unique(ins[ii])
        ok = (~np.isnan(m[540:870, 0])).mean() >= 0.8 and len(di) == 1 and (prev is None or di[0] == prev)
        prev = di[-1]
        if ok:
            out.append((d, m, N))
    return out


def rnd(x, tk):
    return round(x / tk) * tk


def unidad(m):
    o = m[K0:K0 + 5, 0][~np.isnan(m[K0:K0 + 5, 0])]
    return 0.0015 * o[0] if len(o) else None


def bars5(m, k0, k1):
    out = []
    for k in range(k0, k1, 5):
        x = m[k:k + 5]
        ok = ~np.isnan(x[:, 3])
        if ok.any():
            out.append((k, np.nanmax(x[:, 1]), np.nanmin(x[:, 2]), x[ok][-1, 3]))
    return out


def momento(m, prev, tk, ex, U, contra, tgt):
    O, C = m[:, 0], m[:, 3]
    o0 = O[:60][~np.isnan(O[:60])]
    c1 = C[480:540][~np.isnan(C[480:540])]
    if not len(o0) or not len(c1) or c1[-1] == o0[0]:
        return None
    s = int(np.sign(c1[-1] - o0[0])) * (-1 if contra else 1)
    return Order(s, "market", K0, rnd(c1[-1] - s * U, tk), None, ex, target_r=1.0 if tgt else None)


def trampa(m, prev, tk, ex, U, nivel, tgt):
    H, L = m[:, 1], m[:, 2]
    if nivel == "PD":
        if prev is None or np.isnan(prev[:, 1]).all():
            return None
        hi, lo = np.nanmax(prev[:, 1]), np.nanmin(prev[:, 2])
    else:
        a0, a1 = (0, 540) if nivel == "asia_0_9" else (120, 360)
        if np.isnan(H[a0:a1]).sum() > (a1 - a0) / 2:
            return None
        hi, lo = np.nanmax(H[a0:a1]), np.nanmin(L[a0:a1])
    if hi <= lo:
        return None
    sw, ext = 0, None
    for k, h, l, c in bars5(m, K0, K1):
        if sw == 0:
            if h > hi and l < lo:
                return None
            if h > hi:
                sw, ext = -1, h
            elif l < lo:
                sw, ext = 1, l
            else:
                continue
        else:
            ext = max(ext, h) if sw == -1 else min(ext, l)
        if (sw == -1 and c < hi) or (sw == 1 and c > lo):
            kin = k + 5
            if kin > K1:
                return None
            stop = ext + tk if sw == -1 else ext - tk
            if abs(stop - c) < U / 3:
                stop = c - sw * U / 3
            stop = rnd(stop, tk)
            if tgt == "mitad":
                if nivel == "PD":
                    return None
                t = rnd((hi + lo) / 2, tk)
                if sw * (t - c) <= 0:
                    return None
                return Order(sw, "market", kin, stop, t, ex)
            return Order(sw, "market", kin, stop, None, ex, target_r=1.0 if tgt == "1R" else 2.0)
    return None


def hueco(m, prev, tk, ex, U, modo):
    if prev is None:
        return None
    pc = prev[:, 3][~np.isnan(prev[:, 3])]
    o = m[K0:K0 + 5, 0][~np.isnan(m[K0:K0 + 5, 0])]
    if not len(pc) or not len(o):
        return None
    g = o[0] - pc[-1]
    if abs(g) < 2 * U / 3:
        return None
    s = -int(np.sign(g)) if modo == "relleno" else int(np.sign(g))
    t = pc[-1] if modo == "relleno" else o[0] + s * abs(g)
    return Order(s, "market", K0, rnd(o[0] - s * abs(g), tk), rnd(t, tk), ex)


def ruptura(m, prev, tk, ex, U, a, umin, frac):
    H, L = m[:, 1], m[:, 2]
    if np.isnan(H[a:a + 5]).sum() > 2:
        return None
    hi, lo = np.nanmax(H[a:a + 5]), np.nanmin(L[a:a + 5])
    R = hi - lo
    s0, e = a + 5, a + 5 + 210
    if R <= 0:
        return None
    eps = tk * 1e-3
    up = np.nonzero(H[s0:e] >= hi + tk - eps)[0]
    dn = np.nonzero(L[s0:e] <= lo - tk + eps)[0]
    ku = up[0] + s0 if len(up) else None
    kd = dn[0] + s0 if len(dn) else None
    if ku is None and kd is None or (ku is not None and ku == kd):
        return None
    side, k = (1, ku) if kd is None or (ku is not None and ku < kd) else (-1, kd)
    edge = hi if side == 1 else lo
    S = max(R, umin * U)
    return Order(side, "stop", k, rnd(edge - side * S - side * tk, tk), rnd(edge + side * frac * S, tk), e,
                 level=rnd(edge + side * tk, tk), k_last=k + 1)


def variants():
    v = {}
    for ex, contra, tgt in itertools.product((720, 860), (False, True), (True, False)):
        v[f"MOMENTO {'en contra' if contra else 'a favor'} de Asia, obj {'1:1' if tgt else 'solo tiempo'}, "
          f"cierre {ex // 60}:{ex % 60:02d}"] = (momento, dict(contra=contra, tgt=tgt), ex)
    for ex, niv, tgt in itertools.product((720, 860), ("asia_0_9", "asia_2_6", "PD"), ("mitad", "1R", "2R")):
        if not (niv == "PD" and tgt == "mitad"):
            v[f"TRAMPA {niv}, obj {tgt}, cierre {ex // 60}:{ex % 60:02d}"] = (trampa, dict(nivel=niv, tgt=tgt), ex)
    for ex, modo in itertools.product((720, 860), ("relleno", "sigue")):
        v[f"HUECO {modo}, cierre {ex // 60}:{ex % 60:02d}"] = (hueco, dict(modo=modo), ex)
    for a, umin, frac in itertools.product((480, 535, 540), (0.5, 1.0), (0.5, 1.0)):
        v[f"RUPTURA vela 5 min {a // 60}:{a % 60:02d}, stop mín {umin} U, obj {frac} S"] = (
            ruptura, dict(a=a, umin=umin, frac=frac), a + 215)
    return v


def main():
    D = oro_dias()
    per = periods("intradia", include_test=True)
    c = fut("MGC", "base")
    exp = new_experiment("oro_londres_busqueda")
    rows = []
    for name, (fn, p, ex) in variants().items():
        fills, prev, pdate = [], None, None
        for date, m, cm in D:
            pv = prev if pdate is not None and (date - pdate).days <= 4 else None
            U = unidad(m)
            if U:
                o = fn(m, pv, c.tick, ex, U, **p)
                if o is not None:
                    f = simulate(date, m, min(cm, ex + 1), o, c)
                    if f is not None:
                        fills.append(f)
            prev, pdate = m, date
        t = trades_frame(fills, c)
        g = t.gross_pts
        rows.append(dict(variante=name, ops_año=len(t) / 8.75, gana=(g > 0).mean(), pierde=(g < 0).mean(),
                         gana_usd=g[g > 0].mean() * 10, pierde_usd=g[g < 0].mean() * 10, **stats(t, per, c)))
        print(name, "ok", flush=True)
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="oro en Londres: búsqueda de estrategia simple", reglas=__doc__,
                   seleccionadas=r[r.pasa].variante.tolist())
    pd.set_option("display.width", 300, "display.max_rows", 200, "display.max_colwidth", 60)
    print(len(D), "días")
    print(r[["variante", "ops_año", "gana", "pierde", "gana_usd", "pierde_usd", "dev", "val", "prueba", "ic90_FM",
             "años_pos", "pasa"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
