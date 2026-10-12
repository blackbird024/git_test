"""Guía de edgeful ("data-backed futures trading", sept. 2026): ¿las frecuencias altas se traducen en dinero? NQ/MNQ.
Reglas fijadas ANTES de ver resultados. "Ayer" = sesión regular (9:30-16:00 ET) anterior, como en la guía.

Parte 1 · Reproducir sus porcentajes (10-mar-2026 a 8-sep-2026) y ver cómo cambian por año en 2018-2026:
  IB 60 min: un solo lado roto / ambos / ninguno (ruptura por mecha, 10:30-16:00).
  Outside day alcista (abre > PDH): "reversal" = el precio vuelve a tocar el PDH en la sesión. Bajista: espejo con PDL.
  Inside day (abre dentro de ayer): toca PDH o PDL.

Parte 2 · Estrategias, tal como las propone la guía:
  OD (outside day reversal). Abre por encima del PDH → corto; por debajo del PDL → largo (variante "ambos lados";
      la guía solo operaría el alcista). Objetivo: el PDH (PDL). Cierre 15:55. Una operación al día.
      entrada "apertura": a mercado a las 9:30; stop = apertura + q × ATR14 diario, con q = percentil 75 del "spike"
          (lo que sube desde la apertura antes de tocar el PDH) en los outside days que revirtieron de DESARROLLO
          (2018-21) — equivalente al subreport "by-spike", calculado sin mirar validación ni prueba.
      entrada "confirmacion": primera vela de 5 min (9:35-15:00) que cierra por debajo del mínimo de la vela 9:30-9:35
          (cortos); entrada en la apertura siguiente; stop = máximo de la sesión hasta ese momento + 1 tick.
  IB (initial balance breakout). IB = 9:30-10:30. Primera ruptura entre 10:30 y 15:00: orden stop 1 tick fuera del IB,
      stop al otro lado del IB (como dice la guía). Objetivo (variantes): mediana de la extensión más allá del IB
      en DESARROLLO (en múltiplos del rango del IB; equivalente al subreport "by-levels"), 1R, o sin objetivo (15:55).
      Si los dos lados se rompen en el mismo minuto, no se opera.
"""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, run
from data.loaders import TICK, bars5, daily_from_sessions, sessions
from execution_costs.costs import mnq
from strategies.features import daily_context
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest

EXIT_K, LAST_K = 385, 330


def _r(x):
    return round(x / TICK) * TICK


def _open(s):
    O = s.m[:, 0]
    k0 = 0
    while k0 < 5 and np.isnan(O[k0]):
        k0 += 1
    return k0, O[k0]


# ── parte 1: frecuencias
def freq_rows(S, ctx):
    rows = []
    for s in S:
        cd = ctx.get(s.date)
        if not cd or np.isnan(cd.get("prev_high", np.nan)):
            continue
        H, L = s.m[:, 1], s.m[:, 2]
        k0, op = _open(s)
        if np.isnan(op) or s.close_min < 390:
            continue
        ph, pl = cd["prev_high"], cd["prev_low"]
        ibh, ibl = np.nanmax(H[:60]), np.nanmin(L[:60])
        up, dn = np.nanmax(H[60:]) > ibh, np.nanmin(L[60:]) < ibl
        r = dict(date=s.date, ib=("ambos" if up and dn else "uno" if up or dn else "ninguno"))
        if op > ph:
            r["od"] = "alcista"
            r["od_rev"] = np.nanmin(L[k0:]) <= ph
        elif op < pl:
            r["od"] = "bajista"
            r["od_rev"] = np.nanmax(H[k0:]) >= pl
        else:
            r["od"] = "inside"
            r["in_touch"] = (np.nanmax(H[k0:]) >= ph) or (np.nanmin(L[k0:]) <= pl)
        rows.append(r)
    return pd.DataFrame(rows)


def freq_table(f):
    def one(g):
        a, b, i = g[g.od == "alcista"], g[g.od == "bajista"], g[g.od == "inside"]
        return pd.Series(dict(dias=len(g), ib_un_lado=(g.ib == "uno").mean(), od_alc_n=len(a),
                              od_alc_revierte=a.od_rev.astype(float).mean(), od_baj_n=len(b), od_baj_revierte=b.od_rev.astype(float).mean(),
                              inside_n=len(i), inside_toca=i.in_touch.astype(float).mean()))
    return one


# ── parámetros "by-spike" y "by-levels" calculados solo con desarrollo
def spike_q(S, ctx, dev_end):
    xs = []
    for s in S:
        if s.date > dev_end:
            break
        cd = ctx.get(s.date)
        if not cd or np.isnan(cd.get("atr14", np.nan)):
            continue
        k0, op = _open(s)
        if np.isnan(op):
            continue
        H, L = s.m[:, 1], s.m[:, 2]
        for side, lvl in ((-1, cd["prev_high"]), (1, cd["prev_low"])):
            if (side == -1 and op > lvl) or (side == 1 and op < lvl):
                hit = np.where(L[k0:] <= lvl)[0] if side == -1 else np.where(H[k0:] >= lvl)[0]
                if len(hit):
                    j = k0 + hit[0] + 1
                    sp = (np.nanmax(H[k0:j]) - op) if side == -1 else (op - np.nanmin(L[k0:j]))
                    xs.append(sp / cd["atr14"])
    return float(np.percentile(xs, 75)), len(xs)


def ib_ext(S, dev_end):
    xs = []
    for s in S:
        if s.date > dev_end:
            break
        if s.close_min < 390:
            continue
        H, L = s.m[:, 1], s.m[:, 2]
        ibh, ibl = np.nanmax(H[:60]), np.nanmin(L[:60])
        rng = ibh - ibl
        side, k = _first_break(s, ibh, ibl)
        if side is None or rng <= 0:
            continue
        ext = (np.nanmax(H[k:]) - ibh) if side == 1 else (ibl - np.nanmin(L[k:]))
        xs.append(ext / rng)
    return float(np.median(xs)), len(xs)


def _first_break(s, ibh, ibl):
    H, L = s.m[:, 1], s.m[:, 2]
    for k in range(60, min(LAST_K, s.close_min)):
        if np.isnan(H[k]):
            continue
        up, dn = H[k] >= ibh + TICK, L[k] <= ibl - TICK
        if up and dn:
            return None, None
        if up or dn:
            return (1 if up else -1), k
    return None, None


# ── estrategias
def od(s, ctx, entry="apertura", sides="alcista", q=1.0):
    cd = ctx.get(s.date)
    if not cd or np.isnan(cd.get("atr14", np.nan)):
        return None
    k0, op = _open(s)
    if np.isnan(op):
        return None
    ph, pl = cd["prev_high"], cd["prev_low"]
    if op > ph:
        side, tgt = -1, ph
    elif op < pl and sides == "ambos":
        side, tgt = 1, pl
    else:
        return None
    if entry == "apertura":
        return Order(side, "market", k0, _r(op - side * q * cd["atr14"]), tgt, EXIT_K, tag="od_open")
    b = bars5(s)
    if np.isnan(b[0, 3]):
        return None
    ref_lo, ref_hi = b[0, 2], b[0, 1]
    ext = b[0, 1] if side == -1 else b[0, 2]
    for i in range(1, len(b)):
        if 5 * (i + 1) > LAST_K:
            return None
        o, h, l, c = b[i]
        if np.isnan(c):
            continue
        ext = max(ext, h) if side == -1 else min(ext, l)
        if (side == -1 and c < ref_lo) or (side == 1 and c > ref_hi):
            return Order(side, "market", 5 * (i + 1), ext - side * TICK, tgt, EXIT_K, tag="od_conf")
    return None


def ib(s, ctx, target="ext", ext=1.0):
    if s.close_min < 390:
        return None
    H, L = s.m[:, 1], s.m[:, 2]
    if np.isnan(H[:60]).all():
        return None
    ibh, ibl = np.nanmax(H[:60]), np.nanmin(L[:60])
    rng = ibh - ibl
    side, k = _first_break(s, ibh, ibl)
    if side is None or rng <= 0:
        return None
    lvl = ibh + TICK if side == 1 else ibl - TICK
    stop = ibl - TICK if side == 1 else ibh + TICK
    if target == "ext":
        return Order(side, "stop", k, stop, _r((ibh + ext * rng) if side == 1 else (ibl - ext * rng)), EXIT_K,
                     level=lvl, k_last=k + 1, tag="ib")
    if target == "1R":
        return Order(side, "stop", k, stop, None, EXIT_K, level=lvl, k_last=k + 1, target_r=1.0, tag="ib")
    return Order(side, "stop", k, stop, None, EXIT_K, level=lvl, k_last=k + 1, tag="ib")


def main():
    S = sessions()
    ctx = daily_context(daily_from_sessions(S))
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    exp = new_experiment("edgeful")
    pd.set_option("display.width", 260, "display.max_rows", 200, "display.max_colwidth", 60)

    f = freq_rows(S, ctx)
    win = f[(f.date >= "2026-03-10") & (f.date <= "2026-09-08")]
    fr = pd.concat([freq_table(f)(win).rename("10-mar a 8-sep 2026").to_frame().T,
                    f.groupby(f.date.dt.year).apply(freq_table(f))])
    fr.to_csv(exp / "frecuencias.csv")
    print(fr.round(2).to_string())

    dev_end = per["desarrollo"][1]
    q, nq = spike_q(S, ctx, dev_end)
    e, ne = ib_ext(S, dev_end)
    print(f"spike p75 (desarrollo) = {q:.3f} ATR ({nq} días) · extensión mediana IB = {e:.3f} × rango ({ne} días)")

    variants = {f"OD {en}, {sd}": (od, dict(entry=en, sides=sd, q=q))
                for en, sd in itertools.product(("apertura", "confirmacion"), ("alcista", "ambos"))}
    variants.update({f"IB ruptura, objetivo {t}": (ib, dict(target=t, ext=e)) for t in ("ext", "1R", "cierre")})
    rows = []
    for name, (fn, p) in variants.items():
        for scen in ("bajo", "base", "alto"):
            c = mnq(scen)
            t = trades_frame(run(S, fn, c, ctx=ctx, **p), c)
            if scen == "base":
                t.to_csv(exp / f"ops_{''.join(ch if ch.isalnum() else '_' for ch in name)}.csv.gz", index=False)
            for k, tp in split(t, per).items():
                rows.append(dict(variante=name, coste=scen, periodo=k, **summary(tp, cals[k])))
            o = t[t.date >= "2022-01-01"]
            lo, hi = block_bootstrap_mean(o.pnl.to_numpy())
            rows.append(dict(variante=name, coste=scen, periodo="FM 2022-2026", n=len(o), esperanza=o.pnl.mean(),
                             pf=o.pnl[o.pnl > 0].sum() / -o.pnl[o.pnl < 0].sum(), acierto=(o.pnl > 0).mean(),
                             R_medio=o.R.mean(), R_bruto=(o.gross_pts * 2 / o.risk_usd).mean(), ic90_bajo=lo,
                             ic90_alto=hi, riesgo_mediano=o.risk_usd.median()))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="guía edgeful: outside days e IB breakout", reglas=__doc__,
                   spike_q75_atr=q, ib_ext_mediana=e,
                   periodos={k: [str(a.date()), str(b.date())] for k, (a, b) in per.items()})
    b = res[res.coste == "base"]
    print(b[["variante", "periodo", "n", "ops_año", "neto_año", "pf", "esperanza", "acierto", "R_medio", "R_bruto",
             "ic90_bajo", "ic90_alto", "dd_max", "riesgo_mediano"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
