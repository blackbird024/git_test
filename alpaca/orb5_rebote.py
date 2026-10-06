"""Rango de la primera vela de 5 min de NY en NQ: ¿cuántas veces el precio toca un lado y rebota?

Rango: máximo (H) y mínimo (L) de 9:30-9:35 NY; medio M; tamaño R = H - L.
Se sigue el precio con velas de 1 minuto desde las 9:35 hasta las 16:00 NY (NQ 2018 - oct 2026, Databento).

Para cada toque de un lado se mira qué pasa ANTES:
  rebote   el precio vuelve hacia dentro una distancia D desde el nivel
  ruptura  el precio sigue hacia fuera la MISMA distancia D más allá del nivel
Si fuera azar, cada uno saldría el 50 %. D se prueba como 0,5·R (volver al medio), 1·R (cruzar el rango) y en
puntos fijos (10, 20, 40). Si la misma vela de 1 min toca ambos, se cuenta como "dudosa" (no se sabe el orden).
Un toque nuevo del mismo lado solo cuenta si antes el precio se alejó al menos 0,25·R del nivel hacia dentro.

Además se prueba operarlo: orden límite en el nivel contra la ruptura, stop D más allá, objetivo D hacia dentro
(1:1), coste 1 punto; y la versión a favor (comprar la ruptura). Resultados por 1 MNQ.

Uso:
    python orb5_rebote.py
"""

import pickle

import numpy as np
import pandas as pd

from vwap_globex_8y import load

USD = 2.0
COST = 1.0


def days_1m():
    d = load()[["open", "high", "low", "close"]].sort_index()
    d.index = d.index.tz_convert("America/New_York")
    hm = d.index.hour * 60 + d.index.minute
    d = d[(hm >= 570) & (hm < 960)]
    out = []
    for day, g in d.groupby(d.index.date):
        if len(g) != 390:
            continue
        out.append((pd.Timestamp(day), g.high.to_numpy(), g.low.to_numpy(), g.close.to_numpy()))
    return out


def race(h, l, start, lvl, side, dist):
    """Desde la vela start, tras tocar lvl: +1 rebote (vuelve dist hacia dentro), -1 ruptura (sigue dist fuera),
    0 dudosa (misma vela), None ninguna antes del cierre. side=+1 lado de arriba (H), -1 lado de abajo (L)."""
    inside, outside = lvl - side * dist, lvl + side * dist
    for j in range(start, len(h)):
        a = (l[j] <= inside) if side == 1 else (h[j] >= inside)
        b = (h[j] >= outside) if side == 1 else (l[j] <= outside)
        if j == start:
            a = False                              # en la vela del toque no se sabe si el retroceso vino antes
        if a and b:
            return 0, j
        if a:
            return 1, j
        if b:
            return -1, j
    return None, len(h)


def touches(h, l, H, L, R):
    """Lista de (vela, lado) de cada toque, separando toques del mismo lado por un alejamiento de 0,25·R."""
    out = []
    armed = {1: True, -1: True}
    for j in range(5, len(h)):
        if armed[1] and h[j] >= H:
            out.append((j, 1))
            armed[1] = False
        if armed[-1] and l[j] <= L:
            out.append((j, -1))
            armed[-1] = False
        if not armed[1] and h[j] < H - 0.25 * R:
            armed[1] = True
        if not armed[-1] and l[j] > L + 0.25 * R:
            armed[-1] = True
    return out


def main():
    pd.set_option("display.width", 220)
    days = days_1m()
    rows, trades = [], []
    dists = {"0,5·R (al medio)": ("R", 0.5), "1·R": ("R", 1.0), "10 pts": ("p", 10), "20 pts": ("p", 20), "40 pts": ("p", 40)}
    for d, h, l, c in days:
        H, L = h[:5].max(), l[:5].min()
        R = H - L
        if R <= 0:
            continue
        tl = touches(h, l, H, L, R)
        sides = {s for _, s in tl}
        rows.append(dict(d=d, R=R, toca_H=1 in sides, toca_L=-1 in sides, n_toques=len(tl)))
        for k, (j, s) in enumerate(tl):
            first_side = k == next(i for i, (_, ss) in enumerate(tl) if ss == s)
            t = dict(d=d, R=R, lado="arriba" if s == 1 else "abajo", primero=first_side, n=k + 1,
                     hora=f"{(570 + j) // 60}:{(570 + j) % 60:02d}")
            for name, (kind, v) in dists.items():
                dist = v * R if kind == "R" else v
                res, _ = race(h, l, j, H if s == 1 else L, s, dist)
                t[name] = res
                # operar el rebote a 1:1 (límite en el nivel) y la ruptura a 1:1
                if res is None:
                    lvl = H if s == 1 else L
                    pnl = -s * (c[-1] - lvl)
                elif res == 0:
                    pnl = -dist                     # dudosa: se cuenta como pérdida (conservador)
                else:
                    pnl = res * dist
                t[f"pnl_{name}"] = pnl
            trades.append(t)
    D = pd.DataFrame(rows)
    T = pd.DataFrame(trades)
    T["per"] = np.where(T.d.dt.year < 2023, "2018-22", "2023-26")
    print(f"NQ, {len(D)} sesiones ({D.d.min():%Y-%m-%d} a {D.d.max():%Y-%m-%d}). Rango de la 1.ª vela de 5 min: "
          f"mediana {D.R.median():.0f} pts (2026: {D[D.d.dt.year == 2026].R.median():.0f} pts)")
    print(f"Días que tocan el máximo: {D.toca_H.mean():.0%} · el mínimo: {D.toca_L.mean():.0%} · "
          f"los dos: {(D.toca_H & D.toca_L).mean():.0%} · ninguno: {(~D.toca_H & ~D.toca_L).mean():.0%}")
    print(f"Toques por día (separados por un alejamiento de 0,25·R): media {D.n_toques.mean():.1f}, mediana {D.n_toques.median():.0f}")

    def tabla(sub, titulo):
        print(f"\n── {titulo} ({len(sub)} toques) ──")
        out = []
        for name in dists:
            v = sub[name]
            n = v.notna().sum()
            reb, rup, dud = (v == 1).sum(), (v == -1).sum(), (v == 0).sum()
            p = sub[f"pnl_{name}"] - COST
            pr = -sub[f"pnl_{name}"] - COST         # la operación contraria: a favor de la ruptura
            out.append({"distancia": name, "rebota": f"{reb / n:.0%}", "rompe": f"{rup / n:.0%}", "dudosa": f"{dud / n:.0%}",
                        "sin resolver": f"{1 - n / len(v):.0%}",
                        "fade 1:1 $/año": round(p.sum() * USD / 8.75), "ruptura 1:1 $/año": round(pr.sum() * USD / 8.75)})
        print(pd.DataFrame(out).to_string(index=False))

    tabla(T, "Todos los toques")
    tabla(T[T.primero], "Solo el PRIMER toque de cada lado")
    tabla(T[T.n == 1], "Solo el primer toque del día (el primer lado que se toca)")
    tabla(T[(T.n > 1) & ~T.primero], "Toques repetidos (2.º, 3.º… del mismo lado)")
    print("\nRebote al medio (0,5·R) del PRIMER toque, por periodo, lado y hora:")
    F = T[T.primero].copy()
    F["franja"] = pd.cut(F.hora.str.replace(":", "").astype(int), [0, 959, 1059, 1259, 1600],
                         labels=["9:35-10:00", "10:00-11:00", "11:00-13:00", "13:00-16:00"])
    name = "0,5·R (al medio)"
    for col in ("per", "lado", "franja"):
        g = F.groupby(col, observed=True)[name]
        print(pd.DataFrame({"toques": g.size(), "rebota": g.apply(lambda v: f"{(v == 1).sum() / v.notna().sum():.0%}"),
                            "rompe": g.apply(lambda v: f"{(v == -1).sum() / v.notna().sum():.0%}")}).to_string(), "\n")
    T.to_pickle(".lab_cache/orb5_rebote.pkl")


if __name__ == "__main__":
    main()
