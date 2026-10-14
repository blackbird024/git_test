"""Pregunta del usuario: "de las 3 sesiones, la de Londres parece la menos volátil, tanto en oro como en MNQ".
Medida (hora de Italia, días laborables 2018 → 2026): rango (máximo − mínimo) de cada sesión y movimiento medio por
hora (suma de |cierre − apertura| de cada vela de 1 h / horas). Sesiones: Asia 0:00-9:00, Londres 9:00-14:30,
Nueva York 15:30-22:00 (más el tramo 14:30-15:30 del dato aparte). Se excluyen días con <80 % de minutos en la sesión."""
import numpy as np
import pandas as pd

from data.loaders import nq_1m
from rangos_lib import FILES

SES = {"Asia 0:00-9:00": (0, 9 * 60), "Londres 9:00-14:30": (9 * 60, 14 * 60 + 30),
       "Dato 14:30-15:30": (14 * 60 + 30, 15 * 60 + 30), "Nueva York 15:30-22:00": (15 * 60 + 30, 22 * 60)}


def medir(df, nombre):
    df = df.tz_convert("Europe/Rome")
    df = df[df.index.dayofweek < 5]
    mins = df.index.hour * 60 + df.index.minute
    rows = []
    for s, (a, b) in SES.items():
        x = df[(mins >= a) & (mins < b)]
        g = x.groupby(x.index.date)
        d = pd.DataFrame(dict(h=g.high.max(), l=g.low.min(), c=g.close.last(), o=g.open.first(), n=g.size()))
        d = d[d.n >= 0.8 * (b - a)]
        rng = d.h - d.l
        hrs = (b - a) / 60
        h1 = x.resample("60min").agg({"open": "first", "close": "last"}).dropna()
        hm = h1.index.hour * 60 + h1.index.minute
        mv = (h1.close - h1.open).abs()
        rows.append(dict(activo=nombre, sesion=s, dias=len(d), rango_mediano=rng.median(),
                         rango_por_hora=(rng / hrs).median(), mov_medio_vela_1h=mv[(hm >= a - 59) & (hm < b)].median(),
                         rango_rel_pct=100 * (rng / d.c).median()))
    return rows


def main():
    nq = nq_1m()
    gc = pd.read_pickle(FILES["MGC"])
    r = pd.DataFrame(medir(nq, "MNQ (pts)") + medir(gc, "Oro (pts)"))
    pd.set_option("display.width", 200)
    print(r.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
