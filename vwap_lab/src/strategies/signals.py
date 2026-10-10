"""Las seis estrategias (A-F). Cada función recibe los arrays de UNA sesión y devuelve, por vela cerrada t, la señal
(+1 largo, −1 corto, 0 nada) y la vela de referencia del stop (la de señal, o la de retesteo en E).

Cruce alcista de X sobre Y en t: X[t−1] <= Y[t−1] y X[t] > Y[t], con t−1 dentro de la misma sesión. Permanecer encima no
es un cruce. Todas las condiciones usan valores de la vela t ya cerrada; nada posterior.

  A  EMA9 cruza el VWAP;  cierre del lado del cruce respecto al VWAP
  B  EMA20 cruza el VWAP; ídem
  C  EMA9 cruza EMA21;    cierre > VWAP (largos) / < VWAP (cortos)
  D  EMA20 cruza EMA50;   ídem
  E  cruce de C; en las 3 velas siguientes una vela retestea la EMA21 (mínimo <= EMA21 + tolerancia y
     >= EMA21 − profundidad·ATR) y cierra por encima → señal en esa vela; si no, la señal caduca
  F  C + cierre > EMA50 y EMA50[t] − EMA50[t−6] >= 0 (largos; cortos espejo)
Filtro de VWAP plano (todas): pendiente >= umbral (largos) / <= −umbral (cortos); umbral None = sin filtro.
En E el filtro se evalúa en la vela del cruce.
"""
import numpy as np

STRATEGIES = ("A", "B", "C", "D", "E", "F")


def _cross(x, y):
    up = np.zeros(len(x), bool)
    dn = np.zeros(len(x), bool)
    up[1:] = (x[:-1] <= y[:-1]) & (x[1:] > y[1:])
    dn[1:] = (x[:-1] >= y[:-1]) & (x[1:] < y[1:])
    return up, dn


def _slope_ok(slope, thr, side):
    if thr is None:
        return np.ones(len(slope), bool)
    with np.errstate(invalid="ignore"):
        return (slope >= thr) if side == 1 else (slope <= -thr)


def signals(a: dict, strat: str, thr, p: dict, tick: float):
    """a: arrays de sesión c, h, l, o, vwap, slope, ema9, ema20, ema21, ema50, atr. Devuelve (side[], ref[])."""
    c, h, l = a["c"], a["h"], a["l"]
    n = len(c)
    side = np.zeros(n, int)
    ref = np.arange(n)
    vw = a["vwap"]
    if strat in ("A", "B"):
        x = a["ema9"] if strat == "A" else a["ema20"]
        up, dn = _cross(x, vw)
        L = up & (c > vw)
        S = dn & (c < vw)
    else:
        x, y = (a["ema9"], a["ema21"]) if strat in ("C", "E", "F") else (a["ema20"], a["ema50"])
        up, dn = _cross(x, y)
        L = up & (c > vw)
        S = dn & (c < vw)
        if strat == "F":
            k = p["ema50_slope_bars"]
            e50 = a["ema50"]
            d50 = np.full(n, np.nan)
            d50[k:] = e50[k:] - e50[:-k]
            d50_all = a.get("ema50_delta", d50)
            L &= (c > e50) & (d50_all >= 0)
            S &= (c < e50) & (d50_all <= 0)
    L &= _slope_ok(a["slope"], thr, 1)
    S &= _slope_ok(a["slope"], thr, -1)
    if strat != "E":
        side[L] = 1
        side[S] = -1
        return side, ref
    e21, at = a["ema21"], a["atr"]
    tol = p["retest_tolerance_ticks"] * tick
    deep = p["retest_max_depth_atr"]
    for t in np.nonzero(L | S)[0]:
        s = 1 if L[t] else -1
        for j in range(t + 1, min(t + 1 + p["retest_bars"], n)):
            if s == 1:
                ok = (l[j] <= e21[j] + tol) and (l[j] >= e21[j] - deep * at[j]) and (c[j] > e21[j])
            else:
                ok = (h[j] >= e21[j] - tol) and (h[j] <= e21[j] + deep * at[j]) and (c[j] < e21[j])
            if ok:
                if side[j] == 0:
                    side[j] = s
                    ref[j] = j
                break
    return side, ref
