"""Estrategia de un post de Instagram (prompt para NinjaTrader): MNQ 5 min, 2018 - oct 2026, datos de 1 min con volumen.

Reglas del post:
  Largo: la EMA 9 cruza por encima de la EMA 21 (vela de 5 min cerrada) y el precio (cierre) está sobre el VWAP.
  Corto: lo contrario. Stop 20 ticks (5 puntos) · objetivo 40 ticks (10 puntos) · 1 contrato.
  Horario 9:30-11:30 NY · máximo 3 operaciones al día · pérdida diaria máxima 200 $ (con 1 MNQ nunca se alcanza).
Detalles que el post no dice (se prueban las dos opciones cuando importa):
  VWAP de la sesión Globex (desde las 18:00, el de NinjaTrader por defecto) o anclado a las 9:30.
  Entrada en la apertura de la vela siguiente; stop y objetivo se revisan con velas de 1 min (si caen en la misma,
  cuenta el stop); lo que siga abierto se cierra a las 16:00. Una operación a la vez.
Costes por operación: 1 punto (comisión + deslizamiento, como en el resto de pruebas) y 0,5 puntos (optimista).
1 MNQ = 2 $/punto. Control: lo mismo en ES (MES, 20 ticks = 5 puntos, 5 $/punto).

Uso:
    python instagram_ema921_vwap.py
"""

import numpy as np
import pandas as pd
from numba import njit

import vwap_globex_8y as V


@njit(cache=True)
def run(o1, h1, l1, c1, ent_k, side, day_end, stop, tgt):
    n = len(ent_k)
    out = np.full(n, np.nan)
    busy = -1
    for i in range(n):
        k = ent_k[i]
        if k <= busy:
            continue
        s = side[i]
        e = o1[k]
        sl, tg = e - s * stop, e + s * tgt
        px = c1[day_end[i]]
        qe = day_end[i]
        for q in range(k, day_end[i] + 1):
            if (s == 1 and l1[q] <= sl) or (s == -1 and h1[q] >= sl):
                px = sl
                qe = q
                break
            if (s == 1 and h1[q] >= tg) or (s == -1 and l1[q] <= tg):
                px = tg
                qe = q
                break
        busy = qe
        out[i] = s * (px - e)
    return out


def main():
    pd.set_option("display.width", 250)
    m1 = V.load()
    m1.index = m1.index.tz_convert("America/New_York")
    t1 = m1.index
    o1, h1, l1, c1, v1 = (m1[k].to_numpy() for k in ("open", "high", "low", "close", "volume"))
    hm1 = (t1.hour * 60 + t1.minute).to_numpy()
    day1 = np.array(t1.normalize().asi8)
    eod1 = pd.Series(np.where(hm1 < 960, np.arange(len(t1)), -1)).groupby(day1).max().reindex(day1).to_numpy()
    b = m1.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    t5 = b.index
    hm5 = (t5.hour * 60 + t5.minute).to_numpy()
    c5 = b.close
    e9, e21 = c5.ewm(span=9, adjust=False).mean(), c5.ewm(span=21, adjust=False).mean()
    typ = (b.high + b.low + b.close) / 3
    gday = (t5 + pd.Timedelta(hours=6)).normalize()
    vw_g = (typ * b.volume).groupby(gday).cumsum() / b.volume.groupby(gday).cumsum()
    rth = (hm5 >= 570) & (hm5 < 960)
    rday = t5.normalize()
    pv = (typ * b.volume).where(rth, 0.0).groupby(rday).cumsum()
    vv = b.volume.where(rth, 0.0).groupby(rday).cumsum()
    vw_r = (pv / vv.replace(0, np.nan))
    up = (e9 > e21) & (e9.shift() <= e21.shift())
    dn = (e9 < e21) & (e9.shift() >= e21.shift())
    close_hm = hm5 + 5                                          # la vela se cierra 5 min después de su apertura
    win = (close_hm >= 575) & (close_hm <= 690)                 # señales con la vela cerrada entre 9:35 y 11:30
    rows = []
    for vname, vw in (("Globex (desde 18:00)", vw_g), ("anclado 9:30", vw_r)):
        long_ = (up & (c5 > vw)).to_numpy() & win
        short = (dn & (c5 < vw)).to_numpy() & win
        idx = np.flatnonzero(long_ | short)
        side = np.where(long_[idx], 1, -1)
        ent_t = (t5[idx] + pd.Timedelta(minutes=5)).asi8
        k1 = np.searchsorted(t1.asi8, ent_t)
        ok = (k1 < len(t1))
        idx, side, k1 = idx[ok], side[ok], k1[ok]
        # máximo 3 señales por día (las primeras)
        d = rday[idx]
        rank = pd.Series(1, index=np.arange(len(idx))).groupby(np.asarray(d)).cumsum().to_numpy()
        keep = rank <= 3
        idx, side, k1 = idx[keep], side[keep], k1[keep]
        pts = run(o1, h1, l1, c1, k1.astype(np.int64), side.astype(np.int64), eod1[k1].astype(np.int64), 5.0, 10.0)
        yrs = t1.year.to_numpy()[k1]
        for cost in (1.0, 0.5):
            u = (pts - cost) * 2.0
            m = np.isfinite(u)
            uu, yy = u[m], yrs[m]
            dv, vl = uu[yy < 2023], uu[yy >= 2023]
            pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
            eq = np.cumsum(uu)
            rows.append(dict(vwap=vname, coste=f"{cost:g} pt", ops_año=round(len(uu) / 8.75), acierto=round((pts[m] > 0).mean(), 2),
                             dev=round(dv.sum() / 5), pf_dev=pf(dv), val=round(vl.sum() / 3.75), pf_val=pf(vl),
                             peor_racha=round((np.maximum.accumulate(eq) - eq).max()),
                             años=f"{sum(uu[yy == y].sum() > 0 for y in range(2018, 2027))}/9",
                             por_año={y: int(round(uu[yy == y].sum())) for y in range(2018, 2027)}))
    R = pd.DataFrame(rows)
    pd.set_option("display.max_colwidth", 150)
    print(R.to_string(index=False))
    R.to_pickle(".lab_cache/instagram_ema921_vwap.pkl")


if __name__ == "__main__":
    main()
