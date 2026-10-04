"""Motor de referencia: Daily CRT + Reversal / Continuation + Confirmation Model B+ (ejecución en 5m).

Misma lógica que tradingview/DailyCRT_BPlus.pine. Todo con velas cerradas; nada mira al futuro.

Jerarquía (Daily alcista; el bajista es el espejo):
  Daily fuerte alcista (vela CME 18:00-17:00 ya cerrada) → PDH/PDL → reversal CORTO en el PDH primero:
    barrido del PDH → cierre de vuelta < PDH + CISD bajista dentro de `rev_window` velas desde el extremo
    → REVERSAL CONFIRMADO (bloquea la continuación ese día).
  Si aparece un CISD bajista con cierre todavía ≥ PDH, o expira la ventana → REVERSAL FALLIDO (irreversible)
    → CONTINUACIÓN LARGA: retroceso desde el último máximo que toca un POI (FVG, swing roto, order block)
      y CISD alcista sobre la serie bajista del retroceso (continuation block).
  Modelos: A reversal · B reversal + continuación · C + B+ (liquidez + iFVG) · D + FVG HTF de 15m/1h.

Uso:
    python dcrt_bplus_engine.py
"""

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

import cm_bplus_engine as E

NS_H = 3600 * 10**9


@dataclass
class Cfg:
    name: str = "D"
    body_min: float = 0.5
    close_dist: float = 0.25
    above_prev: bool = False
    min_sweep: float = 0.0
    rev_window: int = 12
    use_cont: bool = True
    bplus: bool = True
    use_htf: bool = True
    poi_fvg: bool = True
    poi_swing: bool = True
    poi_ob: bool = True
    cont_window: int = 12
    ifvg_lookback: int = 12
    sessions: tuple = ((2.0, 5.0, 11.0),)
    entry: str = "next_open"
    stop_buf: float = 0.0
    rr: float = 2.0
    cost_pts: float = 1.0


MODELS = {
    "A · Daily + PDH/PDL + reversal": dict(use_cont=False, bplus=False, use_htf=False),
    "B · + continuación": dict(use_cont=True, bplus=False, use_htf=False),
    "C · + B+ (liquidez, iFVG, CISD)": dict(use_cont=True, bplus=True, use_htf=False),
    "D · + FVG HTF 15m/1h": dict(use_cont=True, bplus=True, use_htf=True),
}


def series_open(m, i, bull):
    """Apertura de la primera vela de la última serie (alcista si bull) que termina en i (o en i-1)."""
    o, c = m.o, m.c
    is_s = (lambda q: c[q] > o[q]) if bull else (lambda q: c[q] < o[q])
    s = i if is_s(i) else i - 1
    if s < 1 or not is_s(s):
        return o[i]
    while s > 1 and is_s(s - 1):
        s -= 1
    return o[s]


def gaps(m, a, b, kind):
    """FVG de 5m con tercera vela en [a, b]: kind 1 alcista (borde a romper = h[q-2]), -1 bajista (l[q-2])."""
    out = []
    for q in range(max(a, 2), b + 1):
        if kind == 1 and m.l[q] > m.h[q - 2]:
            out.append((q, m.h[q - 2], m.l[q]))
        if kind == -1 and m.h[q] < m.l[q - 2]:
            out.append((q, m.l[q - 2], m.h[q]))
    return out


def ifvg_cands(m, ext, d_move, lb):
    """FVG del movimiento que llega al extremo (d_move = dirección de ese movimiento), no invertidos antes."""
    out = []
    for q, edge, far in gaps(m, ext - lb, ext, d_move):
        seg = m.c[q + 1:ext]
        if d_move == 1 and (seg < edge).any():
            continue
        if d_move == -1 and (seg > edge).any():
            continue
        out.append(edge)
    return out


def inverted(m, j, cands, d_move):
    return any((m.c[j] < e) if d_move == 1 else (m.c[j] > e) for e in cands)


def poi_touch(m, cfg, ecfg, zones, d, p, hi, lvl):
    """¿El extremo del retroceso p toca un POI a favor de d? Devuelve el tipo o ''."""
    ext = m.l[p] if d == 1 else m.h[p]
    tol = 0.25 * m.atr[p]
    if cfg.poi_fvg:
        for q, near, far in gaps(m, p - 48, p - 1, d):
            bot, top = (near, far) if d == 1 else (far, near)
            seg = m.c[q + 1:p]
            if (d == 1 and (seg < bot).any()) or (d == -1 and (seg > top).any()):
                continue
            if (d == 1 and ext <= top and m.c[p] >= bot) or (d == -1 and ext >= bot and m.c[p] <= top):
                return "FVG 5m"
        ok, tf, _, _ = E.htf_touch(m, ecfg, zones, p, d, ext)
        if ok:
            return f"FVG {tf}"
    if cfg.poi_swing:
        levels = [lvl]
        lo_p, hi_p = m.pivots(3, 3)
        piv = hi_p if d == 1 else lo_p
        for k in range(max(hi - 48, 0), hi - 3):
            if piv[k]:
                levels.append(m.h[k] if d == 1 else m.l[k])
        for L in levels:
            if (d == 1 and ext <= L + tol and m.c[p] >= L - tol and L < m.h[hi]) or \
               (d == -1 and ext >= L - tol and m.c[p] <= L + tol and L > m.l[hi]):
                return "swing"
    if cfg.poi_ob:
        for q in range(hi - 1, max(hi - 36, 1), -1):
            if (d == 1 and m.c[q] < m.o[q]) or (d == -1 and m.c[q] > m.o[q]):
                if (d == 1 and ext <= m.h[q] and m.c[p] >= m.l[q]) or (d == -1 and ext >= m.l[q] and m.c[p] <= m.h[q]):
                    return "OB"
                break
    return ""


def liq_taken(m, p, d):
    """¿El extremo del retroceso barrió un swing de 5m (pivote 3/3) que seguía vivo?"""
    lo_p, hi_p = m.pivots(3, 3)
    piv = lo_p if d == 1 else hi_p
    for k in range(p - 4, max(p - 48, 0), -1):
        if piv[k]:
            if d == 1 and m.l[p] < m.l[k] and m.l[k + 1:p].min() >= m.l[k]:
                return True
            if d == -1 and m.h[p] > m.h[k] and m.h[k + 1:p].max() <= m.h[k]:
                return True
    return False


def trade(m, cfg, i, side, stop, exit_h, kind, bias, info):
    if cfg.entry == "next_open":
        k0, entry = i + 1, m.o[i + 1]
    else:
        k0, entry = i + 1, m.c[i]
    stop = stop - side * cfg.stop_buf
    risk = (entry - stop) * side
    if risk <= 0:
        return None
    tgt = entry + side * cfg.rr * risk
    exit_t = m.day[i] + int(exit_h * NS_H)
    r = None
    q = k0
    while q < len(m.c) and m.t[q] < exit_t:
        if (side == 1 and m.l[q] <= stop) or (side == -1 and m.h[q] >= stop):
            r = -1.0
            break
        if (side == 1 and m.h[q] >= tgt) or (side == -1 and m.l[q] <= tgt):
            r = cfg.rr
            break
        q += 1
    if r is None:
        px = m.o[q] if q < len(m.c) else m.c[-1]
        r = side * (px - entry) / risk
    return dict(t=m.idx[i], kind=kind, side=side, bias=bias, r=r - cfg.cost_pts / risk, risk=risk, **info)


def run(m, cfg):
    ecfg = E.Config(htf_days=3.0)
    zones = [m.fvgs(tf, "htf_close", 3.0) for tf in ("15min", "1h")]
    sday = ((m.idx + pd.Timedelta(hours=6)).normalize()).asi8
    starts = np.r_[0, np.nonzero(sday[1:] != sday[:-1])[0] + 1]
    ends = np.r_[starts[1:], len(sday)]
    O = np.array([m.o[a] for a in starts])
    Hh = np.array([m.h[a:b].max() for a, b in zip(starts, ends)])
    Ll = np.array([m.l[a:b].min() for a, b in zip(starts, ends)])
    C = np.array([m.c[b - 1] for b in ends])
    win = np.zeros(len(m.c), float)                                  # hora de salida de la sesión (0 = fuera)
    for s, e, x in cfg.sessions:
        win[(m.hr >= s) & (m.hr < e)] = x
    st = {k: 0 for k in ("días alcistas", "días bajistas", "días neutrales", "barridos", "reversal confirmado",
                         "reversal fallido: CISD fuera", "reversal fallido: expirado", "continuación: CISD tras POI",
                         "entradas reversal", "entradas continuación", "rechazo: sin HTF", "rechazo: sin iFVG",
                         "rechazo: sin liquidez", "rechazo: sin POI", "rechazo: fuera de sesión", "sin desenlace")}
    trades = []
    for n in range(2, len(starts)):
        rng = Hh[n - 1] - Ll[n - 1]
        if rng <= 0:
            continue
        body = abs(C[n - 1] - O[n - 1]) / rng
        bull = C[n - 1] > O[n - 1] and body >= cfg.body_min and (Hh[n - 1] - C[n - 1]) / rng <= cfg.close_dist
        bear = C[n - 1] < O[n - 1] and body >= cfg.body_min and (C[n - 1] - Ll[n - 1]) / rng <= cfg.close_dist
        if cfg.above_prev:
            bull &= C[n - 1] > Hh[n - 2]
            bear &= C[n - 1] < Ll[n - 2]
        if not (bull or bear):
            st["días neutrales"] += 1
            continue
        d = 1 if bull else -1
        st["días alcistas" if bull else "días bajistas"] += 1
        pdh, pdl = Hh[n - 1], Ll[n - 1]
        lvl = pdh if d == 1 else pdl
        a, b = starts[n], ends[n]
        state, done = "WAIT", False
        for j in range(max(a, 60), b - 1):
            if state == "WAIT":
                if (d == 1 and m.h[j] > lvl + cfg.min_sweep) or (d == -1 and m.l[j] < lvl - cfg.min_sweep):
                    st["barridos"] += 1
                    state, ext = "REV", j
                    rcands = ifvg_cands(m, ext, d, cfg.ifvg_lookback)
                    rhtf = E.htf_touch(m, ecfg, zones, ext, -d, m.h[ext] if d == 1 else m.l[ext])[0]
                    rifvg = inverted(m, j, rcands, d)
                    conf_i = -1
                else:
                    continue
            if state in ("REV", "REVCONF"):
                newx = j > ext and ((d == 1 and m.h[j] > m.h[ext]) or (d == -1 and m.l[j] < m.l[ext]))
                if newx and state == "REV":
                    ext = j
                    rcands = ifvg_cands(m, ext, d, cfg.ifvg_lookback)
                    rhtf = E.htf_touch(m, ecfg, zones, ext, -d, m.h[ext] if d == 1 else m.l[ext])[0]
                    rifvg = inverted(m, j, rcands, d)
                elif not rifvg and inverted(m, j, rcands, d):
                    rifvg = True
                if state == "REV":
                    lev = series_open(m, ext, bull=(d == 1))
                    cisd = (m.c[j] < lev) if d == 1 else (m.c[j] > lev)
                    ins = (m.c[j] < lvl) if d == 1 else (m.c[j] > lvl)
                    if cisd and ins:
                        st["reversal confirmado"] += 1
                        state, conf_i = "REVCONF", j
                    elif cisd:
                        st["reversal fallido: CISD fuera"] += 1
                        state = "FAILED"
                    elif j - ext > cfg.rev_window:
                        st["reversal fallido: expirado"] += 1
                        state = "FAILED"
                if state == "REVCONF":
                    if cfg.use_htf and not rhtf:
                        st["rechazo: sin HTF"] += 1
                        done = True
                    elif cfg.bplus and not rifvg:
                        if j - ext > cfg.rev_window:
                            st["rechazo: sin iFVG"] += 1
                            done = True
                    elif not win[j]:
                        st["rechazo: fuera de sesión"] += 1
                        done = True
                    else:
                        tr = trade(m, cfg, j, -d, m.h[ext] if d == 1 else m.l[ext], win[j], "reversal", d,
                                   dict(htf=rhtf, ifvg=rifvg, poi=""))
                        if tr:
                            trades.append(tr)
                            st["entradas reversal"] += 1
                        done = True
                if done:
                    break
                if state == "FAILED":
                    if not cfg.use_cont:
                        break
                    state, hi, p, dead = "CONT", ext, -1, -1
                    continue
                continue
            if state == "CONT":
                if (d == 1 and m.h[j] > m.h[hi]) or (d == -1 and m.l[j] < m.l[hi]):
                    hi, p = j, -1
                    continue
                if j <= hi:
                    continue
                if p < 0 or (d == 1 and m.l[j] < m.l[p]) or (d == -1 and m.h[j] > m.h[p]):
                    p = j
                    poi = poi_touch(m, cfg, ecfg, zones, d, p, hi, lvl)
                    liq = liq_taken(m, p, d)
                    chtf = E.htf_touch(m, ecfg, zones, p, d, m.l[p] if d == 1 else m.h[p])[0]
                    ccands = ifvg_cands(m, p, -d, cfg.ifvg_lookback)
                    ccands = ccands if ccands else []
                    cifvg = False
                    clev = series_open(m, p, bull=(d != 1))
                    continue
                if p == dead or j - p > cfg.cont_window:
                    continue
                if not cifvg and inverted(m, j, ccands, -d):
                    cifvg = True
                if (d == 1 and m.c[j] > clev) or (d == -1 and m.c[j] < clev):
                    dead = p
                    if not poi:
                        st["rechazo: sin POI"] += 1
                        continue
                    st["continuación: CISD tras POI"] += 1
                    if cfg.bplus and not liq:
                        st["rechazo: sin liquidez"] += 1
                        continue
                    if cfg.bplus and not cifvg:
                        st["rechazo: sin iFVG"] += 1
                        continue
                    if cfg.use_htf and not chtf:
                        st["rechazo: sin HTF"] += 1
                        continue
                    if not win[j]:
                        st["rechazo: fuera de sesión"] += 1
                        continue
                    tr = trade(m, cfg, j, d, m.l[p] if d == 1 else m.h[p], win[j], "continuación", d,
                               dict(htf=chtf, ifvg=cifvg, poi=poi))
                    if tr:
                        trades.append(tr)
                        st["entradas continuación"] += 1
                    break
        else:
            if state != "WAIT":
                st["sin desenlace"] += 1
    return pd.DataFrame(trades), st


def summary(t, months=105):
    if t.empty:
        return dict(ops=0)
    r = t.r.to_numpy()
    eq = np.cumsum(r)
    y = t.t.dt.year.to_numpy()
    g, ls = r[r > 0].sum(), -r[r < 0].sum()
    by = pd.Series(r).groupby(y).sum()
    return {"ops": len(r), "al mes": round(len(r) / months, 1), "acierto": f"{(r > 0).mean():.0%}",
            "R/op": round(r.mean(), 3), "PF": round(g / ls, 2) if ls else np.inf, "R neto": round(r.sum(), 1),
            "DD R": round((np.maximum.accumulate(eq) - eq).max(), 1), "ganancia R": round(g, 1), "pérdida R": round(-ls, 1),
            "2018-22": round(r[y < 2023].mean(), 3) if (y < 2023).any() else np.nan,
            "2023-26": round(r[y >= 2023].mean(), 3) if (y >= 2023).any() else np.nan,
            "años +": f"{(by > 0).sum()}/{len(by)}"}


def main():
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 30)
    m = E.Market("NQ")
    months = (m.idx[-1] - m.idx[0]).days / 30.44
    for ses_name, ses in (("London 2:00-5:00 NY", ((2.0, 5.0, 11.0),)), ("NY 9:30-11:00", ((9.5, 11.0, 15.9),)),
                          ("London + NY", ((2.0, 5.0, 11.0), (9.5, 11.0, 15.9)))):
        rows, keep = [], {}
        for name, kw in MODELS.items():
            cfg = replace(Cfg(), sessions=ses, **kw)
            t, st = run(m, cfg)
            keep[name] = (t, st)
            rows.append({"modelo": name, **summary(t, months),
                         "rev": int((t.kind == "reversal").sum()) if len(t) else 0,
                         "cont": int((t.kind == "continuación").sum()) if len(t) else 0})
        print(f"\n=== NQ · {ses_name} · objetivo 2R · coste 1 punto · 2018-2026 ===")
        print(pd.DataFrame(rows).to_string(index=False))
        for name, (t, st) in keep.items():
            if t.empty:
                continue
            print(f"\n-- {name}")
            print("   por tipo:", t.groupby("kind").r.agg(["count", "mean", "sum"]).round(3).to_dict("index"))
            print("   por lado:", t.groupby("side").r.agg(["count", "mean", "sum"]).round(3).to_dict("index"))
            if name.startswith("D") or name.startswith("B"):
                print("   embudo:", st)
                t = t.assign(año=t.t.dt.year, dia=t.t.dt.day_name(), hora=t.t.dt.hour)
                print("   por año:", t.groupby("año").r.sum().round(1).to_dict())
                print("   por día:", t.groupby("dia").r.agg(["count", "mean"]).round(2).to_dict("index"))
                print("   por hora:", t.groupby("hora").r.agg(["count", "mean"]).round(2).to_dict("index"))
                if "poi" in t:
                    print("   por POI:", t[t.kind == "continuación"].groupby("poi").r.agg(["count", "mean"]).round(2).to_dict("index"))


if __name__ == "__main__":
    main()
