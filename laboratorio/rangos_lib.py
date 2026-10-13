"""Funciones comunes para los estudios de "rango de una vela" en cualquier futuro (NQ, oro, EUR/USD, GBP/USD).
Todo en una rejilla de minutos de 0:00 a 16:00 ET (NE = 960). Mismas reglas que run_rangos_multi_tf.py / run_oro_rangos.py,
pero con el tick como parámetro."""
import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from validation.metrics import block_bootstrap_mean, trades_frame
from validation.runner import split

NE = 960
CACHE = "/home/user/git_test/vwap_lab/data/cache/"
FILES = {"MGC": CACHE + "GC_v0_1m.pkl", "M6E": CACHE + "6E_v_0_1m.pkl", "M6B": CACHE + "6B_v_0_1m.pkl"}
COVER = {"MGC": (500, 810), "M6E": (180, 660), "M6B": (180, 660)}   # minutos ET que deben tener datos (>= 80 %)


def load_days(sym):
    """Días (fecha, matriz 960×5) para MGC/M6E/M6B; para MNQ usar run_orb_ventanas_edgeful.et_days."""
    if sym == "MNQ":
        from data.loaders import sessions
        from run_orb_ventanas_edgeful import et_days
        return et_days(sessions()), {}
    df = pd.read_pickle(FILES[sym])
    df.index = df.index.tz_convert("America/New_York")
    arr = df[["open", "high", "low", "close", "volume"]].to_numpy()
    ins = df["instrument_id"].to_numpy()
    t = df.index
    mins = (t.hour * 60 + t.minute).to_numpy()
    c0, c1 = COVER[sym]
    out, prev, excl = [], None, dict(cobertura=0, cambio_contrato=0, primer_dia_tras_cambio=0)
    for d, idx in pd.Series(np.arange(len(df)), index=pd.Index(t.date)).groupby(level=0):
        d = pd.Timestamp(d)
        if d.weekday() >= 5:
            continue
        ii = idx.to_numpy()
        ii = ii[mins[ii] < NE]
        if len(ii) == 0:
            continue
        m = np.full((NE, 5), np.nan)
        m[mins[ii]] = arr[ii]
        di = np.unique(ins[ii])
        if (~np.isnan(m[c0:c1, 0])).mean() < 0.8:
            excl["cobertura"] += 1
        elif len(di) > 1:
            excl["cambio_contrato"] += 1
        elif prev is not None and di[0] != prev:
            excl["primer_dia_tras_cambio"] += 1
        else:
            out.append((d, m))
        prev = di[-1]
    return out, excl


def setup(m, a, dur, tick):
    H, L = m[:, 1], m[:, 2]
    if np.isnan(H[a:a + dur]).sum() > dur / 2:
        return None
    hi, lo = np.nanmax(H[a:a + dur]), np.nanmin(L[a:a + dur])
    R = hi - lo
    if R <= 0:
        return None
    s0 = a + dur
    ex = min(s0 + max(210, 2 * dur), 955)
    if s0 >= ex:
        return None
    eps = tick * 1e-3
    up = np.nonzero(H[s0:ex] >= hi + tick - eps)[0]
    dn = np.nonzero(L[s0:ex] <= lo - tick + eps)[0]
    ku = up[0] + s0 if len(up) else None
    kd = dn[0] + s0 if len(dn) else None
    if ku is None and kd is None:
        return None
    if ku is not None and ku == kd:
        return "mismo"
    side, k = (1, ku) if kd is None or (ku is not None and ku < kd) else (-1, kd)
    return hi, lo, R, side, k, ex


def race(m, st):
    hi, lo, R, side, k, ex = st
    H, L = m[k:ex, 1], m[k:ex, 2]
    c, r = (H >= hi + R, L <= lo) if side == 1 else (L <= lo - R, H >= hi)
    ic = np.argmax(c) if c.any() else 10 ** 6
    ir = np.argmax(r) if r.any() else 10 ** 6
    if ic == ir == 10 ** 6:
        return "nada"
    if ic == ir:
        return "ambos"
    return "continua" if ic < ir else "gira"


def run_strategy(D, dur, a, c, mode="favor", frac=1.0, stop_mode="opuesto"):
    """mode: favor (orden stop en la ruptura) · pullback (límite en el nivel roto tras la ruptura; se cancela si antes
    toca el objetivo o el stop) · contra (en contra en la ruptura, objetivo el otro lado, stop a 1 rango)."""
    tk = c.tick
    rnd = lambda x: round(x / tk) * tk
    fills = []
    for date, m in D:
        st = setup(m, a, dur, tk)
        if st is None or st == "mismo":
            continue
        hi, lo, R, side, k, ex = st
        edge, opp = (hi, lo) if side == 1 else (lo, hi)
        stop = rnd(opp - side * tk) if stop_mode == "opuesto" else rnd((hi + lo) / 2 - side * tk)
        tgt = rnd(edge + side * frac * R)
        if mode == "favor":
            o = Order(side, "stop", k, stop, tgt, ex, level=rnd(edge + side * tk), k_last=k + 1)
        elif mode == "pullback":
            H, L = m[k:ex, 1], m[k:ex, 2]
            hit = np.nonzero(H >= tgt if side == 1 else L <= tgt)[0]
            klast = k + (hit[0] if len(hit) else ex - k)
            if klast <= k + 1:
                continue
            o = Order(side, "limit", k + 1, stop, tgt, ex, level=edge, k_last=klast)
        else:
            o = Order(-side, "market", k + 1, rnd(edge + side * R), opp, ex)
        f = simulate(date, m, ex + 1, o, c)
        if f is not None:
            fills.append(f)
    return trades_frame(fills, c)


def stats(t, per, c):
    if len(t) == 0:
        return dict(n=0)
    sp = split(t, per)
    fm = t[t.date >= "2022-01-01"]
    lo_, hi_ = block_bootstrap_mean(fm.pnl.to_numpy()) if len(fm) > 20 else (np.nan, np.nan)
    srt = fm.pnl.sort_values(ascending=False)
    g = lambda k: sp[k].pnl.mean() if k in sp and len(sp[k]) else np.nan
    return dict(n=len(t), dev=g("desarrollo"), val=g("validacion"), prueba=g("prueba"),
                n_val=len(sp.get("validacion", [])), ic90_FM=f"[{lo_:.1f}; {hi_:.1f}]",
                top10=100 * srt[:10].sum() / fm.pnl.sum() if len(fm) and fm.pnl.sum() > 0 else np.nan,
                neto_año=t.pnl.sum() / 8.75, acierto=(t.pnl > 0).mean(), riesgo_med=t.risk_usd.median(),
                R_bruto=(t.gross_pts * c.point_value / t.risk_usd).mean(),
                años_pos=int((t.groupby(t.date.dt.year).pnl.sum() > 0).sum()))


def lab(dur, a):
    return f"{dur} min {a // 60}:{a % 60:02d} ET ({(a // 60 + 6) % 24}:{a % 60:02d} Italia)"
