"""ORB (ruptura del rango de apertura) en NQ / MNQ: búsqueda amplia con validación fuera de muestra.

Datos: velas de 5 min de NQ (Databento) 2018 - oct 2026, sesión regular de NY. Se ELIGE con 2018-2022 y se
JUZGA con 2023-2026; se mira qué fracción de la rejilla gana en ambos periodos y se repite en ES como control.
Coste 1 punto por operación; resultados por 1 MNQ (2 $/punto). Todo cierra a las 16:00 NY.

Familias:
  clasico   rango de los primeros N minutos; entrada con orden STOP en el máximo/mínimo; stop en el otro lado
            o en el medio del rango; objetivo k·R o cierre de la sesión; entradas hasta cierta hora
  vela5     ORB de 5 min de Zarattini-Aziz-Barbon (2023): dirección de la primera vela de 5 min, entrada a la
            apertura de la segunda, stop a una fracción del ATR(14) diario, salida al cierre (u objetivo k·R)
  filtro    clasico solo los días con rango de apertura pequeño frente al ATR diario

Uso:
    python orb_research.py
"""

import itertools

import numpy as np
import pandas as pd

from nq_intraday_research import COST, build_days, evaluate


def clasico(days, n=6, stop="lado", tgt=None, last_k=18, maxor=None, only=0):
    out = []
    for x in days:
        B = x["rth"]
        hi, lo = B[:n, 1].max(), B[:n, 2].min()
        if maxor and (hi - lo) > maxor * x["atr"]:
            continue
        for k in range(n, min(last_k, 77)):
            up, dn = B[k, 1] > hi, B[k, 2] < lo
            if not (up or dn):
                continue
            side = 1 if up else -1                 # si la vela toca los dos lados cuenta el máximo (conservador da igual: raro)
            if only and side != only:
                break
            e = hi if side == 1 else lo
            if B[k, 0] * side > e * side:          # hueco más allá del nivel: se entra a la apertura
                e = B[k, 0]
            sl = (lo if side == 1 else hi) if stop == "lado" else (hi + lo) / 2
            risk = abs(e - sl)
            T = e + side * tgt * risk if tgt else None
            px = B[-1, 3]
            for q in range(k + 1, 78):
                if (side == 1 and B[q, 2] <= sl) or (side == -1 and B[q, 1] >= sl):
                    px = sl if (side == 1 and B[q, 0] > sl) or (side == -1 and B[q, 0] < sl) else B[q, 0]
                    break
                if T is not None and ((side == 1 and B[q, 1] >= T) or (side == -1 and B[q, 2] <= T)):
                    px = T
                    break
            out.append((x["d"], side * (px - e) - COST))
            break
    return out


def vela5(days, frac=0.1, tgt=None, only=0):
    out = []
    for x in days:
        B = x["rth"]
        side = int(np.sign(B[0, 3] - B[0, 0]))
        if side == 0 or (only and side != only):
            continue
        e = B[1, 0]
        risk = frac * x["atr"]
        sl = e - side * risk
        T = e + side * tgt * risk if tgt else None
        px = B[-1, 3]
        for q in range(1, 78):
            if (side == 1 and B[q, 2] <= sl) or (side == -1 and B[q, 1] >= sl):
                px = sl if q > 1 or (side * (B[q, 0] - sl) > 0) else B[q, 0]
                break
            if T is not None and ((side == 1 and B[q, 1] >= T) or (side == -1 and B[q, 2] <= T)):
                px = T
                break
        out.append((x["d"], side * (px - e) - COST))
    return out


GRID = {
    "clasico": [dict(f=clasico, n=n, stop=s, tgt=t, last_k=lk, only=o) for n, s, t, lk, o in
                itertools.product((1, 3, 6, 12), ("lado", "medio"), (None, 1, 2, 3), (18, 30, 72), (0, 1))],
    "vela5": [dict(f=vela5, frac=fr, tgt=t, only=o) for fr, t, o in
              itertools.product((0.05, 0.1, 0.15, 0.25), (None, 2, 5, 10), (0, 1))],
    "filtro": [dict(f=clasico, n=n, stop=s, tgt=t, maxor=m) for n, s, t, m in
               itertools.product((3, 6, 12), ("lado", "medio"), (None, 2), (0.15, 0.25, 0.35))],
}


def run(sym):
    days = build_days(sym)
    rows = []
    for fam, grid in GRID.items():
        for p in grid:
            q = {k: v for k, v in p.items() if k != "f"}
            r = evaluate(p["f"](days, **q))
            if r is None:
                continue
            rows.append(dict(fam=fam, params=", ".join(f"{k}={v}" for k, v in q.items()),
                             dev_ops=round(r["dev"]["ops"] / 5), dev_usd=round(r["dev"]["usd_y"]), dev_pf=round(r["dev"]["pf"], 2),
                             val_ops=round(r["val"]["ops"] / 3.75), val_usd=round(r["val"]["usd_y"]), val_pf=round(r["val"]["pf"], 2),
                             val_dd=round(r["val"]["dd"]), val_win=round(r["val"]["win"], 2), val_sh=round(r["val"]["sharpe"], 2),
                             años=r["years_pos"], by_year=r["by_year"]))
    return pd.DataFrame(rows)


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 70)
    for sym in ("NQ", "ES"):
        r = run(sym)
        r.to_pickle(f".lab_cache/orb_{sym}.pkl")
        print(f"\n══════════ {sym}: $/año por 1 MNQ · dev 2018-2022 · val 2023-2026 ══════════")
        print(r.groupby("fam").apply(lambda g: pd.Series({
            "variantes": len(g), "% gana ambos": f"{((g.dev_usd > 0) & (g.val_usd > 0)).mean():.0%}",
            "mediana dev": int(g.dev_usd.median()), "mediana val": int(g.val_usd.median())}), include_groups=False).to_string())
        cols = [c for c in r.columns if c != "by_year"]
        print("\nMejor de cada familia ELEGIDA con 2018-2022:")
        print(r.loc[r.groupby("fam").dev_usd.idxmax(), cols].to_string(index=False))
        print("\nLas 12 con el peor periodo más alto:")
        r = r.assign(minimo=r[["dev_usd", "val_usd"]].min(axis=1)).sort_values("minimo", ascending=False)
        print(r.head(12)[cols].to_string(index=False))


if __name__ == "__main__":
    main()
