"""Estrategia "ABC / pullback de rompimiento" de Voy a Ser Trader ("Robin Hood"), traducida a reglas mecánicas para MNQ.
Reglas fijadas ANTES de ver resultados (la versión del vídeo tiene partes discrecionales; esta es la más fiel posible):

Velas de 5 min de la sesión regular, con volumen (suma del volumen de 1 min). Señales de 10:00 a 15:00 ET.
Swings: pivote 2/2 (máximo/mínimo estrictamente mayor/menor que las 2 velas a cada lado), confirmado al cierre de la
2.ª vela posterior. Solo se usan pivotes ya confirmados.
Largo (corto espejo):
  0. Contexto ("fuerza dominante"): EMA20 > EMA200 en 5 min (continuas) y cierre > EMA20 en la vela A-alta… se exige
     EMA20 > EMA200 en la vela de señal.
  1. Impulso A: último swing low confirmado L0 seguido de un swing high confirmado H1, con H1 − L0 >= 1 × ATR14 (5 min).
  2. Retroceso B "ordenado": desde H1, el mínimo B_low queda entre el 23,6 % y el 78,6 % del impulso (sin perder L0),
     dura al menos 2 velas y su volumen medio es MENOR que el del impulso ("secado").
  3. Inicio de C: vela alcista que cierra por encima del máximo de la vela anterior, con volumen > volumen medio de B.
  4. Entrada en la apertura siguiente. Stop: B_low − 1 tick.
Objetivos (variantes): máximo anterior H1 (el que el vídeo dice que da 60-70 % de acierto; se descarta la operación si
H1 está a menos de 0,5R), proyección del impulso (entrada + (H1 − L0)) y 2R fijo. Cierre 15:55; máx. 3 operaciones/día.
"""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from data.loaders import TICK, sessions
from execution_costs.costs import mnq
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest

FIRST_K, LAST_K, MAX_TRADES, TF = 30, 330, 3, 5


def bars_df(S):
    rows = []
    for di, s in enumerate(S):
        m = s.m
        for k in range(s.close_min // TF):
            x = m[TF * k: TF * k + TF]
            ok = ~np.isnan(x[:, 0])
            if ok.any():
                y = x[ok]
                rows.append((di, TF * k + TF, y[0, 0], y[:, 1].max(), y[:, 2].min(), y[-1, 3], np.nansum(y[:, 4])))
    df = pd.DataFrame(rows, columns=["d", "e", "o", "h", "l", "c", "v"])
    df["ema20"] = df.c.ewm(span=20, adjust=False).mean()
    df["ema200"] = df.c.ewm(span=200, adjust=False).mean()
    pc = df.c.shift()
    tr = pd.concat([df.h - df.l, (df.h - pc).abs(), (df.l - pc).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    return df


def signals_day(g, side):
    """Devuelve lista de (índice de la vela de señal, stop, H1/L1, tamaño del impulso) para un lado."""
    h, l, c, o, v = (g[k].to_numpy() for k in ("h", "l", "c", "o", "v"))
    e20, e200, atr = g.ema20.to_numpy(), g.ema200.to_numpy(), g.atr.to_numpy()
    n = len(g)
    hi_piv = [i for i in range(2, n - 2) if h[i] > max(h[i - 2:i]) and h[i] > max(h[i + 1:i + 3])]
    lo_piv = [i for i in range(2, n - 2) if l[i] < min(l[i - 2:i]) and l[i] < min(l[i + 1:i + 3])]
    out = []
    for t in range(4, n):
        if side == 1 and not e20[t] > e200[t]:
            continue
        if side == -1 and not e20[t] < e200[t]:
            continue
        # pivotes confirmados en t: índice <= t-2
        if side == 1:
            hs = [i for i in hi_piv if i <= t - 2]
            if not hs:
                continue
            H1 = hs[-1]
            ls = [i for i in lo_piv if i < H1]
            if not ls:
                continue
            L0 = ls[-1]
            imp = h[H1] - l[L0]
            if imp < atr[t]:
                continue
            if t - H1 < 3:                                   # al menos 2 velas de retroceso antes de la señal
                continue
            b_low = l[H1 + 1:t].min()
            ret = (h[H1] - b_low) / imp
            if not (0.236 <= ret <= 0.786) or b_low <= l[L0] or h[H1 + 1:t].max() > h[H1]:
                continue
            vb, va = v[H1 + 1:t].mean(), v[L0:H1 + 1].mean()
            if not vb < va:
                continue
            if c[t] > o[t] and c[t] > h[t - 1] and v[t] > vb:
                out.append((t, b_low - TICK, h[H1], imp))
        else:
            ls = [i for i in lo_piv if i <= t - 2]
            if not ls:
                continue
            L1 = ls[-1]
            hs = [i for i in hi_piv if i < L1]
            if not hs:
                continue
            H0 = hs[-1]
            imp = h[H0] - l[L1]
            if imp < atr[t] or t - L1 < 3:
                continue
            b_high = h[L1 + 1:t].max()
            ret = (b_high - l[L1]) / imp
            if not (0.236 <= ret <= 0.786) or b_high >= h[H0] or l[L1 + 1:t].min() < l[L1]:
                continue
            vb, va = v[L1 + 1:t].mean(), v[H0:L1 + 1].mean()
            if not vb < va:
                continue
            if c[t] < o[t] and c[t] < l[t - 1] and v[t] > vb:
                out.append((t, b_high + TICK, l[L1], imp))
    return out


def run(S, df, target, cost):
    fills = []
    for di, g in df.groupby("d"):
        g = g.reset_index(drop=True)
        s = S[di]
        sig = sorted([(t, 1, st, lvl, imp) for t, st, lvl, imp in signals_day(g, 1)] +
                     [(t, -1, st, lvl, imp) for t, st, lvl, imp in signals_day(g, -1)])
        free, n = -1, 0
        for t, side, stop, lvl, imp in sig:
            e = int(g.e[t])
            if n >= MAX_TRADES or e < FIRST_K or e > LAST_K or e <= free:
                continue
            ref = g.c[t]
            risk = side * (ref - stop)
            if risk <= 0:
                continue
            if target == "maximo_anterior":
                if side * (lvl - ref) < 0.5 * risk:
                    continue
                o = Order(side, "market", e, stop, lvl, 385, tag="vst_abc")
            elif target == "proyeccion_impulso":
                o = Order(side, "market", e, stop, ref + side * imp, 385, tag="vst_abc")
            else:
                o = Order(side, "market", e, stop, None, 385, target_r=2.0, tag="vst_abc")
            f = simulate(s.date, s.m, s.close_min, o, cost)
            if f is None:
                continue
            fills.append(f)
            n += 1
            free = f.exit_k
    return fills


def main():
    S = sessions()
    df = bars_df(S)
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    exp = new_experiment("vst_abc")
    rows = []
    for target in ("maximo_anterior", "proyeccion_impulso", "2R"):
        for scen in ("bajo", "base", "alto"):
            c = mnq(scen)
            t = trades_frame(run(S, df, target, c), c)
            if scen == "base":
                t.to_csv(exp / f"ops_{target}.csv.gz", index=False)
            for k, tp in split(t, per).items():
                rows.append(dict(variante=target, coste=scen, periodo=k, **summary(tp, cals[k])))
            o = t[t.date >= "2022-01-01"]
            lo, hi = block_bootstrap_mean(o.pnl.to_numpy())
            rows.append(dict(variante=target, coste=scen, periodo="FM 2022-2026", n=len(o), esperanza=o.pnl.mean(),
                             pf=o.pnl[o.pnl > 0].sum() / -o.pnl[o.pnl < 0].sum(), acierto=(o.pnl > 0).mean(),
                             R_medio=o.R.mean(), R_bruto=(o.gross_pts * 2 / o.risk_usd).mean(), ic90_bajo=lo, ic90_alto=hi,
                             riesgo_mediano=o.risk_usd.median()))
        print(target, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="VST ABC / pullback (Robin Hood)", reglas=__doc__,
                   periodos={k: [str(a.date()), str(b.date())] for k, (a, b) in per.items()})
    pd.set_option("display.width", 260, "display.max_rows", 200)
    b = res[res.coste == "base"]
    print(b[["variante", "periodo", "n", "ops_año", "neto_año", "pf", "esperanza", "acierto", "R_medio", "R_bruto",
             "ic90_bajo", "ic90_alto", "dd_max", "riesgo_mediano"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
