"""Confirmación con 8 años (2018 - oct 2026) de la estrategia «largo sobre la VWAP de Globex» en NQ / MNQ.

Reglas (familia «lado» de vwap_research.py, que con 2 años de datos parecía buena):
  · VWAP anclada a las 18:00 NY (sesión Globex).
  · A la hora T de la sesión regular, si el precio está por encima → largo (variante «ambos»: por debajo → corto).
  · Salida: una vela de 5 min cierra al otro lado de la VWAP (trail) o cierre a las 16:00 NY.
Datos: velas de 1 minuto con volumen de Databento (2018-2024 + 2024-2026). Coste 1 punto; 1 MNQ.
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026; se compara con estar comprado sin filtro.

Uso:
    python vwap_globex_8y.py
"""

import itertools
import pickle

import numpy as np
import pandas as pd

import vwap_research as vr


def load():
    a = pickle.loads((vr.CACHE / "databento_nq_1m_2018_2024.pkl").read_bytes())
    b = pickle.loads((vr.CACHE / "databento_glbx_1m.pkl").read_bytes())
    b = b[b.symbol == "NQ.c.0"]
    d = pd.concat([a[a.index < b.index.min()], b])
    return d[~d.index.duplicated()]


def stats(tr):
    t = pd.DataFrame(tr, columns=["d", "pts"])
    y = t.d.dt.year
    u = t.pts * vr.USD
    out = {}
    for name, sel, yrs in (("dev", y < 2023, 5), ("val", y >= 2023, 3.75)):
        v = u[sel]
        g, l = v[v > 0].sum(), -v[v < 0].sum()
        eq = v.cumsum()
        out |= {f"{name}_ops": round(len(v) / yrs), f"{name}_usd": round(v.sum() / yrs), f"{name}_pf": round(g / l, 2) if l else np.inf,
                f"{name}_dd": round((eq.cummax() - eq).max()), f"{name}_win": round((v > 0).mean(), 2)}
    by = u.groupby(y).sum()
    out["años_pos"] = f"{(by > 0).sum()}/{len(by)}"
    out["by_year"] = by.round().astype(int).to_dict()
    return out


def main():
    pd.set_option("display.width", 250)
    days = vr.build_days("NQ", load())
    print(f"{len(days)} sesiones, {days[0]['d']:%Y-%m-%d} a {days[-1]['d']:%Y-%m-%d}")
    rows = []
    for t, anchor, only, trail in itertools.product((15, 30, 45, 60, 75, 90, 120), ("vwg", "vw"), (1, -1, 0), (True, False)):
        rows.append(dict(T=f"{(570 + t) // 60}:{(570 + t) % 60:02d}", vwap="Globex" if anchor == "vwg" else "9:30",
                         lado={1: "largos", -1: "cortos", 0: "ambos"}[only], salida="pierde VWAP" if trail else "16:00",
                         **stats(vr.lado(days, t=t, anchor=anchor, only=only, trail=trail))))
    for t in (30, 60, 90):
        rows.append(dict(T=f"{(570 + t) // 60}:{(570 + t) % 60:02d}", vwap="(sin filtro)", lado="siempre largo", salida="16:00",
                         **stats([(x["d"], x["c"][-1] - x["o"][t + 1] - vr.COST) for x in days])))
    r = pd.DataFrame(rows)
    r.to_pickle(vr.CACHE / "vwap_globex_8y.pkl")
    cols = [c for c in r.columns if c != "by_year"]
    for k, g in r.groupby(["vwap", "lado", "salida"], sort=False):
        print(f"\n── VWAP {k[0]} · {k[1]} · salida {k[2]} ──  ganan ambos periodos: {((g.dev_usd > 0) & (g.val_usd > 0)).mean():.0%}")
        print(g[cols].drop(columns=["vwap", "lado", "salida"]).to_string(index=False))
    best = r[(r.vwap == "Globex") & (r.lado == "largos") & (r.salida == "pierde VWAP")]
    print("\nPor año (Globex, largos, pierde VWAP):")
    for _, x in best.iterrows():
        print(x["T"], x["by_year"])


if __name__ == "__main__":
    main()
