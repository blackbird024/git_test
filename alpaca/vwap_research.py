"""Estrategias intradía con VWAP en NQ / MNQ: búsqueda amplia con validación fuera de muestra.

Datos: velas de 1 minuto con volumen (Databento, NQ y ES continuos), oct 2024 - oct 2026.
Método: cada familia tiene una rejilla de parámetros. Se ELIGE la variante con el primer año (desarrollo,
oct 2024 - sep 2025) y se JUZGA con el segundo (validación). También se mira qué fracción de la rejilla gana
en cada mitad: si solo gana una variante suelta, es suerte. Y se repite en ES como control.
Coste: 1 punto por operación ida y vuelta. Resultados por 1 MNQ (2 $/punto). Todo cierra el mismo día.

Familias:
  rev      reversión: precio a k desviaciones de la VWAP → contra él, objetivo la VWAP, stop s desviaciones más allá
  lado     a la hora T, el lado de la VWAP decide la dirección; se mantiene hasta el cierre (o hasta perder la VWAP)
  pull     día con tendencia (por encima de la VWAP y VWAP subiendo a la hora T) → compra en el primer retroceso a la VWAP
  cruce    primer cruce de la VWAP tras la hora T con vela de 5 min; stop al volver a cruzar; cierre a las 16:00
  pdr_vw   ruptura del rango de ayer (la de RupturaRangoAyer.pine) solo si la VWAP del día va a favor

Uso:
    python vwap_research.py
"""

import itertools
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).with_name(".lab_cache")
COST = 1.0
USD = 2.0
SPLIT = pd.Timestamp("2025-10-01", tz="America/New_York")
N = 390                                            # minutos de la sesión regular


def build_days(sym):
    d = pickle.loads((CACHE / "databento_glbx_1m.pkl").read_bytes())
    d = d[d["symbol"] == f"{sym}.c.0"][["open", "high", "low", "close", "volume"]].sort_index()
    d.index = d.index.tz_convert("America/New_York")
    typ = ((d.high + d.low + d.close) / 3).to_numpy()
    vol = d.volume.to_numpy().astype(float)
    hm = (d.index.hour * 60 + d.index.minute).to_numpy()
    gkey = (d.index + pd.Timedelta(hours=6)).normalize()          # sesión Globex 18:00 → día siguiente
    out, prev = [], None
    for g, idx in pd.Series(np.arange(len(d))).groupby(gkey).indices.items():
        idx = np.asarray(idx)
        m = hm[idx]
        r = idx[(m >= 570) & (m < 960)]
        if len(r) != N:
            prev = None
            continue
        o, h, l, c = (d[k].to_numpy()[r] for k in ("open", "high", "low", "close"))
        # VWAP de la sesión regular (anclada 9:30) y su desviación ponderada por volumen
        pv, v, p2 = np.cumsum(typ[r] * vol[r]), np.cumsum(vol[r]), np.cumsum(typ[r] ** 2 * vol[r])
        vw = pv / np.maximum(v, 1)
        sd = np.sqrt(np.maximum(p2 / np.maximum(v, 1) - vw ** 2, 0))
        # VWAP de Globex (anclada 18:00) hasta cada minuto de la sesión regular
        gi = idx[(hm[idx] >= 1080) | (hm[idx] < 960)]
        gpv, gv = np.cumsum(typ[gi] * vol[gi]), np.cumsum(vol[gi])
        pos = np.searchsorted(gi, r)
        vwg = gpv[pos] / np.maximum(gv[pos], 1)
        day = dict(d=g, o=o, h=h, l=l, c=c, vw=vw, sd=sd, vwg=vwg)
        if prev is not None:
            day["ph"], day["pl"] = prev["h"].max(), prev["l"].min()
            out.append(day)
        prev = day
    return out


# ───────────────────────── familias (devuelven [(fecha, puntos), ...]) ─────────────────────────

def rev(days, k=2.0, s=1.0, t0=30, last=330, maxn=3):
    tr = []
    for x in days:
        o, h, l, c, vw, sd = x["o"], x["h"], x["l"], x["c"], x["vw"], x["sd"]
        n, i = 0, t0
        while i < last and n < maxn:
            side = 1 if c[i] < vw[i] - k * sd[i] else -1 if c[i] > vw[i] + k * sd[i] else 0
            if not side or sd[i] <= 0:
                i += 1
                continue
            e = o[i + 1]
            stop = e - side * s * sd[i]
            j = i + 1
            res = None
            while j < N:
                if (side == 1 and l[j] <= stop) or (side == -1 and h[j] >= stop):
                    res = side * (stop - e)
                    break
                tgt = vw[j - 1]
                if (side == 1 and h[j] >= tgt) or (side == -1 and l[j] <= tgt):
                    res = side * (max(tgt, o[j]) - e) if side == 1 else side * (min(tgt, o[j]) - e)
                    break
                if j == N - 1:
                    res = side * (c[j] - e)
                j += 1
            tr.append((x["d"], res - COST))
            n += 1
            i = j + 1
    return tr


def lado(days, t=30, anchor="vw", only=0, trail=False):
    tr = []
    for x in days:
        o, c, vw = x["o"], x["c"], x[anchor]
        side = 1 if c[t] > vw[t] else -1
        if only and side != only:
            continue
        e = o[t + 1]
        ex = c[-1]
        if trail:                                  # salida si una vela de 5 min cierra al otro lado de la VWAP
            for j in range(t + 5, N, 5):
                if side * (c[j] - vw[j]) < 0:
                    ex = o[j + 1] if j + 1 < N else c[j]
                    break
        tr.append((x["d"], side * (ex - e) - COST))
    return tr


def pull(days, t=30, s=1.0, rr=None, last=300, slope=15):
    tr = []
    for x in days:
        o, h, l, c, vw, sd = x["o"], x["h"], x["l"], x["c"], x["vw"], x["sd"]
        if c[t] > vw[t] and vw[t] > vw[t - slope]:
            side = 1
        elif c[t] < vw[t] and vw[t] < vw[t - slope]:
            side = -1
        else:
            continue
        for i in range(t + 1, last):
            lvl = vw[i - 1]                        # orden límite en la VWAP de la vela anterior
            if (side == 1 and l[i] <= lvl) or (side == -1 and h[i] >= lvl):
                e = min(lvl, o[i]) if side == 1 else max(lvl, o[i])
                risk = max(s * sd[i - 1], 5)
                stop, tgt = e - side * risk, (e + side * rr * risk if rr else None)
                res = None
                for j in range(i, N):
                    if (side == 1 and l[j] <= stop) or (side == -1 and h[j] >= stop):
                        res = -risk
                        break
                    if tgt is not None and j > i and ((side == 1 and h[j] >= tgt) or (side == -1 and l[j] <= tgt)):
                        res = rr * risk
                        break
                if res is None:
                    res = side * (c[-1] - e)
                tr.append((x["d"], res - COST))
                break
    return tr


def cruce(days, t=30, s=0.5, last=300):
    tr = []
    for x in days:
        o, h, l, c, vw, sd = x["o"], x["h"], x["l"], x["c"], x["vw"], x["sd"]
        for i in range(t + 4, last, 5):            # cierres de 5 min
            a, b = c[i - 5] - vw[i - 5], c[i] - vw[i]
            if a * b < 0:
                side = 1 if b > 0 else -1
                e = o[i + 1]
                ex = c[-1]
                for j in range(i + 5, N, 5):
                    if side * (c[j] - vw[j]) < -s * sd[j]:
                        ex = o[j + 1] if j + 1 < N else c[j]
                        break
                tr.append((x["d"], side * (ex - e) - COST))
                break
    return tr


def pdr_vw(days, filt="none", last=360):
    tr = []
    for x in days:
        o, h, l, c, vw, vwg = x["o"], x["h"], x["l"], x["c"], x["vw"], x["vwg"]
        ph, pl = x["ph"], x["pl"]
        if not (pl <= o[0] <= ph):
            continue
        mid = (ph + pl) / 2
        for i in range(1, last):
            side = 1 if h[i] > ph else -1 if l[i] < pl else 0
            if not side:
                continue
            ref = {"none": None, "vw": vw[i - 1], "vwg": vwg[i - 1]}[filt]
            if ref is not None and side * (vw[i - 1] - vw[max(i - 31, 0)]) < 0 and filt == "vw":
                break                               # VWAP del día en contra (pendiente de 30 min)
            if ref is not None and filt == "vwg" and side * ((ph if side == 1 else pl) - ref) < 0:
                break                               # ruptura al otro lado de la VWAP de Globex
            e = ph if side == 1 else pl
            res = side * (c[-1] - e)
            for j in range(i + 1, N):
                if (side == 1 and l[j] <= mid) or (side == -1 and h[j] >= mid):
                    res = side * (mid - e)
                    break
            tr.append((x["d"], res - COST))
            break
    return tr


# ───────────────────────── evaluación ─────────────────────────

def evaluate(tr):
    t = pd.DataFrame(tr, columns=["d", "pts"])
    if len(t) < 40:
        return None
    usd = t.pts * USD
    out = {}
    for name, sel in (("dev", t.d < SPLIT), ("val", t.d >= SPLIT)):
        u = usd[sel.to_numpy()]
        g, l = u[u > 0].sum(), -u[u < 0].sum()
        eq = u.cumsum()
        out[name] = dict(ops=len(u), usd=u.sum(), pf=g / l if l else np.inf, dd=(eq.cummax() - eq).max(),
                         win=(u > 0).mean(), sh=u.mean() / u.std() * np.sqrt(252) if u.std() else 0)
    return out


GRID = {
    "rev": [dict(f=rev, k=k, s=s, t0=t0) for k, s, t0 in itertools.product((1.5, 2.0, 2.5, 3.0), (0.5, 1.0, 1.5), (15, 30, 60))],
    "lado": [dict(f=lado, t=t, anchor=a, only=o, trail=tr) for t, a, o, tr in
             itertools.product((15, 30, 60, 90), ("vw", "vwg"), (0, 1), (False, True))],
    "pull": [dict(f=pull, t=t, s=s, rr=rr, slope=sl) for t, s, rr, sl in
             itertools.product((30, 60, 90), (0.5, 1.0, 1.5), (None, 1.5, 3.0), (15, 30))],
    "cruce": [dict(f=cruce, t=t, s=s) for t, s in itertools.product((15, 30, 60, 90), (0.0, 0.25, 0.5, 1.0))],
    "pdr_vw": [dict(f=pdr_vw, filt=f) for f in ("none", "vw", "vwg")],
}


def run(days, label):
    rows = []
    for fam, grid in GRID.items():
        for p in grid:
            f = p.pop("f")
            r = evaluate(f(days, **p))
            p["f"] = f
            if r is None:
                continue
            rows.append(dict(fam=fam, params=", ".join(f"{k}={v}" for k, v in p.items() if k != "f"),
                             dev_ops=r["dev"]["ops"], dev_usd=round(r["dev"]["usd"]), dev_pf=round(r["dev"]["pf"], 2),
                             val_ops=r["val"]["ops"], val_usd=round(r["val"]["usd"]), val_pf=round(r["val"]["pf"], 2),
                             val_dd=round(r["val"]["dd"]), val_win=f"{r['val']['win']:.0%}", val_sh=round(r["val"]["sh"], 2)))
    r = pd.DataFrame(rows)
    print(f"\n══════ {label}: año 1 = desarrollo (oct 2024 - sep 2025), año 2 = validación ══════")
    summ = r.groupby("fam").apply(lambda g: pd.Series({
        "variantes": len(g), "% gana año 1": f"{(g.dev_usd > 0).mean():.0%}", "% gana año 2": f"{(g.val_usd > 0).mean():.0%}",
        "mediana año 1 $": int(g.dev_usd.median()), "mediana año 2 $": int(g.val_usd.median())}), include_groups=False)
    print(summ.to_string())
    print("\nMejor variante de cada familia según el AÑO 1, y lo que hizo en el año 2:")
    best = r.loc[r.groupby("fam").dev_usd.idxmax()]
    print(best.to_string(index=False))
    return r


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 60)
    rn = run(build_days("NQ"), "NQ")
    re = run(build_days("ES"), "ES (control; 1 punto de ES no vale lo mismo, solo importa el signo)")
    rn.to_csv(CACHE / "vwap_research_nq.csv", index=False)
    re.to_csv(CACHE / "vwap_research_es.csv", index=False)


if __name__ == "__main__":
    main()
