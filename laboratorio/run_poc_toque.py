"""Pregunta: "si el precio llega al POC, ¿debo estar atento a un cambio de tendencia?". MNQ (NQ 1 min) 2018-2026.
POC = precio con más volumen del perfil (volumen de cada vela de 1 min asignado a su precio típico (H+L+C)/3,
redondeado a 1 punto). Perfiles (fijados antes de ver resultados):
  POC_AYER   sesión regular del día anterior (9:30-16:00 NY)
  POC_NOCHE  sesión nocturna del mismo día (18:00 del día anterior → 9:29 NY)
Evento: durante la sesión regular (9:30-15:00 NY), el PRIMER toque del POC; el precio viene del lado en que abrió la
sesión (si abrió encima, viene de arriba). Se excluye si la sesión abre a menos de X del POC.
Carrera tras el toque, desde la vela SIGUIENTE al toque (hasta 16:00): ¿vuelve X puntos hacia el lado del que vino (REBOTA) o atraviesa X puntos al otro
lado (ATRAVIESA)? X ∈ {10, 20, 40} pts. Además: operación de rebote (a mercado en el toque, stop X, objetivo X, 1:1)
en bruto (puntos)."""
import numpy as np
import pandas as pd

from data.loaders import nq_1m
from validation.runner import new_experiment, write_manifest


def poc(x):
    if len(x) < 30:
        return np.nan
    p = ((x.high + x.low + x.close) / 3).round()
    return x.volume.groupby(p).sum().idxmax()


def main():
    df = nq_1m()
    df = df[df.index.dayofweek < 5]
    t = df.index
    mins = t.hour * 60 + t.minute
    rth = df[(mins >= 570) & (mins < 960)]
    noche_all = df[(mins >= 1080) | (mins < 570)]
    noches = dict(tuple(noche_all.groupby((noche_all.index + pd.Timedelta(hours=6)).date)))
    rows = []
    prev_poc = np.nan
    for d, day in rth.groupby(rth.index.date):
        if len(day) < 300:
            prev_poc = np.nan
            continue
        night = noches.get(d, df.iloc[:0])
        same_ins = day.instrument_id.iloc[0]
        pocs = {"POC_AYER": prev_poc,
                "POC_NOCHE": poc(night[night.instrument_id == same_ins]) if len(night) else np.nan}
        H, L, C = day.high.to_numpy(), day.low.to_numpy(), day.close.to_numpy()
        hm = (day.index.hour * 60 + day.index.minute).to_numpy()
        o0 = day.open.iloc[0]
        for nombre, P in pocs.items():
            if np.isnan(P) or day.instrument_id.nunique() > 1:
                continue
            desde = 1 if o0 > P else -1                     # viene de arriba (1) o de abajo (-1)
            hit = np.nonzero((L <= P) & (H >= P) & (hm < 900))[0]
            if not len(hit):
                rows.append(dict(fecha=d, poc=nombre, toca=False))
                continue
            k = hit[0]
            r = dict(fecha=d, poc=nombre, toca=True, dist_apertura=abs(o0 - P), hora=hm[k] / 60)
            for X in (10, 20, 40):
                if abs(o0 - P) < X:
                    r[f"X{X}"] = "cerca"
                    continue
                reb, atr_ = P + desde * X, P - desde * X
                res = "nada"
                # en la vela del toque solo se mira si ya atraviesa (su máximo/mínimo del lado de origen es de ANTES)
                if (L[k] <= atr_) if desde == 1 else (H[k] >= atr_):
                    r[f"X{X}"] = "ambos"
                    continue
                for j in range(k + 1, len(H)):
                    rh = (H[j] >= reb) if desde == 1 else (L[j] <= reb)
                    ah = (L[j] <= atr_) if desde == 1 else (H[j] >= atr_)
                    if ah:                                   # pesimista: primero el lado de pérdida
                        res = "atraviesa"
                        break
                    if rh:
                        res = "rebota"
                        break
                r[f"X{X}"] = res
            rows.append(r)
        prev_poc = poc(day)
    t = pd.DataFrame(rows)
    exp = new_experiment("poc_toque")
    t.to_csv(exp / "eventos.csv.gz", index=False)
    out = []
    for nombre, g in t.groupby("poc"):
        tg = g[g.toca == True]
        for X in (10, 20, 40):
            v = tg[f"X{X}"]
            v = v[v != "cerca"]
            yr = pd.to_datetime(tg.loc[v.index, "fecha"]).dt.year
            reb = (v == "rebota")
            out.append(dict(poc=nombre, X=X, dias_toca=f"{g.toca.mean():.0%}", eventos=len(v),
                            rebota=reb.mean(), atraviesa=(v == "atraviesa").mean(),
                            rebota_18_21=reb[yr <= 2021].mean(), rebota_22_24=reb[(yr >= 2022) & (yr <= 2024)].mean(),
                            rebota_25_26=reb[yr >= 2025].mean()))
    r = pd.DataFrame(out)
    r.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="primer toque del POC en la sesión regular: ¿rebota o atraviesa?", reglas=__doc__)
    pd.set_option("display.width", 220)
    print(r.round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
