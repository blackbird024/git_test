"""Estrategia de RUPTURA de la liquidez de sesión (lo contrario de «barrida y giro»), NQ y oro, 2018 - oct 2026.

Idea (de liquidez_asia_london.py y sweep_1h_4h.py): cuando el precio toma el máximo/mínimo de una sesión anterior,
lo normal es que SIGA, no que gire. Se opera esa continuación.
Rango de referencia (hora de Londres para Asia/Londres):
  Asia        00:00-06:00 Londres
  Londres     08:00-12:00 Londres
  noche       todo lo anterior a la apertura de NY (18:00 NY del día anterior → 9:30 NY; 8:20 NY en oro)
  ayer NY     sesión regular de ayer (la «ruptura del rango de ayer», como referencia)
Reglas: solo si la sesión de NY abre DENTRO del rango. Orden STOP de compra en el máximo y de venta en el mínimo;
la primera que entra, una al día. Ventana de entradas: NQ 9:30-15:30 / 9:30-11:30 NY; oro 8:20-12:30 / 8:20-10:20 NY.
Stop: medio del rango · otro lado del rango.  Objetivo: 0,5 × rango (1:1 con stop al medio) · 1 × rango · ninguno.
Salida forzosa: NQ 16:00 NY · oro 13:30 NY. Si stop y objetivo caen en la misma vela de 5 min, cuenta el stop.
Coste NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC).
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python liquidez_ruptura.py
"""

import itertools

import numpy as np
import pandas as pd

from crt_backtest import load_5m


def build(sym):
    df = load_5m(sym)
    tn = df.index
    tl = tn.tz_convert("Europe/London")
    gd = np.array((tn + pd.Timedelta(hours=6)).normalize().date)
    lm = (tl.hour * 60 + tl.minute).to_numpy()
    lm = np.where(np.array(tl.date) < gd, lm - 1440, lm)
    nm = (tn.hour * 60 + tn.minute).to_numpy()
    nm = np.where(nm >= 1080, nm - 1440, nm)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    open_ny = 570 if sym == "NQ" else 500
    close_ny = 960 if sym == "NQ" else 810
    days, prev = [], None
    for d, idx in pd.Series(np.arange(len(df))).groupby(gd).indices.items():
        idx = np.asarray(idx)
        L, N = lm[idx], nm[idx]
        sel = lambda m: idx[m]
        asia, ldn = sel((L >= 0) & (L < 360)), sel((L >= 480) & (L < 720))
        night, ny = sel(N < open_ny), sel((N >= open_ny) & (N < close_ny))
        if len(asia) < 50 or len(ldn) < 40 or len(ny) < (close_ny - open_ny) // 5 * 0.9:
            prev = None
            continue
        x = dict(d=pd.Timestamp(d), ny=ny, nym=N[(N >= open_ny) & (N < close_ny)],
                 ref={"Asia": (h[asia].max(), l[asia].min()), "Londres": (h[ldn].max(), l[ldn].min()),
                      "noche": (h[night].max(), l[night].min())})
        if prev is not None:
            x["ref"]["ayer NY"] = (h[prev["ny"]].max(), l[prev["ny"]].min())
            days.append(x)
        prev = x
    return days, o, h, l, c, open_ny


def run(days, o, h, l, c, ref, last_entry, stop, tgt, cost, usd):
    res = []
    for x in days:
        if ref not in x["ref"]:
            continue
        H, L = x["ref"][ref]
        R, mid = H - L, (H + L) / 2
        ny, nym = x["ny"], x["nym"]
        if R <= 0 or not (L < o[ny[0]] < H):
            continue
        for j, k in enumerate(ny):
            if nym[j] > last_entry:
                break
            up, dn = h[k] > H, l[k] < L
            if not (up or dn):
                continue
            if up and dn:
                break                                   # misma vela rompe los dos lados: se descarta el día
            s = 1 if up else -1
            e = max(H, o[k]) if s == 1 else min(L, o[k])
            sl = mid if stop == "medio" else (L if s == 1 else H)
            tg = None if tgt == 0 else (H if s == 1 else L) + s * tgt * R
            px = c[ny[-1]]
            # la propia vela de entrada: si después de entrar toca el stop, pérdida (conservador)
            if (s == 1 and l[k] <= sl) or (s == -1 and h[k] >= sl):
                px = sl
            else:
                for q in ny[j + 1:]:
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
        days, o, h, l, c, op = build(sym)
        for ref, le, stop, tgt in itertools.product(("Asia", "Londres", "noche", "ayer NY"), (op + 120, op + 360 if sym == "NQ" else op + 250),
                                                    ("medio", "otro lado"), (0.5, 1.0, 0)):
            R = run(days, o, h, l, c, ref, le, stop, tgt, cost, usd)
            if len(R) < 50:
                continue
            d, v = R[R.y < 2023].u, R[R.y >= 2023].u
            pf = lambda z: round(z[z > 0].sum() / -z[z < 0].sum(), 2)
            eq = R.u.cumsum()
            rows.append(dict(activo=sym, rango=ref, entradas_hasta=f"{le // 60}:{le % 60:02d}", stop=stop,
                             objetivo={0.5: "0,5×rango", 1.0: "1×rango", 0: "cierre"}[tgt], ops_año=round(len(R) / 8.75),
                             acierto=round((R.u > 0).mean(), 2), riesgo_med=round(R.riesgo.median()),
                             dev=round(d.sum() / 5), pf_dev=pf(d), val=round(v.sum() / 3.75), pf_val=pf(v),
                             peor_racha=round((eq.cummax() - eq).max()), años=f"{(R.groupby('y').u.sum() > 0).sum()}/9",
                             por_año=R.groupby("y").u.sum().round().astype(int).to_dict()))
        print(f"{sym} listo", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/liquidez_ruptura.pkl")
    cols = [k for k in R.columns if k != "por_año"]
    both = lambda x: f"{((x.dev > 0) & (x.val > 0)).mean():.0%}"
    for (sym, ref), g in R.groupby(["activo", "rango"], sort=False):
        print(f"\n══════ {sym} · rango {ref} · {len(g)} variantes · ganan en ambos periodos: {both(g)} ══════")
        print(g.sort_values("val", ascending=False)[cols].to_string(index=False))
    S = R.assign(mn=R[["dev", "val"]].min(axis=1)).sort_values("mn", ascending=False)
    print("\nMejores en conjunto:")
    print(S.head(10)[cols].to_string(index=False))
    for _, x in S.head(3).iterrows():
        print(x.activo, x.rango, x.stop, x.objetivo, x.entradas_hasta, x.por_año)


if __name__ == "__main__":
    main()
