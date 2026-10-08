"""ORB de 30 minutos en NQ / MNQ y oro / MGC, en la sesión de Nueva York y en la de Londres.

Rango: máximo y mínimo de los primeros 30 minutos de la sesión.
  NY: 9:30-10:00 NY · Londres: 08:00-08:30 Londres (hora de Londres, las semanas de cambio de hora quedan bien).
Si el precio rompe por arriba → compra; si rompe por abajo → vende. Una operación al día (la primera ruptura).
Variantes:
  entrada  orden STOP en el nivel (entra en el instante de la ruptura) o al CIERRE de una vela de 5 min fuera del rango
  stop     el otro lado del rango · el medio del rango
  objetivo ninguno (cierre de sesión) · 1R · 2R
  última entrada  2 h después de abrir o hasta 30 min antes del cierre
  salida   NY: 16:00 NY · Londres: 12:00 Londres o 14:25 Londres (antes de NY)
Coste: NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC). Datos 5 min 2018 - oct 2026.
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python orb30_test.py
"""

import itertools

import numpy as np
import pandas as pd

from crt_backtest import load_5m


def days_of(sym):
    df = load_5m(sym)
    tn = df.index
    tl = tn.tz_convert("Europe/London")
    gd = np.array((tn + pd.Timedelta(hours=6)).normalize().date)
    nm = (tn.hour * 60 + tn.minute).to_numpy()
    lm = (tl.hour * 60 + tl.minute).to_numpy()
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    out = []
    for d, idx in pd.Series(np.arange(len(df))).groupby(gd).indices.items():
        idx = np.asarray(idx)
        out.append(dict(d=pd.Timestamp(d), idx=idx, nm=nm[idx], lm=lm[idx]))
    return out, o, h, l, c


def run(days, o, h, l, c, ses, entry, stop, rr, last_rel, exit_m, cost, usd):
    res = []
    for x in days:
        clock = x["nm"] if ses == "NY" else x["lm"]
        idx = x["idx"]
        start = 570 if ses == "NY" else 480
        rng = idx[(clock >= start) & (clock < start + 30)]
        if len(rng) < 6:
            continue
        H, L = h[rng].max(), l[rng].min()
        mid = (H + L) / 2
        after = idx[(clock >= start + 30) & (clock <= exit_m)]
        if len(after) < 2:
            continue
        kend = after[-1]
        last_entry = start + 30 + last_rel if last_rel else exit_m - 30
        for k in after:
            ck = clock[np.searchsorted(idx, k)]
            if ck > last_entry or k >= kend:
                break
            if entry == "stop":
                up, dn = h[k] > H, l[k] < L
                if not (up or dn):
                    continue
                s = 1 if up else -1
                e = max(H, o[k]) if s == 1 else min(L, o[k])
                k0 = k
            else:
                up, dn = c[k] > H, c[k] < L
                if not (up or dn):
                    continue
                s = 1 if up else -1
                e = c[k]
                k0 = k
            sl = (L if s == 1 else H) if stop == "otro lado" else mid
            if (s == 1 and e <= sl) or (s == -1 and e >= sl):
                break
            tg = e + s * rr * abs(e - sl) if rr else None
            px = c[kend]
            for q in range(k0 + 1, kend + 1):
                if (s == 1 and l[q] <= sl) or (s == -1 and h[q] >= sl):
                    px = min(sl, o[q]) if s == 1 else max(sl, o[q])
                    break
                if tg is not None and ((s == 1 and h[q] >= tg) or (s == -1 and l[q] <= tg)):
                    px = tg
                    break
            res.append((x["d"].year, (s * (px - e) - cost) * usd, abs(e - sl) * usd))
            break
    return pd.DataFrame(res, columns=["y", "u", "riesgo"])


def main():
    pd.set_option("display.width", 260)
    rows = []
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0)):
        days, o, h, l, c = days_of(sym)
        for ses, entry, stop, rr, last_rel in itertools.product(("NY", "Londres"), ("stop", "cierre 5m"), ("otro lado", "medio"),
                                                                 (0, 1, 2), (120, 0)):
            exits = [955] if ses == "NY" else [715, 865]
            for ex in exits:
                R = run(days, o, h, l, c, ses, entry, stop, rr, last_rel, ex, cost, usd)
                if len(R) < 50:
                    continue
                d, v = R[R.y < 2023].u, R[R.y >= 2023].u
                pf = lambda z: round(z[z > 0].sum() / -z[z < 0].sum(), 2)
                eq = R.u.cumsum()
                rows.append(dict(activo=sym, sesion=ses, entrada=entry, stop=stop, objetivo=f"{rr}R" if rr else "cierre",
                                 ultima_entrada="2 h" if last_rel else "hasta el final",
                                 salida={955: "16:00 NY", 715: "12:00 Lon", 865: "14:25 Lon"}[ex],
                                 ops_año=round(len(R) / 8.75), acierto=round((R.u > 0).mean(), 2), riesgo_med=round(R.riesgo.median()),
                                 dev=round(d.sum() / 5), pf_dev=pf(d), val=round(v.sum() / 3.75), pf_val=pf(v),
                                 peor_racha=round((eq.cummax() - eq).max()), años=f"{(R.groupby('y').u.sum() > 0).sum()}/9",
                                 por_año=R.groupby("y").u.sum().round().astype(int).to_dict()))
        print(f"{sym} listo", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/orb30.pkl")
    both = lambda x: f"{((x.dev > 0) & (x.val > 0)).mean():.0%}"
    cols = [k for k in R.columns if k != "por_año"]
    for (sym, ses), g in R.groupby(["activo", "sesion"], sort=False):
        print(f"\n══════ {sym} · {ses} · {len(g)} variantes · ganan en ambos periodos: {both(g)} ══════")
        for col in ("entrada", "stop", "objetivo", "ultima_entrada", "salida"):
            print(g.groupby(col).apply(lambda x: pd.Series({"n": len(x), "% ambos": both(x), "med dev": int(x.dev.median()),
                  "med val": int(x.val.median()), "med racha": int(x.peor_racha.median())}), include_groups=False).to_string())
        S = g.assign(mn=g[["dev", "val"]].min(axis=1)).sort_values("mn", ascending=False)
        print(S.head(6)[cols].to_string(index=False))
        print("por año (mejor):", S.iloc[0].por_año)


if __name__ == "__main__":
    main()
