"""Búsqueda amplia de estrategias intradía para NQ/MNQ con validación fuera de muestra.

Método: cada familia tiene una pequeña rejilla de parámetros. La variante se ELIGE solo con 2018-2022 (desarrollo)
y se JUZGA con 2023-2026 (validación), que no participa en la elección. Todo cierra el mismo día (vale para Apex).
Coste: 1 punto por operación ida y vuelta. Resultados en $ por 1 MNQ (2 $/punto).

Familias:
  noise      bandas de ruido en NY (referencia; Zarattini-Aziz-Barbon 2024)
  noise_vt   las mismas con tamaño inverso a la volatilidad reciente (mismo riesgo medio)
  ldn_fade   desvanecer las salidas de la banda de ruido en London (hipótesis sacada de datos anteriores)
  gap        hueco de apertura de NY medido en ATR: seguirlo o desvanecerlo, salida a hora fija
  pdr        ruptura del máximo/mínimo del día anterior en NY, stop en el medio del rango, cierre al final
  orb        ruptura del rango de los primeros N minutos con stop en el otro lado, objetivo k·R o cierre
  overnight  la dirección de la noche (18:00-9:30) decide la de la sesión (9:30 → hora fija)
  nr7        días tras un rango estrecho (NR7 / día interior): ruptura del rango de apertura
  tod        ventanas horarias fijas solo largo (estacionalidad intradía)

Uso:
    python nq_intraday_research.py
"""

import itertools

import numpy as np
import pandas as pd

from crt_backtest import load_5m

COST = 1.0
USD = 2.0
SPLIT = 2023


# ───────────────────────── datos por día ─────────────────────────

def build_days(sym="NQ"):
    df = load_5m(sym)
    t = df.index
    m = (t.hour * 60 + t.minute).to_numpy()
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    date = np.array(t.date)
    out = []
    rth_idx = {}
    for d in pd.unique(date):
        rth_idx.setdefault(d, None)
    # índices por fecha natural
    df2 = pd.DataFrame({"m": m, "d": date})
    groups = df2.groupby("d").indices
    prev = None
    for d in sorted(groups):
        idx = groups[d]
        mm = m[idx]
        rth = idx[(mm >= 570) & (mm < 960)]
        ldn = idx[(mm >= 120) & (mm < 480)]
        pre = idx[(mm >= 0) & (mm < 570)]
        if len(rth) != 78:
            prev = None
            continue
        R = np.c_[o[rth], h[rth], l[rth], c[rth]]
        day = dict(d=d, rth=R, wd=pd.Timestamp(d).weekday())
        day["ldn"] = np.c_[o[ldn], h[ldn], l[ldn], c[ldn]] if len(ldn) == 72 else None
        day["pre_open"] = o[pre[0]] if len(pre) else np.nan
        if prev is not None:
            day["pc"] = prev["rth"][-1, 3]
            day["ph"] = prev["rth"][:, 1].max()
            day["pl"] = prev["rth"][:, 2].min()
            out.append(day)
        prev = day
    # ATR(14) de los rangos de la sesión regular, conocido antes de abrir
    rngs = np.array([x["rth"][:, 1].max() - x["rth"][:, 2].min() for x in out])
    atr = pd.Series(rngs).rolling(14).mean().shift(1).to_numpy()
    for x, a, r in zip(out, atr, rngs):
        x["atr"] = a
        x["rng"] = r
    return [x for x in out if np.isfinite(x["atr"])]


# ───────────────────────── familias ─────────────────────────

def noise(days, step=6, lookback=14, mult=1.0, vt=False, session="rth", fade=False):
    key = "rth" if session == "rth" else "ldn"
    ds = [x for x in days if x[key] is not None]
    moves = np.array([np.abs(x[key][:, 3] / x[key][0, 0] - 1) for x in ds])
    n = moves.shape[1]
    out = []
    for i in range(lookback, len(ds)):
        x = ds[i]
        B = x[key]
        sig = moves[i - lookback:i].mean(axis=0) * mult
        o = B[0, 0]
        ref_hi, ref_lo = (max(o, x["pc"]), min(o, x["pc"])) if key == "rth" else (o, o)
        ub, lb = ref_hi * (1 + sig), ref_lo * (1 - sig)
        size = 1.0
        if vt:
            size = np.nanmean([d["atr"] for d in days]) / x["atr"]
        pos, entry, pnl = 0, 0.0, 0.0
        for k in range(step - 1, n - 1, step):
            c, px = B[k, 3], B[k + 1, 0]
            if not fade:
                if pos == 1 and c < ub[k]:
                    pnl += px - entry - COST; pos = 0
                elif pos == -1 and c > lb[k]:
                    pnl += entry - px - COST; pos = 0
                if pos == 0 and c > ub[k]:
                    pos, entry = 1, px
                elif pos == 0 and c < lb[k]:
                    pos, entry = -1, px
            else:                                   # desvanecer: vender arriba, comprar abajo, salir al volver a la apertura
                if pos == -1 and c <= o:
                    pnl += entry - px - COST; pos = 0
                elif pos == 1 and c >= o:
                    pnl += px - entry - COST; pos = 0
                if pos == 0 and c > ub[k]:
                    pos, entry = -1, px
                elif pos == 0 and c < lb[k]:
                    pos, entry = 1, px
        if pos:
            pnl += pos * (B[-1, 3] - entry) - COST
        if pnl:
            out.append((x["d"], pnl * size))
    return out


def gap(days, thr=0.25, follow=True, exit_k=12):
    out = []
    for x in days:
        B = x["rth"]
        g = (B[0, 0] - x["pc"]) / x["atr"]
        if abs(g) < thr:
            continue
        side = np.sign(g) if follow else -np.sign(g)
        out.append((x["d"], side * (B[exit_k - 1, 3] - B[0, 0]) - COST))
    return out


def pdr(days, last_entry_k=24):
    """Ruptura del máximo/mínimo del día anterior; stop en el medio del rango anterior; cierre al final."""
    out = []
    for x in days:
        B = x["rth"]
        hi, lo, mid = x["ph"], x["pl"], (x["ph"] + x["pl"]) / 2
        if B[0, 0] > hi or B[0, 0] < lo:
            continue                                 # abre fuera: no hay ruptura limpia
        res = None
        for k in range(78):
            if k > last_entry_k:
                break
            if B[k, 1] > hi:
                side, entry, stop, k0 = 1, hi, mid, k
            elif B[k, 2] < lo:
                side, entry, stop, k0 = -1, lo, mid, k
            else:
                continue
            px = B[-1, 3]
            for q in range(k0 + 1, 78):
                if (side == 1 and B[q, 2] <= stop) or (side == -1 and B[q, 1] >= stop):
                    px = stop
                    break
            res = side * (px - entry) - COST
            break
        if res is not None:
            out.append((x["d"], res))
    return out


def orb(days, n=6, tgt=None, last_entry_k=36, only=None):
    out = []
    for x in days:
        if only == "nr7" and not x.get("nr7"):
            continue
        B = x["rth"]
        hi, lo = B[:n, 1].max(), B[:n, 2].min()
        for k in range(n, min(last_entry_k, 77)):
            if B[k, 1] > hi or B[k, 2] < lo:
                side = 1 if B[k, 1] > hi else -1
                entry = hi if side == 1 else lo
                stop = lo if side == 1 else hi
                risk = abs(entry - stop)
                T = entry + side * tgt * risk if tgt else None
                px = B[-1, 3]
                for q in range(k + (0 if False else 1), 78):
                    if (side == 1 and B[q, 2] <= stop) or (side == -1 and B[q, 1] >= stop):
                        px = stop; break
                    if T and ((side == 1 and B[q, 1] >= T) or (side == -1 and B[q, 2] <= T)):
                        px = T; break
                out.append((x["d"], side * (px - entry) - COST))
                break
    return out


def overnight(days, exit_k=78, thr=0.0):
    out = []
    for x in days:
        if not np.isfinite(x["pre_open"]):
            continue
        B = x["rth"]
        r = (B[0, 0] - x["pc"]) / x["atr"]
        if abs(r) < thr:
            continue
        side = np.sign(r)
        out.append((x["d"], side * (B[exit_k - 1, 3] - B[0, 0]) - COST))
    return out


def tod(days, k0, k1):
    return [(x["d"], x["rth"][k1 - 1, 3] - x["rth"][k0, 0] - COST) for x in days]


# ───────────────────────── evaluación ─────────────────────────

def evaluate(tr):
    t = pd.DataFrame(tr, columns=["d", "pts"])
    if len(t) < 30:
        return None
    y = pd.to_datetime(t.d).dt.year
    usd = t.pts * USD
    out = {}
    for name, sel in (("dev", y < SPLIT), ("val", y >= SPLIT)):
        u = usd[sel.to_numpy()]
        yrs = len(set(y[sel])) if name == "dev" else (pd.to_datetime(t.d[sel]).max() - pd.to_datetime(t.d[sel]).min()).days / 365.25
        g, l = u[u > 0].sum(), -u[u < 0].sum()
        eq = u.cumsum()
        daily_sd = u.std()
        out[name] = dict(ops=len(u), usd_y=u.sum() / max(yrs, 0.1), pf=g / l if l else np.inf,
                         dd=(eq.cummax() - eq).max(), sharpe=(u.mean() / daily_sd * np.sqrt(252)) if daily_sd else 0,
                         win=(u > 0).mean())
    by = usd.groupby(y).sum()
    out["years_pos"] = f"{(by > 0).sum()}/{len(by)}"
    out["by_year"] = by.round(0).to_dict()
    return out


def main():
    days = build_days("NQ")
    rngs = [x["rng"] for x in days]
    for i, x in enumerate(days):                     # NR7: el rango de AYER fue el menor de 7 (conocido antes de abrir)
        x["nr7"] = i >= 7 and rngs[i - 1] == min(rngs[i - 7:i])
    fams = {
        "noise": [dict(f=noise, step=s, lookback=lb, mult=m) for s, lb, m in itertools.product((3, 6, 12), (10, 14, 20), (0.8, 1.0, 1.2))],
        "noise_vt": [dict(f=noise, step=s, lookback=14, mult=m, vt=True) for s, m in itertools.product((3, 6, 12), (0.8, 1.0, 1.2))],
        "ldn_fade": [dict(f=noise, session="ldn", fade=True, step=s, lookback=14, mult=m) for s, m in itertools.product((3, 6, 12), (0.8, 1.0, 1.5))],
        "gap": [dict(f=gap, thr=t, follow=fw, exit_k=e) for t, fw, e in itertools.product((0.1, 0.25, 0.5), (True, False), (6, 12, 24, 78))],
        "pdr": [dict(f=pdr, last_entry_k=k) for k in (12, 24, 48, 72)],
        "orb": [dict(f=orb, n=n, tgt=tg) for n, tg in itertools.product((1, 3, 6), (None, 2, 3))],
        "nr7_orb": [dict(f=orb, n=n, tgt=tg, only="nr7") for n, tg in itertools.product((3, 6), (None, 2))],
        "overnight": [dict(f=overnight, exit_k=e, thr=t) for e, t in itertools.product((6, 12, 24, 78), (0.0, 0.2, 0.5))],
        "tod": [dict(f=tod, k0=a, k1=b) for a, b in ((0, 6), (0, 12), (6, 78), (66, 78), (72, 78), (12, 72), (0, 78))],
    }
    rows = []
    for fam, grid in fams.items():
        res = []
        for p in grid:
            f = p.pop("f")
            ev = evaluate(f(days, **p))
            p["f"] = f
            if ev:
                res.append((p, ev))
        if not res:
            continue
        # elección SOLO con desarrollo: mejor Sharpe de 2018-2022
        best_p, best = max(res, key=lambda z: z[1]["dev"]["sharpe"])
        # robustez: fracción de la rejilla positiva en desarrollo y en validación
        frac_dev = np.mean([e["dev"]["usd_y"] > 0 for _, e in res])
        frac_val = np.mean([e["val"]["usd_y"] > 0 for _, e in res])
        rows.append({"familia": fam, "parámetros": {k: v for k, v in best_p.items() if k != "f"},
                     "dev $/año": round(best["dev"]["usd_y"]), "dev Sharpe": round(best["dev"]["sharpe"], 2),
                     "val $/año": round(best["val"]["usd_y"]), "val Sharpe": round(best["val"]["sharpe"], 2),
                     "val PF": round(best["val"]["pf"], 2), "val DD $": round(best["val"]["dd"]),
                     "ops/año": round((best["dev"]["ops"] + best["val"]["ops"]) / 8.75), "acierto": f"{best['val']['win']:.0%}",
                     "años +": best["years_pos"], "rejilla + dev": f"{frac_dev:.0%}", "rejilla + val": f"{frac_val:.0%}"})
        print(f"{fam} listo", flush=True)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_colwidth", 60)
    r = pd.DataFrame(rows).sort_values("val Sharpe", ascending=False)
    print("\nElegido con 2018-2022 (dev) · juzgado con 2023-2026 (val) · 1 MNQ · coste 1 punto")
    print(r.to_string(index=False))


if __name__ == "__main__":
    main()
