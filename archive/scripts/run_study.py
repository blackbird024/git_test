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
from src.strategies import gold_ict  # noqa: E402
from src.strategies import intraday_vwap as iv  # noqa: E402
from src.strategies import ma_cross as ma  # noqa: E402
from src.strategies import noise_area  # noqa: E402
from src.strategies import orb_5m as orb  # noqa: E402
from src.strategies import po3  # noqa: E402
from src.validation.metrics import trade_list_stats  # noqa: E402

STUDIES = {"orb_final": "config/orb_5m_final.yaml", "cm": "config/close_momentum.yaml",
           "mr": "config/mean_reversion.yaml", "vwap_mgc": "config/vwap_mgc.yaml",
           "po3_mnq": "config/po3_mnq.yaml", "po3_mgc": "config/po3_mgc.yaml",
           "ma_mnq": "config/ma_mnq.yaml", "ma_mgc": "config/ma_mgc.yaml",
           "gold_ict": "config/gold_ict.yaml", "noise_area": "config/noise_area.yaml",
           "macd_mnq": "config/macd_mnq.yaml", "macd_mgc": "config/macd_mgc.yaml"}


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
    if study == "noise_area":
        base = noise_area.NoiseConfig.from_yaml(STUDIES[study])
        variants = []
        for hs in val["variantes_stop_duro"]:
            variants.append(base.variant(hard_stop=hs))
            variants.append(base.variant(hard_stop=hs, fixed_contracts=val["diagnostico_contratos_fijos"]))

        def run_noise(cfg):  # necesita 14 días previos para sigma: se usan todos los datos y se recorta
            t, dd, pp = noise_area.backtest(minutes, atr, cfg)
            if t.empty:
                return t, dd, pp
            k = (t.date >= start).to_numpy()
            return t[k].reset_index(drop=True), dd[dd.date >= start], [p for p, x in zip(pp, k) if x]
        return variants, run_noise, minutes[keep]
    if study == "gold_ict":
        base = gold_ict.GoldICTConfig.from_yaml(STUDIES[study])
        silver = None
        if True in val["variantes_smt"]:
            silver = load_clean(raw["instrumento"]["datos_smt"], warmup, val["fecha_fin"])
        variants = []
        for bm in val["variantes_velas"]:
            for smt in val["variantes_smt"]:
                variants.append(base.variant(bar_minutes=bm, smt=smt))
                variants.append(base.variant(bar_minutes=bm, smt=smt, fixed_contracts=val["diagnostico_contratos_fijos"]))
        # El contexto (día anterior, EMA diaria y de 4H) necesita historia previa: se pasan todos los datos
        # y se descartan después las operaciones anteriores a fecha_inicio.
        def run_gold(cfg):
            t, dd, pp = gold_ict.backtest(minutes, atr, cfg, silver)
            if t.empty:
                return t, dd, pp
            keep_t = (t.date >= start).to_numpy()
            return t[keep_t].reset_index(drop=True), dd[dd.date >= start], [p for p, k in zip(pp, keep_t) if k]
        return variants, run_gold, minutes[keep]
    if study.startswith("macd_"):
        base = ma.MAConfig.from_yaml(STUDIES[study])
        variants = []
        for bm in val["variantes_velas"]:
            for mode in val["variantes_senal"]:
                variants.append(base.variant(bar_minutes=bm, signal_mode=mode))
                variants.append(base.variant(bar_minutes=bm, signal_mode=mode, fixed_contracts=val["diagnostico_contratos_fijos"]))
        return variants, (lambda cfg: ma.backtest(minutes[keep], atr, cfg)), minutes[keep]
    if study.startswith("ma_"):
        base = ma.MAConfig.from_yaml(STUDIES[study])
        variants = []
        for fast, slow in val["variantes_medias"]:
            for a in val["variantes_adx"]:
                variants.append(base.variant(fast=fast, slow=slow, adx_min=a))
                variants.append(base.variant(fast=fast, slow=slow, adx_min=a, fixed_contracts=val["diagnostico_contratos_fijos"]))
        return variants, (lambda cfg: ma.backtest(minutes[keep], atr, cfg)), minutes[keep]
    if study.startswith("po3"):
        base = po3.PO3Config.from_yaml(STUDIES[study])
        variants = []
        for e in val["variantes_entrada"]:
            for t in val["variantes_target"]:
                variants.append(base.variant(entry_mode=e, target_r=t))
                variants.append(base.variant(entry_mode=e, target_r=t, fixed_contracts=val["diagnostico_contratos_fijos"]))
        return variants, (lambda cfg: po3.backtest(minutes[keep], atr, cfg)), minutes[keep]
    if study == "cm":
        base = cm.CMConfig.from_yaml(STUDIES[study])
        variants = [base.variant(risk_usd=r) for r in val["variantes_riesgo_usd"]]
        return variants, (lambda cfg: cm.backtest(minutes[keep], atr, cfg)), minutes[keep]
    # Estudios VWAP: variantes del parámetro principal x riesgo, más el diagnóstico con contratos fijos.
    base, key, field = (iv.MRConfig.from_yaml(STUDIES[study]), "variantes_desviacion_atr", "deviation_atr") \
        if study == "mr" else (iv.VTConfig.from_yaml(STUDIES[study]), "variantes_stop_atr", "stop_atr")
    variants = []
    for k in val[key]:
        variants += [base.variant(**{field: k}, risk_usd=r) for r in val["variantes_riesgo_usd"]]
        if val.get("diagnostico_contratos_fijos"):
            variants.append(base.variant(**{field: k}, fixed_contracts=val["diagnostico_contratos_fijos"]))
    return variants, (lambda cfg: iv.backtest(minutes[keep], atr, cfg)), minutes[keep]


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
