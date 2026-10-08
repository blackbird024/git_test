"""La vela de las 08:00 de Italia en NQ / MNQ (control: ES), 2018 - oct 2026.

Hora de Italia (Europe/Rome; 08:00 Italia = 07:00 Londres = 02:00 NY casi todo el año).
Vela: la que empieza a las 08:00 Italia, de 5, 15, 30 o 60 min.
A) Dirección: al cerrar la vela, entrada en la apertura siguiente a favor de su color (o en contra, como control).
   Stop: el otro extremo de la vela · 10 % del ATR diario. Objetivo: 1R · 2R · ninguno.
B) Ruptura (ORB de esa vela): orden STOP en su máximo y en su mínimo; la primera que entra, una al día;
   entradas hasta las 12:00 Italia. Stop: el otro lado · el medio. Objetivo: 1R · 2R · ninguno.
Salida forzosa: 12:00 Italia · 15:25 Italia (antes de NY) · 22:00 Italia (cierre de NY).
ATR diario = media de 14 días del rango de la sesión Globex. Si stop y objetivo caen en la misma vela de 5 min,
cuenta el stop. Coste 1 punto (NQ: 2 $/punto por MNQ · ES: 5 $/punto por MES).
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python vela8_italia.py
"""

import itertools

import numpy as np
import pandas as pd

from crt_backtest import load_5m


def run_day(o, h, l, c, idx, im, n, mode, stop, rr, ex, atr):
    first = idx[(im >= 480) & (im < 480 + n)]
    if len(first) < n // 5:
        return None
    after = idx[(im >= 480 + n) & (im < ex)]
    if len(after) < 3:
        return None
    H, L = h[first].max(), l[first].min()
    if mode in ("a favor", "en contra"):
        col = np.sign(c[first[-1]] - o[first[0]])
        if col == 0:
            return None
        s = int(col if mode == "a favor" else -col)
        k0, e = 0, o[after[0]]
        if stop == "vela":
            sl = L if s == 1 else H
        else:
            sl = e - s * 0.1 * atr
    else:
        k0 = None
        for j, k in enumerate(after):
            if im[np.searchsorted(idx, k)] >= 720:
                return None
            up, dn = h[k] > H, l[k] < L
            if up and dn:
                return None
            if up or dn:
                s = 1 if up else -1
                e = max(H, o[k]) if s == 1 else min(L, o[k])
                k0 = j
                break
        if k0 is None:
            return None
        sl = (L if s == 1 else H) if stop == "vela" else (H + L) / 2
    risk = s * (e - sl)
    if risk <= 0:
        return None
    tg = e + s * rr * risk if rr else None
    px = c[after[-1]]
    for q in after[k0:]:
        if (s == 1 and l[q] <= sl) or (s == -1 and h[q] >= sl):
            px = min(sl, o[q]) if s == 1 else max(sl, o[q])
            break
        if tg is not None and ((s == 1 and h[q] >= tg) or (s == -1 and l[q] <= tg)):
            px = tg
            break
    return s * (px - e)


def main():
    pd.set_option("display.width", 250)
    rows = []
    for sym, usd in (("NQ", 2.0), ("ES", 5.0)):
        df = load_5m(sym)
        t = df.index
        ti = t.tz_convert("Europe/Rome")
        im = (ti.hour * 60 + ti.minute).to_numpy()
        o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
        gd = (t + pd.Timedelta(hours=6)).normalize()
        D = df.groupby(gd).agg(high=("high", "max"), low=("low", "min"))
        atr_d = (D.high - D.low).rolling(14).mean().shift(1)
        groups = pd.Series(np.arange(len(df))).groupby(np.array(ti.normalize().asi8)).indices
        days = []
        for d, idx in groups.items():
            idx = np.asarray(idx)
            a = atr_d.get(gd[idx[0]], np.nan)
            if ti[idx[0]].weekday() >= 5 or not np.isfinite(a):
                continue
            days.append((ti[idx[0]].year, idx, im[idx], a))
        for n, mode, stop, rr, ex in itertools.product((5, 15, 30, 60), ("a favor", "en contra", "ruptura"),
                                                        ("vela", "otro"), (1.0, 2.0, 0.0), (720, 925, 1320)):
            res = []
            for y, idx, m, a in days:
                st = stop if mode != "ruptura" else ("vela" if stop == "vela" else "medio")
                r = run_day(o, h, l, c, idx, m, n, mode, st if mode == "ruptura" else ("vela" if stop == "vela" else "atr"), rr, ex, a)
                if r is not None:
                    res.append((y, (r - 1.0) * usd))
            R = pd.DataFrame(res, columns=["y", "u"])
            if len(R) < 100:
                continue
            dv, vv = R[R.y < 2023].u, R[R.y >= 2023].u
            pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
            eq = R.u.cumsum()
            stop_name = ("otro extremo" if stop == "vela" else "10 % ATR") if mode != "ruptura" else ("otro lado" if stop == "vela" else "medio")
            rows.append(dict(activo=sym, vela=f"{n}m", modo=mode, stop=stop_name, obj=f"{rr:g}R" if rr else "ninguno",
                             salida={720: "12:00", 925: "15:25", 1320: "22:00"}[ex], ops_año=round(len(R) / 8.75),
                             acierto=round((R.u > 0).mean(), 2), dev=round(dv.sum() / 5), pf_dev=pf(dv), val=round(vv.sum() / 3.75),
                             pf_val=pf(vv), peor_racha=round((eq.cummax() - eq).max()), años=f"{(R.groupby('y').u.sum() > 0).sum()}/9"))
        print(sym, "listo", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/vela8_italia.pkl")
    both = lambda x: f"{((x.dev > 0) & (x.val > 0)).mean():.0%}"
    print(f"\nTotal: {len(R)} variantes")
    print(R.groupby(["activo", "modo"]).apply(lambda g: pd.Series({"n": len(g), "% ganan ambos": both(g), "acierto medio": round(g.acierto.mean(), 2),
          "med dev": int(g.dev.median()), "med val": int(g.val.median())}), include_groups=False).to_string())
    print(R.groupby(["activo", "vela"]).apply(lambda g: pd.Series({"% ganan ambos": both(g), "med val": int(g.val.median())}), include_groups=False).unstack(0).to_string())
    C = R[(R.activo == "NQ") & (R.dev > 0) & (R.val > 0)]
    print(f"\n══ NQ: variantes que ganan en ambos periodos ({len(C)}) ══")
    print(C.sort_values("val", ascending=False).head(30).to_string(index=False))


if __name__ == "__main__":
    main()
