"""Backtest del "Confirmation Model" (The Creative Trader) con su escala de notas A+/A/B+/B.

Interpretación mecánica (velas de 5 minutos para la ejecución). Para un CORTO (largo simétrico):
  1. Barrido de liquidez: el precio supera un máximo de swing reciente (pivote de 3 velas a cada
     lado, de las últimas 4 horas). Es obligatorio.
  2. Entrega HTF: en el barrido, el precio toca un FVG bajista de 15m o 1h aún no invalidado
     (ninguna vela ha cerrado por encima de él) y no cierra por encima.
  3. iFVG: un FVG alcista de 5m formado en la subida que precede al extremo y que, al entrar,
     ya ha sido cerrado por debajo (invertido).
  4. CISD (disparador): cierre por debajo de la apertura de la última serie de velas alcistas
     que hicieron el extremo. Entrada al cierre de esa vela. Obligatorio.
  5. SMT: el otro índice (SPY para QQQ, ETH para BTC) no supera su máximo equivalente.
  Stop: por encima del extremo del barrido. Objetivo: la liquidez opuesta (último mínimo de swing)
  o 2R fijo. Una operación por sesión.

Notas: B = barrido + HTF + CISD; B+ = B + iFVG; A = B+ + SMT. ("Barrido interno" de la A+ no se
puede definir de forma objetiva y no se prueba.) También se mide "sin HTF" (solo barrido + CISD).

Datos: futuros CME de Databento (NQ, ES, GC; 24 h), así que la sesión de Londres es completa.
Antes de usarlo hay que descargarlos (ver alpaca/README.md, sección Databento).

Uso:
    python confirmation_model_backtest.py
"""

import numpy as np
import pandas as pd

from crt_backtest import load_5m

PIVOT = 3
LOOKBACK = 48          # 4 horas de velas de 5m para buscar swings que barrer
CISD_WINDOW = 12       # el CISD debe llegar en la hora siguiente al extremo


def resample(df, rule):
    return df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def htf_fvgs(df5):
    """FVGs de 15m y 1h: lista de (hora de formación, arriba, abajo, tipo +1 alcista / -1 bajista)."""
    out = []
    for rule in ("15min", "1h"):
        b = resample(df5, rule)
        h, l = b["high"].to_numpy(), b["low"].to_numpy()
        step = pd.Timedelta(rule)
        for i in range(2, len(b)):
            t = b.index[i] + step                              # se conoce al cerrar la vela
            if l[i] > h[i - 2]:
                out.append((t, l[i], h[i - 2], 1))
            elif h[i] < l[i - 2]:
                out.append((t, l[i - 2], h[i], -1))
    return pd.DataFrame(out, columns=["t", "top", "bot", "kind"]).sort_values("t")


class Market:
    def __init__(self, df5):
        self.df = df5
        self.t = df5.index
        self.o, self.h, self.l, self.c = (df5[k].to_numpy() for k in ("open", "high", "low", "close"))
        n = len(df5)
        self.piv_hi = np.zeros(n, bool)
        self.piv_lo = np.zeros(n, bool)
        for i in range(PIVOT, n - PIVOT):
            w = slice(i - PIVOT, i + PIVOT + 1)
            self.piv_hi[i] = self.h[i] == self.h[w].max()
            self.piv_lo[i] = self.l[i] == self.l[w].min()
        self.fvg = htf_fvgs(df5)


def htf_touch(m, i, direction, extreme):
    """¿El extremo del barrido toca un FVG HTF activo y la vela no cierra al otro lado?"""
    t = m.t[i]
    # Corregido (oct 2026): un corto necesita un FVG BAJISTA (kind -1) y un largo uno ALCISTA (kind 1).
    # Antes se filtraba kind == -direction, es decir, el FVG del tipo contrario: los resultados B/B+/A anteriores
    # a esta corrección no son válidos.
    f = m.fvg[(m.fvg["t"] <= t) & (m.fvg["t"] >= t - pd.Timedelta(days=3)) & (m.fvg["kind"] == direction)]
    for _, z in f.iterrows():
        seg = m.c[(m.t >= z["t"]) & (m.t < t)]
        if direction == -1:                                     # corto: FVG bajista por encima
            if (seg > z["top"]).any():
                continue                                        # invalidado
            if extreme >= z["bot"] and m.c[i] <= z["top"]:
                return True
        else:
            if (seg < z["bot"]).any():
                continue
            if extreme <= z["top"] and m.c[i] >= z["bot"]:
                return True
    return False


def find_setup(m, other, start, end, require_htf=False):
    """Primer setup de la sesión [start, end) (con entrega HTF si require_htf): diccionario o None."""
    idx = np.where((m.t >= start) & (m.t < end))[0]
    for i in idx:
        if i < LOOKBACK + PIVOT:
            continue
        for direction in (-1, 1):
            # 1. barrido de un swing confirmado en las últimas 4 horas
            cand = range(i - LOOKBACK, i - PIVOT)
            if direction == -1:
                swings = [k for k in cand if m.piv_hi[k] and m.h[i] > m.h[k] and m.h[k + 1:i].max() <= m.h[k]]
            else:
                swings = [k for k in cand if m.piv_lo[k] and m.l[i] < m.l[k] and m.l[k + 1:i].min() >= m.l[k]]
            if not swings:
                continue
            k = swings[-1]
            # 4. CISD en la hora siguiente; el extremo puede seguir extendiéndose hasta entonces
            ext_i = i
            for j in range(i + 1, min(i + CISD_WINDOW, len(m.c))):
                if m.t[j] >= end:
                    break
                if (direction == -1 and m.h[j] > m.h[ext_i]) or (direction == 1 and m.l[j] < m.l[ext_i]):
                    ext_i = j
                    continue
                s = ext_i                                       # última serie de velas a favor del barrido
                while s > 0 and ((m.c[s - 1] > m.o[s - 1]) if direction == -1 else (m.c[s - 1] < m.o[s - 1])):
                    s -= 1
                level = m.o[s]
                if (direction == -1 and m.c[j] < level) or (direction == 1 and m.c[j] > level):
                    extreme = m.h[ext_i] if direction == -1 else m.l[ext_i]
                    setup = build(m, other, direction, k, ext_i, j, extreme)
                    if require_htf and not setup["htf"]:
                        break                                   # no cumple: seguir buscando
                    return setup
            break
    return None


def build(m, other, direction, k, ext_i, j, extreme):
    entry = m.c[j]
    htf = htf_touch(m, ext_i, direction, extreme)
    # 3. iFVG: FVG de 5m a favor del barrido, en las 12 velas antes del extremo, cerrado al revés
    ifvg = False
    for q in range(max(2, ext_i - 12), ext_i + 1):
        if direction == -1 and m.l[q] > m.h[q - 2]:            # FVG alcista
            if (m.c[ext_i:j + 1] < m.h[q - 2]).any():
                ifvg = True
        if direction == 1 and m.h[q] < m.l[q - 2]:             # FVG bajista
            if (m.c[ext_i:j + 1] > m.l[q - 2]).any():
                ifvg = True
    # 5. SMT con el otro mercado
    smt = False
    if other is not None:
        tk, te = m.t[k], m.t[ext_i]
        ref = other.df.loc[(other.df.index >= tk - pd.Timedelta(minutes=10)) & (other.df.index <= tk + pd.Timedelta(minutes=10))]
        now = other.df.loc[(other.df.index > tk + pd.Timedelta(minutes=10)) & (other.df.index <= te)]
        if not ref.empty and not now.empty:
            smt = now["high"].max() <= ref["high"].max() if direction == -1 else now["low"].min() >= ref["low"].min()
    # objetivo: liquidez opuesta = último swing confirmado en sentido contrario
    target = None
    for q in range(ext_i - PIVOT, max(0, ext_i - 96), -1):
        if direction == -1 and m.piv_lo[q] and m.l[q] < entry:
            target = m.l[q]
            break
        if direction == 1 and m.piv_hi[q] and m.h[q] > entry:
            target = m.h[q]
            break
    return dict(dir=direction, i=j, entry=entry, stop=extreme, target=target, htf=htf, ifvg=ifvg, smt=smt)


def manage(m, s, exit_time, mode, cost):
    d, entry, stop = s["dir"], s["entry"], s["stop"]
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    target = s["target"] if mode == "liquidez" else entry + d * 2 * risk
    if target is None or (target - entry) * d <= 0:
        return None
    for q in range(s["i"] + 1, len(m.c)):
        if m.t[q] >= exit_time:
            px = m.o[q]
            break
        if (d == 1 and m.l[q] <= stop) or (d == -1 and m.h[q] >= stop):
            px = stop
            break
        if (d == 1 and m.h[q] >= target) or (d == -1 and m.l[q] <= target):
            px = target
            break
    else:
        px = m.c[-1]
    return d * (px - entry) / risk - 2 * cost * entry / risk


def grade(s):
    if not s["htf"]:
        return "sin HTF"
    if s["ifvg"] and s["smt"]:
        return "A"
    if s["ifvg"]:
        return "B+"
    return "B"


def run(symbol, other_symbol, sessions, cost, rth_only=False):
    m = Market(load_5m(symbol))
    other = Market(load_5m(other_symbol)) if other_symbol else None
    days = sorted(set(m.t.date))
    rows = []
    for name, (s_h, e_h, x_h) in sessions.items():
        for d in days:
            if pd.Timestamp(d).weekday() >= 5 and rth_only:
                continue
            base = pd.Timestamp(d, tz="America/New_York")
            start, end, exit_t = (base + pd.Timedelta(hours=x) for x in (s_h, e_h, x_h))
            for require_htf in (False, True):
                s = find_setup(m, other, start, end, require_htf)
                if not s:
                    continue
                for mode in ("liquidez", "2R"):
                    r = manage(m, s, exit_t, mode, cost)
                    if r is not None:
                        rows.append(dict(session=name, mode=mode, grade=grade(s) if require_htf else "primera",
                                         r=r, day=d))
    return pd.DataFrame(rows)


def report(title, df):
    print(f"\n=== {title} ===")
    print(f"  {'Sesión / objetivo / nota':44}{'Ops':>5}{'Gan.':>7}{'R med':>8}{'R tot':>8}{'1ª mit':>8}{'2ª mit':>8}")
    for (sess, mode), g in df.groupby(["session", "mode"], sort=False):
        graded = g[g["grade"] != "primera"]
        for label, sub in ([("primer setup (barrido+CISD)", g[g["grade"] == "primera"]),
                            ("B o mejor (con HTF)", graded)]
                           + [(gr, graded[graded["grade"] == gr]) for gr in ("B", "B+", "A")]):
            r = sub["r"].reset_index(drop=True)
            if r.empty:
                print(f"  {sess + ' / ' + mode + ' / ' + label:44}{0:>5}")
                continue
            h = len(r) // 2
            print(f"  {sess + ' / ' + mode + ' / ' + label:44}{len(r):>5}{(r > 0).mean():>7.0%}{r.mean():>+8.2f}"
                  f"{r.sum():>+8.1f}{r.iloc[:h].sum():>+8.1f}{r.iloc[h:].sum():>+8.1f}")


def main():
    sessions = {"Londres killzone 2:00-5:00 NY": (2, 5, 11),
                "Londres ampliada 2:00-8:00 NY": (2, 8, 11),
                "Apertura NY 9:30-11:00": (9.5, 11, 15.9)}
    report("Nasdaq futuros (NQ), SMT con S&P 500 (ES) — Databento", run("NQ", "ES", sessions, cost=0.00003))
    report("Oro futuros (GC) — Databento, sin SMT", run("GC", None, sessions, cost=0.00003))
    print("\n  R = veces el riesgo. Con objetivo 2R hace falta acertar >33% para no perder.")


if __name__ == "__main__":
    main()
