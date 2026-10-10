"""VWAP + EMA 9 + RSI(14) en MNQ, velas de 5 y 15 min (señales) con ejecución en velas de 1 min.

Reglas fijadas ANTES de ver resultados (versión habitual de la estrategia):
  Largo, al cierre de una vela del marco elegido:
    1. cierre > VWAP de la sesión (tendencia del día)
    2. RSI(14) > 50 (impulso)
    3. retroceso a la EMA 9: el mínimo de la vela toca la EMA 9 y la vela cierra por encima, alcista (cierre > apertura)
  Corto: espejo (cierre < VWAP, RSI < 50, el máximo toca la EMA 9, cierre por debajo, vela bajista).
  Entrada a mercado en la apertura siguiente. Stop: mínimo (máximo) de la vela de señal ∓ 1 tick.
  Salidas (dos variantes): objetivo 2R, o salir cuando una vela cierra al otro lado de la EMA 9 (sin objetivo).
  Señales de 10:00 a 15:00 ET; cierre forzoso 15:55; máx. 3 operaciones al día, una después de otra.
  VWAP: anclado a las 9:30 con el volumen de 1 min. EMA 9 y RSI 14 (Wilder): calculados de forma continua sobre las
  velas de la sesión regular (se arrastran de un día a otro).
"""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from data.loaders import TICK, sessions
from execution_costs.costs import mnq
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest

FIRST_K, LAST_K, MAX_TRADES = 30, 330, 3          # 10:00, 15:00 ET


def tf_bars(s, tf):
    n = s.close_min // tf
    out = []
    m = s.m
    pv = np.nan_to_num((m[:, 1] + m[:, 2] + m[:, 3]) / 3) * np.nan_to_num(m[:, 4])
    cpv, cv = np.cumsum(pv), np.cumsum(np.nan_to_num(m[:, 4]))
    for k in range(n):
        x = m[tf * k: tf * k + tf]
        ok = ~np.isnan(x[:, 0])
        if not ok.any():
            continue
        y = x[ok]
        e = tf * k + tf                                  # minuto de cierre (exclusivo)
        vw = cpv[e - 1] / cv[e - 1] if cv[e - 1] > 0 else np.nan
        out.append((e, y[0, 0], y[:, 1].max(), y[:, 2].min(), y[-1, 3], vw))
    return out


def indicators(S, tf):
    """EMA 9 y RSI 14 continuos sobre las velas de la sesión regular de todos los días."""
    rows = []
    for di, s in enumerate(S):
        for b in tf_bars(s, tf):
            rows.append((di,) + b)
    df = pd.DataFrame(rows, columns=["d", "e", "o", "h", "l", "c", "vwap"])
    df["ema9"] = df.c.ewm(span=9, adjust=False).mean()
    delta = df.c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    df["rsi"] = 100 - 100 / (1 + up / dn)
    return df


def run(S, tf, exit_mode, cost):
    df = indicators(S, tf)
    fills = []
    for di, g in df.groupby("d"):
        s = S[di]
        bars = g.to_dict("records")
        free_from, n = 0, 0
        for i, b in enumerate(bars):
            if n >= MAX_TRADES:
                break
            e = b["e"]
            if e < FIRST_K or e > LAST_K or e <= free_from or np.isnan(b["vwap"]):
                continue
            side = 0
            if b["c"] > b["vwap"] and b["rsi"] > 50 and b["l"] <= b["ema9"] < b["c"] and b["c"] > b["o"]:
                side = 1
            elif b["c"] < b["vwap"] and b["rsi"] < 50 and b["h"] >= b["ema9"] > b["c"] and b["c"] < b["o"]:
                side = -1
            if not side:
                continue
            stop = b["l"] - TICK if side == 1 else b["h"] + TICK
            if exit_mode == "2R":
                o = Order(side, "market", e, stop, None, 385, target_r=2.0, tag=f"vwap_ema9_rsi_{tf}")
            else:
                xk = 385
                for b2 in bars[i + 1:]:
                    if (side == 1 and b2["c"] < b2["ema9"]) or (side == -1 and b2["c"] > b2["ema9"]):
                        xk = b2["e"]; break
                o = Order(side, "market", e, stop, None, xk, tag=f"vwap_ema9_rsi_{tf}")
            f = simulate(s.date, s.m, s.close_min, o, cost)
            if f is None:
                continue
            fills.append(f)
            n += 1
            free_from = f.exit_k
    return fills


def main():
    S = sessions()
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    exp = new_experiment("vwap_ema9_rsi")
    rows = []
    for tf, ex in itertools.product((5, 15), ("2R", "cruce_EMA9")):
        name = f"{tf} min, salida {ex}"
        for scen in ("bajo", "base", "alto"):
            c = mnq(scen)
            t = trades_frame(run(S, tf, ex, c), c)
            if scen == "base":
                t.to_csv(exp / f"ops_{tf}m_{ex}.csv.gz", index=False)
            for k, tp in split(t, per).items():
                rows.append(dict(variante=name, coste=scen, periodo=k, **summary(tp, cals[k])))
            o = t[t.date >= "2022-01-01"]
            lo, hi = block_bootstrap_mean(o.pnl.to_numpy())
            rows.append(dict(variante=name, coste=scen, periodo="FM 2022-2026", n=len(o), esperanza=o.pnl.mean(),
                             pf=o.pnl[o.pnl > 0].sum() / -o.pnl[o.pnl < 0].sum(), acierto=(o.pnl > 0).mean(),
                             ic90_bajo=lo, ic90_alto=hi, R_medio=o.R.mean(),
                             R_bruto=(o.gross_pts * 2 / o.risk_usd).mean(), riesgo_mediano=o.risk_usd.median()))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="VWAP + EMA 9 + RSI(14), 5 y 15 min, MNQ",
                   periodos={k: [str(a.date()), str(b.date())] for k, (a, b) in per.items()},
                   reglas=__doc__)
    pd.set_option("display.width", 260, "display.max_rows", 200)
    b = res[res.coste == "base"]
    print(b[["variante", "periodo", "n", "ops_año", "neto_año", "pf", "esperanza", "acierto", "R_medio", "R_bruto",
             "ic90_bajo", "ic90_alto", "dd_max", "riesgo_mediano"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
