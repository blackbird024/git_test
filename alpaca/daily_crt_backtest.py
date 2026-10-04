"""Backtest del modelo "CRT diario: giro primero, continuación si el giro falla" (vídeo de NQ, ejecución en 1H).

Reglas (sesgo alcista; el bajista es el espejo):
  1. Sesgo diario: la vela diaria de CME (18:00-17:00 NY) cerró FUERTE al alza: cuerpo alcista y cierre en el
     `strong`·100 % superior de su rango (opcional: además por encima del máximo de la vela anterior).
     Se marcan su máximo (PDH) y mínimo (PDL).
  2. Al día siguiente, en velas de 1H, primero se busca el GIRO (corto):
       - una vela de 1H supera el PDH (barrido; el extremo se actualiza si sigue subiendo),
       - un CISD bajista: cierre por debajo de la apertura de la primera vela de la última serie alcista
         que hizo el máximo, Y ese cierre por debajo del PDH (de vuelta dentro del rango).
       Entrada en la apertura de la vela siguiente, stop en el máximo del barrido, objetivo 2R.
  3. El giro FALLA si el CISD bajista cierra todavía por encima del PDH, o si el precio retrocede y hace un CISD
     alcista antes de confirmar el giro.
  4. CONTINUACIÓN (largo) tras el fallo: un retroceso que toca un FVG alcista de 1H activo o vuelve al PDH
     (swing roto), y un CISD alcista (cierre por encima de la apertura de la primera vela de la última serie
     bajista que hizo el mínimo del retroceso). Entrada en la apertura siguiente, stop en el mínimo del
     retroceso, objetivo 2R.
  Una operación por día. Ventana de 1H configurable; salida forzosa por tiempo.

Uso:
    python daily_crt_backtest.py
"""

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from crt_backtest import load_5m

COST_FRAC = 0.00004          # ida y vuelta, fracción del precio (≈1 punto en NQ, 0,25 en ES, 0,1 en GC)


@dataclass
class Cfg:
    name: str = "base"
    strong: float = 0.75           # cierre en el 25 % superior del rango
    above_prev_high: bool = False  # exigir además cierre por encima del máximo de la vela anterior
    start_h: int = 0               # primera vela de 1H que puede barrer (hora NY; 18 = toda la sesión)
    last_entry_h: int = 14         # última hora de entrada
    exit_h: int = 16               # salida forzosa
    max_hold_h: int = 99           # horas máximas en la operación
    reversal: bool = True
    continuation: bool = True
    use_bias: bool = True          # False = control: misma lógica en ambas direcciones sin mirar la vela diaria
    rr: float = 2.0


def hourly(sym):
    df = load_5m(sym)
    h = df.resample("1h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    sd = (h.index + pd.Timedelta(hours=6)).normalize()       # sesión CME: 18:00 → día siguiente
    h["sday"] = sd.tz_localize(None)
    return h


def daily(h):
    d = h.groupby("sday").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
    return d


def last_series_open(o, c, i, bull):
    """Apertura de la primera vela de la última serie (alcista si bull) que termina en i o en i-1."""
    is_s = (lambda q: c[q] > o[q]) if bull else (lambda q: c[q] < o[q])
    s = i if is_s(i) else i - 1
    if s < 0 or not is_s(s):
        return o[i]
    while s > 0 and is_s(s - 1):
        s -= 1
    return o[s]


def run_day(H, i0, i1, pdh, pdl, bias, cfg, hrs):
    """Barras 1H [i0, i1) del día. Devuelve dict de la operación o None."""
    o, h, l, c = H["o"], H["h"], H["l"], H["c"]
    d = bias                      # dirección del sesgo diario: la continuación va a favor, el giro en contra
    lvl = pdh if d == 1 else pdl
    swept, ext_i, failed = False, None, False
    fvgs = []                     # FVG de 1H a favor del sesgo: (borde cercano, borde lejano, índice)
    for j in range(max(i0 - 48, 2), i1):
        # FVG a favor del sesgo (alcista para d=1) formados hasta j
        if d == 1 and l[j] > h[j - 2]:
            fvgs.append((l[j], h[j - 2], j))
        if d == -1 and h[j] < l[j - 2]:
            fvgs.append((h[j], l[j - 2], j))
        # invalidación por cierre al otro lado
        fvgs = [z for z in fvgs if (c[j] >= z[1] if d == 1 else c[j] <= z[1]) or z[2] == j]
        if j < i0:
            continue
        if not swept:
            if (d == 1 and h[j] > lvl) or (d == -1 and l[j] < lvl):
                swept, ext_i = True, j
            else:
                continue
        elif (d == 1 and h[j] > h[ext_i]) or (d == -1 and l[j] < l[ext_i]):
            ext_i = j
        can_enter = (hrs[j] <= cfg.last_entry_h or hrs[j] >= 18) and j + 1 < i1
        # 2. GIRO: CISD en contra del sesgo
        if not failed and cfg.reversal:
            rev_lvl = last_series_open(o, c, ext_i, bull=(d == 1))
            if (d == 1 and c[j] < rev_lvl) or (d == -1 and c[j] > rev_lvl):
                inside = (c[j] < lvl) if d == 1 else (c[j] > lvl)
                if inside:
                    if can_enter:
                        stop = h[ext_i] if d == 1 else l[ext_i]
                        return dict(kind="giro", side=-d, i=j + 1, stop=stop)
                    return None
                failed = True
        # 3/4. CONTINUACIÓN: retroceso tras el extremo y CISD a favor del sesgo
        if j > ext_i + 1:
            seg = l[ext_i + 1:j] if d == 1 else h[ext_i + 1:j]
            if len(seg) == 0:
                continue
            pi = ext_i + 1 + (int(np.argmin(seg)) if d == 1 else int(np.argmax(seg)))
            cont_lvl = last_series_open(o, c, pi, bull=(d != 1))
            if (d == 1 and c[j] > cont_lvl) or (d == -1 and c[j] < cont_lvl):
                failed = True
                pext = l[pi] if d == 1 else h[pi]
                poi = abs(pext - lvl) <= 0.1 * (pdh - pdl) or (pext <= lvl if d == 1 else pext >= lvl)
                for near, far, zi in fvgs:
                    if zi < pi and ((d == 1 and pext <= near and c[pi] >= far) or (d == -1 and pext >= near and c[pi] <= far)):
                        poi = True
                if poi and cfg.continuation and can_enter:
                    return dict(kind="continuación", side=d, i=j + 1, stop=pext)
                if poi:
                    return None
    return None


def manage(H, t, side, i, stop, cfg, i_end):
    o, h, l, c = H["o"], H["h"], H["l"], H["c"]
    entry = o[i]
    risk = (entry - stop) * side
    if risk <= 0:
        return None
    tgt = entry + side * cfg.rr * risk
    last = min(i_end, i + cfg.max_hold_h)
    for q in range(i, last):
        if (side == 1 and l[q] <= stop) or (side == -1 and h[q] >= stop):
            return -1 - COST_FRAC * entry / risk
        if (side == 1 and h[q] >= tgt) or (side == -1 and l[q] <= tgt):
            return cfg.rr - COST_FRAC * entry / risk
    px = o[last] if last < len(o) else c[-1]
    return side * (px - entry) / risk - COST_FRAC * entry / risk


def run(sym, cfg, Hdf=None):
    Hdf = hourly(sym) if Hdf is None else Hdf
    D = daily(Hdf)
    H = {k: Hdf[n].to_numpy() for k, n in (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close"))}
    hrs = Hdf.index.hour.to_numpy()
    days = Hdf["sday"].to_numpy()
    starts = np.r_[0, np.nonzero(days[1:] != days[:-1])[0] + 1]
    ends = np.r_[starts[1:], len(days)]
    rows = []
    for n in range(1, len(starts)):
        prev = D.iloc[n - 1]
        rng = prev.high - prev.low
        if rng <= 0:
            continue
        pos = (prev.close - prev.low) / rng
        bull = prev.close > prev.open and pos >= cfg.strong
        bear = prev.close < prev.open and pos <= 1 - cfg.strong
        if cfg.above_prev_high and n >= 2:
            pp = D.iloc[n - 2]
            bull &= prev.close > pp.high
            bear &= prev.close < pp.low
        cands = [1] if bull else [-1] if bear else []
        if not cfg.use_bias:
            cands = [1, -1]
        i0, i1 = starts[n], ends[n]
        # recorte de la ventana: desde start_h (hora NY) hasta exit_h
        idx = np.arange(i0, i1)
        hh = hrs[idx]
        if cfg.start_h != 18:
            sel = idx[(hh >= cfg.start_h) & (hh < 17)]
            if len(sel) == 0:
                continue
            i0 = sel[0]
        ex = [q for q in range(i0, i1) if hrs[q] == cfg.exit_h]
        i_end = ex[0] if ex else i1
        for b in cands:
            tr = run_day(H, i0, i_end, prev.high, prev.low, b, cfg, hrs)
            if tr:
                r = manage(H, Hdf.index[tr["i"]], tr["side"], tr["i"], tr["stop"], cfg, i_end)
                if r is not None:
                    rows.append(dict(day=days[i0], kind=tr["kind"], side=tr["side"], bias=b, r=r))
                break
    return pd.DataFrame(rows)


def summary(t):
    if t.empty:
        return dict(ops=0)
    r = t.r.to_numpy()
    eq = np.cumsum(r)
    y = pd.to_datetime(t.day).dt.year.to_numpy()
    g, ls = r[r > 0].sum(), -r[r < 0].sum()
    by = pd.Series(r).groupby(y).sum()
    return {"ops": len(r), "al mes": round(len(r) / 105, 1), "acierto": f"{(r > 0).mean():.0%}", "R/op": round(r.mean(), 3),
            "PF": round(g / ls, 2) if ls else np.inf, "R total": round(r.sum(), 1),
            "DD R": round((np.maximum.accumulate(eq) - eq).max(), 1),
            "2018-22 R/op": round(r[y < 2023].mean(), 3), "2023-26 R/op": round(r[y >= 2023].mean(), 3),
            "años +": f"{(by > 0).sum()}/{len(by)}"}


CFGS = [
    Cfg(),
    Cfg(name="solo giro", continuation=False),
    Cfg(name="solo continuación", reversal=False),
    Cfg(name="cierre fuerte 80 % + por encima del máximo anterior", strong=0.8, above_prev_high=True),
    Cfg(name="cierre fuerte 65 %", strong=0.65),
    Cfg(name="toda la sesión (desde 18:00)", start_h=18),
    Cfg(name="ventana NY 8:00-14:00", start_h=8),
    Cfg(name="máximo 2 h en la operación", max_hold_h=2),
    Cfg(name="máximo 4 h en la operación", max_hold_h=4),
    Cfg(name="CONTROL sin sesgo diario", use_bias=False),
]


def main():
    pd.set_option("display.width", 250)
    for sym in ("NQ", "ES", "GC"):
        Hdf = hourly(sym)
        rows = []
        for c in CFGS:
            t = run(sym, c, Hdf)
            rows.append({"variante": c.name, **summary(t)})
            if c.name == "base":
                base = t
        print(f"\n=== {sym} · CRT diario (giro / continuación), 1H, objetivo 2R, costes incluidos, 2018-2026 ===")
        print(pd.DataFrame(rows).to_string(index=False))
        print("base por tipo:", base.groupby("kind").r.agg(["count", "mean", "sum"]).round(2).to_dict("index"))


if __name__ == "__main__":
    main()
