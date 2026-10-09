"""Cruce EMA 120 / EMA 200 en NQ / MNQ y oro / MGC (control ES), 5 min, 15 min y 1 h, 2018 - oct 2026.

Mismo motor y mismas variantes que ema_cross_research.py (ventana NY o Globex, ambos lados o solo largos,
filtro EMA 200, stop ninguno / 1,5 / 3 ATR, solo cruces nuevos o también el estado al abrir), con los pares
120/200 y, como referencia, 50/200. Costes: NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC) ·
ES 1 punto en las mismas unidades que NQ (control). Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python ema120_200.py
"""

import pandas as pd

import ema_cross_research as E


def main():
    pd.set_option("display.width", 250)
    E.PAIRS = [(120, 200), (50, 200)]
    out = []
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0), ("ES", 1.0, 2.0)):
        E.COST, E.USD = cost, usd
        r = E.run(sym).assign(activo=sym)
        out.append(r)
        print(sym, "listo", flush=True)
    R = pd.concat(out, ignore_index=True)
    R.to_pickle(".lab_cache/ema120_200.pkl")
    both = lambda x: f"{((x.dev_usd > 0) & (x.val_usd > 0)).mean():.0%}"
    print(R.groupby(["activo", "emas", "tf"]).apply(lambda g: pd.Series({"n": len(g), "% ganan ambos": both(g),
          "acierto": round(g.val_win.mean(), 2), "med dev": int(g.dev_usd.median()), "med val": int(g.val_usd.median())}),
          include_groups=False).to_string())
    cols = ["activo", "tf", "ventana", "emas", "lado", "filtro", "stop", "entrada", "dev_ops", "dev_usd", "dev_pf",
            "val_ops", "val_usd", "val_pf", "val_dd", "val_win", "años_pos"]
    C = R[(R.emas == "120/200") & (R.dev_usd > 0) & (R.val_usd > 0)]
    C = C.assign(mn=C[["dev_usd", "val_usd"]].min(axis=1)).sort_values("mn", ascending=False)
    print(f"\n══ EMA 120/200 que ganan en ambos periodos: {len(C)} ══")
    print(C[cols].head(25).to_string(index=False))


if __name__ == "__main__":
    main()
