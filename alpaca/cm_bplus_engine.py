"""Motor de referencia del Confirmation Model B+ (especificación v2) con diagnóstico de frecuencia.

Es la misma lógica que el indicador tradingview/ConfirmationModelBPlus.pine, escrita en Python para medir
con futuros CME de Databento (velas de 5 minutos, 2018-2026) cuántos setups pasan cada fase y qué resultado
tienen. Todo se calcula con información disponible al cierre de cada vela (sin mirar el futuro).

Setup alcista (el bajista es simétrico):
  1. Barrido: la mecha de una vela de 5m perfora un swing low confirmado (pivote L/R) de las últimas
     `swing_lookback` velas que nadie había perforado. Opcional: exigir que esa vela cierre por encima del nivel.
  2. Entrega HTF: la vela que marca el mínimo del barrido (el extremo, que se actualiza si el precio sigue
     bajando) toca con la mecha un FVG ALCISTA activo de 15m o 1h (de los últimos `htf_days` días)
     y cierra por encima de su límite inferior.
  3. iFVG: un FVG BAJISTA de 5m formado en la caída (tercera vela entre extremo-`ifvg_lookback` y el extremo),
     sin invertir antes del extremo, que una vela cierra por encima de su límite superior a partir del extremo.
  4. CISD: una vela posterior al extremo cierra por encima de la apertura de la primera vela de la última
     serie bajista que llevó al mínimo.
  Ventana: las confirmaciones deben llegar en `window` velas desde el extremo (o desde el barrido).
  Señal B+: la vela en que se completan las condiciones activas. Stop en el extremo (± buffer), objetivo `rr`R.

Uso:
    python cm_bplus_engine.py            # embudo y comparación de configuraciones (NQ, London y NY)
"""

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from crt_backtest import load_5m

NS_MIN = 60 * 10**9


@dataclass
class Config:
    name: str = "A · B+ estricto"
    piv_l: int = 3
    piv_r: int = 3
    swing_lookback: int = 48
    sweep_close_back: bool = False
    use_htf: bool = True
    htf_tfs: tuple = ("15min", "1h")
    htf_days: float = 3.0
    htf_invalidation: str = "htf_close"     # htf_close | ltf_close | wick
    htf_side: str = "a favor"               # "a favor" (FVG alcista para largos) | "invertido" (error de la v1)
    use_ifvg: bool = True
    ifvg_select: str = "any"                # any | last | nearest
    ifvg_lookback: int = 12
    use_cisd: bool = True
    cisd_mode: str = "consecutive"          # consecutive | tolerant | structure
    window: int = 12
    window_anchor: str = "extreme"          # extreme | sweep
    sessions: tuple = ((2.0, 5.0, 11.0),)   # (inicio barridos, fin señales, salida) en horas NY
    one_per_session: bool = False
    weekdays: tuple = (0, 1, 2, 3, 4)
    rr: float = 2.0
    stop_buffer: float = 0.0                # puntos
    entry: str = "close"                    # close | next_open
    cost_pts: float = 1.0                   # ida y vuelta (comisión MNQ + 1 tick de deslizamiento por lado)


# ───────────────────────── datos y precálculos ─────────────────────────

class Market:
    def __init__(self, sym):
        df = load_5m(sym)
        self.sym = sym
        self.t = df.index.asi8
        self.idx = df.index
        self.o, self.h, self.l, self.c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
        self.hr = (df.index.hour + df.index.minute / 60).to_numpy()
        self.wd = df.index.weekday.to_numpy()
        self.day = df.index.normalize().asi8
        tr = np.maximum(self.h - self.l, np.abs(self.h - np.r_[self.c[0], self.c[:-1]]))
        self.atr = pd.Series(tr).rolling(14, min_periods=1).mean().to_numpy()
        self.df = df
        self._piv, self._fvg = {}, {}

    def pivots(self, L, R):
        key = (L, R)
        if key not in self._piv:
            n = len(self.l)
            lo = np.zeros(n, bool)
            hi = np.zeros(n, bool)
            from numpy.lib.stride_tricks import sliding_window_view as sw
            wl = sw(self.l, L + R + 1).min(axis=1)
            wh = sw(self.h, L + R + 1).max(axis=1)
            lo[L:n - R] = self.l[L:n - R] == wl
            hi[L:n - R] = self.h[L:n - R] == wh
            self._piv[key] = (lo, hi)
        return self._piv[key]

    def fvgs(self, tf, inval, days):
        """FVG de temporalidad tf: arrays (form_t, inv_t, top, bot, kind, tf). form_t = cierre de la 3.ª vela."""
        key = (tf, inval, days)
        if key in self._fvg:
            return self._fvg[key]
        b = self.df.resample(tf, label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        step = pd.Timedelta(tf).value
        st, H, Lw, C = b.index.asi8, b["high"].to_numpy(), b["low"].to_numpy(), b["close"].to_numpy()
        out = []
        horizon = int(days * 24 * 60 * NS_MIN)
        for i in range(2, len(b)):
            if Lw[i] > H[i - 2]:
                top, bot, kind = Lw[i], H[i - 2], 1
            elif H[i] < Lw[i - 2]:
                top, bot, kind = Lw[i - 2], H[i], -1
            else:
                continue
            form = st[i] + step
            end = form + horizon
            if inval == "htf_close":
                j1 = np.searchsorted(st, end)
                seg = C[i + 1:j1]
                bad = np.nonzero(seg < bot)[0] if kind == 1 else np.nonzero(seg > top)[0]
                inv = st[i + 1 + bad[0]] + step if len(bad) else end
            else:
                a, z = np.searchsorted(self.t, form), np.searchsorted(self.t, end)
                if inval == "ltf_close":
                    seg = self.c[a:z]
                    bad = np.nonzero(seg < bot)[0] if kind == 1 else np.nonzero(seg > top)[0]
                else:                                            # wick: la mecha atraviesa toda la zona
                    bad = np.nonzero(self.l[a:z] < bot)[0] if kind == 1 else np.nonzero(self.h[a:z] > top)[0]
                inv = self.t[a + bad[0]] + 5 * NS_MIN if len(bad) else end
            out.append((form, min(inv, end), top, bot, kind))
        arr = np.array(out)
        res = (arr[:, 0].astype(np.int64), arr[:, 1].astype(np.int64), arr[:, 2], arr[:, 3], arr[:, 4].astype(int),
               tf)
        self._fvg[key] = res
        return res


def htf_touch(m, cfg, zones, i, d, ext):
    """¿La vela i (extremo) toca un FVG HTF activo a favor (d)? Devuelve (ok, tf, penetración %, distancia en ATR)."""
    t_open = m.t[i]
    best = (False, None, 0.0, np.inf)
    lo_t = t_open - int(cfg.htf_days * 24 * 60 * NS_MIN)
    for form, inv, top, bot, kind, tf in zones:
        a, z = np.searchsorted(form, lo_t), np.searchsorted(form, t_open, side="right")
        if a >= z:
            continue
        sel = slice(a, z)
        want = d if cfg.htf_side == "a favor" else -d
        act = (inv[sel] > t_open) & (kind[sel] == want)
        if not act.any():
            continue
        T, B = top[sel][act], bot[sel][act]
        if d == 1:
            hit = (ext <= T) & (m.c[i] >= B)
            dist = np.where(ext > T, ext - T, 0.0)
        else:
            hit = (ext >= B) & (m.c[i] <= T)
            dist = np.where(ext < B, B - ext, 0.0)
        if hit.any():
            k = np.argmax(hit)
            pen = (T[k] - ext) / (T[k] - B[k]) if d == 1 else (ext - B[k]) / (T[k] - B[k])
            return True, tf, float(min(pen, 9.99)), 0.0
        dmin = dist[dist > 0].min() / max(m.atr[i], 1e-9) if (dist > 0).any() else np.inf
        if dmin < best[3]:
            best = (False, None, 0.0, dmin)
    return best


def cisd_level(m, cfg, ext_i, d):
    """Apertura de la primera vela de la última serie en contra (bajista para un largo) que llevó al extremo."""
    against = (lambda q: m.c[q] < m.o[q]) if d == 1 else (lambda q: m.c[q] > m.o[q])
    s = ext_i if against(ext_i) else ext_i - 1
    if cfg.cisd_mode == "structure":
        lo, hi = m.pivots(cfg.piv_l, cfg.piv_r)
        piv = hi if d == 1 else lo
        q = ext_i - cfg.piv_r - 1
        while q > max(ext_i - 200, 0) and not piv[q]:
            q -= 1
        s = q + 1
        while s < ext_i and not against(s):
            s += 1
        return m.o[s]
    while s > 0 and against(s - 1):
        s -= 1
    if cfg.cisd_mode == "tolerant":                          # admite una vela intermedia a favor
        while s > 1 and not against(s - 1) and against(s - 2):
            s -= 2
            while s > 0 and against(s - 1):
                s -= 1
    return m.o[s]


def ifvg_candidates(m, cfg, ext_i, d):
    """FVG de 5m en contra formados en el movimiento que lleva al extremo y todavía no invertidos."""
    out = []
    for q in range(max(2, ext_i - cfg.ifvg_lookback), ext_i + 1):
        if d == 1 and m.h[q] < m.l[q - 2]:                   # FVG bajista: zona [h[q], l[q-2]]
            edge = m.l[q - 2]
            if q < ext_i and (m.c[q + 1:ext_i] > edge).any():
                continue
            out.append((q, edge))
        if d == -1 and m.l[q] > m.h[q - 2]:                  # FVG alcista: zona [h[q-2], l[q]]
            edge = m.h[q - 2]
            if q < ext_i and (m.c[q + 1:ext_i] < edge).any():
                continue
            out.append((q, edge))
    if not out:
        return []
    if cfg.ifvg_select == "last":
        return [max(out)]
    if cfg.ifvg_select == "nearest":
        return [min(out, key=lambda x: x[1]) if d == 1 else max(out, key=lambda x: x[1])]
    return out


@dataclass
class Setup:
    d: int
    sweep_i: int
    swing_i: int
    ext_i: int
    ext: float
    htf: tuple
    level: float
    cands: list
    ifvg_i: int = -1
    cisd_i: int = -1
    htf_ever: bool = False


def run(m, cfg):
    lo_p, hi_p = m.pivots(cfg.piv_l, cfg.piv_r)
    zones = [m.fvgs(tf, cfg.htf_invalidation, cfg.htf_days) for tf in cfg.htf_tfs] if cfg.use_htf else []
    setups, trades = [], []
    n = len(m.c)
    for s_h, e_h, x_h in cfg.sessions:
        in_win = (m.hr >= s_h) & (m.hr < e_h) & np.isin(m.wd, cfg.weekdays)
        bars = np.nonzero(in_win)[0]
        active = {1: None, -1: None}
        traded_day = {}
        prev_i = -10
        for i in bars:
            if i != prev_i + 1:                                   # nueva sesión: se descartan los setups abiertos
                for d in (1, -1):
                    if active[d]:
                        setups.append((active[d], "fin de sesión"))
                        active[d] = None
            prev_i = i
            if i < cfg.swing_lookback + cfg.piv_l + 2 or i >= n - 1:
                continue
            for d in (1, -1):
                st = active[d]
                if st is not None:
                    anchor = st.ext_i if cfg.window_anchor == "extreme" else st.sweep_i
                    newx = (m.l[i] < st.ext) if d == 1 else (m.h[i] > st.ext)
                    if i - anchor > cfg.window and (not newx or cfg.window_anchor == "sweep"):
                        setups.append((st, "expirado"))
                        active[d] = st = None
                    elif newx:
                        st.ext_i, st.ext = i, (m.l[i] if d == 1 else m.h[i])
                        st.htf = htf_touch(m, cfg, zones, i, d, st.ext) if cfg.use_htf else (True, None, 0, 0)
                        st.htf_ever |= st.htf[0]
                        st.level = cisd_level(m, cfg, i, d)
                        st.cands = ifvg_candidates(m, cfg, i, d)
                        st.ifvg_i = st.cisd_i = -1
                        if any((m.c[i] > e) if d == 1 else (m.c[i] < e) for _, e in st.cands):
                            st.ifvg_i = i
                        continue
                    else:
                        if st.ifvg_i < 0 and any((m.c[i] > e) if d == 1 else (m.c[i] < e) for _, e in st.cands):
                            st.ifvg_i = i
                        if st.cisd_i < 0 and ((m.c[i] > st.level) if d == 1 else (m.c[i] < st.level)):
                            st.cisd_i = i
                        ok = ((not cfg.use_htf or st.htf[0]) and (not cfg.use_ifvg or st.ifvg_i >= 0)
                              and (not cfg.use_cisd or st.cisd_i >= 0))
                        if ok:
                            setups.append((st, "señal"))
                            trades.append(trade(m, cfg, st, i, x_h))
                            active[d] = None
                            traded_day[m.day[i]] = True
                            continue
                if active[d] is None and not (cfg.one_per_session and traded_day.get(m.day[i])):
                    lv = cfg.swing_lookback
                    ks = np.nonzero((lo_p if d == 1 else hi_p)[i - lv:i - cfg.piv_r])[0] + i - lv
                    hit = None
                    for k in ks[::-1]:
                        if d == 1 and m.l[i] < m.l[k] and m.l[k + 1:i].min() >= m.l[k]:
                            hit = k
                            break
                        if d == -1 and m.h[i] > m.h[k] and m.h[k + 1:i].max() <= m.h[k]:
                            hit = k
                            break
                    if hit is None:
                        continue
                    lvl = m.l[hit] if d == 1 else m.h[hit]
                    if cfg.sweep_close_back and ((m.c[i] <= lvl) if d == 1 else (m.c[i] >= lvl)):
                        continue
                    ext = m.l[i] if d == 1 else m.h[i]
                    htf = htf_touch(m, cfg, zones, i, d, ext) if cfg.use_htf else (True, None, 0, 0)
                    st = Setup(d, i, hit, i, ext, htf, cisd_level(m, cfg, i, d), ifvg_candidates(m, cfg, i, d),
                               htf_ever=htf[0])
                    if any((m.c[i] > e) if d == 1 else (m.c[i] < e) for _, e in st.cands):
                        st.ifvg_i = i
                    active[d] = st
        for d in (1, -1):
            if active[d]:
                setups.append((active[d], "fin de sesión"))
    return setups, pd.DataFrame(trades)


def trade(m, cfg, st, i, exit_h):
    d = st.d
    if cfg.entry == "next_open":
        entry, k0 = m.o[i + 1], i + 1
    else:
        entry, k0 = m.c[i], i + 1
    stop = st.ext - d * cfg.stop_buffer
    risk = abs(entry - stop)
    day0 = m.day[i]
    exit_t = day0 + int(exit_h * 60 * NS_MIN)
    r = None
    if risk <= 0:
        r = 0.0
    else:
        tgt = entry + d * cfg.rr * risk
        q = k0
        while q < len(m.c) and m.t[q] < exit_t:
            if (d == 1 and m.l[q] <= stop) or (d == -1 and m.h[q] >= stop):
                r = -1.0
                break
            if (d == 1 and m.h[q] >= tgt) or (d == -1 and m.l[q] <= tgt):
                r = cfg.rr
                break
            q += 1
        if r is None:
            px = m.o[q] if q < len(m.c) else m.c[-1]
            r = d * (px - entry) / risk
        r -= cfg.cost_pts / risk
    return dict(t=m.idx[i], d=d, r=r, risk_pts=risk, htf_tf=st.htf[1], pen=st.htf[2],
                bars_to_signal=i - st.sweep_i, sess_hr=m.hr[i])


# ───────────────────────── informes ─────────────────────────

def funnel(setups, months):
    rows = []
    for d, name in ((1, "alcistas"), (-1, "bajistas"), (0, "total")):
        S = [(s, e) for s, e in setups if d == 0 or s.d == d]
        n = len(S)
        htf = sum(s.htf[0] for s, _ in S)
        htf_if = sum(s.htf[0] and s.ifvg_i >= 0 for s, _ in S)
        sig = sum(e == "señal" for _, e in S)
        rows.append({"dirección": name, "barridos": n, "con HTF": htf, "HTF+iFVG": htf_if, "B+ (HTF+iFVG+CISD)": sig,
                     "solo CISD": sum(s.cisd_i >= 0 for s, _ in S), "solo iFVG": sum(s.ifvg_i >= 0 for s, _ in S),
                     "B+/mes": round(sig / months, 2)})
    return pd.DataFrame(rows)


def why_lost(setups):
    """Para los setups que no llegaron a señal: qué faltaba al expirar."""
    c = {}
    dist = []
    for s, e in setups:
        if e == "señal":
            continue
        miss = []
        if not s.htf[0]:
            miss.append("HTF")
            dist.append(s.htf[3])
        if s.ifvg_i < 0:
            miss.append("iFVG")
        if s.cisd_i < 0:
            miss.append("CISD")
        key = " + ".join(miss) if miss else "(completo tras la ventana)"
        c[key] = c.get(key, 0) + 1
    dist = np.array(dist)
    fin = dist[np.isfinite(dist)]
    return c, dict(sin_fvg_cerca=int((~np.isfinite(dist)).sum()), a_menos_0_5atr=int((fin <= 0.5).sum()),
                   a_0_5_2atr=int(((fin > 0.5) & (fin <= 2)).sum()), a_mas_2atr=int((fin > 2).sum()))


def summary(tr, months):
    if tr.empty:
        return dict(señales=0)
    r = tr["r"].to_numpy()
    eq = np.cumsum(r)
    y = tr["t"].dt.year
    g, ls = r[r > 0].sum(), -r[r < 0].sum()
    return {"señales": len(r), "al mes": round(len(r) / months, 2), "acierto": f"{(r > 0).mean():.0%}",
            "R/op": round(r.mean(), 2), "PF": round(g / ls, 2) if ls else np.inf,
            "R total": round(r.sum(), 1), "DD máx (R)": round((np.maximum.accumulate(eq) - eq).max(), 1),
            "2018-22 R": round(r[(y < 2023).to_numpy()].sum(), 1), "2023-26 R": round(r[(y >= 2023).to_numpy()].sum(), 1),
            "largos R": round(r[tr["d"].to_numpy() == 1].sum(), 1), "cortos R": round(r[tr["d"].to_numpy() == -1].sum(), 1)}


LONDON = ((2.0, 5.0, 11.0),)
NYOPEN = ((9.5, 11.0, 15.9),)


def configs():
    base = Config()
    return [
        base,
        replace(base, name="v1 (FVG HTF invertido, ventana desde barrido, 1 por sesión)", htf_side="invertido",
                window_anchor="sweep", one_per_session=True),
        replace(base, name="C · sin HTF", use_htf=False),
        replace(base, name="C · sin iFVG (B)", use_ifvg=False),
        replace(base, name="C · sin CISD (entra en iFVG)", use_cisd=False),
        replace(base, name="C · solo barrido + CISD", use_htf=False, use_ifvg=False),
        replace(base, name="pivote 2/2", piv_l=2, piv_r=2),
        replace(base, name="pivote 5/5", piv_l=5, piv_r=5),
        replace(base, name="swings de 8 h", swing_lookback=96),
        replace(base, name="FVG HTF de 5 días", htf_days=5),
        replace(base, name="FVG solo 15m", htf_tfs=("15min",)),
        replace(base, name="FVG solo 1h", htf_tfs=("1h",)),
        replace(base, name="invalidación por cierre 5m", htf_invalidation="ltf_close"),
        replace(base, name="invalidación por mecha", htf_invalidation="wick"),
        replace(base, name="iFVG: el último", ifvg_select="last"),
        replace(base, name="iFVG: 24 velas atrás", ifvg_lookback=24),
        replace(base, name="CISD tolerante", cisd_mode="tolerant"),
        replace(base, name="CISD por estructura", cisd_mode="structure"),
        replace(base, name="ventana 2 h", window=24),
        replace(base, name="ventana desde el barrido", window_anchor="sweep"),
        replace(base, name="barrido con cierre de vuelta", sweep_close_back=True),
        replace(base, name="London ampliada 2-8", sessions=((2.0, 8.0, 11.0),)),
        replace(base, name="NY 9:30-11", sessions=NYOPEN),
        replace(base, name="London + NY", sessions=LONDON + NYOPEN),
        replace(base, name="1 por sesión", one_per_session=True),
    ]


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    for sym in ("NQ",):
        m = Market(sym)
        months = (m.idx[-1] - m.idx[0]).days / 30.44
        base = Config()
        st, tr = run(m, base)
        print(f"\n=== {sym} · {base.name} · London 2:00-5:00 NY · {m.idx[0]:%Y-%m-%d} a {m.idx[-1]:%Y-%m-%d} ===")
        print(funnel(st, months).to_string(index=False))
        lost, dist = why_lost(st)
        print("\nQué faltaba en los setups que no dieron señal:")
        for k, v in sorted(lost.items(), key=lambda x: -x[1]):
            print(f"  {k:30} {v}")
        print("Distancia del extremo al FVG HTF más cercano (setups sin entrega):", dist)
        rows = []
        for cfg in configs():
            s2, t2 = run(m, cfg)
            sig = sum(e == "señal" for _, e in s2)
            rows.append({"configuración": cfg.name, "barridos": len(s2), **summary(t2, months)})
            print(f"  {cfg.name} listo", flush=True)
        print("\n=== Comparación de configuraciones (un cambio cada vez respecto al modo A) ===")
        print(pd.DataFrame(rows).to_string(index=False))
        if not tr.empty:
            tr["año"] = tr["t"].dt.year
            tr["día"] = tr["t"].dt.day_name()
            print("\nModo A por año:\n", tr.groupby("año")["r"].agg(["count", "mean", "sum"]).round(2).T.to_string())
            print("\nModo A por día:\n", tr.groupby("día")["r"].agg(["count", "mean", "sum"]).round(2).T.to_string())
            print("\nModo A por temporalidad del FVG:\n", tr.groupby("htf_tf")["r"].agg(["count", "mean", "sum"]).round(2).T.to_string())


if __name__ == "__main__":
    main()
