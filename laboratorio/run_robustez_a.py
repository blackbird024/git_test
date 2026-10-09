"""Robustez del sistema A SOLO en desarrollo + validación: perturbación de parámetros, deslizamiento creciente,
coste fijo doble, y placebo (misma hora de entrada y misma gestión, dirección aleatoria)."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import run, Order
from data.loaders import daily_from_sessions, sessions
from execution_costs.costs import mnq
from strategies.features import daily_context
from strategies.noise import noise_trades
from strategies.orb import orb
from strategies.trend import trend
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, write_manifest

S = sessions()
ctx = daily_context(daily_from_sessions(S))
per = periods("intradia")
OOS_END = per["validacion"][1]


def esp(t, k):
    a, b = per[k]
    x = t[(t.date >= a) & (t.date <= b)]
    return x.pnl.mean() if len(x) else np.nan, len(x)


def ev(fn, cost, **p):
    fills = noise_trades(S, cost, **p) if fn == "noise" else run(S, fn, cost, ctx=ctx, **p)
    t = trades_frame(fills, cost)
    t = t[t.date <= OOS_END]
    (d, nd), (v, nv) = esp(t, "desarrollo"), esp(t, "validacion")
    return dict(esp_desarrollo=d, esp_validacion=v, n_dev=nd, n_val=nv, pf_total=t.pnl[t.pnl > 0].sum() / -t.pnl[t.pnl < 0].sum())


rows = []
base = mnq("base")
FROZEN = {
    "A1_immediate": (orb, dict(variant="immediate", stop_mode="rango", exit="2R_1130", vol=True)),
    "A1_close": (orb, dict(variant="close", stop_mode="rango", exit="2R_1130", vol=True)),
    "A1_retest": (orb, dict(variant="retest", stop_mode="rango", exit="2R_1130")),
    "A1_immediate_eod": (orb, dict(variant="immediate", stop_mode="rango", exit="eod")),
    "A2_tendencia": (trend, dict(vwap=True)),
    "A3_ruido": ("noise", dict(lookback=14, step=6, band_mult=1.0)),
}
# 1) deslizamiento y coste fijo
for name, (fn, p) in FROZEN.items():
    for xs in (0, 1, 2, 4):
        for fm in (1.0, 2.0):
            r = ev(fn, mnq("base", fixed_mult=fm, extra_slip_ticks=xs), **p)
            rows.append(dict(prueba="costes", estrategia=name, cambio=f"+{xs} ticks/lado, fijo x{fm}", **r))
    print(name, "costes ok", flush=True)
# 2) perturbación de parámetros (vecindario moderado)
pert = {
    "A1_immediate_eod": [dict(range_min=rm, exit_k=xk, entry_last_k=el) for rm, xk, el in
                         itertools.product((3, 5, 10), (330, 360, 385), (60, 90, 120))],
    "A1_close": [dict(exit_k=xk, entry_last_k=el) for xk, el in itertools.product((105, 120, 150), (60, 90, 120))],
    "A1_immediate": [dict(exit_k=xk, entry_last_k=el, range_min=rm) for xk, el, rm in
                     itertools.product((105, 120, 150), (60, 90, 120), (3, 5, 10))],
    "A3_ruido": [dict(lookback=lb, step=st, band_mult=bm) for lb, st, bm in
                 itertools.product((10, 14, 20), (3, 6, 12), (0.8, 1.0, 1.2))],
    "A2_tendencia": [dict(target_r=tr) for tr in (1.0, 1.5, 2.0, 3.0)],
}
for name, grid in pert.items():
    fn, p0 = FROZEN[name]
    for q in grid:
        p = {**p0, **q}
        r = ev(fn, base, **p)
        rows.append(dict(prueba="parametros", estrategia=name, cambio=str(q), **r))
    print(name, "parametros ok", flush=True)


# 3) placebo: mismas entradas (hora, stop a la misma distancia, misma salida) con dirección aleatoria
def placebo(fn, p, seed):
    rng = np.random.default_rng(seed)

    def strat(s, c, **kw):
        o = fn(s, c, **kw)
        if o is None:
            return None
        flip = rng.random() < 0.5
        if not flip:
            return o
        side = -o.side
        if o.kind == "stop":
            return None if True else o                 # una orden stop no se puede invertir sin cambiar la entrada
        dist = abs(s.m[o.k, 0] - o.stop) if not np.isnan(s.m[o.k, 0]) else 0
        ref = s.m[o.k, 0]
        return Order(side, "market", o.k, ref - side * dist, None, o.exit_k, target_r=o.target_r, tag="placebo")
    return strat


for name in ("A1_close", "A1_retest"):
    fn, p = FROZEN[name]
    for seed in range(20):
        r = ev(placebo(fn, p, seed), base, **p)
        rows.append(dict(prueba="placebo", estrategia=name, cambio=f"semilla {seed}", **r))
    print(name, "placebo ok", flush=True)


def noise_placebo(seed):
    rng = np.random.default_rng(seed)
    fills = noise_trades(S, base)
    out = []
    for f in fills:
        if rng.random() < 0.5:
            f.side, f.gross_pts = -f.side, -f.gross_pts - 2 * 2 * base.slip   # invertida, pagando el deslizamiento
        out.append(f)
    return out


for seed in range(20):
    t = trades_frame(noise_placebo(seed), base)
    t = t[t.date <= OOS_END]
    (d, nd), (v, nv) = esp(t, "desarrollo"), esp(t, "validacion")
    rows.append(dict(prueba="placebo", estrategia="A3_ruido", cambio=f"semilla {seed}", esp_desarrollo=d,
                     esp_validacion=v, n_dev=nd, n_val=nv))
res = pd.DataFrame(rows)
exp = new_experiment("robustez_a")
res.to_csv(exp / "robustez.csv", index=False)
write_manifest(exp, experimento="robustez sistema A (sin prueba final)", reglas="experiments/reglas_congeladas.yaml",
               periodos={k: [str(a.date()), str(b.date())] for k, (a, b) in per.items()}, semillas=list(range(20)))
pd.set_option("display.width", 250, "display.max_rows", 400)
print(res.round(2).to_string(index=False))
print("→", exp)
