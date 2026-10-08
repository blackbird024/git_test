"""Búsqueda de estrategias SENCILLAS (como el ORB) con ALTO ACIERTO (≥ 60 %) en NQ y oro, sesión de NY, 2018 - oct 2026.

Todas son una regla de una línea con entrada, stop y objetivo fijos, una operación al día, cierre 16:00 NY:
  hueco      a las 9:30 NY, si el precio abre lejos del cierre de ayer (g · ATR), se opera hacia el cierre de ayer.
             Objetivo = cierre de ayer (hueco cerrado). Stop = m × el tamaño del hueco más allá de la entrada.
  vuelta     a las 10:00 / 10:30 NY, si el precio está a más de d · ATR de la apertura de las 9:30, se opera hacia
             la apertura. Objetivo = la apertura. Stop = m × esa distancia más allá.
  orb        rango de los primeros 15 / 30 / 60 min; orden stop en máximo y mínimo; objetivo t × rango; stop en el
             otro lado o en el medio. Entradas hasta las 12:00.
  rango ayer ruptura del máximo/mínimo de ayer (si abre dentro); objetivo t × rango de ayer; stop en el medio.
  vela       dirección de la primera vela de 5 min; objetivo t · ATR; stop s · ATR (objetivo más cerca que el stop).
ATR = media de 14 días del rango de la sesión 9:30-16:00. Coste NQ 1 punto (2 $/punto por MNQ), oro 0,3 puntos
(10 $/punto por MGC). Si stop y objetivo caen en la misma vela de 5 min, cuenta el stop.
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python alto_acierto_simple.py
"""

import itertools

import numpy as np
import pandas as pd

from nq_intraday_research import build_days


def bracket(B, k0, s, e, sl, tg, same_bar_target=True):
    """Desde la vela k0 (incluida) busca stop u objetivo; si no, cierre de la última vela."""
    for q in range(k0, 78):
        hs = B[q, 2] <= sl if s == 1 else B[q, 1] >= sl
        ht = B[q, 1] >= tg if s == 1 else B[q, 2] <= tg
        if q == k0 and not same_bar_target:
            ht = False
        if hs:
            return min(sl, B[q, 0]) if s == 1 else max(sl, B[q, 0])
        if ht:
            return tg
    return B[-1, 3]


def hueco(x, g_min, g_max, m):
    B, gap = x["rth"], x["rth"][0, 0] - x["pc"]
    if not (g_min * x["atr"] <= abs(gap) <= g_max * x["atr"]):
        return None
    s = -int(np.sign(gap))
    e = B[0, 0]
    return s, bracket(B, 0, s, e, e - s * m * abs(gap), x["pc"]), e


def vuelta(x, k, d, m):
    B = x["rth"]
    op, e = B[0, 0], B[k, 0]
    dist = e - op
    if abs(dist) < d * x["atr"]:
        return None
    s = -int(np.sign(dist))
    return s, bracket(B, k, s, e, e - s * m * abs(dist), op), e


def ruptura(B, H, L, k_from, k_to, stop_mode, t, R):
    mid = (H + L) / 2
    for k in range(k_from, k_to):
        up, dn = B[k, 1] > H, B[k, 2] < L
        if up and dn:
            return None
        if not (up or dn):
            continue
        s = 1 if up else -1
        e = max(H, B[k, 0]) if s == 1 else min(L, B[k, 0])
        sl = mid if stop_mode == "medio" else (L if s == 1 else H)
        tg = e + s * t * R
        if (s == 1 and B[k, 2] <= sl) or (s == -1 and B[k, 1] >= sl):
            return s, sl, e
        return s, bracket(B, k + 1, s, e, sl, tg), e
    return None


def orb(x, n, t, stop_mode):
    B = x["rth"]
    H, L = B[:n, 1].max(), B[:n, 2].min()
    return ruptura(B, H, L, n, 30, stop_mode, t, H - L)


def rango_ayer(x, t):
    B = x["rth"]
    if not (x["pl"] < B[0, 0] < x["ph"]):
        return None
    return ruptura(B, x["ph"], x["pl"], 0, 73, "medio", t, x["ph"] - x["pl"])


def vela(x, t, s_):
    B = x["rth"]
    side = int(np.sign(B[0, 3] - B[0, 0]))
    if side == 0:
        return None
    e = B[1, 0]
    return side, bracket(B, 1, side, e, e - side * s_ * x["atr"], e + side * t * x["atr"]), e


FAMILIAS = {
    "hueco": [(f"hueco {a}-{b} ATR, stop {m}× hueco", lambda x, a=a, b=b, m=m: hueco(x, a, b, m))
              for (a, b), m in itertools.product(((0.02, 0.1), (0.1, 0.2), (0.2, 0.4), (0.02, 0.2)), (1, 2, 3))],
    "vuelta": [(f"vuelta a la apertura a las {['10:00', '10:30'][k == 12]}, dist ≥ {d} ATR, stop {m}×",
                lambda x, k=k, d=d, m=m: vuelta(x, k, d, m)) for k, d, m in itertools.product((6, 12), (0.1, 0.2, 0.3), (1, 2, 3))],
    "orb": [(f"ORB {n * 5} min, objetivo {t}× rango, stop {sm}", lambda x, n=n, t=t, sm=sm: orb(x, n, t, sm))
            for n, t, sm in itertools.product((3, 6, 12), (0.25, 0.5), ("otro lado", "medio"))],
    "rango ayer": [(f"rango de ayer, objetivo {t}× rango, stop medio", lambda x, t=t: rango_ayer(x, t)) for t in (0.1, 0.2, 0.3)],
    "vela": [(f"primera vela 5m, objetivo {t} ATR, stop {s} ATR", lambda x, t=t, s=s: vela(x, t, s))
             for t, s in ((0.05, 0.1), (0.05, 0.2), (0.1, 0.2), (0.1, 0.3), (0.15, 0.3))],
}


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 60)
    rows = []
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0)):
        days = build_days(sym)
        for fam, variants in FAMILIAS.items():
            for name, f in variants:
                res = []
                for x in days:
                    r = f(x)
                    if r is None:
                        continue
                    s, px, e = r
                    res.append((pd.Timestamp(x["d"]).year, (s * (px - e) - cost) * usd))
                R = pd.DataFrame(res, columns=["y", "u"])
                if len(R) < 80:
                    continue
                d, v = R[R.y < 2023].u, R[R.y >= 2023].u
                pf = lambda z: round(z[z > 0].sum() / -z[z < 0].sum(), 2)
                eq = R.u.cumsum()
                streak = (R.u <= 0).astype(int)
                rows.append(dict(activo=sym, familia=fam, regla=name, ops_año=round(len(R) / 8.75), acierto=round((R.u > 0).mean(), 2),
                                 gan_media=round(R.u[R.u > 0].mean()), perd_media=round(R.u[R.u <= 0].mean()),
                                 dev=round(d.sum() / 5), pf_dev=pf(d), val=round(v.sum() / 3.75), pf_val=pf(v),
                                 peor_racha=round((eq.cummax() - eq).max()),
                                 max_perd_seguidas=int(streak.groupby((streak == 0).cumsum()).sum().max()),
                                 años=f"{(R.groupby('y').u.sum() > 0).sum()}/9"))
        print(f"{sym} listo", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/alto_acierto_simple.pkl")
    both = lambda x: f"{((x.dev > 0) & (x.val > 0)).mean():.0%}"
    for (sym, fam), g in R.groupby(["activo", "familia"], sort=False):
        print(f"\n══ {sym} · {fam} · {len(g)} variantes · ganan en ambos periodos: {both(g)} ══")
        print(g.sort_values("acierto", ascending=False).drop(columns=["activo", "familia"]).to_string(index=False))
    print("\n══ Candidatas: acierto ≥ 60 %, ganan en ambos periodos, ≥ 7/9 años ══")
    C = R[(R.acierto >= 0.6) & (R.dev > 0) & (R.val > 0) & (R.años.str[0].astype(int) >= 7)]
    print(C.sort_values("val", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
