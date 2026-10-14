"""Petición: "vamos, busca una buena" (estrategia para la sesión de Londres). MNQ, reloj de Italia (0:00-22:00).
Familias y variantes fijadas ANTES de ver resultados. Una operación al día; señales entre 9:00 y 11:00 Italia;
cierre forzoso a las 12:00 o a las 14:20 Italia (antes del dato).
  MOMENTO   dirección del movimiento de Asia (apertura 0:00 → cierre 8:59 Italia); a mercado a las 9:00 A FAVOR o EN
            CONTRA; stop 30 pts; objetivo 30 pts (1:1) o sin objetivo (solo tiempo).
  TRAMPA    (turtle soup) rango de Asia 0:00-9:00 o 2:00-6:00 Italia, o máximo/mínimo del día anterior (PD). Una vela
            de 5 min (desde las 9:00) supera el máximo (o perfora el mínimo) y después una vela de 5 min CIERRA de
            nuevo dentro → entrada a mercado en contra en la apertura siguiente (como muy tarde 11:00). Stop: extremo
            de la barrida ± 1 tick (mínimo 10 pts). Objetivo: mitad del rango (solo rangos de Asia), 1R o 2R.
            Si la misma vela barre los dos lados, no se opera.
  HUECO     referencia = cierre de NY del día anterior (22:00 Italia). A las 9:00, si |apertura − cierre| >= 20 pts:
            RELLENO (en contra del hueco, objetivo el cierre anterior, stop a la misma distancia) o SIGUE (a favor,
            stop y objetivo a la distancia del hueco).
  DERIVA    comprar a las 9:00 sin más condición; stop 30 pts; solo tiempo (referencia).
Probabilidades: gana / pierde = resultado bruto > 0 / < 0. Selección: esperanza neta > 0 en desarrollo Y validación
(coste base), n_val >= 30; la prueba (2025-26) solo se mira después."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from data.loaders import sessions
from execution_costs.costs import fut
from rangos_lib import stats
from run_crt_italia import rome_days
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

K0, K1 = 540, 660


def rnd(x, tk):
    return round(x / tk) * tk


def bars5(m, k0, k1):
    out = []
    for k in range(k0, k1, 5):
        x = m[k:k + 5]
        ok = ~np.isnan(x[:, 3])
        if ok.any():
            out.append((k, np.nanmax(x[:, 1]), np.nanmin(x[:, 2]), x[ok][-1, 3]))
    return out


def momento(m, prev, tk, ex, contra, tgt):
    O, C = m[:, 0], m[:, 3]
    o0 = O[:60][~np.isnan(O[:60])]
    c1 = C[480:540][~np.isnan(C[480:540])]
    if not len(o0) or not len(c1) or c1[-1] == o0[0]:
        return None
    s = int(np.sign(c1[-1] - o0[0])) * (-1 if contra else 1)
    ref = c1[-1]
    return Order(s, "market", K0, rnd(ref - s * 30, tk), None, ex, target_r=1.0 if tgt else None, tag="momento")


def trampa(m, prev, tk, ex, nivel, tgt):
    H, L = m[:, 1], m[:, 2]
    if nivel == "PD":
        if prev is None:
            return None
        ph, pl = prev[:, 1], prev[:, 2]
        if np.isnan(ph).all():
            return None
        hi, lo = np.nanmax(ph), np.nanmin(pl)
    else:
        a0, a1 = (0, 540) if nivel == "asia_0_9" else (120, 360)
        if np.isnan(H[a0:a1]).sum() > (a1 - a0) / 2:
            return None
        hi, lo = np.nanmax(H[a0:a1]), np.nanmin(L[a0:a1])
    if hi <= lo:
        return None
    b = bars5(m, K0, K1)
    sw, ext = 0, None
    for k, h, l, c in b:
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
            ref = c
            stop = ext + tk if sw == -1 else ext - tk
            if abs(stop - ref) < 10:
                stop = ref - sw * 10
            stop = rnd(stop, tk)
            if tgt == "mitad":
                if nivel == "PD":
                    return None
                t = rnd((hi + lo) / 2, tk)
                if sw * (t - ref) <= 0:
                    return None
                return Order(sw, "market", kin, stop, t, ex, tag="trampa")
            return Order(sw, "market", kin, stop, None, ex, target_r=1.0 if tgt == "1R" else 2.0, tag="trampa")
    return None


def hueco(m, prev, tk, ex, modo):
    if prev is None:
        return None
    pc = prev[:, 3][~np.isnan(prev[:, 3])]
    O = m[:, 0]
    o = O[K0:K0 + 5][~np.isnan(O[K0:K0 + 5])]
    if not len(pc) or not len(o):
        return None
    g = o[0] - pc[-1]
    if abs(g) < 20:
        return None
    if modo == "relleno":
        s = -int(np.sign(g))
        return Order(s, "market", K0, rnd(o[0] - s * abs(g), tk), rnd(pc[-1], tk), ex, tag="hueco")
    s = int(np.sign(g))
    return Order(s, "market", K0, rnd(o[0] - s * abs(g), tk), rnd(o[0] + s * abs(g), tk), ex, tag="hueco")


def deriva(m, prev, tk, ex):
    C = m[:, 3]
    c1 = C[480:540][~np.isnan(C[480:540])]
    if not len(c1):
        return None
    return Order(1, "market", K0, rnd(c1[-1] - 30, tk), None, ex, tag="deriva")


def variants():
    v = {}
    for ex, contra, tgt in itertools.product((720, 860), (False, True), (True, False)):
        v[f"MOMENTO {'en contra' if contra else 'a favor'} de Asia, obj {'1:1' if tgt else 'solo tiempo'}, "
          f"cierre {ex // 60}:{ex % 60:02d}"] = (momento, dict(contra=contra, tgt=tgt), ex)
    for ex, niv, tgt in itertools.product((720, 860), ("asia_0_9", "asia_2_6", "PD"), ("mitad", "1R", "2R")):
        if niv == "PD" and tgt == "mitad":
            continue
        v[f"TRAMPA {niv}, obj {tgt}, cierre {ex // 60}:{ex % 60:02d}"] = (trampa, dict(nivel=niv, tgt=tgt), ex)
    for ex, modo in itertools.product((720, 860), ("relleno", "sigue")):
        v[f"HUECO {modo}, cierre {ex // 60}:{ex % 60:02d}"] = (hueco, dict(modo=modo), ex)
    for ex in (720, 860):
        v[f"DERIVA largo 9:00, cierre {ex // 60}:{ex % 60:02d}"] = (deriva, {}, ex)
    return v


def probs(t):
    g = t.gross_pts
    return dict(gana=(g > 0).mean(), pierde=(g < 0).mean(), gana_pts=g[g > 0].mean(), pierde_pts=g[g < 0].mean(),
                media_pts=g.mean())


def main():
    D = rome_days(sessions())
    per = periods("intradia", include_test=True)
    c = fut("MNQ", "base")
    tk = c.tick
    exp = new_experiment("londres_busqueda")
    rows = []
    for name, (fn, p, ex) in variants().items():
        fills, prev, pdate = [], None, None
        for date, m, cm in D:
            pv = prev if pdate is not None and (date - pdate).days <= 4 else None
            o = fn(m, pv, tk, ex, **p)
            if o is not None:
                f = simulate(date, m, min(cm, ex + 1), o, c)
                if f is not None:
                    fills.append(f)
            prev, pdate = m, date
        t = trades_frame(fills, c)
        t.to_csv(exp / f"ops_{''.join(ch if ch.isalnum() else '_' for ch in name)}.csv.gz", index=False)
        rows.append(dict(variante=name, ops_año=len(t) / 8.75, **probs(t), **stats(t, per, c)))
        print(name, "ok", flush=True)
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="búsqueda de una estrategia simple para Londres", reglas=__doc__,
                   seleccionadas=r[r.pasa].variante.tolist())
    pd.set_option("display.width", 300, "display.max_rows", 200, "display.max_colwidth", 60)
    print(r[["variante", "ops_año", "gana", "pierde", "gana_pts", "pierde_pts", "media_pts", "dev", "val", "prueba",
             "ic90_FM", "años_pos", "pasa"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
