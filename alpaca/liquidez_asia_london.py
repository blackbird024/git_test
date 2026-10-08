"""¿Cuánta verdad hay en la «liquidez» de Asia y Londres? Estadística descriptiva en NQ y oro (2018 - oct 2026, 5 min).

Rangos (hora de Londres): Asia 00:00-06:00 · Londres 08:00-12:00 (horario Londres) · NY = 14:30-21:00 Londres (9:30-16:00 NY).
1) ¿Con qué frecuencia la sesión siguiente toma el máximo/mínimo de la anterior?
2) Tras la PRIMERA toma de un lado, carrera simétrica: ¿vuelve hacia dentro hasta el medio del rango barrido
   (reversión, lo que dice la teoría de la liquidez) o sigue fuera la MISMA distancia (continuación)?
   Si el nivel no significara nada, saldría ~50 %.
3) ¿Se toman los DOS lados el mismo día (barrida y luego el lado contrario)?

Uso:
    python liquidez_asia_london.py
"""

import numpy as np
import pandas as pd

from crt_backtest import load_5m


def main():
    pd.set_option("display.width", 200)
    for sym in ("NQ", "GC"):
        df = load_5m(sym)
        tl = df.index.tz_convert("Europe/London")
        tn = df.index
        gd = np.array((tn + pd.Timedelta(hours=6)).normalize().date)
        lm = (tl.hour * 60 + tl.minute).to_numpy()
        lm = np.where(np.array(tl.date) < gd, lm - 1440, lm)
        nm = (tn.hour * 60 + tn.minute).to_numpy()
        h, l = df.high.to_numpy(), df.low.to_numpy()
        stats = {k: [] for k in ("Londres toma Asia", "NY toma Londres", "NY toma Asia")}
        for d, idx in pd.Series(np.arange(len(df))).groupby(gd).indices.items():
            idx = np.asarray(idx)
            L, N = lm[idx], nm[idx]
            asia = idx[(L >= 0) & (L < 360)]
            ldn = idx[(L >= 480) & (L < 720)]
            ny = idx[(N >= 570) & (N < 960)]
            if len(asia) < 60 or len(ldn) < 40 or len(ny) < 70:
                continue
            ref = {"Asia": (h[asia].max(), l[asia].min()), "Londres": (h[ldn].max(), l[ldn].min())}
            for key, (rname, seg, after) in {"Londres toma Asia": ("Asia", ldn, np.r_[ldn, ny]),
                                             "NY toma Londres": ("Londres", ny, ny),
                                             "NY toma Asia": ("Asia", ny, ny)}.items():
                H, Lo = ref[rname]
                mid, R = (H + Lo) / 2, H - Lo
                if R <= 0:
                    continue
                up = np.flatnonzero(h[seg] > H)
                dn = np.flatnonzero(l[seg] < Lo)
                first = None
                if len(up) and (not len(dn) or up[0] <= dn[0]):
                    first, s, k0 = "máx", 1, seg[up[0]]
                elif len(dn):
                    first, s, k0 = "mín", -1, seg[dn[0]]
                res = None
                if first:
                    lvl = H if s == 1 else Lo
                    rest = after[after > k0]
                    for q in rest:
                        rev = l[q] <= mid if s == 1 else h[q] >= mid
                        con = h[q] >= lvl + 0.5 * R if s == 1 else l[q] <= lvl - 0.5 * R
                        if rev and con:
                            res = None
                            break
                        if rev:
                            res = "revierte"
                            break
                        if con:
                            res = "continúa"
                            break
                stats[key].append(dict(y=pd.Timestamp(d).year, up=len(up) > 0, dn=len(dn) > 0, res=res))
        print(f"\n══════ {sym} ══════")
        for key, rows in stats.items():
            T = pd.DataFrame(rows)
            both = (T.up & T.dn).mean()
            r = T.res.dropna()
            rv = (r == "revierte").mean()
            by = T.dropna(subset=["res"]).groupby(T.y < 2023).res.apply(lambda z: (z == "revierte").mean())
            print(f"{key:18s} días {len(T)} · toma el máx {T.up.mean():.0%} · el mín {T.dn.mean():.0%} · alguno {(T.up | T.dn).mean():.0%} · "
                  f"los dos {both:.0%} · ninguno {(~T.up & ~T.dn).mean():.0%} | tras la 1.ª toma: revierte al medio {rv:.0%} vs continúa {1 - rv:.0%} "
                  f"(2018-22 {by.get(True, np.nan):.0%} · 2023-26 {by.get(False, np.nan):.0%})")


if __name__ == "__main__":
    main()
