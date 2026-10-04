"""Backtest de Smart Money Concepts (SMC) en la sesión de Londres, con las definiciones del indicador
"Smart Money Concepts [LuxAlgo]" y futuros CME de Databento 2018-2026 (velas de 5 minutos).

Definiciones (copiadas de LuxAlgo):
  Pivote interno (tamaño 5): una vela cuyo máximo no superan las 5 siguientes y que cambia la "pierna"
  de alcista a bajista (al revés para mínimos). Se conoce 5 velas después.
  BOS / CHoCH: un cierre por encima del último pivote alto interno (o por debajo del bajo). Es CHoCH si la
  tendencia interna era la contraria; BOS si era la misma.
  Order block: en una ruptura alcista, la vela con el mínimo más bajo entre el pivote roto y la ruptura
  (con el cambio de LuxAlgo para velas muy volátiles). Bajista al revés.
  Rango asiático: 20:00-00:00 NY.
  Sesgo HTF: tendencia de la estructura interna en velas de 1 hora (último BOS/CHoCH de 1h ya cerrado).

Variantes (entradas de 2:00 a 5:00 NY, una operación por sesión, cierre forzoso a las 11:00 NY):
  CHoCH directo           entrar al abrir la vela siguiente al CHoCH, stop en el extremo del order block.
  CHoCH + OB              orden límite en el borde del order block (hasta 12 velas), stop al otro lado.
  Asia sweep + ...        antes del CHoCH el precio barrió el máximo (para cortos) o mínimo (largos) de Asia.
  ... + sesgo 1h          solo a favor de la tendencia de 1 hora.
  BOS + OB + sesgo 1h     continuación: BOS a favor de la tendencia de 1h y entrada en el order block.
Objetivo 2R. Coste 0,003 % por lado. Resultados en R (veces el riesgo).

Uso:
    python smc_london_backtest.py
"""

from datetime import timedelta

import numpy as np
import pandas as pd

from crt_backtest import load_5m

SIZE = 5
COST = 0.00003
SPLIT = 2023


def structure(df, size=SIZE):
    """Rupturas de estructura interna al estilo LuxAlgo: lista de dicts (i, dir, tag, ob_top, ob_bot)."""
    h, l, c = (df[k].to_numpy() for k in ("high", "low", "close"))
    n = len(df)
    tr = np.maximum(h - l, np.maximum(abs(h - np.r_[c[0], c[:-1]]), abs(l - np.r_[c[0], c[:-1]])))
    atr = pd.Series(tr).ewm(alpha=1 / 200, adjust=False).mean().to_numpy()
    vol = (h - l) >= 2 * atr
    ph = np.where(vol, l, h)                       # parsedHigh / parsedLow de LuxAlgo
    pl = np.where(vol, h, l)
    leg, trend = 0, 0
    hi_lvl = lo_lvl = np.nan
    hi_idx = lo_idx = 0
    hi_x = lo_x = True
    events = []
    trend_arr = np.zeros(n, int)
    for i in range(size, n):
        win_h, win_l = h[i - size + 1:i + 1].max(), l[i - size + 1:i + 1].min()
        new_leg = leg
        if h[i - size] > win_h:
            new_leg = 0
        elif l[i - size] < win_l:
            new_leg = 1
        if new_leg != leg:
            if new_leg == 1:                                       # empieza pierna alcista: pivote bajo
                lo_lvl, lo_idx, lo_x = l[i - size], i - size, False
            else:
                hi_lvl, hi_idx, hi_x = h[i - size], i - size, False
            leg = new_leg
        if not hi_x and c[i] > hi_lvl and c[i - 1] <= hi_lvl:
            tag = "CHoCH" if trend == -1 else "BOS"
            hi_x, trend = True, 1
            k = hi_idx + int(np.argmin(pl[hi_idx:i]))
            events.append(dict(i=i, dir=1, tag=tag, ob_top=ph[k], ob_bot=pl[k], piv=hi_idx))
        if not lo_x and c[i] < lo_lvl and c[i - 1] >= lo_lvl:
            tag = "CHoCH" if trend == 1 else "BOS"
            lo_x, trend = True, -1
            k = lo_idx + int(np.argmax(ph[lo_idx:i]))
            events.append(dict(i=i, dir=-1, tag=tag, ob_top=ph[k], ob_bot=pl[k], piv=lo_idx))
        trend_arr[i] = trend
    return events, trend_arr


def htf_trend(df5):
    h1 = df5.resample("1h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    _, tr = structure(h1)
    s = pd.Series(tr, index=h1.index + pd.Timedelta(hours=1))      # se conoce al cerrar la vela de 1h
    return s.reindex(df5.index, method="ffill").fillna(0).to_numpy()


def run(sym):
    df = load_5m(sym)
    t = df.index
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    hrs = (t.hour + t.minute / 60).to_numpy()
    events, _ = structure(df)
    bias = htf_trend(df)
    ev = pd.DataFrame(events)
    ev["t"] = t[ev["i"].to_numpy()]
    ev["date"] = ev["t"].dt.date
    ev["hr"] = hrs[ev["i"].to_numpy()]
    london = ev[(ev["hr"] >= 2) & (ev["hr"] < 5)]
    # rango asiático y máximos/mínimos desde medianoche
    date_arr = np.array(t.date)
    asia = {}
    for d, g in df[(hrs >= 20)].groupby(pd.Index(t[hrs >= 20].date)):
        asia[d + timedelta(days=1)] = (g["high"].max(), g["low"].min())
    pos_of_date = {}
    for d in sorted(set(london["date"])):
        pos_of_date[d] = np.searchsorted(t, pd.Timestamp(d, tz="America/New_York"))

    def manage(i_entry, entry, stop, d, side, exit_i):
        risk = abs(entry - stop)
        if risk <= 0:
            return None
        tgt = entry + side * 2 * risk
        for j in range(i_entry, min(exit_i, len(c))):
            if (side == 1 and l[j] <= stop) or (side == -1 and h[j] >= stop):
                return -1 - 2 * COST * entry / risk
            if (side == 1 and h[j] >= tgt) or (side == -1 and l[j] <= tgt):
                return 2 - 2 * COST * entry / risk
        px = o[min(exit_i, len(c) - 1)]
        return side * (px - entry) / risk - 2 * COST * entry / risk

    variants = {
        "CHoCH directo": dict(tags=("CHoCH",), ob=False, sweep=False, htf=False),
        "CHoCH + OB": dict(tags=("CHoCH",), ob=True, sweep=False, htf=False),
        "CHoCH directo + sesgo 1h": dict(tags=("CHoCH",), ob=False, sweep=False, htf=True),
        "CHoCH + OB + sesgo 1h": dict(tags=("CHoCH",), ob=True, sweep=False, htf=True),
        "Asia sweep + CHoCH directo": dict(tags=("CHoCH",), ob=False, sweep=True, htf=False),
        "Asia sweep + CHoCH + OB": dict(tags=("CHoCH",), ob=True, sweep=True, htf=False),
        "Asia sweep + CHoCH + OB + sesgo 1h": dict(tags=("CHoCH",), ob=True, sweep=True, htf=True),
        "BOS + OB + sesgo 1h": dict(tags=("BOS",), ob=True, sweep=False, htf=True),
        "BOS o CHoCH + OB + sesgo 1h": dict(tags=("BOS", "CHoCH"), ob=True, sweep=False, htf=True),
    }
    rows = []
    for name, v in variants.items():
        for d, g in london.groupby("date"):
            if v["sweep"] and d not in asia:
                continue
            day0 = pos_of_date[d]
            exit_i = np.searchsorted(t, pd.Timestamp(d, tz="America/New_York") + pd.Timedelta(hours=11))
            for _, e in g.iterrows():
                if e["tag"] not in v["tags"]:
                    continue
                side, i = e["dir"], e["i"]
                if v["htf"] and bias[i] != side:
                    continue
                if v["sweep"]:
                    ah, al = asia[d]
                    seg_h, seg_l = h[day0:i + 1], l[day0:i + 1]
                    if side == -1 and not (seg_h.max() > ah):
                        continue
                    if side == 1 and not (seg_l.min() < al):
                        continue
                if not v["ob"]:
                    entry, stop = o[i + 1], (e["ob_bot"] if side == 1 else e["ob_top"])
                    if (entry - stop) * side <= 0:
                        continue
                    r = manage(i + 1, entry, stop, d, side, exit_i)
                else:
                    edge, stop = (e["ob_top"], e["ob_bot"]) if side == 1 else (e["ob_bot"], e["ob_top"])
                    r = None
                    for j in range(i + 1, min(i + 13, exit_i)):
                        if hrs[j] >= 5:
                            break
                        if (side == 1 and l[j] <= edge) or (side == -1 and h[j] >= edge):
                            entry = min(o[j], edge) if side == 1 else max(o[j], edge)
                            if (entry - stop) * side <= 0:
                                break
                            r = manage(j, entry, stop, d, side, exit_i)
                            break
                    if r is None:
                        continue
                if r is not None:
                    rows.append(dict(variante=name, day=d, r=r))
                    break                                    # una operación por sesión
    return pd.DataFrame(rows)


def report(sym, res):
    print(f"\n=== {sym}: SMC en Londres (entradas 2:00-5:00 NY, objetivo 2R), 2018-2026 ===")
    print(f"  {'Variante':38}{'Ops':>5}{'Ops/mes':>9}{'Acierto':>9}{'R med':>8}{'R tot':>8}{'2018-22':>9}{'2023-26':>9}{'Años+':>7}")
    months = 105
    for name, g in res.groupby("variante", sort=False):
        y = pd.to_datetime(g["day"]).dt.year
        by = g.groupby(y)["r"].sum()
        print(f"  {name:38}{len(g):>5}{len(g) / months:>9.1f}{(g.r > 0).mean():>9.0%}{g.r.mean():>+8.2f}{g.r.sum():>+8.1f}"
              f"{g.r[y < SPLIT].sum():>+9.1f}{g.r[y >= SPLIT].sum():>+9.1f}{f'{(by > 0).sum()}/{len(by)}':>7}")


def main():
    for sym in ("NQ", "ES", "GC"):
        report(sym, run(sym))
    print("\n  R = veces el riesgo. Con objetivo 2R hace falta acertar más del 33 % para ganar.")


if __name__ == "__main__":
    main()
