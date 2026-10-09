"""Simulación del Topstep 50K Combine con las operaciones de las reglas congeladas (coste base).

Para cada día de inicio posible (ventanas secuenciales, sin barajar: se conserva la dependencia entre días) se simula
un intento completo. Tamaño:
  - estrategias con stop: contratos = floor(riesgo_usd / (riesgo_en_puntos × 2 $ + costes fijos)); 0 → no se opera
  - zona de ruido (sin stop): contratos fijos 1, 2 o 3
"""
import numpy as np
import pandas as pd
import yaml

from backtests.intraday import run
from data.loaders import daily_from_sessions, sessions
from execution_costs.costs import mnq
from risk.topstep import CFG, Rules, attempt
from strategies.features import daily_context
from strategies.noise import noise_trades
from strategies.orb import orb
from strategies.trend import trend
from validation.runner import new_experiment, write_manifest

FROZEN = {
    "A1 ORB immediate + vol (2R 11:30)": (orb, dict(variant="immediate", stop_mode="rango", exit="2R_1130", vol=True)),
    "A1 ORB close + vol (2R 11:30)": (orb, dict(variant="close", stop_mode="rango", exit="2R_1130", vol=True)),
    "A1 ORB retest (2R 11:30)": (orb, dict(variant="retest", stop_mode="rango", exit="2R_1130")),
    "A1 ORB immediate salida cierre": (orb, dict(variant="immediate", stop_mode="rango", exit="eod")),
    "A2 Tendencia + VWAP": (trend, dict(vwap=True)),
    "A3 Zona de ruido": ("noise", {}),
    "Control: ruido con dirección aleatoria (semilla 1)": ("noise_placebo", dict(seed=1)),
    "Control: ruido con dirección aleatoria (semilla 2)": ("noise_placebo", dict(seed=2)),
    "Control: ruido con dirección aleatoria (semilla 3)": ("noise_placebo", dict(seed=3)),
}


def noise_placebo(S, cost, seed):
    """Mismas horas de entrada y salida que la zona de ruido, dirección al azar, pagando el mismo deslizamiento."""
    rng = np.random.default_rng(seed)
    out = []
    for f in noise_trades(S, cost):
        if rng.random() < 0.5:
            f.side = -f.side
            f.entry, f.exit = f.entry + 2 * f.side * cost.slip, f.exit - 2 * f.side * cost.slip
            f.gross_pts = f.side * (f.exit - f.entry)
        out.append(f)
    return out


def with_mae(fills, S_by_date, pv):
    out = []
    for f in fills:
        m = S_by_date[f.date].m
        seg = m[f.entry_k: f.exit_k + 1]
        adverse = np.nanmin(seg[:, 2]) if f.side == 1 else np.nanmax(seg[:, 1])
        mae = min(f.side * (adverse - f.entry), f.gross_pts, 0.0) * pv
        out.append((f.date, f.gross_pts * pv, mae, f.risk_pts))
    return pd.DataFrame(out, columns=["date", "gross_usd", "mae_usd", "risk_pts"])


def build_days(t, cal, contracts_fn, fixed_rt):
    by = {d: [] for d in cal}
    for r in t.itertuples():
        n = contracts_fn(r)
        if n <= 0:
            continue
        by[r.date].append((n * (r.gross_usd - fixed_rt), n * r.mae_usd - n * fixed_rt))
    return [by[d] for d in cal]


def main():
    S = sessions()
    ctx = daily_context(daily_from_sessions(S))
    by_date = {s.date: s for s in S}
    cal = [s.date for s in S]
    cost = mnq("base")
    fixed_rt = 2 * cost.fixed_per_side
    R = Rules.load()
    lim = yaml.safe_load(CFG.read_text())["limites_personales"]
    rows = []
    for name, (fn, p) in FROZEN.items():
        if fn == "noise":
            fills = noise_trades(S, cost)
        elif fn == "noise_placebo":
            fills = noise_placebo(S, cost, **p)
        else:
            fills = run(S, fn, cost, ctx=ctx, **p)
        t = with_mae(fills, by_date, cost.point_value)
        if fn in ("noise", "noise_placebo"):
            sizes = {f"{n} MNQ fijos": (lambda r, n=n: n) for n in (1, 2, 3)}
        else:
            sizes = {f"riesgo {rk} $": (lambda r, rk=rk: min(int(rk // (r.risk_pts * cost.point_value + fixed_rt)),
                                                             lim["max_contratos_operativos"]))
                     for rk in lim["riesgo_por_operacion_usd"]}
        for sname, fnz in sizes.items():
            days = build_days(t, cal, fnz, fixed_rt)
            for label, a, b in (("2022-2026 (fuera de muestra)", "2022-01-01", "2026-10-02"),
                                ("2018-2026 (todo)", "2018-01-01", "2026-10-02")):
                idx = [i for i, d in enumerate(cal) if pd.Timestamp(a) <= d <= pd.Timestamp(b)]
                res = [attempt(days[i: idx[-1] + 1], R, max_days=250) for i in idx[:-60]]
                r = pd.DataFrame(res, columns=["res", "dias"])
                ok = r[r.res == "aprobado"]
                rows.append(dict(estrategia=name, tamaño=sname, ventanas=label, intentos=len(r),
                                 p_aprobar=(r.res == "aprobado").mean(), p_suspender=(r.res == "suspendido").mean(),
                                 p_sin_resolver=(r.res == "sin_resolver").mean(),
                                 dias_mediana_aprobar=ok.dias.median() if len(ok) else np.nan,
                                 dias_media_intento=r.dias.mean(),
                                 ops_saltadas_por_riesgo=float(np.mean([fnz(x) <= 0 for x in t.itertuples()]))))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    exp = new_experiment("topstep_combine")
    res.to_csv(exp / "topstep_combine.csv", index=False)
    write_manifest(exp, experimento="simulación Topstep 50K Combine", reglas=Rules.load().__dict__,
                   limites_personales=lim, coste="base", max_dias_por_intento=250,
                   metodo="un intento por cada día de inicio, ventanas secuenciales solapadas (no independientes)")
    pd.set_option("display.width", 250, "display.max_rows", 200)
    print(res.round(3).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
