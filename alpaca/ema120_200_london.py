"""Cruce EMA 120 / EMA 200 en la sesión de LONDRES, NQ / MNQ y oro / MGC (control ES), 2018 - oct 2026.

Mismo motor y variantes que ema_cross_research.py / ema120_200.py, con ventanas en hora de Londres:
  Londres        entradas 08:00-13:55, todo cerrado a las 14:25 Londres (antes de la apertura de NY)
  Londres corta  entradas 08:00-11:30, todo cerrado a las 12:00 Londres
Costes: NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC) · ES 1 punto (control).
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python ema120_200_london.py
"""

import numpy as np
import pandas as pd

import ema_cross_research as E
from crt_backtest import load_5m

_prepare = E.prepare


def prepare(sym):
    P = _prepare(sym)
    t = load_5m(sym).index.tz_convert("Europe/London")
    lm = (t.hour * 60 + t.minute).to_numpy()
    w1 = (lm >= 480) & (lm < 865)
    w2 = (lm >= 480) & (lm < 720)
    P["wins"] = {"Londres": (w1, (lm >= 480) & (lm <= 835), lm == 860),
                 "Londres corta": (w2, (lm >= 480) & (lm <= 690), lm == 715)}
    return P


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 120)
    E.PAIRS = [(120, 200)]
    E.prepare = prepare
    out = []
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0), ("ES", 1.0, 2.0)):
        E.COST, E.USD = cost, usd
        out.append(E.run(sym).assign(activo=sym))
        print(sym, "listo", flush=True)
    R = pd.concat(out, ignore_index=True)
    R.to_pickle(".lab_cache/ema120_200_london.pkl")
    both = lambda x: f"{((x.dev_usd > 0) & (x.val_usd > 0)).mean():.0%}"
    print(R.groupby(["activo", "ventana", "tf"]).apply(lambda g: pd.Series({"n": len(g), "% ganan ambos": both(g),
          "acierto": round(g.val_win.mean(), 2), "med dev": int(g.dev_usd.median()), "med val": int(g.val_usd.median()),
          "med racha": int(g.val_dd.median())}), include_groups=False).to_string())
    cols = ["activo", "tf", "ventana", "lado", "filtro", "stop", "entrada", "dev_ops", "dev_usd", "dev_pf",
            "val_usd", "val_pf", "val_dd", "val_win", "años_pos", "by_year"]
    C = R[(R.dev_usd > 0) & (R.val_usd > 0)]
    C = C.assign(mn=C[["dev_usd", "val_usd"]].min(axis=1)).sort_values("mn", ascending=False)
    print(f"\n══ Ganan en ambos periodos: {len(C)} ══")
    print(C[cols].head(20).to_string(index=False))


if __name__ == "__main__":
    main()
