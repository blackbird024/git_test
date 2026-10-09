"""ORB de 15 min + ruptura con FVG + entrada en el FVG (NQ / MNQ, sesión de NY), 2018 - oct 2026.

1. Rango: máximo y mínimo de 9:30-9:45 NY (15:30-15:45 Italia).
2. Ruptura: una vela de 5 min CIERRA fuera del rango (entre 9:45 y 12:00 NY).
3. FVG de la ruptura: en esa vela o en las 2 siguientes aparece un FVG a favor (alcista: mínimo de la vela i >
   máximo de la vela i-2; bajista espejo). Si no aparece, no hay operación ese día.
4. Entrada: orden LÍMITE en el borde cercano del FVG o en su 50 % (CE), válida hasta las 12:00 NY.
5. Stop: debajo del FVG (borde lejano − 1 tick) · en el medio del rango de 15 min · en el otro lado del rango.
   Objetivo: 2R · 3R · cierre 16:00.
Referencias: ORB 15 min normal (orden stop en el máximo/mínimo, stop en el otro lado, cierre 16:00) y ORB 5 min.
Una operación al día. Coste 1 punto (2 $/punto por MNQ). Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python orb15_fvg.py
"""

import itertools

import numpy as np
import pandas as pd

from nq_intraday_research import build_days


def exit_px(B, k0, s, sl, tg):
    for q in range(k0, 78):
        if (s == 1 and B[q, 2] <= sl) or (s == -1 and B[q, 1] >= sl):
            return min(sl, B[q, 0]) if s == 1 else max(sl, B[q, 0])
        if tg is not None and ((s == 1 and B[q, 1] >= tg) or (s == -1 and B[q, 2] <= tg)):
            return tg
    return B[-1, 3]


def orb15_fvg(B, entry, stop, rr):
    H, L = B[:3, 1].max(), B[:3, 2].min()
    for k in range(3, 30):
        s = 1 if B[k, 3] > H else -1 if B[k, 3] < L else 0
        if s == 0:
            continue
        fvg = None
        for i in range(max(k, 2), min(k + 3, 30)):
            if s == 1 and B[i, 2] > B[i - 2, 1]:
                fvg = (B[i - 2, 1], B[i, 2], i)            # (lo, hi, vela)
                break
            if s == -1 and B[i, 1] < B[i - 2, 2]:
                fvg = (B[i, 1], B[i - 2, 2], i)
                break
        if fvg is None:
            return None
        lo, hi, i0 = fvg
        lvl = (hi if s == 1 else lo) if entry == "borde" else (lo + hi) / 2
        if stop == "FVG":
            sl = lo - 0.25 if s == 1 else hi + 0.25
        elif stop == "medio rango":
            sl = (H + L) / 2
        else:
            sl = L if s == 1 else H
        if s * (lvl - sl) <= 0:
            return None
        for j in range(i0 + 1, 30):
            if (s == 1 and B[j, 2] <= lvl) or (s == -1 and B[j, 1] >= lvl):
                e = min(lvl, B[j, 0]) if s == 1 else max(lvl, B[j, 0])
                risk = s * (e - sl)
                if risk <= 0:
                    return None
                if (s == 1 and B[j, 2] <= sl) or (s == -1 and B[j, 1] >= sl):
                    return s * (sl - e)                     # entra y toca el stop en la misma vela
                tg = e + s * rr * risk if rr else None
                return s * (exit_px(B, j + 1, s, sl, tg) - e)
        return None
    return None


def orb15_plain(B):
    H, L = B[:3, 1].max(), B[:3, 2].min()
    for k in range(3, 30):
        up, dn = B[k, 1] > H, B[k, 2] < L
        if up and dn:
            return None
        if up or dn:
            s = 1 if up else -1
            e = max(H, B[k, 0]) if s == 1 else min(L, B[k, 0])
            return s * (exit_px(B, k + 1, s, L if s == 1 else H, None) - e)
    return None


def orb5(B, atr):
    s = int(np.sign(B[0, 3] - B[0, 0]))
    if s == 0:
        return None
    e = B[1, 0]
    return s * (exit_px(B, 1, s, e - s * 0.1 * atr, None) - e)


def stats(rows, name, res):
    R = pd.DataFrame(res, columns=["y", "u"])
    d, v = R[R.y < 2023].u, R[R.y >= 2023].u
    pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
    eq = R.u.cumsum()
    rows.append(dict(estrategia=name, ops_año=round(len(R) / 8.75), acierto=f"{(R.u > 0).mean():.0%}", dev=round(d.sum() / 5),
                     pf_dev=pf(d), val=round(v.sum() / 3.75), pf_val=pf(v), peor_racha=round((eq.cummax() - eq).max()),
                     años=f"{(R.groupby('y').u.sum() > 0).sum()}/9"))


def main():
    pd.set_option("display.width", 250)
    days = build_days("NQ")
    rows = []
    run = lambda f: [(pd.Timestamp(x["d"]).year, (r - 1.0) * 2.0) for x in days for r in [f(x)] if r is not None]
    stats(rows, "ORB 5 min (tu estrategia)", run(lambda x: orb5(x["rth"], x["atr"])))
    stats(rows, "ORB 15 min normal (stop orden, SL otro lado)", run(lambda x: orb15_plain(x["rth"])))
    for entry, stop, rr in itertools.product(("borde", "CE 50 %"), ("FVG", "medio rango", "otro lado"), (2.0, 3.0, 0.0)):
        stats(rows, f"ORB 15 + FVG · entrada {entry} · SL {stop} · {'cierre' if not rr else f'{rr:g}R'}",
              run(lambda x: orb15_fvg(x["rth"], entry, stop, rr)))
    T = pd.DataFrame(rows)
    T.to_pickle(".lab_cache/orb15_fvg.pkl")
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
