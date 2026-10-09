"""ORB 5 min en NQ / MNQ con REVERSIÓN (stop and reverse), 2018 - oct 2026.

Base (como ORB5_NQ.pine): dirección de la primera vela 9:30-9:35, entrada 9:35, stop 10 % del ATR de la sesión,
cierre 16:00. Reversión: cuando salta el stop, se abre la operación CONTRARIA en ese mismo precio, con su propio
stop (0,1 o 0,2 ATR) y cierre 16:00. Variantes: 1 reversión, hasta 3 reversiones; reversión permitida todo el día
o solo si el stop salta antes de las 10:30. También «solo la reversión» (no se opera la primera entrada).
Si stop y nada más en la misma vela de 5 min: se aplica el stop. Coste 1 punto por operación (2 $/punto por MNQ).
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python orb5_reversion.py
"""

import itertools

import numpy as np
import pandas as pd

from nq_intraday_research import build_days


def day_pnl(B, atr, k_rev, max_rev, rev_until, only_rev):
    s = int(np.sign(B[0, 3] - B[0, 0]))
    if s == 0:
        return None
    e, k0 = B[1, 0], 1
    risk = 0.1 * atr
    total, n, revs = 0.0, 0, 0
    first = True
    while True:
        sl = e - s * risk
        hit = None
        for q in range(k0, 78):
            if (s == 1 and B[q, 2] <= sl) or (s == -1 and B[q, 1] >= sl):
                hit = q
                break
        px = (min(sl, B[hit, 0]) if s == 1 else max(sl, B[hit, 0])) if hit is not None else B[-1, 3]
        if not (first and only_rev):
            total += s * (px - e) - 1.0
            n += 1
        first = False
        if hit is None or revs >= max_rev or hit >= rev_until or hit >= 77:
            break
        revs += 1
        s, e, k0, risk = -s, px, hit + 1, k_rev * atr
        # la vela del stop ya cuenta para la nueva operación desde el siguiente bar (conservador: empieza en hit+1)
    return (total, n) if n else None


def main():
    pd.set_option("display.width", 250)
    days = build_days("NQ")
    rows = []
    variants = [("ORB normal (sin reversión)", 0.1, 0, 78, False)]
    for k_rev, max_rev, until, only in itertools.product((0.1, 0.2), (1, 3), (78, 12), (False, True)):
        if only and max_rev > 1:
            continue
        name = f"{'solo la reversión' if only else 'ORB + reversión'} · stop rev {k_rev} ATR · máx {max_rev} · {'todo el día' if until == 78 else 'stop antes de 10:30'}"
        variants.append((name, k_rev, max_rev, until, only))
    for name, k_rev, max_rev, until, only in variants:
        res = []
        for x in days:
            r = day_pnl(x["rth"], x["atr"], k_rev, max_rev, until, only)
            if r is not None:
                res.append((pd.Timestamp(x["d"]).year, r[0] * 2, r[1]))
        R = pd.DataFrame(res, columns=["y", "u", "n"])
        d, v = R[R.y < 2023].u, R[R.y >= 2023].u
        pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
        eq = R.u.cumsum()
        rows.append(dict(variante=name, ops_año=round(R.n.sum() / 8.75), dias_año=round(len(R) / 8.75),
                         dias_ganadores=f"{(R.u > 0).mean():.0%}", dev=round(d.sum() / 5), pf_dev=pf(d), val=round(v.sum() / 3.75),
                         pf_val=pf(v), peor_dia=round(R.u.min()), peor_racha=round((eq.cummax() - eq).max()),
                         años=f"{(R.groupby('y').u.sum() > 0).sum()}/9", y2026=round(R[R.y == 2026].u.sum())))
    T = pd.DataFrame(rows)
    T.to_pickle(".lab_cache/orb5_reversion.pkl")
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
