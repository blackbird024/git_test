"""Buyside & Sellside Liquidity [LuxAlgo] reproducido: zonas de MÁXIMOS / MÍNIMOS IGUALES (equal highs / equal lows).
NQ / MNQ y oro / MGC, 2018 - oct 2026.

Zona buyside: ≥ 2 pivotes altos (fractal de 7 velas a cada lado, velas de 15 min) de las últimas 100 velas a menos de
0,1 × ATR(14) entre sí → nivel = el más alto del grupo. Sellside: espejo con pivotes bajos. Una zona vale hasta que se rompe.
A) Solo (velas de 15 min, NY 9:30-15:00 NY / Londres 3:00-8:00 NY):
   barrida   la vela supera la zona con la mecha y CIERRA de vuelta → operación de giro, stop tras la mecha
   ruptura   la vela CIERRA más allá de la zona → operación a favor, stop al otro lado de la vela
   Objetivo 1R · 2R · cierre (16:00 NY o 11:30 NY en Londres). Coste NQ 1 pt (2 $/pt) · oro 0,3 pt (10 $/pt).
B) Confluencia con el ORB «la vela habla» (NQ): ¿hay una zona de liquidez sin tomar en la dirección de la operación a
   < 0,5 ATR de la sesión? ¿la apertura barrió una zona en contra?

Uso:
    python lux_buy_sell_liquidity.py
"""

import itertools

import numpy as np
import pandas as pd

from crt_backtest import load_5m
from nq_intraday_research import build_days
from orb15_forma_vela import candle, trade
from orb_velas_30_60 import summary


def zones(b, L=7, look=100, k=0.1):
    """Devuelve, para cada vela i, la zona buyside y sellside vigente (nivel o nan) conocida al ABRIR i."""
    h, l, c = b.high.to_numpy(), b.low.to_numpy(), b.close.to_numpy()
    pc = np.r_[c[0], c[:-1]]
    atr = pd.Series(np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))).rolling(14).mean().to_numpy()
    n = len(h)
    ph, pl = [], []
    bs, ss = np.full(n, np.nan), np.full(n, np.nan)
    cur_b, cur_s = np.nan, np.nan
    for i in range(2 * L + 1, n):
        j = i - L - 1                                         # pivote confirmado al abrir la vela i
        if h[j] == h[j - L:j + L + 1].max():
            ph.append((j, h[j]))
        if l[j] == l[j - L:j + L + 1].min():
            pl.append((j, l[j]))
        ph = [p for p in ph if p[0] > i - look]
        pl = [p for p in pl if p[0] > i - look]
        a = atr[i - 1]
        if np.isfinite(a):
            for lst, side in ((ph, 1), (pl, -1)):
                if len(lst) >= 2:
                    v = np.array([p[1] for p in lst])
                    last = v[-1]
                    grp = v[np.abs(v - last) <= k * a]
                    if len(grp) >= 2:
                        if side == 1:
                            cur_b = grp.max()
                        else:
                            cur_s = grp.min()
        if np.isfinite(cur_b) and h[i - 1] > cur_b:
            cur_b = np.nan                                    # tomada
        if np.isfinite(cur_s) and l[i - 1] < cur_s:
            cur_s = np.nan
        bs[i], ss[i] = cur_b, cur_s
    return bs, ss


def main():
    pd.set_option("display.width", 250)
    res = {}
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0)):
        df = load_5m(sym)
        b = df.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        bs, ss = zones(b)
        o, h, l, c = (b[k].to_numpy() for k in ("open", "high", "low", "close"))
        t = b.index
        hm = (t.hour * 60 + t.minute).to_numpy()
        day = np.array(t.normalize().asi8)
        for (ses, a0, a1, ex), mode, rr in itertools.product((("NY", 570, 900, 945), ("Londres", 180, 480, 690)),
                                                              ("barrida", "ruptura"), (1.0, 2.0, 0.0)):
            rows, busy_day = [], None
            for i in range(30, len(c) - 1):
                if not (a0 <= hm[i] <= a1) or day[i] == busy_day:
                    continue
                s = 0
                for lvl, side in ((bs[i], 1), (ss[i], -1)):
                    if not np.isfinite(lvl):
                        continue
                    pierce = h[i] > lvl if side == 1 else l[i] < lvl
                    closed_beyond = c[i] > lvl if side == 1 else c[i] < lvl
                    if pierce and mode == "barrida" and not closed_beyond:
                        s, sl = -side, (h[i] if side == 1 else l[i])
                    elif pierce and mode == "ruptura" and closed_beyond:
                        s, sl = side, (l[i] if side == 1 else h[i])
                if s == 0:
                    continue
                e = o[i + 1]
                risk = s * (e - sl)
                if risk <= 0:
                    continue
                tg = e + s * rr * risk if rr else None
                px = None
                for q in range(i + 1, len(c)):
                    if day[q] != day[i] or hm[q] >= ex:
                        px = c[q - 1]
                        break
                    if (s == 1 and l[q] <= sl) or (s == -1 and h[q] >= sl):
                        px = min(sl, o[q]) if s == 1 else max(sl, o[q])
                        break
                    if tg is not None and ((s == 1 and h[q] >= tg) or (s == -1 and l[q] <= tg)):
                        px = tg
                        break
                if px is None:
                    continue
                rows.append((t[i].year, (s * (px - e) - cost) * usd))
                busy_day = day[i]
            if len(rows) > 50:
                res[(sym, ses, mode, f"{rr:g}R" if rr else "cierre")] = summary(pd.DataFrame(rows, columns=["y", "u"]))
        print(sym, "listo", flush=True)
    T = pd.DataFrame(res).T
    T.index.names = ["activo", "sesión", "tipo", "objetivo"]
    print(T.to_string())
    # B) confluencia con el ORB (NQ)
    df = load_5m("NQ")
    b = df.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    bs, ss = zones(b)
    Z = pd.DataFrame({"bs": bs, "ss": ss}, index=b.index)
    t5 = df.index
    pre = df[(t5.hour == 9) & (t5.minute == 25)]
    pre.index = pre.index.normalize().tz_localize(None)
    rows = []
    for x in build_days("NQ"):
        d = pd.Timestamp(x["d"])
        if d not in pre.index:
            continue
        ph, pl = pre.loc[d, ["high", "low"]]
        B, a = x["rth"], x["atr"]
        c5, c15 = candle(B, 1), candle(B, 3)
        if c5 and ((c5[0] == 1 and B[0, 3] > ph) or (c5[0] == -1 and B[0, 3] < pl)):
            n, s, k = 1, c5[0], 0.1
        elif c15 and not c15[2]:
            n, s, k = 3, c15[0], 0.15
        else:
            continue
        ts = (d + pd.Timedelta(minutes=570)).tz_localize("America/New_York")
        if ts not in Z.index:
            continue
        zb, zs = Z.loc[ts, "bs"], Z.loc[ts, "ss"]
        px = B[n - 1, 3]
        target = zb if s == 1 else zs
        against = zs if s == 1 else zb
        near = np.isfinite(target) and 0 < s * (target - px) < 0.5 * a
        swept = np.isfinite(against) and ((s == 1 and B[:n, 2].min() < against) or (s == -1 and B[:n, 1].max() > against))
        rows.append(dict(y=d.year, u=(trade(B, n, s, k * a) - 1) * 2,
                         liquidez_a_favor="zona a < 0,5 ATR" if near else "no", barrio_en_contra="sí" if swept else "no"))
    D = pd.DataFrame(rows)
    print("\n══ ORB + Buyside/Sellside Liquidity ══\ntodas:", summary(D).to_dict())
    print(D.groupby("liquidez_a_favor").apply(summary, include_groups=False).to_string())
    print(D.groupby("barrio_en_contra").apply(summary, include_groups=False).to_string())


if __name__ == "__main__":
    main()
