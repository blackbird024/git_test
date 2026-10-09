"""Backtest de la estrategia del vídeo (strategies/video_sweep_ob.py) en NQ/MNQ, 2018-2026, con los periodos y costes
del protocolo. 5 variantes fijadas antes de ver resultados."""
import numpy as np
import pandas as pd

from backtests.intraday import simulate
from data.loaders import daily_from_sessions, nq_1m, sessions
from execution_costs.costs import mnq
from strategies.features import daily_context
from strategies.video_sweep_ob import signal
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest

VARIANTS = {
    "M3 + H1/H4, 1R (vídeo)": dict(tf=3, htf=True, target_r=1.0),
    "M5 + H1/H4, 1R (vídeo)": dict(tf=5, htf=True, target_r=1.0),
    "M3 sin H1/H4, 1R": dict(tf=3, htf=False, target_r=1.0),
    "M5 sin H1/H4, 1R": dict(tf=5, htf=False, target_r=1.0),
    "M3 + H1/H4, 2R": dict(tf=3, htf=True, target_r=2.0),
}


def days24(S):
    df = nq_1m()
    arr = df[["open", "high", "low", "close", "volume"]].to_numpy()
    out = []
    for s in S:
        prev = s.date - pd.tseries.offsets.BDay(1)
        t0 = pd.Timestamp(f"{prev.date()} 18:00", tz="America/New_York")
        if s.date.weekday() == 0:
            t0 = pd.Timestamp(f"{(s.date - pd.Timedelta(days=1)).date()} 18:00", tz="America/New_York")
        lo, hi = df.index.searchsorted(t0), df.index.searchsorted(t0 + pd.Timedelta(minutes=1320))
        m = np.full((1320, 5), np.nan)
        mm = ((df.index[lo:hi] - t0).total_seconds() // 60).astype(int)
        m[mm] = arr[lo:hi]
        if np.isnan(m[120:660, 0]).all():
            continue
        out.append(dict(date=s.date, m24=m, sess=s))
    return out


def main():
    S = sessions()
    ctx = daily_context(daily_from_sessions(S))
    D = days24(S)
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    exp = new_experiment("video_barrida_ob")
    rows = []
    for name, p in VARIANTS.items():
        for scen in ("bajo", "base", "alto"):
            c = mnq(scen)
            fills = []
            for d in D:
                o = signal(d, ctx, **p)
                if o is not None:
                    f = simulate(d["date"], d["sess"].m, d["sess"].close_min, o, c)
                    if f is not None:
                        fills.append(f)
            t = trades_frame(fills, c)
            if scen == "base":
                t.to_csv(exp / f"ops_{''.join(ch if ch.isalnum() else '_' for ch in name)}.csv.gz", index=False)
            for k, tp in split(t, per).items():
                rows.append(dict(variante=name, coste=scen, periodo=k, **summary(tp, cals[k])))
            o_ = t[t.date >= "2022-01-01"]
            lo, hi = block_bootstrap_mean(o_.pnl.to_numpy())
            rows.append(dict(variante=name, coste=scen, periodo="FM 2022-2026", n=len(o_), esperanza=o_.pnl.mean(),
                             pf=o_.pnl[o_.pnl > 0].sum() / -o_.pnl[o_.pnl < 0].sum(), acierto=(o_.pnl > 0).mean(),
                             ic90_bajo=lo, ic90_alto=hi, riesgo_mediano=o_.risk_usd.median()))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="estrategia del vídeo: barrida + liquidity sweep H1/H4 + envolvente 1:1",
                   variantes=VARIANTS, periodos={k: [str(a.date()), str(b.date())] for k, (a, b) in per.items()})
    pd.set_option("display.width", 250, "display.max_rows", 200)
    b = res[res.coste == "base"]
    print(b[["variante", "periodo", "n", "ops_año", "neto_año", "pf", "esperanza", "acierto", "ic90_bajo", "ic90_alto",
             "dd_max", "riesgo_mediano", "racha_perdedora"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
