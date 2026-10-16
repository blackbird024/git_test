"""Indicador "Order Flow VWAP Deviation" (LuxAlgo): el CÍRCULO de "stop run" = el precio cruza un máximo/mínimo pivote
anterior con un volumen mucho mayor de lo normal → "posible agotamiento o giro". Se mide en MNQ (NQ 1 min → velas de
5 min, 24 h, 2018-2026). Reglas fijadas ANTES de ver resultados (la configuración exacta de LuxAlgo no se publica):
  Pivotes: máximo (mínimo) estricto con N velas a cada lado, N ∈ {5, 10}; confirmado N velas después; nivel activo
    hasta que se cruza o pasan 2 días; se borran en cada cambio de contrato.
  Barrida ("punto"): vela de 5 min cuyo máximo supera un pivote alto activo (o mínimo bajo uno bajo) con volumen
    > M × media de volumen de 20 velas, M ∈ {1,5, 2}. Una señal por vela (si cruza varios, cuenta una).
  Medida 1 · CARRERA (2 h): desde el cierre de la vela del punto, ¿llega antes a 1 ATR(14) en CONTRA de la barrida
    (gira) o a 1 ATR a FAVOR (sigue)?
  Medida 2 · OPERACIONES (entrada en la apertura siguiente, salida en 2 h como máximo, 1 MNQ, coste base):
    GIRO: en contra de la barrida, stop 1 tick más allá del extremo de la vela del punto, objetivo 1 R y 2 R.
    SIGUE: a favor, mismo riesgo en puntos, objetivo 1 R.
  Por sesión (hora de NY): Asia 18-3, Londres 3-9:30, NY 9:30-16.
Selección: neto > 0 en dev (2018-21) Y val (2022-24), n_val >= 30."""
import itertools

import numpy as np
import pandas as pd

from data.loaders import nq_1m
from execution_costs.costs import fut
from validation.runner import new_experiment, write_manifest

TICK, PV, H = 0.25, 2.0, 24


def barras5():
    df = nq_1m()
    g = df.resample("5min", label="left", closed="left")
    b = pd.DataFrame(dict(o=g.open.first(), h=g.high.max(), l=g.low.min(), c=g.close.last(), v=g.volume.sum(),
                          ins=g.instrument_id.last())).dropna(subset=["o"])
    pc = b.c.shift()
    tr = pd.concat([b.h - b.l, (b.h - pc).abs(), (b.l - pc).abs()], axis=1).max(axis=1)
    b["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    b["vma"] = b.v.rolling(20).mean()
    return b


def eventos(b, N, M):
    h, l, v, vma, ins = (b[k].to_numpy() for k in ("h", "l", "v", "vma", "ins"))
    n = len(b)
    act_h, act_l, out = [], [], []
    for i in range(n):
        if i > 0 and ins[i] != ins[i - 1]:
            act_h, act_l = [], []
        p = i - N                                       # pivote que se confirma ahora
        if p >= N:
            w = slice(p - N, p + N + 1)
            if h[p] == h[w].max() and (h[w] == h[p]).sum() == 1:
                act_h.append((h[p], p))
            if l[p] == l[w].min() and (l[w] == l[p]).sum() == 1:
                act_l.append((l[p], p))
        act_h = [(x, k) for x, k in act_h if i - k < 576]
        act_l = [(x, k) for x, k in act_l if i - k < 576]
        cu = [x for x in act_h if h[i] > x[0]]
        cd = [x for x in act_l if l[i] < x[0]]
        if cu:
            act_h = [x for x in act_h if x not in cu]
        if cd:
            act_l = [x for x in act_l if x not in cd]
        surge = vma[i] > 0 and v[i] > M * vma[i]
        if surge and cu and not cd:
            out.append((i, 1))
        elif surge and cd and not cu:
            out.append((i, -1))
    return out


def medir(b, ev, c):
    o, h, l, cl, atr, ins = (b[k].to_numpy() for k in ("o", "h", "l", "c", "atr", "ins"))
    idx = b.index
    rows = []
    sl = c.slip
    for i, s in ev:
        if i + 1 + H >= len(b) or ins[i + H + 1] != ins[i]:
            continue
        X = atr[i]
        ref = cl[i]
        rev, con = ref - s * X, ref + s * X
        res = "nada"
        for j in range(i + 1, i + 1 + H):
            r_hit = (l[j] <= rev) if s == 1 else (h[j] >= rev)
            c_hit = (h[j] >= con) if s == 1 else (l[j] <= con)
            if r_hit and c_hit:
                res = "ambos"
                break
            if r_hit:
                res = "gira"
                break
            if c_hit:
                res = "sigue"
                break
        row = dict(date=idx[i], hora=idx[i].hour + idx[i].minute / 60, lado=s, carrera=res)
        ext = h[i] if s == 1 else l[i]
        for nombre, side, objr in (("giro_1R", -s, 1.0), ("giro_2R", -s, 2.0), ("sigue_1R", s, 1.0)):
            e = o[i + 1] + side * sl
            if nombre.startswith("giro"):
                stop = ext + s * TICK
                R = side * (e - stop)
            else:
                R = abs(e - (ext + s * TICK))
                stop = e - side * R
            if R <= 0:
                continue
            tgt = e + side * objr * R
            xp = None
            for j in range(i + 1, i + 1 + H):
                if (side == 1 and l[j] <= stop) or (side == -1 and h[j] >= stop):
                    xp = (min(o[j], stop) if side == 1 else max(o[j], stop)) - side * sl
                    break
                if (side == 1 and h[j] >= tgt + TICK) or (side == -1 and l[j] <= tgt - TICK):
                    xp = tgt
                    break
            if xp is None:
                xp = cl[i + H] - side * sl
            row[nombre] = side * (xp - e) * PV - 2 * c.fixed_per_side
            row[nombre + "_bruto"] = side * (xp - e)
        rows.append(row)
    return pd.DataFrame(rows)


def sesion(hh):
    return "NY 9:30-16" if 9.5 <= hh < 16 else "Londres 3-9:30" if 3 <= hh < 9.5 else "Asia 18-3"


def main():
    b = barras5()
    c = fut("MNQ", "base")
    exp = new_experiment("stop_run_luxalgo")
    rows = []
    for N, M in itertools.product((5, 10), (1.5, 2.0)):
        t = medir(b, eventos(b, N, M), c)
        t["sesion"] = t.hora.map(sesion)
        t.to_csv(exp / f"eventos_N{N}_M{M}.csv.gz", index=False)
        for ses, g in [("TODAS", t)] + list(t.groupby("sesion")):
            y = g.date.dt.year
            d = dict(N=N, M=M, sesion=ses, eventos_año=len(g) / 8.75,
                     gira=(g.carrera == "gira").mean(), sigue=(g.carrera == "sigue").mean())
            for k in ("giro_1R", "giro_2R", "sigue_1R"):
                x = g[k].dropna()
                yy = g.loc[x.index, "date"].dt.year
                d[k + "_gana"] = (g.loc[x.index, k + "_bruto"] > 0).mean()
                d[k + "_año$"] = x.sum() / 8.75
                d[k + "_dev"] = x[yy <= 2021].mean()
                d[k + "_val"] = x[(yy >= 2022) & (yy <= 2024)].mean()
                d[k + "_prueba"] = x[yy >= 2025].mean()
                d[k + "_pasa"] = d[k + "_dev"] > 0 and d[k + "_val"] > 0 and ((yy >= 2022) & (yy <= 2024)).sum() >= 30
            rows.append(d)
        print(N, M, "ok", flush=True)
    r = pd.DataFrame(rows)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="stop run (círculo) del indicador LuxAlgo Order Flow VWAP Deviation", reglas=__doc__)
    pd.set_option("display.width", 320)
    print(r[["N", "M", "sesion", "eventos_año", "gira", "sigue", "giro_1R_gana", "giro_1R_año$", "giro_1R_dev",
             "giro_1R_val", "giro_1R_prueba", "giro_2R_año$", "sigue_1R_gana", "sigue_1R_año$", "giro_1R_pasa",
             "giro_2R_pasa", "sigue_1R_pasa"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
