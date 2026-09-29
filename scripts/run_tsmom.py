"""Backtest del seguimiento de tendencia en una cesta de futuros (config/tsmom.yaml).

Muestra: rentabilidad, volatilidad, Sharpe, t, drawdown, profit factor mensual, resultados por año,
por periodo (desarrollo / fuera de muestra), por mercado, y la correlación con el S&P 500 (ES).
"""
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.strategies.tsmom import load_returns, portfolio, stats, weights  # noqa: E402


def main() -> None:
    c = yaml.safe_load(open(ROOT / "config" / "tsmom.yaml", encoding="utf-8"))
    rets, rolls = load_returns(c["mercados"])
    print(f"Mercados con datos: {len(rets.columns)} de {len(c['mercados'])}: {', '.join(rets.columns)}")
    w = weights(rets, tuple(c["senal_lookbacks_dias"]), c["vol_dias"], c["vol_objetivo_por_mercado"])
    pf = portfolio(rets, rolls, w, c["coste_bps"])
    pf = pf[pf.index >= c["fecha_inicio"]]
    cut = pf.index[int(len(pf) * c["fraccion_desarrollo"])]
    rows = {"completo (neto)": stats(pf.neto), "completo (bruto)": stats(pf.bruto),
            f"desarrollo (< {cut.date()})": stats(pf.neto[pf.index < cut]),
            f"fuera de muestra (>= {cut.date()})": stats(pf.neto[pf.index >= cut])}
    table = pd.DataFrame(rows).T
    yearly = ((1 + pf.neto).groupby(pf.index.year).prod() - 1).mul(100).round(1)
    es = rets["ES"].reindex(pf.index) if "ES" in rets else None
    es_year = ((1 + es.fillna(0)).groupby(pf.index.year).prod() - 1).mul(100).round(1) if es is not None else None
    per_market = (w * rets.fillna(0)).reindex(pf.index).sum().mul(100).round(1).sort_values()
    full, crit = rows["completo (neto)"], c["criterios"]
    dev, oos = list(rows.values())[2], list(rows.values())[3]
    ok = full["t"] > crit["t_min"] and full["pf_mensual"] > crit["pf_mensual_min"] and \
        (not crit["positivo_en_desarrollo_y_oos"] or (dev["rend_anual_%"] > 0 and oos["rend_anual_%"] > 0))
    corr = pf.neto.corr(es) if es is not None else None

    out = ROOT / "reports" / "estudio_tsmom.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# Seguimiento de tendencia en {len(rets.columns)} futuros ({pf.index[0].date()} → {pf.index[-1].date()})\n\n")
        f.write(table.to_markdown() + "\n\n")
        f.write(f"Correlación diaria con el S&P 500 (ES): {corr:.2f}\n\n")
        f.write(f"**¿Cumple los criterios? {'SÍ' if ok else 'NO'}**\n\n")
        f.write("## Rendimiento por año (%): estrategia vs. S&P 500\n\n")
        f.write(pd.DataFrame({"tendencia": yearly, "S&P 500 (ES)": es_year}).to_markdown() + "\n\n")
        f.write("## Contribución acumulada por mercado (% de capital, sin costes)\n\n" + per_market.to_markdown() + "\n")
    print(table.to_string())
    print(f"\nCorrelación con ES: {corr:.2f} | ¿Cumple? {'SÍ' if ok else 'NO'}")
    print(pd.DataFrame({"tendencia": yearly, "S&P 500": es_year}).T.to_string())
    print(f"\nInforme: {out}")


if __name__ == "__main__":
    main()
