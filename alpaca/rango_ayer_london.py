"""La ruptura del rango de ayer aplicada a la sesión de Londres (NQ y oro).

Misma lógica que en NY: si al abrir Londres el precio está DENTRO del rango de referencia, orden STOP de compra en
su máximo y de venta en su mínimo; stop en el punto medio; sin objetivo; una operación al día.
Rangos de referencia: sesión de NY de ayer (9:30-16:00), día completo de ayer (Globex 18:00-17:00) o Asia de hoy
(00:00-06:00 Londres). Inicio: 07:00 u 08:00 Londres. Salida: 12:00 Londres, 14:25 Londres (antes de NY) o 16:00 NY.
Horas de Londres en hora de Londres. Coste: NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC).
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python rango_ayer_london.py
"""

import itertools

import numpy as np
import pandas as pd

from crt_backtest import load_5m


def run(sym, cost, usd):
    df = load_5m(sym)
    tn = df.index
    tl = tn.tz_convert("Europe/London")
    gdate = np.array((tn + pd.Timedelta(hours=6)).normalize().date)
    lm = (tl.hour * 60 + tl.minute).to_numpy()
    lm = np.where(np.array(tl.date) < gdate, lm - 1440, lm)
    nm = (tn.hour * 60 + tn.minute).to_numpy()
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    groups = pd.Series(np.arange(len(df))).groupby(gdate).indices
    days = []
    for d in sorted(groups):
        idx = np.asarray(groups[d])
        rth = idx[(nm[idx] >= 570) & (nm[idx] < 960)]
        asia = idx[(lm[idx] >= 0) & (lm[idx] < 360)]
        days.append(dict(d=pd.Timestamp(d), idx=idx, lm=lm[idx], nm=nm[idx],
                         rthH=h[rth].max() if len(rth) > 60 else np.nan, rthL=l[rth].min() if len(rth) > 60 else np.nan,
                         dayH=h[idx].max(), dayL=l[idx].min(),
                         asiaH=h[asia].max() if len(asia) > 50 else np.nan, asiaL=l[asia].min() if len(asia) > 50 else np.nan))
    rows = []
    for ref, start, ex in itertools.product(("NY de ayer", "día de ayer", "Asia de hoy"), (420, 480), ("12:00", "14:25", "16:00 NY")):
        res = []
        for i in range(1, len(days)):
            x, p = days[i], days[i - 1]
            if (x["d"] - p["d"]).days > 4:
                continue
            H, L = {"NY de ayer": (p["rthH"], p["rthL"]), "día de ayer": (p["dayH"], p["dayL"]), "Asia de hoy": (x["asiaH"], x["asiaL"])}[ref]
            if not (np.isfinite(H) and np.isfinite(L)):
                continue
            idx, Lm, Nm = x["idx"], x["lm"], x["nm"]
            ks = idx[Lm >= start]
            if len(ks) == 0 or not (L <= o[ks[0]] <= H):
                continue
            if ex == "16:00 NY":
                ends = idx[(Nm >= 0) & (Nm < 960)]
            else:
                em = 720 if ex == "12:00" else 865
                ends = idx[(Lm >= 0) & (Lm < em + 5)]
            if len(ends) == 0:
                continue
            kend = ends[-1]
            mid = (H + L) / 2
            last_entry = (em - 30) if ex != "16:00 NY" else 10_000
            for k in ks:
                if k >= kend or (ex != "16:00 NY" and lm[k] > last_entry) or (ex == "16:00 NY" and Nm[np.searchsorted(idx, k)] >= 930 and Nm[np.searchsorted(idx, k)] < 1080):
                    break
                if h[k] > H:
                    s, e = 1, max(H, o[k])
                elif l[k] < L:
                    s, e = -1, min(L, o[k])
                else:
                    continue
                px = c[kend]
                for q in range(k + 1, kend + 1):
                    if (s == 1 and l[q] <= mid) or (s == -1 and h[q] >= mid):
                        px = min(mid, o[q]) if s == 1 else max(mid, o[q])
                        break
                res.append((x["d"].year, (s * (px - e) - cost) * usd))
                break
        if len(res) < 50:
            continue
        R = pd.DataFrame(res, columns=["y", "usd"])
        d, v = R[R.y < 2023].usd, R[R.y >= 2023].usd
        pf = lambda z: round(z[z > 0].sum() / -z[z < 0].sum(), 2)
        eq = R.usd.cumsum()
        rows.append(dict(activo=sym, rango=ref, inicio=f"{start // 60:02d}:00 Lon", salida=ex, ops_año=round(len(R) / 8.75),
                         acierto=round((R.usd > 0).mean(), 2), dev=round(d.sum() / 5), pf_dev=pf(d), val=round(v.sum() / 3.75), pf_val=pf(v),
                         dd=round((eq.cummax() - eq).max()), años=f"{(R.groupby('y').usd.sum() > 0).sum()}/9"))
    return pd.DataFrame(rows)


def main():
    pd.set_option("display.width", 250)
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0)):
        R = run(sym, cost, usd)
        ok = (R.dev > 0) & (R.val > 0)
        print(f"\n══════ {sym} · Londres · {len(R)} variantes · ganan en ambos periodos: {ok.mean():.0%} ══════")
        print(R.to_string(index=False))


if __name__ == "__main__":
    main()
