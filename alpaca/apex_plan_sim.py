"""B+ del Confirmation Model (Londres 2:00-5:00 NY, NQ y oro) y el camino al primer retiro en Apex.

1. Saca las operaciones B+ del backtest (futuros de Databento) con objetivo 2R.
2. Resultado por año y por mercado.
3. Simula el camino al primer retiro remuestreando la secuencia histórica de operaciones:
   cuenta 50k (drawdown 2.000 $, objetivo +2.600 $, días válidos >= 200 $) y 25k (1.000 $, +1.600 $, >= 100 $),
   con distintos riesgos por operación.

Uso:
    python apex_plan_sim.py
"""

import numpy as np
import pandas as pd

from confirmation_model_backtest import run

SESSION = {"Londres 2:00-5:00 NY": (2, 5, 11)}


def trades():
    out = []
    for sym, other in (("NQ", "ES"), ("GC", None)):
        df = run(sym, other, SESSION, cost=0.00003)
        df = df[(df["grade"].isin(["B+", "A"])) & (df["mode"] == "2R")].copy()
        df["mercado"] = sym
        out.append(df)
    t = pd.concat(out).sort_values("day").reset_index(drop=True)
    t["year"] = pd.to_datetime(t["day"]).dt.year
    return t


def simulate(r, risk, dd, goal, min_day, n_sims=20000, horizon=400, seed=1):
    """Bloques de la secuencia real (con reemplazo). Devuelve P(retiro), P(cuenta perdida), mediana de operaciones."""
    rng = np.random.default_rng(seed)
    r = np.asarray(r)
    ok = lost = 0
    used = []
    for _ in range(n_sims):
        bal, peak, good_days = 0.0, 0.0, 0
        start = rng.integers(len(r))
        for k in range(horizon):
            x = r[(start + k) % len(r)] if k < len(r) else rng.choice(r)   # primero la secuencia real, luego remuestreo
            pnl = x * risk
            bal += pnl
            if pnl >= min_day:
                good_days += 1
            floor = min(peak, dd + 100) - dd          # drawdown que sigue al máximo hasta el safety net
            peak = max(peak, bal)
            if bal <= floor:
                lost += 1
                break
            if bal >= goal and good_days >= 5:
                ok += 1
                used.append(k + 1)
                break
    return ok / n_sims, lost / n_sims, (np.median(used) if used else np.nan)


def main():
    t = trades()
    months = (pd.to_datetime(t["day"]).max() - pd.to_datetime(t["day"]).min()).days / 30.4
    print(f"\nOperaciones B+/A (objetivo 2R): {len(t)} en {months:.0f} meses = {len(t) / months:.1f} al mes")
    print(f"Acierto {(t['r'] > 0).mean():.0%} · R medio {t['r'].mean():+.2f} · total {t['r'].sum():+.1f}R\n")
    print(t.groupby(["year"]).agg(ops=("r", "size"), acierto=("r", lambda s: (s > 0).mean()),
                                  R_medio=("r", "mean"), R_total=("r", "sum")).round(2).to_string())
    print()
    print(t.groupby("mercado").agg(ops=("r", "size"), acierto=("r", lambda s: (s > 0).mean()),
                                   R_medio=("r", "mean"), R_total=("r", "sum")).round(2).to_string())
    rpm = len(t) / months
    print("\nCamino al primer retiro (simulación sobre la secuencia real de operaciones)")
    for name, dd, goal, min_day in (("50k", 2000, 2600, 200), ("25k", 1000, 1600, 100)):
        for frac in (0.05, 0.10, 0.15, 0.25):
            risk = dd * frac
            p_ok, p_lost, n = simulate(t["r"].to_numpy(), risk, dd, goal, min_day)
            print(f"  {name}: riesgo {risk:>4.0f} $ ({frac:.0%} del drawdown) -> retiro {p_ok:.0%}, "
                  f"cuenta perdida {p_lost:.0%}, mediana {n:.0f} operaciones (~{n / rpm:.0f} meses)")


if __name__ == "__main__":
    main()
