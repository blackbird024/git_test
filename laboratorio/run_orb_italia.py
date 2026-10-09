"""ORB de 5 minutos a partir de las 13:00 (o la hora indicada con --hora) de Italia (Europe/Rome) en MNQ. Hipótesis nueva (no probada antes).

13:00 en Italia = 7:00 ET casi todo el año (8:00 ET en las semanas en que solo un país ha cambiado de hora).
Reglas fijadas antes de mirar resultados (las mismas del ORB del laboratorio, solo cambia la hora):
  rango = velas de 1 min de 13:00 a 13:04 (Italia); entradas hasta las 14:30; variantes immediate / close / retest;
  stop = lado opuesto del rango (retest: vela de retesteo); salidas:
    2R_1500  objetivo 2R, cierre forzoso 15:00 Italia
    2R_1525  objetivo 2R, cierre forzoso 15:25 (antes de la apertura de Nueva York)
    cierre   sin objetivo, cierre a las 15:55 ET (21:55 Italia normalmente)
Costes del laboratorio (bajo/base/alto). Particiones de config/PROTOCOLO.yaml. Se informan todas las variantes.
"""
import argparse

import numpy as np
import pandas as pd

from backtests.intraday import run
from data.loaders import Session, daily_from_sessions, nq_1m, sessions
from execution_costs.costs import mnq
from strategies.features import daily_context
from strategies.orb import orb
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest

HORA = 13
N = 540                                    # desde la hora de inicio, 9 horas


def rome_sessions():
    df = nq_1m()
    rome = df.index.tz_convert("Europe/Rome")
    arr = df[["open", "high", "low", "close", "volume"]].to_numpy()
    pos = pd.Series(np.arange(len(df)), index=df.index)
    out = []
    for s in sessions():
        d = s.date.date()
        t0 = pd.Timestamp(f"{d} {HORA:02d}:00", tz="Europe/Rome")
        close_et = pd.Timestamp(f"{d} 09:30", tz="America/New_York") + pd.Timedelta(minutes=s.close_min)
        close_min = min(int((close_et - t0).total_seconds() // 60) - 5, N)       # 5 min antes del cierre de NY
        lo, hi = df.index.searchsorted(t0), df.index.searchsorted(t0 + pd.Timedelta(minutes=N))
        if hi - lo < 60:
            continue
        mm = ((df.index[lo:hi] - t0).total_seconds() // 60).astype(int)
        m = np.full((N, 5), np.nan)
        m[mm] = arr[lo:hi]
        out.append(Session(s.date, m, close_min, s.instrument_id, s.roll_week))
    return out


def variants():
    """Salidas: 2R con cierre forzoso 2 h después del inicio; 2R con cierre a las 15:25 Italia (antes de NY,
    solo si es posterior al inicio + 30 min); sin objetivo hasta 5 min antes del cierre de NY."""
    exits = {f"2R_+2h": 120, "cierre": 10_000}
    k1525 = (15 * 60 + 25) - HORA * 60
    if k1525 >= 30:
        exits["2R_1525"] = k1525
    return {f"{v} {x}": dict(variant=v, stop_mode="rango", exit="2R_1130" if x != "cierre" else "eod", exit_k=k)
            for v in ("immediate", "close", "retest") for x, k in exits.items()}


def main():
    S = rome_sessions()
    ctx = daily_context(daily_from_sessions(sessions()))
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    exp = new_experiment(f"orb_italia_{HORA}h")
    rows = []
    for name, p in variants().items():
        for scen in ("bajo", "base", "alto"):
            c = mnq(scen)
            t = trades_frame(run(S, orb, c, ctx=ctx, **p), c)
            if scen == "base":
                t.to_csv(exp / f"ops_{name.replace(' ', '_')}.csv.gz", index=False)
            for k, tp in split(t, per).items():
                s = summary(tp, cals[k], minutes_per_session=N)
                rows.append(dict(variante=name, coste=scen, periodo=k, riesgo_medio_usd=tp["risk_usd"].median(), **s))
            o = t[t.date >= "2022-01-01"]
            lo, hi = block_bootstrap_mean(o.pnl.to_numpy())
            rows.append(dict(variante=name, coste=scen, periodo="FM 2022-2026", n=len(o), esperanza=o.pnl.mean(),
                             pf=o.pnl[o.pnl > 0].sum() / -o.pnl[o.pnl < 0].sum(), ic90_bajo=lo, ic90_alto=hi,
                             riesgo_medio_usd=o["risk_usd"].median()))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento=f"ORB 5 min desde las {HORA}:00 Italia", variantes=variants(), sesiones=len(S),
                   periodos={k: [str(a.date()), str(b.date())] for k, (a, b) in per.items()})
    pd.set_option("display.width", 250, "display.max_rows", 300)
    b = res[res.coste == "base"]
    print(b[["variante", "periodo", "n", "neto_año", "pf", "esperanza", "ic90_bajo", "ic90_alto", "dd_max",
             "riesgo_medio_usd", "años_pos"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hora", type=int, default=13)
    HORA = ap.parse_args().hora
    main()
