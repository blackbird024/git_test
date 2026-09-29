"""Backtest completo de la ORB de 5 minutos en MNQ (parámetros en config/orb_5m.yaml).

Uso:
    python scripts/run_orb_5m.py --periodo desarrollo   # primeros 70 % de los días
    python scripts/run_orb_5m.py --periodo oos          # 30 % final: SOLO al final, una vez

Para cada variante (rango 5/15/30 min x objetivo 1,5R/2R/3R/solo tiempo x con/sin filtro de noticias):
métricas, resultados por año, simulación de la cuenta Apex con trailing intradía (¿cuándo se quema?)
y Monte Carlo reordenando operaciones (probabilidad de tocar el drawdown).
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data.loader import load_clean  # noqa: E402
from src.risk.apex_trailing import TrailingAccount, monte_carlo, path_summary, run_sequence  # noqa: E402
from src.strategies.orb_5m import ORB5Config, backtest, daily_atr, load_news_dates, to_bars  # noqa: E402
from src.validation.metrics import trade_list_stats  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--periodo", choices=("desarrollo", "oos"), required=True)
    args = ap.parse_args()

    raw = yaml.safe_load(open(ROOT / "config" / "orb_5m.yaml", encoding="utf-8"))
    val, apex = raw["validacion"], raw["apex"]
    base = ORB5Config.from_yaml()
    account = TrailingAccount(apex["saldo_inicial"], apex["drawdown_trailing_usd"], apex["trailing_se_detiene_en"])

    start = pd.Timestamp(val["fecha_inicio"])
    warmup = (start - pd.Timedelta(days=40)).strftime("%Y-%m-%d")
    minutes = load_clean(raw["instrumento"]["datos"], warmup, val["fecha_fin"])
    bars = to_bars(minutes, base.bar_minutes)
    atr = daily_atr(minutes, base.atr_days)
    news = load_news_dates(base)

    dates = sorted(d for d in set(bars.index.date) if d >= start.date())
    cut = dates[int(len(dates) * val["fraccion_desarrollo"])]
    period = [d for d in dates if (d < cut) == (args.periodo == "desarrollo")]
    sel = bars[[d in set(period) for d in bars.index.date]]
    print(f"Periodo {args.periodo}: {period[0]} -> {period[-1]} ({len(period)} días). Corte en {cut}.", flush=True)

    rows, yearly, reasons = [], {}, None
    for news_filter in (False, True):
        for orm in val["variantes_rango"]:
            for tgt in val["variantes_target"]:
                cfg = base.variant(or_minutes=orm, target_r=tgt, news_filter=news_filter)
                trades, days, paths = backtest(sel, atr, cfg, news)
                stats = trade_list_stats(trades)
                burns = run_sequence(paths, account, restart=True)
                first_burn = trades.iloc[burns[0]["trade_idx"]].date.date() if burns else None
                mc = monte_carlo(path_summary(paths), account, val["montecarlo_simulaciones"], val["semilla"]) \
                    if paths else {}
                rows.append({"variante": cfg.label, **stats, "cuentas_quemadas": len(burns),
                             "primera_quema": first_burn, **mc})
                if not trades.empty:
                    yearly[cfg.label] = trades.groupby(trades.date.dt.year).pnl.sum().round(0)
                if cfg.or_minutes == base.or_minutes and cfg.target_r == base.target_r and not news_filter:
                    reasons = days.status.value_counts()
                    base_trades = trades
                print(f"{cfg.label:24s} ops={stats.get('operaciones')} neto={stats.get('beneficio_neto')} "
                      f"PF={stats.get('profit_factor')} quemas={len(burns)} MC={mc.get('prob_quemar_%')}%",
                      flush=True)

    table = pd.DataFrame(rows)
    by_year = pd.DataFrame(yearly).fillna(0).astype(int)
    base_year = base_trades.groupby(base_trades.date.dt.year).apply(
        lambda t: pd.Series(trade_list_stats(t))).drop(columns=["racha_perdedora_max"], errors="ignore")

    out = ROOT / "reports" / f"orb_5m_{args.periodo}.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# ORB 5 min en MNQ — {args.periodo} ({period[0]} → {period[-1]}, {len(period)} días)\n\n")
        f.write(f"Parámetros base: {base}\n\n")
        f.write("## Todas las variantes\n\n" + table.to_markdown(index=False) + "\n\n")
        f.write(f"## Variante base ({base.label}) por año\n\n" + base_year.to_markdown() + "\n\n")
        f.write("## Beneficio neto por año y variante ($)\n\n" + by_year.to_markdown() + "\n\n")
        f.write(f"## Días de la variante base: operados y motivos para no operar\n\n{reasons.to_markdown()}\n")
    print(f"\nInforme: {out}")


if __name__ == "__main__":
    main()
