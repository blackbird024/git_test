"""Exporta CSV, gráficos (matplotlib) e informe Markdown."""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .stats import breakdown


def _fmt(x):
    if isinstance(x, float):
        return f"{x:,.2f}" if abs(x) >= 1 else f"{x:.3f}"
    return str(x)


def _md_table(df: pd.DataFrame, cols=None):
    if cols:
        df = df[[c for c in cols if c in df.columns]]
    head = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns) + "\n"
    return head + "\n".join("| " + " | ".join(_fmt(v) for v in r) + " |" for r in df.itertuples(index=False))


def write_report(cfg, out) -> Path:
    stamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    d = Path(cfg.output_dir) / f"{cfg.instrument.symbol}_{stamp}"
    d.mkdir(parents=True, exist_ok=False)
    for name, (t, l) in out["results"].items():
        t.to_csv(d / f"operaciones_{name}.csv", index=False)
        l.to_csv(d / f"sesiones_{name}.csv", index=False)
        l[l.status.isin(["invalida", "descartada_riesgo", "descartada_hora", "descartada_hueco"])].to_csv(
            d / f"sesiones_excluidas_y_descartadas_{name}.csv", index=False)
    out["summary"].to_csv(d / "resumen.csv", index=False)
    (d / "manifest.json").write_text(json.dumps(out["manifest"], indent=2, ensure_ascii=False, default=str))
    (d / "bootstrap.json").write_text(json.dumps(out["bootstrap"], indent=2))
    # gráficos
    cap0 = cfg.risk.initial_capital
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw=dict(height_ratios=[3, 1.3]))
    for name, (t, _) in out["results"].items():
        if not len(t):
            continue
        x = pd.to_datetime(t["exit_time"].str[:19])
        eq = cap0 + t["net_usd"].cumsum()
        a1.step(x, eq, where="post", label=name)
        a2.step(x, (eq - np.maximum.accumulate(np.r_[cap0, eq.to_numpy()])[1:]), where="post")
    for k, (a, _) in out["periods"].items():
        for ax in (a1, a2):
            ax.axvline(pd.Timestamp(a), color="grey", ls="--", lw=0.8)
        a1.text(pd.Timestamp(a), a1.get_ylim()[1], " " + k, va="top", fontsize=8, color="grey")
    a1.set_title(f"{cfg.instrument.symbol} · ORB 1h + estructura 1h + entrada 5m · capital neto (USD)")
    a1.legend(); a1.grid(alpha=.3); a2.set_ylabel("Drawdown USD"); a2.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(d / "capital_y_drawdown.png", dpi=110); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4))
    for name, (t, _) in out["results"].items():
        if len(t):
            ax.hist(t["net_R"], bins=np.arange(-2, 3.01, 0.1), alpha=0.6, label=name)
    ax.set_title("Distribución del resultado neto por operación (R)"); ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(d / "distribucion_R.png", dpi=110); plt.close(fig)
    # informe
    m = out["manifest"]
    s = out["summary"]
    cols = ["version", "periodo", "sesiones_validas", "sesiones_sin_operacion", "operaciones", "acierto", "expectativa_R",
            "profit_factor", "resultado_neto", "comisiones", "slippage", "dd_max_usd", "dd_max_pct", "racha_perdedora_max",
            "duracion_media_min", "exposicion"]
    main = s[s.version.isin(["completa", "sin_filtro_1h"])]
    other = s[~s.version.isin(["completa", "sin_filtro_1h"])]
    lines = [f"# Informe ORB 1h + estructura 1h + entrada 5m — {cfg.instrument.symbol}", "",
             "**Aviso:** resultados de un backtest. No demuestran rentabilidad futura. "
             f"Costes: {cfg.costs.nota or 'ver configuración'}.", "",
             "## Datos", f"- Archivo: `{m['datos']['archivo']}` (sha256 `{m['datos']['sha256'][:16]}…`) — {m['datos']['etiqueta']}",
             f"- Filas: {m['datos']['filas']:,}; desde {m['datos']['primera']} hasta {m['datos']['ultima']}",
             f"- Avisos de validación: {'; '.join(m['validacion']['warnings']) or 'ninguno'}",
             f"- Calendario: {m['aviso_calendario'] or 'XNYS (exchange_calendars)'}",
             f"- Velas de 1 h válidas: {m['velas_1h']:,} (descartadas por incompletas: {m['velas_1h_descartadas_incompletas']}); "
             f"pivotes confirmados: {m['pivotes']}",
             f"- Periodos (60/20/20 por sesiones): " + ", ".join(f"{k} {a} → {b}" for k, (a, b) in out["periods"].items()), "",
             "## Resultados: estrategia completa frente a sin filtro 1H (solo cambia el filtro)", "", _md_table(main, cols), "",
             "## Pruebas de estrés de costes y sensibilidad", "", _md_table(other, cols), ""]
    for name, b in out["bootstrap"].items():
        if b.get("iid"):
            lines += [f"## Bootstrap ({name})",
                      f"- iid: R total p5/p50/p95 = {b['iid']['R_total']['p5']:.1f} / {b['iid']['R_total']['p50']:.1f} / "
                      f"{b['iid']['R_total']['p95']:.1f}; drawdown máx. en R p50/p95 = {b['iid']['dd_max_R']['p50']:.1f} / "
                      f"{b['iid']['dd_max_R']['p95']:.1f}; P(R total < 0) = {b['iid']['prob_R_total_negativo']:.1%}",
                      f"- bloques de 5: P(R total < 0) = {b['bloques_5']['prob_R_total_negativo']:.1%}; dd máx. R p95 = "
                      f"{b['bloques_5']['dd_max_R']['p95']:.1f}",
                      "- Limitaciones: supone que las operaciones futuras se parecen a las pasadas; el remuestreo iid ignora "
                      "la dependencia entre operaciones; no captura cambios de régimen.", ""]
    for name, (t, _) in out["results"].items():
        bd = breakdown(t)
        if not bd:
            continue
        lines += [f"## Desglose ({name})", ""]
        for k, v in bd.items():
            lines += [f"### Por {k.replace('_', ' ')}", "", _md_table(v.reset_index()), ""]
    lines += ["## Archivos", "- `operaciones_*.csv`: cada operación (sesgo, OR, ruptura, retesteo, entrada, stop, objetivo, "
              "contratos, riesgo, salida, bruto, comisiones, slippage, neto en USD y R, avisos)",
              "- `sesiones_*.csv` y `sesiones_excluidas_y_descartadas_*.csv`: estado y motivo de cada sesión",
              "- `resumen.csv`, `bootstrap.json`, `manifest.json` (configuración, datos y versión del código)",
              "- `capital_y_drawdown.png`, `distribucion_R.png`"]
    (d / "INFORME.md").write_text("\n".join(lines))
    return d
