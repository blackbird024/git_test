"""Estadística (no estrategia): ¿cuántas veces el NQ rompe el máximo/mínimo de un rango nocturno en la sesión de Londres
y retrocede, y cuántas continúa? Hora de Italia. Velas de 5 min alineadas a la hora de Italia; 2018-2026.

Rangos: (A) vela de 4 h 0:00-4:00, ventana 4:00-15:30; (B) rango de Asia 0:00-9:00, ventana Londres 9:00-15:30.
Por día, la PRIMERA ruptura de la ventana:
  sin_toque           el precio no supera ni el máximo ni el mínimo
  solo_mecha          lo supera con mecha pero ninguna vela de 5 min cierra fuera (barrida)
  ruptura_cierre      una vela de 5 min cierra fuera ("con cuerpo"); después, hasta las 15:30:
      vuelve_dentro       alguna vela de 5 min vuelve a cerrar dentro del rango (falsa ruptura)
        llega_mitad / llega_opuesto   además toca la mitad / el extremo opuesto del rango
      continua            no vuelve a cerrar dentro hasta las 15:30
  extension_50 / extension_100: tras la ruptura, el precio se aleja >= 50 % / 100 % del tamaño del rango desde el
      nivel roto ANTES de volver a cerrar dentro.
"""
import numpy as np
import pandas as pd

from data.loaders import sessions
from run_crt_italia import rome_days
from validation.runner import new_experiment, write_manifest

RANGES = {"A · vela 4h 0:00-4:00 (ventana 4:00-15:30)": (0, 240, 240, 930),
          "B · Asia 0:00-9:00 (ventana Londres 9:00-15:30)": (0, 540, 540, 930)}


def day_stats(m, ra, rb, wa, wb):
    O, H, L, C = m[:, 0], m[:, 1], m[:, 2], m[:, 3]
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
    r = dict(R=R, wick_up=False, wick_dn=False)
    side, ib = 0, None
    for i, (h, l, c) in enumerate(bars):
        if c > hi or c < lo:
            side, ib = (1 if c > hi else -1), i
            break
        r["wick_up"] |= h > hi
        r["wick_dn"] |= l < lo
    touched = any(h > hi or l < lo for h, l, c in bars)
    if side == 0:
        r["tipo"] = "solo_mecha" if touched else "sin_toque"
        return r
    r["tipo"] = "ruptura_cierre"
    r["lado"] = "alcista" if side == 1 else "bajista"
    edge = hi if side == 1 else lo
    ext, back, mid_hit, opp_hit = 0.0, False, False, False
    for h, l, c in bars[ib:]:
        if not back:
            ext = max(ext, side * ((h if side == 1 else l) - edge))
            if lo <= c <= hi:
                back = True
        if back:
            mid_hit |= (l <= mid) if side == 1 else (h >= mid)
            opp_hit |= (l <= lo) if side == 1 else (h >= hi)
    r.update(vuelve_dentro=back, llega_mitad=mid_hit, llega_opuesto=opp_hit,
             extension_50=ext >= 0.5 * R, extension_100=ext >= R, ext_R=ext / R)
    return r


def main():
    S = sessions()
    D = rome_days(S)
    exp = new_experiment("stats_londres_rupturas")
    out = []
    for name, (ra, rb, wa, wb) in RANGES.items():
        rows = []
        for date, m, cm in D:
            r = day_stats(m, ra, rb, wa, wb)
            if r is not None:
                r.update(date=date, rango=name)
                rows.append(r)
        df = pd.DataFrame(rows)
        df.to_csv(exp / f"dias_{name[0]}.csv.gz", index=False)
        out.append(df)
        n = len(df)
        b = df[df.tipo == "ruptura_cierre"].copy()
        for c in ("vuelve_dentro", "llega_mitad", "llega_opuesto", "extension_50", "extension_100"):
            b[c] = b[c].astype(bool)
        print(f"\n=== {name} · {n} días ({df.date.min().date()} a {df.date.max().date()}) ===")
        print((df.tipo.value_counts() / n * 100).round(1).to_string())
        print(f"Rango mediano: {df.R.median():.0f} puntos NQ")
        print(f"Con ruptura con cierre ({len(b)} días):")
        print(f"  vuelve a cerrar dentro: {b.vuelve_dentro.mean()*100:.1f} %  · continúa sin volver: {(~b.vuelve_dentro).mean()*100:.1f} %")
        print(f"  vuelve y toca la mitad: {b.llega_mitad.mean()*100:.1f} %  · llega al extremo opuesto: {b.llega_opuesto.mean()*100:.1f} %")
        print(f"  antes de volver se aleja >= 50 % del rango: {b.extension_50.mean()*100:.1f} %  · >= 100 %: {b.extension_100.mean()*100:.1f} %")
        print(f"  extensión mediana antes de volver: {b.ext_R.median():.2f} × rango")
        print("  por lado:")
        print((b.groupby("lado")[["vuelve_dentro", "llega_opuesto", "extension_50"]].mean() * 100).round(1).to_string())
        y = b.groupby(b.date.dt.year).agg(dias=("vuelve_dentro", "size"), vuelve=("vuelve_dentro", "mean"),
                                          opuesto=("llega_opuesto", "mean"), ext50=("extension_50", "mean"))
        y[["vuelve", "opuesto", "ext50"]] = (y[["vuelve", "opuesto", "ext50"]] * 100).round(1)
        print("  por año:")
        print(y.to_string())
    write_manifest(exp, experimento="estadística de rupturas en Londres", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
