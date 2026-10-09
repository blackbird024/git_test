"""EMA 120 (exponencial) cruzando la MA 200 (media SIMPLE) en NQ / MNQ y oro / MGC (control ES), 2018 - oct 2026.

Mismo motor y variantes que ema_cross_research.py / ema120_200.py; solo cambia la media lenta: SMA 200 en vez
de EMA 200. Como referencia se repite la EMA 120 / EMA 200. Costes: NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos
(10 $/punto por MGC) · ES 1 punto (control). Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python ema120_ma200.py
"""

import numpy as np
import pandas as pd

import ema_cross_research as E
from crt_backtest import load_5m

SLOW = "sma"


def prepare(sym):
    df = load_5m(sym)
    t = df.index
    hm = (t.hour * 60 + t.minute).to_numpy()
    gday = ((t + pd.Timedelta(hours=6)).normalize()).asi8 // 86_400_000_000_000
    out = {}
    for tfn, tf in E.TFS.items():
        b = E.tf_frame(df, tf)
        cl = b.close
        fast = cl.ewm(span=120, adjust=False).mean()
        slow = cl.rolling(200).mean() if SLOW == "sma" else cl.ewm(span=200, adjust=False).mean()
        b["s120_200"] = np.sign(fast - slow)
        b["tr"] = np.sign(cl - b.e200)
        out[tfn] = E.align(df, b, ["atr", "tr", "s120_200"])
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    ny = (hm >= 570) & (hm < 960)
    gx = (hm >= 1080) | (hm < 1020)
    wins = {"NY": (ny, (hm >= 570) & (hm <= 930), ny & (hm == 955)), "Globex": (gx, (hm >= 1080) | (hm < 960), hm == 1015)}
    return dict(o=o, h=h, l=l, c=c, gday=gday, wins=wins, tf=out, year=t.year.to_numpy())


def main():
    global SLOW
    pd.set_option("display.width", 250)
    E.PAIRS = [(120, 200)]
    E.prepare = prepare
    out = []
    for slow in ("sma", "ema"):
        SLOW = slow
        for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0), ("ES", 1.0, 2.0)):
            E.COST, E.USD = cost, usd
            out.append(E.run(sym).assign(activo=sym, emas="EMA120/MA200" if slow == "sma" else "EMA120/EMA200"))
            print(slow, sym, "listo", flush=True)
    R = pd.concat(out, ignore_index=True)
    R.to_pickle(".lab_cache/ema120_ma200.pkl")
    both = lambda x: f"{((x.dev_usd > 0) & (x.val_usd > 0)).mean():.0%}"
    print(R.groupby(["activo", "emas", "tf"]).apply(lambda g: pd.Series({"n": len(g), "% ganan ambos": both(g),
          "acierto": round(g.val_win.mean(), 2), "med dev": int(g.dev_usd.median()), "med val": int(g.val_usd.median()),
          "med racha": int(g.val_dd.median())}), include_groups=False).to_string())
    cols = ["activo", "tf", "ventana", "emas", "lado", "filtro", "stop", "entrada", "dev_ops", "dev_usd", "dev_pf",
            "val_ops", "val_usd", "val_pf", "val_dd", "val_win", "años_pos", "by_year"]
    pd.set_option("display.max_colwidth", 120)
    C = R[(R.emas == "EMA120/MA200") & (R.lado == "ambos") & (R.entrada == "cruce") & (R.filtro == "-")]
    print("\n══ EMA120/MA200, compras y ventas en cada cruce ══")
    print(C[cols].to_string(index=False))


if __name__ == "__main__":
    main()
