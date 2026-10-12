"""Estadística (no estrategia): tras la primera ruptura con cierre de 5 min del rango nocturno, ¿el precio hace pullback
al nivel roto y continúa? Mismos rangos y ventanas que run_stats_londres.py (hora de Italia, NQ 2018-2026).

Tras la vela de ruptura (largos; cortos espejo), hasta las 15:30:
  sin_pullback   el precio no vuelve a tocar el nivel roto (máximo del rango)
  pullback       alguna vela de 5 min toca el nivel roto (mínimo <= máximo del rango)
      cierra_dentro   en el pullback alguna vela cierra dentro del rango (antes de la carrera de abajo)
  Carrera tras el primer toque del nivel: ¿qué llega antes?
      "continúa (nuevo extremo)"  supera el máximo hecho entre la ruptura y el pullback
      "continúa +0,5 R"           llega a nivel roto + 0,5 × tamaño del rango
      "falla"                      llega a la mitad del rango
  Si las dos cosas pasan en la misma vela de 5 min, cuenta como fallo (conservador). Si ninguna, "nada".
"""
import numpy as np
import pandas as pd

from data.loaders import sessions
from run_crt_italia import rome_days
from validation.runner import new_experiment, write_manifest

RANGES = {"A · vela 4h 0:00-4:00 (ventana 4:00-15:30)": (0, 240, 240, 930),
          "B · Asia 0:00-9:00 (ventana Londres 9:00-15:30)": (0, 540, 540, 930)}


def race(bars, start, win, lose, side):
    for h, l, c in bars[start:]:
        w = (h >= win) if side == 1 else (l <= win)
        f = (l <= lose) if side == 1 else (h >= lose)
        if f:
            return "falla"
        if w:
            return "continua"
    return "nada"


def day(m, ra, rb, wa, wb):
    H, L, C = m[:, 1], m[:, 2], m[:, 3]
    if np.isnan(H[ra:rb]).sum() > (rb - ra) / 2 or np.isnan(C[wa:wb]).sum() > (wb - wa) / 2:
        return None
    hi, lo = np.nanmax(H[ra:rb]), np.nanmin(L[ra:rb])
    R = hi - lo
    if R <= 0:
        return None
    mid = (hi + lo) / 2
    bars = []
    for k in range(wa, wb, 5):
        ok = ~np.isnan(C[k:k + 5])
        if ok.any():
            bars.append((np.nanmax(H[k:k + 5]), np.nanmin(L[k:k + 5]), C[k:k + 5][ok][-1]))
    ib, side = None, 0
    for i, (h, l, c) in enumerate(bars):
        if c > hi or c < lo:
            ib, side = i, (1 if c > hi else -1)
            break
    if ib is None:
        return None
    edge = hi if side == 1 else lo
    ext = bars[ib][0] if side == 1 else bars[ib][1]
    ip = None
    for i in range(ib + 1, len(bars)):
        h, l, c = bars[i]
        if (side == 1 and l <= edge) or (side == -1 and h >= edge):
            ip = i
            break
        ext = max(ext, h) if side == 1 else min(ext, l)
    r = dict(lado=side, ext_antes_R=side * (ext - edge) / R)
    if ip is None:
        r["tipo"] = "sin_pullback"
        return r
    r["tipo"] = "pullback"
    r["min_pullback"] = int((ip - ib) * 5)
    r["cierra_dentro"] = lo <= bars[ip][2] <= hi
    r["nuevo_extremo"] = race(bars, ip, ext + side * 0.25, mid, side) if True else None
    r["mas_05R"] = race(bars, ip, edge + side * 0.5 * R, mid, side)
    r["mas_1R"] = race(bars, ip, edge + side * R, mid, side)
    return r


def main():
    S = sessions()
    D = rome_days(S)
    exp = new_experiment("stats_londres_pullback")
    for name, (ra, rb, wa, wb) in RANGES.items():
        rows = []
        for date, m, cm in D:
            r = day(m, ra, rb, wa, wb)
            if r is not None:
                r.update(date=date)
                rows.append(r)
        df = pd.DataFrame(rows)
        df.to_csv(exp / f"dias_{name[0]}.csv.gz", index=False)
        n = len(df)
        p = df[df.tipo == "pullback"]
        print(f"\n=== {name} · {n} días con ruptura con cierre ===")
        print(f"sin pullback al nivel roto: {(df.tipo == 'sin_pullback').mean()*100:.1f} %  · con pullback: {len(p)/n*100:.1f} %")
        print(f"  minutos medianos hasta el pullback: {p.min_pullback.median():.0f}; la vela del pullback cierra dentro: {p.cierra_dentro.astype(bool).mean()*100:.1f} %")
        for col, lab in (("nuevo_extremo", "nuevo extremo"), ("mas_05R", "nivel + 0,5 R"), ("mas_1R", "nivel + 1 R")):
            v = p[col].value_counts(normalize=True) * 100
            print(f"  tras el pullback, antes de la mitad del rango llega a {lab:13s}: "
                  f"continúa {v.get('continua', 0):.1f} % · falla {v.get('falla', 0):.1f} % · nada {v.get('nada', 0):.1f} %")
        pc = p[~p.cierra_dentro.astype(bool)]
        v = pc["nuevo_extremo"].value_counts(normalize=True) * 100
        print(f"  solo pullbacks SIN cierre dentro ({len(pc)} días): nuevo extremo {v.get('continua', 0):.1f} % · falla {v.get('falla', 0):.1f} %")
        y = p.groupby(p.date.dt.year)["nuevo_extremo"].apply(lambda s: (s == "continua").mean() * 100).round(1)
        print("  % continúa a nuevo extremo por año:", y.to_dict())
    write_manifest(exp, experimento="estadística pullback y continuación en Londres", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
