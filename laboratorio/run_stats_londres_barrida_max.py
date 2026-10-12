"""Estadística (no estrategia), idea del usuario: el precio rompe el rango nocturno hacia abajo (5 min, con cierre), hace
pullback, una vela de 5 min rompe el ÚLTIMO MÁXIMO de 5 min, ¿y sigue hacia abajo? (largos: espejo). Hora de Italia.

Mismos rangos/ventanas que run_stats_londres.py. Velas de 5 min de la ventana; pivotes 2/2 (máximo mayor que las 2
velas anteriores y las 2 siguientes), confirmados 2 velas después. "Último máximo" = el pivote alto más reciente con
índice >= vela de ruptura − 2, ya confirmado. Evento = la primera vela posterior cuyo máximo lo supera:
  "barrida"  solo con mecha (cierra por debajo del máximo)      "rompe con cuerpo"  cierra por encima
Desde la vela siguiente al evento, ¿qué llega antes?
  continúa a nuevo mínimo (por debajo del mínimo hecho desde la ruptura) / a nivel roto − 0,5 × rango
  falla: el precio sube a la mitad del rango (misma vela → fallo). "nada" si ninguna hasta las 15:30.
Añadido (pregunta "o entra en un FVG"): FVG bajista de 5 min (máximo de la vela i+1 < mínimo de la vela i−1) formado
desde la vela de ruptura − 1; evento = la primera vela que entra en el FVG más reciente ya formado (su máximo llega al
borde inferior del hueco). "respeta" si esa vela cierra por debajo del borde superior del FVG; "atraviesa" si cierra
por encima. Misma carrera desde la vela siguiente.
"""
import numpy as np
import pandas as pd

from data.loaders import sessions
from run_crt_italia import rome_days
from validation.runner import new_experiment, write_manifest

RANGES = {"A · vela 4h 0:00-4:00 (ventana 4:00-15:30)": (0, 240, 240, 930),
          "B · Asia 0:00-9:00 (ventana Londres 9:00-15:30)": (0, 540, 540, 930)}


def race(h, l, start, win, lose, side):
    for i in range(start, len(h)):
        if (side == 1 and l[i] <= lose) or (side == -1 and h[i] >= lose):
            return "falla"
        if (side == 1 and h[i] >= win) or (side == -1 and l[i] <= win):
            return "continua"
    return "nada"


def day(m, ra, rb, wa, wb, mode="maximo"):
    H, L, C = m[:, 1], m[:, 2], m[:, 3]
    if np.isnan(H[ra:rb]).sum() > (rb - ra) / 2 or np.isnan(C[wa:wb]).sum() > (wb - wa) / 2:
        return None
    hi, lo = np.nanmax(H[ra:rb]), np.nanmin(L[ra:rb])
    R = hi - lo
    if R <= 0:
        return None
    mid = (hi + lo) / 2
    b = []
    for k in range(wa, wb, 5):
        ok = ~np.isnan(C[k:k + 5])
        if ok.any():
            b.append((np.nanmax(H[k:k + 5]), np.nanmin(L[k:k + 5]), C[k:k + 5][ok][-1]))
    if len(b) < 10:
        return None
    h, l, c = (np.array(x) for x in zip(*b))
    ib = next((i for i in range(len(c)) if c[i] > hi or c[i] < lo), None)
    if ib is None:
        return None
    side = 1 if c[ib] > hi else -1
    edge = hi if side == 1 else lo
    # trabajamos en "espacio corto": para largos se invierte el signo (el "último máximo" de un corto = último mínimo de un largo)
    x_h, x_l = (h, l) if side == -1 else (-l, -h)
    x_c = c if side == -1 else -c
    piv = [i for i in range(max(2, ib - 2), len(c) - 2)
           if x_h[i] > max(x_h[i - 2], x_h[i - 1]) and x_h[i] > max(x_h[i + 1], x_h[i + 2])]
    ext = x_l[ib]
    xmid = mid if side == -1 else -mid
    xedge = edge if side == -1 else -edge
    if mode == "fvg":
        fvg = None
        for t in range(ib + 1, len(c)):
            if fvg is not None and x_h[t] >= fvg[0]:
                kind = "FVG respeta" if x_c[t] < fvg[1] else "FVG atraviesa"
                return dict(evento=kind, lado=side, minutos=(t - ib) * 5,
                            nuevo_min=race(x_h, x_l, t + 1, ext, xmid, -1),
                            menos_05R=race(x_h, x_l, t + 1, xedge - 0.5 * R, xmid, -1),
                            ya_en_mitad=x_h[t] >= xmid)
            ext = min(ext, x_l[t])
            i = t - 1                                   # FVG con velas t-2, t-1, t (completo al cierre de t)
            if i - 1 >= ib - 1 and x_h[t] < x_l[i - 1]:
                fvg = (x_h[t], x_l[i - 1])
        return dict(evento="no entra en un FVG", lado=side)
    last = None
    for t in range(ib + 1, len(c)):
        conf = [p for p in piv if p + 2 <= t - 1]
        if conf:
            last = conf[-1]
        if last is not None and x_h[t] > x_h[last]:
            kind = "rompe con cuerpo" if x_c[t] > x_h[last] else "barrida"
            r = dict(evento=kind, lado=side, minutos=(t - ib) * 5,
                     nuevo_min=race(x_h, x_l, t + 1, ext, xmid, -1),
                     menos_05R=race(x_h, x_l, t + 1, xedge - 0.5 * R, xmid, -1),
                     ya_en_mitad=x_h[t] >= xmid)
            return r
        ext = min(ext, x_l[t])
    return dict(evento="no rompe el último máximo", lado=side)


def main():
    S = sessions()
    D = rome_days(S)
    exp = new_experiment("stats_londres_barrida_ultimo_max")
    for (name, (ra, rb, wa, wb)), mode in [(kv, md) for kv in RANGES.items() for md in ("maximo", "fvg")]:
        rows = []
        for date, m, cm in D:
            r = day(m, ra, rb, wa, wb, mode)
            if r is not None:
                r["date"] = date
                rows.append(r)
        df = pd.DataFrame(rows)
        df.to_csv(exp / f"dias_{name[0]}_{mode}.csv.gz", index=False)
        print(f"\n=== {name} · {mode} · {len(df)} días con ruptura con cierre ===")
        print((df.evento.value_counts(normalize=True) * 100).round(1).to_string())
        for ev in ("barrida", "rompe con cuerpo", "FVG respeta", "FVG atraviesa"):
            g = df[(df.evento == ev) & (~df.ya_en_mitad.astype(bool))]
            if not len(g):
                continue
            a = g.nuevo_min.value_counts(normalize=True) * 100
            bb = g.menos_05R.value_counts(normalize=True) * 100
            print(f"  {ev} ({len(g)} días, sin contar los que ya llegaron a la mitad del rango en esa vela; "
                  f"minutos medianos tras la ruptura {g.minutos.median():.0f}):")
            print(f"     → nuevo mínimo antes de la mitad: continúa {a.get('continua', 0):.1f} % · falla {a.get('falla', 0):.1f} % · nada {a.get('nada', 0):.1f} %")
            print(f"     → nivel roto − 0,5 R antes de la mitad: continúa {bb.get('continua', 0):.1f} % · falla {bb.get('falla', 0):.1f} % · nada {bb.get('nada', 0):.1f} %")
            y = g.groupby(g.date.dt.year).nuevo_min.apply(lambda s: round((s == "continua").mean() * 100, 1))
            print("     % nuevo mínimo por año:", y.to_dict())
    write_manifest(exp, experimento="ruptura, pullback que rompe el último máximo de 5 min, ¿continúa?", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
