"""CRT del usuario (hora de Italia): la vela de 4 h cierra; después una vela de 1 h rompe fuera de su rango y CIERRA de
nuevo dentro → entrada en la apertura de la hora siguiente en dirección contraria a la ruptura.

Reglas fijadas antes de ver resultados:
- C1 = vela de 4 h de 4:00-8:00 Italia (variante: 0:00-4:00, "la que cierra a las 4").
- Velas de 1 h en punto (hora de Italia) desde el cierre de C1 hasta la de 16:00-17:00 Italia (≈ 10:00-11:00 ET).
  Señal bajista: máximo de la vela de 1 h > máximo de C1 y cierre < máximo de C1 (y > mínimo de C1). Alcista: espejo.
  Si la vela de 1 h rompe por los dos lados, no hay señal. Primera señal del día.
- Entrada a mercado en la apertura de la hora siguiente. Stop: extremo de esa vela de 1 h ± 1 tick.
- Objetivo: extremo opuesto de C1 (o 2R). Cierre forzoso 5 min antes del cierre de Nueva York (21:55 Italia normalmente).
"""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from data.loaders import TICK, nq_1m, sessions
from execution_costs.costs import mnq
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest

N = 1320                                       # 0:00 → 22:00 Italia


def rome_days(S):
    df = nq_1m()
    arr = df[["open", "high", "low", "close", "volume"]].to_numpy()
    out = []
    for s in S:
        d = s.date.date()
        t0 = pd.Timestamp(f"{d} 00:00", tz="Europe/Rome")
        close_et = pd.Timestamp(f"{d} 09:30", tz="America/New_York") + pd.Timedelta(minutes=s.close_min)
        close_min = min(int((close_et - t0).total_seconds() // 60) - 5, N)
        lo, hi = df.index.searchsorted(t0), df.index.searchsorted(t0 + pd.Timedelta(minutes=N))
        m = np.full((N, 5), np.nan)
        mm = ((df.index[lo:hi] - t0).total_seconds() // 60).astype(int)
        m[mm] = arr[lo:hi]
        out.append((s.date, m, close_min))
    return out


def signal(m, c1_start, target):
    O, H, L, C = m[:, 0], m[:, 1], m[:, 2], m[:, 3]
    a, b = c1_start * 60, c1_start * 60 + 240
    if np.isnan(H[a:b]).all():
        return None
    h1, l1 = np.nanmax(H[a:b]), np.nanmin(L[a:b])
    for hs in range(b, 17 * 60, 60):
        x = m[hs:hs + 60]
        ok = ~np.isnan(x[:, 0])
        if not ok.any():
            continue
        h, l = np.nanmax(x[:, 1]), np.nanmin(x[:, 2])
        c = x[ok][-1, 3]
        up = h > h1 and l1 < c < h1
        dn = l < l1 and l1 < c < h1
        if h > h1 and l < l1:
            return None
        if up or dn:
            side = -1 if up else 1
            stop = h + TICK if side == -1 else l - TICK
            tgt = l1 if side == -1 else h1
            if target == "2R":
                return Order(side, "market", hs + 60, stop, None, N, target_r=2.0, tag="crt_it")
            return Order(side, "market", hs + 60, stop, tgt, N, tag="crt_it")
    return None


def main():
    S = sessions()
    D = rome_days(S)
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    variants = {f"C1 {c1}:00-{c1 + 4}:00 Italia, objetivo {t}": dict(c1_start=c1, target=t)
                for c1, t in itertools.product((4, 0), ("extremo_opuesto", "2R"))}
    exp = new_experiment("crt_italia_4h_1h")
    rows = []
    for name, p in variants.items():
        for scen in ("bajo", "base", "alto"):
            c = mnq(scen)
            fills = []
            for date, m, cm in D:
                o = signal(m, **p)
                if o is not None:
                    f = simulate(date, m, cm, o, c)
                    if f is not None:
                        fills.append(f)
            t = trades_frame(fills, c)
            if scen == "base":
                t.to_csv(exp / f"ops_{''.join(ch if ch.isalnum() else '_' for ch in name)}.csv.gz", index=False)
            for k, tp in split(t, per).items():
                rows.append(dict(variante=name, coste=scen, periodo=k, **summary(tp, cals[k], minutes_per_session=N)))
            o_ = t[t.date >= "2022-01-01"]
            lo, hi = block_bootstrap_mean(o_.pnl.to_numpy())
            rows.append(dict(variante=name, coste=scen, periodo="FM 2022-2026", n=len(o_), esperanza=o_.pnl.mean(),
                             pf=o_.pnl[o_.pnl > 0].sum() / -o_.pnl[o_.pnl < 0].sum(), acierto=(o_.pnl > 0).mean(),
                             ic90_bajo=lo, ic90_alto=hi, riesgo_mediano=o_.risk_usd.median(),
                             hora_entrada_mediana=f"{int(o_.entry_k.median() // 60)}:00",
                             salidas=o_.reason.value_counts(normalize=True).round(2).to_dict()))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="CRT usuario: 4 h (hora Italia) + vela 1 h que rompe y cierra dentro",
                   variantes=variants, periodos={k: [str(a.date()), str(b.date())] for k, (a, b) in per.items()})
    pd.set_option("display.width", 280, "display.max_rows", 200, "display.max_colwidth", 70)
    b = res[res.coste == "base"]
    print(b[["variante", "periodo", "n", "neto_año", "pf", "esperanza", "acierto", "ic90_bajo", "ic90_alto", "dd_max",
             "riesgo_mediano", "hora_entrada_mediana", "salidas"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
