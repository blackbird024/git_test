"""Petición del usuario: "sumemos la EMA 100". Filtro de tendencia sobre las rupturas de 5 min.
Reglas fijadas antes de ver resultados:
- EMA 100 calculada con velas de 1, 5, 15 o 60 min de las 24 h (datos ET continuos); se usa el valor de la última vela
  CERRADA al terminar la vela del rango (sin mirar el futuro).
- Si el cierre de la vela del rango está POR ENCIMA de la EMA → solo se coloca la orden stop de COMPRA (1 tick sobre el
  máximo); por debajo → solo la de VENTA. La orden queda activa hasta el plazo (3,5 h); si el precio rompe primero el
  otro lado no pasa nada (la orden sigue esperando).
- Resto igual que el playbook: NQ DATO (8:25 ET, objetivo 0,75 R) y APERTURA (9:25 ET, objetivo 1 S), stop a máx(R, 30)
  del nivel roto. Oro (MGC): 5 min 8:25 ET (14:25 Italia) y 3:00 ET (9:00 Italia), stop = otro lado, objetivo 1 rango.
- Variante "OCO+EMA" (añadida tras ver que la orden solitaria activa 3,5 h empeoraba): órdenes OCO como sin filtro
  (cuenta solo la 1.ª ruptura del evento) y se descarta la operación si esa ruptura va contra la EMA.
- Comparación: sin filtro (orden OCO) frente a cada EMA. Coste base. Regla: dev>0 y val>0, luego prueba."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from data.loaders import nq_1m
from execution_costs.costs import fut
from rangos_lib import FILES, load_days, stats
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest


def ema_lookup(close_1m, tf):
    s = close_1m if tf == 1 else close_1m.resample(f"{tf}min", label="left", closed="left").last().dropna()
    e = s.ewm(span=100, adjust=False).mean()
    e.index = e.index + pd.Timedelta(minutes=tf)          # disponible al cierre de la vela
    return e


def run(D, a, c, ema, tmode, minstop, oco=False):
    tk = c.tick
    rnd = lambda x: round(x / tk) * tk
    fills = []
    for date, m in D:
        H, L, C = m[:, 1], m[:, 2], m[:, 3]
        if np.isnan(H[a:a + 5]).sum() > 2:
            continue
        hi, lo = np.nanmax(H[a:a + 5]), np.nanmin(L[a:a + 5])
        R = hi - lo
        if R <= 0:
            continue
        s0, ex = a + 5, min(a + 5 + 210, 955)
        if ema is None or oco:
            up = np.nonzero(H[s0:ex] >= hi + tk - 1e-9)[0]
            dn = np.nonzero(L[s0:ex] <= lo - tk + 1e-9)[0]
            ku = up[0] + s0 if len(up) else None
            kd = dn[0] + s0 if len(dn) else None
            if (ku is None and kd is None) or (ku is not None and ku == kd):
                continue
            side, k = (1, ku) if kd is None or (ku is not None and ku < kd) else (-1, kd)
            if oco:
                t_end = pd.Timestamp(f"{date.date()}", tz="America/New_York") + pd.Timedelta(minutes=s0)
                ev = ema.asof(t_end)
                cc = C[a:a + 5][~np.isnan(C[a:a + 5])]
                if np.isnan(ev) or not len(cc) or (1 if cc[-1] > ev else -1) != side:
                    continue
        else:
            t_end = pd.Timestamp(f"{date.date()}", tz="America/New_York") + pd.Timedelta(minutes=s0)
            ev = ema.asof(t_end)
            cc = C[a:a + 5][~np.isnan(C[a:a + 5])]
            if np.isnan(ev) or not len(cc):
                continue
            side = 1 if cc[-1] > ev else -1
            hit = np.nonzero(H[s0:ex] >= hi + tk - 1e-9)[0] if side == 1 else np.nonzero(L[s0:ex] <= lo - tk + 1e-9)[0]
            if not len(hit):
                continue
            k = hit[0] + s0
        edge = hi if side == 1 else lo
        S = max(R, minstop)
        stop = rnd(edge - side * S - side * tk)
        dist = 0.75 * R if tmode == "0.75R" else (S if tmode == "1S" else R)
        o = Order(side, "stop", k, stop, rnd(edge + side * dist), ex, level=rnd(edge + side * tk), k_last=k + 1)
        f = simulate(date, m, ex + 1, o, c)
        if f is not None:
            fills.append(f)
    return trades_frame(fills, c)


def main():
    per = periods("intradia", include_test=True)
    exp = new_experiment("ema100_filtro")
    rows = []
    cfg = {"MNQ": [("DATO 14:25", 505, "0.75R", 30.0), ("APERTURA 15:25", 565, "1S", 30.0)],
           "MGC": [("DATO 14:25", 505, "1R", 0.0), ("LONDRES 9:00", 180, "1R", 0.0)]}
    for sym, wins in cfg.items():
        D, _ = load_days(sym)
        if sym == "MNQ":
            close = nq_1m()["close"]
        else:
            g = pd.read_pickle(FILES["MGC"])
            close = g["close"].tz_convert("America/New_York")
        emas = {tf: ema_lookup(close, tf) for tf in (1, 5, 15, 60)}
        c = fut(sym, "base")
        for (nm, a, tm, ms), tf, oco in itertools.product(wins, (None, 1, 5, 15, 60), (False, True)):
            if tf is None and oco:
                continue
            t = run(D, a, c, None if tf is None else emas[tf], tm, ms, oco)
            lbl = "sin filtro" if tf is None else f"EMA100 {tf} min" + (" OCO" if oco else " solo un lado")
            rows.append(dict(mercado=sym, ventana=nm, filtro=lbl, ops_año=len(t) / 8.75, **stats(t, per, c)))
        print(sym, "ok", flush=True)
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    pd.set_option("display.width", 250)
    print(r[["mercado", "ventana", "filtro", "ops_año", "dev", "val", "prueba", "neto_año", "acierto", "años_pos",
             "ic90_FM", "pasa"]].round(2).to_string(index=False))
    write_manifest(exp, experimento="filtro EMA 100 en las rupturas de 5 min", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
