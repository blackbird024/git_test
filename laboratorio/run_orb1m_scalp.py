"""ORB 1 min "scalping" de YouTube (tendencia EMA100 → nivel FVG/demanda → envolvente), traducido a reglas para MNQ.
Reglas fijadas ANTES de ver resultados:

1. Rango: máximo y mínimo de la primera vela de 5 min de NY (9:30-9:35 ET). R = máximo − mínimo.
2. Tendencia: EMA100 de velas de 1 min calculada con las 24 h (como en un gráfico de TradingView con ETH).
   Largos solo si la vela de ruptura cierra por encima de la EMA100; cortos solo por debajo (variante "sin EMA" = ablación).
3. Ruptura con desplazamiento (largos; cortos espejo): una vela de 1 min cierra por encima del máximo del rango y,
   antes de que alguna vela vuelva a cerrar dentro del rango, el precio llega a máximo + 0,7 × R (el "−0,7" del Fibonacci).
   Si vuelve a cerrar dentro antes de llegar, era una "ruptura blanda" y se espera la siguiente.
4. Niveles: demanda = última vela bajista antes de la ruptura (hasta 15 velas atrás, desde las 9:30), zona [mínimo,
   máximo] de esa vela; FVG = el hueco alcista más alto (mín. de la vela i+1 > máx. de la vela i−1) entre la demanda y
   la vela de desplazamiento. Zona de entrada: desde lo alto del FVG (o de la demanda si no hay FVG) hasta el mínimo
   de la demanda.
5. Entrada: después del desplazamiento, el precio retrocede y toca la zona; luego la primera envolvente alcista
   (vela bajista seguida de vela alcista que abre <= cierre anterior y cierra > apertura anterior) → entrada a mercado en la
   apertura siguiente. Se anula si antes alguna vela cierra por debajo del mínimo de la demanda.
6. Stop (variantes): mínimo de la demanda − 1 tick, o mínimo del rango de apertura − 1 tick. Objetivo: 2R.
7. Señales hasta las 11:00 ET; salida por tiempo a las 12:00 ET (scalping "menos de una hora al día"). Una operación al día.
"""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, run
from data.loaders import TICK, nq_1m, sessions
from execution_costs.costs import mnq
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest

DISP, LOOKBACK, LAST_SIG, EXIT_K = 0.7, 15, 90, 150


def ema100_by_session():
    df = nq_1m()
    e = df["close"].ewm(span=100, adjust=False).mean()
    t = e.index
    mm = t.hour * 60 + t.minute - 570
    sel = (mm >= 0) & (mm < 390)
    x = pd.DataFrame({"d": t.date[sel], "k": mm[sel], "e": e.to_numpy()[sel]})
    out = {}
    for d, g in x.groupby("d"):
        a = np.full(390, np.nan)
        a[g.k.to_numpy()] = g.e.to_numpy()
        out[pd.Timestamp(d)] = a
    return out


def orb1m(s, ctx, stop_mode="demanda", use_ema=True):
    O, H, L, C = s.m[:, 0], s.m[:, 1], s.m[:, 2], s.m[:, 3]
    ema = ctx.get(s.date)
    if ema is None or np.isnan(H[:5]).all():
        return None
    orh, orl = np.nanmax(H[:5]), np.nanmin(L[:5])
    R = orh - orl
    if R <= 0:
        return None
    n = min(s.close_min, LAST_SIG)
    k = 5
    while k < n:
        if np.isnan(C[k]):
            k += 1
            continue
        side = 1 if C[k] > orh else -1 if C[k] < orl else 0
        if side == 0:
            k += 1
            continue
        if use_ema and (np.isnan(ema[k]) or side * (C[k] - ema[k]) <= 0):
            k += 1
            continue
        edge = orh if side == 1 else orl
        goal = edge + side * DISP * R
        # 3. desplazamiento antes de volver a cerrar dentro
        j, disp = k, None
        while j < n:
            if not np.isnan(C[j]):
                if side * ((H[j] if side == 1 else L[j]) - goal) >= 0:
                    disp = j
                    break
                if j > k and side * (C[j] - edge) <= 0:
                    break
            j += 1
        if disp is None:
            k = j + 1 if j > k else k + 1
            continue
        # 4. niveles
        d = None
        for i in range(k, max(-1, k - LOOKBACK - 1), -1):
            if not np.isnan(C[i]) and side * (C[i] - O[i]) < 0:
                d = i
                break
        if d is None:
            return None
        dem_far = L[d] if side == 1 else H[d]          # extremo de la demanda (mínimo en largos)
        dem_near = H[d] if side == 1 else L[d]
        top = dem_near
        for i in range(d + 1, disp):
            if np.isnan(H[i - 1]) or np.isnan(L[i + 1]):
                continue
            if side == 1 and L[i + 1] > H[i - 1]:
                top = max(top, L[i + 1])
            if side == -1 and H[i + 1] < L[i - 1]:
                top = min(top, H[i + 1])
        # 5. retroceso a la zona y envolvente
        touched = False
        for t in range(disp + 1, n):
            if np.isnan(C[t]):
                continue
            if side * (C[t] - dem_far) < 0:
                return None
            if side * ((L[t] if side == 1 else H[t]) - top) <= 0:
                touched = True
            if touched and t >= 1 and not np.isnan(C[t - 1]):
                prev_against = side * (C[t - 1] - O[t - 1]) < 0
                engulf = side * (C[t] - O[t]) > 0 and side * (O[t] - C[t - 1]) <= 0 and side * (C[t] - O[t - 1]) > 0
                if prev_against and engulf:
                    base = dem_far if stop_mode == "demanda" else (orl if side == 1 else orh)
                    stop = base - side * TICK
                    return Order(side, "market", t + 1, stop, None, EXIT_K, target_r=2.0, tag="orb1m")
        return None
    return None


def main():
    S = sessions()
    ctx = ema100_by_session()
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    variants = {f"stop {sm}, {'con' if e else 'sin'} EMA100": dict(stop_mode=sm, use_ema=e)
                for sm, e in itertools.product(("demanda", "orb"), (True, False))}
    exp = new_experiment("orb1m_scalp")
    rows = []
    for name, p in variants.items():
        for scen in ("bajo", "base", "alto"):
            c = mnq(scen)
            t = trades_frame(run(S, orb1m, c, ctx=ctx, **p), c)
            if scen == "base":
                t.to_csv(exp / f"ops_{''.join(ch if ch.isalnum() else '_' for ch in name)}.csv.gz", index=False)
            for k, tp in split(t, per).items():
                rows.append(dict(variante=name, coste=scen, periodo=k, **summary(tp, cals[k])))
            o = t[t.date >= "2022-01-01"]
            lo, hi = block_bootstrap_mean(o.pnl.to_numpy())
            rows.append(dict(variante=name, coste=scen, periodo="FM 2022-2026", n=len(o), esperanza=o.pnl.mean(),
                             pf=o.pnl[o.pnl > 0].sum() / -o.pnl[o.pnl < 0].sum(), acierto=(o.pnl > 0).mean(),
                             R_medio=o.R.mean(), R_bruto=(o.gross_pts * 2 / o.risk_usd).mean(), ic90_bajo=lo,
                             ic90_alto=hi, riesgo_mediano=o.risk_usd.median(),
                             salidas=o.reason.value_counts(normalize=True).round(2).to_dict()))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="ORB 1 min scalping (EMA100 + FVG/demanda + envolvente)", reglas=__doc__,
                   periodos={k: [str(a.date()), str(b.date())] for k, (a, b) in per.items()})
    pd.set_option("display.width", 260, "display.max_rows", 200, "display.max_colwidth", 60)
    b = res[res.coste == "base"]
    print(b[["variante", "periodo", "n", "ops_año", "pf", "esperanza", "acierto", "R_medio", "R_bruto",
             "ic90_bajo", "ic90_alto", "riesgo_mediano", "salidas"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
