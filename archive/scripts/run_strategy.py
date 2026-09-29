"""Backtest de todas las variantes de una estrategia.

Uso:
    python scripts/run_strategy.py --estrategia orb --periodo is    # in-sample 2015-2022
    python scripts/run_strategy.py --estrategia cm  --periodo oos   # out-of-sample 2023-hoy

Estrategias: orb (Opening Range Breakout), cm (momentum de cierre).
Para cada variante calcula métricas con y sin costes, y simula evaluaciones Apex EOD.
Además calcula el "promedio de variantes": el resultado de repartir el riesgo a partes iguales
entre todas (en vez de elegir la mejor), que es lo que recomiendan Carver y compañía.
"""
import argparse
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_instruments, load_system  # noqa: E402
from src.data.loader import load_clean  # noqa: E402
from src.engine.backtest import Backtester  # noqa: E402
from src.risk.apex_eod import simulate_all_starts, summarize  # noqa: E402
from src.strategies.close_momentum import CloseMomentum  # noqa: E402
from src.strategies.orb import ORB  # noqa: E402
from src.strategies.vwap_trend import VWAPTrend  # noqa: E402
from src.validation.metrics import trade_metrics  # noqa: E402

PERIODS = {"is": ("2015-01-01", "2023-01-01"), "oos": ("2023-01-01", None)}
REPORTS = Path(__file__).resolve().parent.parent / "reports"

# Variantes de cada estrategia, fijadas de antemano (no se eligen mirando resultados).
# Cada función recibe {"MNQ": velas de NQ, "MGC": velas de GC}.
VARIANTS = {
    "orb": ("ORB en MNQ", lambda d: [ORB.build(d["MNQ"], m, s)
                                     for m in (5, 15, 30) for s in ("range", "atr")]),
    "cm": ("Momentum de cierre en MNQ", lambda d: [CloseMomentum.build(d["MNQ"], k) for k in (0.1, 0.2)]),
    "vwap": ("Tendencia VWAP en MNQ y MGC", lambda d: [VWAPTrend.build(d[i], i, k)
                                                      for i in ("MNQ", "MGC") for k in (0.1, 0.2)]),
}
SOURCES = {"MNQ": "NQ", "MGC": "GC"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--estrategia", choices=VARIANTS, required=True)
    ap.add_argument("--periodo", choices=PERIODS, default="is")
    args = ap.parse_args()
    title, make_variants = VARIANTS[args.estrategia]
    start, end = PERIODS[args.periodo]

    rules, account = load_system()
    instruments = load_instruments()
    free = {k: replace(v, commission_rt=0.0, slippage_ticks=0) for k, v in instruments.items()}

    # Cargamos un mes extra antes del inicio para que el ATR esté disponible desde el primer día.
    warmup = (pd.Timestamp(start) - pd.Timedelta(days=40)).strftime("%Y-%m-%d")
    data = {inst: load_clean(root, warmup, end) for inst, root in SOURCES.items()}

    rows, dailies = [], {}
    for strat in make_variants(data):
        for label, insts in (("con_costes", instruments), ("sin_costes", free)):
            only = {strat.instrument: data[strat.instrument]}  # solo el instrumento que opera
            res = Backtester(insts, rules, account.max_micros).run(only, [strat])
            daily = res.daily[res.daily.index >= pd.Timestamp(start)]
            trades = res.trades[pd.to_datetime(res.trades.entry_time).dt.tz_localize(None) >= pd.Timestamp(start)] \
                if not res.trades.empty else res.trades
            m = trade_metrics(trades, daily)
            rej = res.rejected.reason.value_counts().to_dict() if not res.rejected.empty else {}
            row = {"variante": strat.name, "costes": label, **m,
                   "rechazadas_sin_presupuesto": rej.get("sin_presupuesto_de_riesgo", 0)}
            if label == "con_costes":
                row.update(summarize(simulate_all_starts(daily, account)))
                dailies[strat.name] = daily
            rows.append(row)
            print(f"{strat.name:14s} {label:10s} neto={m.get('beneficio_neto')} "
                  f"PF={m.get('profit_factor')} ops={m.get('operaciones')}", flush=True)

    # Promedio de variantes: 1/N del resultado de cada una.
    avg = pd.concat({k: v[["pnl", "min_intraday_pnl"]] for k, v in dailies.items()}, axis=1, sort=True).fillna(0)
    ens = pd.DataFrame({
        "pnl": avg.xs("pnl", axis=1, level=1).mean(axis=1),
        "min_intraday_pnl": avg.xs("min_intraday_pnl", axis=1, level=1).mean(axis=1),
    })
    corr = avg.xs("pnl", axis=1, level=1).corr().round(2)

    table = pd.DataFrame(rows)
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"{args.estrategia}_{args.periodo}.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# {title} — periodo {args.periodo.upper()} ({start} → {end or 'hoy'})\n\n")
        f.write("## Variantes\n\n" + table.to_markdown(index=False) + "\n\n")
        f.write(f"## Promedio de las {len(dailies)} variantes (riesgo repartido)\n\n")
        f.write(f"- Beneficio neto: {ens.pnl.sum():.0f} $\n")
        eq = ens.pnl.cumsum()
        f.write(f"- Drawdown máximo: {(eq - eq.cummax()).min():.0f} $\n")
        f.write(f"- % días ganadores (con operaciones): {(ens.pnl[ens.pnl != 0] > 0).mean() * 100:.1f} %\n\n")
        f.write("## Correlación diaria entre variantes\n\n" + corr.to_markdown() + "\n")
    print(f"\nInforme guardado en {out}")


if __name__ == "__main__":
    main()
