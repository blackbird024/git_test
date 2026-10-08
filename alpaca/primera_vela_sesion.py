"""¿La primera vela de cada sesión dice hacia dónde va el día? NQ y oro, 2018 - oct 2026.

Regla: al cerrar la primera vela de la sesión (5, 15, 30 o 60 min), se entra en su dirección al abrir la
siguiente vela de 5 min (verde → compra, roja → venta). Una operación por sesión.
Sesiones: Asia 00:00 Londres (cierre 06:00 Londres) · Londres 08:00 Londres (cierre 12:00 o 14:25 Londres) ·
NY 9:30 NY (cierre 16:00 NY; oro también desde la apertura de COMEX 8:20 NY).
Stop: el otro extremo de la primera vela · 10 % del ATR(14) del rango del día Globex (como el ORB de Zarattini).
Sin objetivo: se cierra a la hora de cierre. Si el stop se toca, se sale en el stop (o en la apertura si hay hueco).
Coste NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC).
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026. El control es lo mismo pero en dirección CONTRARIA a la vela.

Uso:
    python primera_vela_sesion.py
"""

import itertools

import numpy as np
import pandas as pd

from crt_backtest import load_5m

SESSIONS = {  # nombre: (reloj, inicio, [salidas])
    "Asia": ("lon", 0, [360]),
    "Londres": ("lon", 480, [720, 865]),
    "NY": ("ny", 570, [960]),
    "COMEX 8:20": ("ny", 500, [960]),
}


def main():
    pd.set_option("display.width", 250)
    rows = []
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0)):
        df = load_5m(sym)
        tn = df.index
        tl = tn.tz_convert("Europe/London")
        gd = np.array((tn + pd.Timedelta(hours=6)).normalize().date)
        nm = (tn.hour * 60 + tn.minute).to_numpy()
        lm = (tl.hour * 60 + tl.minute).to_numpy()
        o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
        groups = pd.Series(np.arange(len(df))).groupby(gd).indices
        keys = sorted(groups)
        rng = np.array([h[groups[k]].max() - l[groups[k]].min() for k in keys])
        atr = pd.Series(rng).rolling(14).mean().shift(1).to_numpy()
        for ses, (clk, start, exits) in SESSIONS.items():
            if ses == "COMEX 8:20" and sym == "NQ":
                continue
            for n, stop, ex, mode in itertools.product((5, 15, 30, 60), ("vela", "10% ATR"), exits, ("a favor", "contraria")):
                res = []
                for di, k in enumerate(keys):
                    if not np.isfinite(atr[di]):
                        continue
                    idx = np.asarray(groups[k])
                    m = (nm if clk == "ny" else lm)[idx]
                    if ses == "Asia":
                        m = np.where(m >= 18 * 60, m - 1440, m)      # las horas de la tarde anterior van antes de medianoche
                    first = idx[(m >= start) & (m < start + n)]
                    after = idx[(m >= start + n) & (m < ex)]
                    if len(first) < n // 5 or len(after) < 3:
                        continue
                    side = np.sign(c[first[-1]] - o[first[0]])
                    if side == 0:
                        continue
                    s = int(side if mode == "a favor" else -side)
                    e = o[after[0]]
                    if stop == "vela":
                        sl = l[first].min() if s == 1 else h[first].max()
                    else:
                        sl = e - s * 0.1 * atr[di]
                    if s * (e - sl) <= 0:
                        continue
                    px = c[after[-1]]
                    for q in after:
                        if (s == 1 and l[q] <= sl) or (s == -1 and h[q] >= sl):
                            px = min(sl, o[q]) if s == 1 else max(sl, o[q])
                            break
                    res.append((pd.Timestamp(k).year, (s * (px - e) - cost) * usd))
                R = pd.DataFrame(res, columns=["y", "u"])
                d, v = R[R.y < 2023].u, R[R.y >= 2023].u
                pf = lambda z: round(z[z > 0].sum() / -z[z < 0].sum(), 2)
                eq = R.u.cumsum()
                rows.append(dict(activo=sym, sesion=ses, vela=f"{n}m", stop=stop, salida=f"{ex // 60}:{ex % 60:02d}",
                                 direccion=mode, ops_año=round(len(R) / 8.75), acierto=round((R.u > 0).mean(), 2),
                                 dev=round(d.sum() / 5), pf_dev=pf(d), val=round(v.sum() / 3.75), pf_val=pf(v),
                                 peor_racha=round((eq.cummax() - eq).max()), años=f"{(R.groupby('y').u.sum() > 0).sum()}/9"))
        print(f"{sym} listo", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/primera_vela_sesion.pkl")
    both = lambda x: f"{((x.dev > 0) & (x.val > 0)).mean():.0%}"
    for (sym, ses, mode), g in R.groupby(["activo", "sesion", "direccion"], sort=False):
        print(f"\n══ {sym} · {ses} · {mode} · {len(g)} variantes · ganan en ambos periodos: {both(g)} ══")
        print(g.sort_values("val", ascending=False).drop(columns=["activo", "sesion", "direccion"]).to_string(index=False))


if __name__ == "__main__":
    main()
