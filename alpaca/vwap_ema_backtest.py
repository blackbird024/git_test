"""Cruce de VWAP + EMA 9 en el Nasdaq (NQ / MNQ), probado en varias temporalidades.

Reglas (la versión más habitual):
  · VWAP de la sesión (anclado a las 9:30 NY por defecto; variante anclada a las 18:00, sesión Globex).
  · EMA de 9 periodos sobre los cierres de la temporalidad elegida.
  · Al cierre de una vela, si la EMA 9 cruza por encima del VWAP → largo; por debajo → corto.
    Se entra en la apertura de la vela siguiente y se da la vuelta en el cruce contrario (siempre dentro).
  · Solo en la sesión regular (9:30-16:00 NY): nada abierto de noche; cierre a las 15:55.
  · Coste: 1 punto por operación ida y vuelta (comisión del micro + deslizamiento). 1 punto = 2 $ en MNQ.

Datos: velas de 1 minuto de NQ (contrato continuo) con volumen, de Databento, oct 2024 - oct 2026.

Uso:
    python vwap_ema_backtest.py
"""

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).with_name(".lab_cache")
COST = 1.0
TFS = [1, 2, 3, 5, 10, 15, 30]


def nq_1m():
    d = pickle.loads((CACHE / "databento_glbx_1m.pkl").read_bytes())
    d = d[d["symbol"] == "NQ.c.0"][["open", "high", "low", "close", "volume"]]
    d.index = d.index.tz_convert("America/New_York")
    return d.sort_index()


def bars(d1, tf, anchor):
    """Velas de tf minutos de la sesión regular con VWAP anclado (calculado en 1m) y EMA 9."""
    d = d1.copy()
    hm = d.index.hour * 60 + d.index.minute
    d["typ"] = (d.high + d.low + d.close) / 3
    if anchor == "9:30":
        key = d.index.normalize()
        d = d[(hm >= 570) & (hm < 960)]
        key = d.index.normalize()
    else:                                          # sesión Globex 18:00
        key = (d.index + pd.Timedelta(hours=6)).normalize()
    pv = (d.typ * d.volume).groupby(key).cumsum()
    vv = d.volume.groupby(key).cumsum()
    d["vwap"] = pv / vv.replace(0, np.nan)
    hm = d.index.hour * 60 + d.index.minute
    d = d[(hm >= 570) & (hm < 960)]
    # velas de tf minutos alineadas a las 9:30
    off = (d.index.hour * 60 + d.index.minute - 570) // tf
    g = d.groupby([d.index.normalize(), off])
    b = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
              vwap=("vwap", "last"))
    b["t"] = g.apply(lambda x: x.index[0]).values
    b = b.reset_index(drop=True).set_index("t")
    b["day"] = b.index.normalize()
    b["ema"] = b.close.ewm(span=9, adjust=False).mean()
    return b


def run(b, side="ambos"):
    """Siempre dentro en la sesión regular, vuelta en cada cruce. Devuelve operaciones en puntos."""
    o, c, ema, vw = b.open.to_numpy(), b.close.to_numpy(), b.ema.to_numpy(), b.vwap.to_numpy()
    day = b.day.to_numpy()
    hm = (b.index.hour * 60 + b.index.minute).to_numpy()
    tr = []
    pos, entry, et = 0, 0.0, None
    for i in range(1, len(b) - 1):
        last_bar = day[i + 1] != day[i]
        if pos and last_bar:                       # cierre de la sesión: fuera
            tr.append((et, pos, pos * (c[i] - entry) - COST))
            pos = 0
            continue
        up = ema[i] > vw[i] and ema[i - 1] <= vw[i - 1] and day[i - 1] == day[i]
        dn = ema[i] < vw[i] and ema[i - 1] >= vw[i - 1] and day[i - 1] == day[i]
        sig = 1 if up else -1 if dn else 0
        if side == "largos" and sig == -1:
            sig = 0 if pos == 0 else -9            # solo salir
        if side == "cortos" and sig == 1:
            sig = 0 if pos == 0 else 9
        if sig and sig != pos:
            if pos:
                tr.append((et, pos, pos * (o[i + 1] - entry) - COST))
                pos = 0
            if sig in (1, -1) and hm[i + 1] < 955:
                pos, entry, et = sig, o[i + 1], b.index[i + 1]
    return pd.DataFrame(tr, columns=["t", "side", "pts"])


def stats(t, days):
    if t.empty:
        return {}
    p = t.pts.to_numpy()
    eq = np.cumsum(p)
    g, l = p[p > 0].sum(), -p[p < 0].sum()
    half = t.t < t.t.iloc[0] + (t.t.iloc[-1] - t.t.iloc[0]) / 2
    return {"ops/día": round(len(p) / days, 1), "acierto": f"{(p > 0).mean():.0%}", "pts/op": round(p.mean(), 2),
            "PF": round(g / l, 2) if l else np.inf, "$/año 1 MNQ": round(p.sum() * 2 / (days / 252)),
            "DD máx $": round((np.maximum.accumulate(eq) - eq).max() * 2), "1.er año $": round(p[half.to_numpy()].sum() * 2),
            "2.º año $": round(p[~half.to_numpy()].sum() * 2), "sin costes $/año": round((p + COST).sum() * 2 / (days / 252))}


def main():
    pd.set_option("display.width", 220)
    d1 = nq_1m()
    rows = []
    for anchor in ("9:30", "18:00"):
        for tf in TFS:
            b = bars(d1, tf, anchor)
            days = b.day.nunique()
            for side in ("ambos", "largos", "cortos"):
                t = run(b, side)
                rows.append({"VWAP": anchor, "temporalidad": f"{tf}m", "lado": side, "ops": len(t), **stats(t, days)})
            print(f"{anchor} {tf}m listo", flush=True)
    r = pd.DataFrame(rows)
    print(f"\nNQ, sesión regular, {d1.index[0]:%Y-%m-%d} a {d1.index[-1]:%Y-%m-%d}, coste 1 punto por operación, resultados por 1 MNQ")
    print(r.to_string(index=False))


if __name__ == "__main__":
    main()
