"""Estudio completo de una estrategia con criterios de aprobación fijados de antemano.

Uso:
    python scripts/run_study.py --estudio orb_final   # config/orb_5m_final.yaml
    python scripts/run_study.py --estudio cm          # config/close_momentum.yaml

Para cada variante: métricas en el periodo completo, en desarrollo (70 % inicial) y fuera de muestra
(30 % final); estadístico t; comisiones frente a ganancia bruta; sensibilidad a 1 tick de deslizamiento
en la salida por tiempo; resultados por año; simulación de la cuenta Apex con trailing intradía y
Monte Carlo reordenando operaciones. Al final, ¿cumple los criterios? SÍ / NO.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data.loader import load_clean  # noqa: E402
from src.risk.apex_trailing import TrailingAccount, monte_carlo, path_summary, run_sequence  # noqa: E402
from src.strategies import close_momentum_5m as cm  # noqa: E402
from src.strategies import orb_5m as orb  # noqa: E402
from src.validation.metrics import trade_list_stats  # noqa: E402

STUDIES = {"orb_final": "config/orb_5m_final.yaml", "cm": "config/close_momentum.yaml"}


def t_stat(trades: pd.DataFrame) -> float:
    """t de la expectativa por operación medida en R. |t| > 2 ≈ difícil de explicar solo por azar."""
    if len(trades) < 2:
        return float("nan")
    r = trades.pnl / trades.risk_usd
    return round(r.mean() / r.std() * np.sqrt(len(r)), 2)


def build(study: str, raw: dict):
    """Devuelve (lista de configuraciones de variantes, función que ejecuta una variante)."""
    val = raw["validacion"]
    start = pd.Timestamp(val["fecha_inicio"])
    warmup = (start - pd.Timedelta(days=40)).strftime("%Y-%m-%d")
    minutes = load_clean(raw["instrumento"]["datos"], warmup, val["fecha_fin"])
    atr = orb.daily_atr(minutes, raw["atr_dias"] if "atr_dias" in raw else raw["filtro_rango_atr"]["atr_dias"])
    keep = minutes.index >= pd.Timestamp(start, tz=minutes.index.tz)
    if study == "orb_final":
        base = orb.ORB5Config.from_yaml(STUDIES[study])
        bars = orb.to_bars(minutes[keep], base.bar_minutes)
        news = orb.load_news_dates(base)
        variants = [base.variant(or_minutes=m, target_r=t, risk_usd=r, news_filter=n)
                    for m in val["variantes_rango"] for t in val["variantes_target"]
                    for r in val["variantes_riesgo_usd"] for n in val["variantes_noticias"]]
        return variants, (lambda cfg: orb.backtest(bars, atr, cfg, news)), bars
    base = cm.CMConfig.from_yaml(STUDIES[study])
    variants = [base.variant(risk_usd=r) for r in val["variantes_riesgo_usd"]]
    return variants, (lambda cfg: cm.backtest(minutes[keep], atr, cfg)), minutes[keep]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--estudio", choices=STUDIES, required=True)
    args = ap.parse_args()
    raw = yaml.safe_load(open(ROOT / STUDIES[args.estudio], encoding="utf-8"))
    val, apex, crit = raw["validacion"], raw["apex"], raw["criterios"]
    account = TrailingAccount(apex["saldo_inicial"], apex["drawdown_trailing_usd"], apex["trailing_se_detiene_en"])

    variants, run, data = build(args.estudio, raw)
    dates = sorted(set(data.index.date))
    cut = pd.Timestamp(dates[int(len(dates) * val["fraccion_desarrollo"])])
    print(f"Datos {dates[0]} -> {dates[-1]} ({len(dates)} días). Desarrollo hasta {cut.date()} (excluido).", flush=True)

    rows, yearly, reasons = [], {}, {}
    for cfg in variants:
        trades, days, paths = run(cfg)
        dev, oos = trades[trades.date < cut], trades[trades.date >= cut]
        full = trade_list_stats(trades)
        slip1, _, _ = run(cfg.variant(slip_time_exit=1))
        burns = run_sequence(paths, account, restart=True)
        mc = monte_carlo(path_summary(paths), account, val["montecarlo_simulaciones"], val["semilla"])
        row = {
            "variante": cfg.label, **full, "t": t_stat(trades),
            "neto_desarrollo": round(dev.pnl.sum()), "t_desarrollo": t_stat(dev),
            "neto_oos": round(oos.pnl.sum()), "t_oos": t_stat(oos),
            "neto_con_1tick_en_salida": round(slip1.pnl.sum()),
            "cuentas_quemadas": len(burns),
            "primera_quema": trades.iloc[burns[0]["trade_idx"]].date.date() if burns else None,
            **mc,
        }
        row["CUMPLE"] = "SÍ" if (full["profit_factor"] > crit["profit_factor_min"] and row["t"] > crit["t_min"]
                                 and (not crit["positivo_en_desarrollo_y_oos"]
                                      or (row["neto_desarrollo"] > 0 and row["neto_oos"] > 0))) else "NO"
        rows.append(row)
        yearly[cfg.label] = trades.groupby(trades.date.dt.year).pnl.sum().round(0)
        reasons[cfg.label] = days.status.value_counts()
        print(f"{cfg.label:34s} ops={full['operaciones']} neto={full['beneficio_neto']} bruto={full['beneficio_bruto']} "
              f"comis={full['comisiones']} PF={full['profit_factor']} t={row['t']} dev={row['neto_desarrollo']} "
              f"oos={row['neto_oos']} MC={mc['prob_quemar_%']}% -> {row['CUMPLE']}", flush=True)

    table = pd.DataFrame(rows)
    out = ROOT / "reports" / f"estudio_{args.estudio}.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# Estudio {args.estudio} ({dates[0]} → {dates[-1]})\n\n")
        f.write(f"Configuración: `{STUDIES[args.estudio]}`. Desarrollo: hasta {cut.date()}; fuera de muestra: desde {cut.date()}.\n\n")
        f.write(f"Criterios (todos): profit factor > {crit['profit_factor_min']}, t > {crit['t_min']}, "
                "neto positivo en desarrollo y fuera de muestra.\n\n")
        f.write("## Variantes\n\n" + table.to_markdown(index=False) + "\n\n")
        f.write("## Beneficio neto por año ($)\n\n" + pd.DataFrame(yearly).fillna(0).astype(int).to_markdown() + "\n\n")
        f.write("## Días operados y motivos para no operar\n\n" + pd.DataFrame(reasons).fillna(0).astype(int).to_markdown() + "\n")
    print(f"\nInforme: {out}")


if __name__ == "__main__":
    main()
