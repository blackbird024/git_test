"""Verificación de ZONA_RUIDO_MNQ_v1.0 en el marco actual + rangos esperados para la prueba en papel.

Uso: python -m src.report.zona_ruido   →   reports/ZONA_RUIDO_MNQ_v1.0/ (nunca se sobrescribe).
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.data.datos import excluidos, inicio_fuera_de_muestra, velas_1m  # noqa: E402
from src.engine.lookahead import comprobar  # noqa: E402
from src.horas import ROMA  # noqa: E402
from src.metrics.metricas import racha  # noqa: E402
from src.strategies import zona_ruido as z  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent.parent


def metricas(o: pd.DataFrame, anios: float) -> dict:
    n = o.neto
    eq = n.cumsum().to_numpy()
    dd = eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]
    return {"operaciones": len(o), "por_año": round(len(o) / anios, 0), "acierto_%": round((n > 0).mean() * 100, 1),
            "profit_factor": round(n[n > 0].sum() / -n[n < 0].sum(), 3), "media_$": round(n.mean(), 2),
            "ganancia_media_$": round(n[n > 0].mean(), 1), "perdida_media_$": round(n[n < 0].mean(), 1),
            "t": round(n.mean() / n.std() * np.sqrt(len(n)), 2), "neto_$": round(n.sum(), 0),
            "drawdown_max_$": round(dd.min(), 0), "racha_perdedora": racha(n < 0), "racha_ganadora": racha(n > 0)}


def carpeta() -> Path:
    out, k = RAIZ / "reports" / z.VERSION, 2
    while out.exists():
        out, k = RAIZ / "reports" / f"{z.VERSION}_v{k}", k + 1
    return out


def ejecutar():
    m1 = velas_1m("NQ")
    cfg = z.Config()
    excl = excluidos("NQ")
    ops, dias = z.backtest(m1, cfg, excl)
    salida = carpeta()
    salida.mkdir(parents=True)

    # Look-ahead: las entradas anteriores a cada corte no cambian al añadir datos posteriores
    sabados = [pd.Timestamp(x, tz="UTC") for x in ("2016-06-11", "2018-10-13", "2020-05-16", "2022-10-15",
                                                    "2024-06-15", "2026-01-10")]
    probs = comprobar(lambda v: z.senales(v, cfg), m1, sabados)
    chk = pd.DatetimeIndex(ops.t_entrada)
    minuto = (chk.hour - 9) * 60 + chk.minute - 30
    solo_chequeos = bool(np.isin(minuto, cfg.chequeos).all())
    if probs or not solo_chequeos:
        (salida / "diagnostics.md").write_text("# LOOK-AHEAD DETECTADO — DETENIDO\n\n" + "\n".join(probs))
        print("LOOK-AHEAD: detenido")
        sys.exit(1)

    corte = inicio_fuera_de_muestra("NQ").date()
    dev, oos = ops[ops.fecha < corte], ops[ops.fecha >= corte]
    anio = lambda o: (pd.Timestamp(o.fecha.max()) - pd.Timestamp(o.fecha.min())).days / 365.25  # noqa: E731
    periodos = pd.DataFrame({"desarrollo (2015 → 21-mar-2023)": metricas(dev, anio(dev)),
                             "fuera de muestra (22-mar-2023 → 2026)": metricas(oos, anio(oos)),
                             "total": metricas(ops, anio(ops))}).T

    f = pd.to_datetime(ops.fecha)
    anual = ops.groupby(f.dt.year).neto.agg(operaciones="size", neto_usd="sum",
                                            acierto=lambda x: round((x > 0).mean() * 100, 1)).round(0)
    mensual = ops.groupby(f.dt.to_period("M")).neto.sum()
    tri = mensual.rolling(3).sum().dropna()
    # Drawdown dentro de cada ventana de 3 meses (sobre el P&L diario)
    diario = ops.groupby(f).neto.sum()
    dd3 = []
    for inicio in pd.date_range(diario.index.min(), diario.index.max() - pd.DateOffset(months=3), freq="MS"):
        v = diario[(diario.index >= inicio) & (diario.index < inicio + pd.DateOffset(months=3))].cumsum().to_numpy()
        if len(v):
            dd3.append((v - np.maximum.accumulate(np.r_[0.0, v])[1:]).min())
    q = [5, 25, 50, 75, 95]
    esperado = pd.DataFrame({
        "P&L de 1 mes ($, 1 MNQ)": np.percentile(mensual, q).round(0),
        "P&L de 3 meses ($)": np.percentile(tri, q).round(0),
        "Peor caída dentro de 3 meses ($)": np.percentile(dd3, [95, 75, 50, 25, 5]).round(0),
    }, index=[f"p{x}" for x in q]).T
    pct_pos = {"meses positivos %": round((mensual > 0).mean() * 100, 1),
               "trimestres positivos %": round((tri > 0).mean() * 100, 1)}

    roma = pd.DatetimeIndex(ops.t_entrada).tz_convert(ROMA)
    por_hora = ops.groupby(roma.strftime("%H:%M")).neto.agg(operaciones="size", media_usd="mean").round(1)
    motivos = ops.motivo.value_counts()

    ops.to_csv(salida / "trades.csv", index=False)
    periodos.to_csv(salida / "summary.csv")
    anual.to_csv(salida / "yearly.csv")
    esperado.to_csv(salida / "expected_ranges.csv")
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(pd.to_datetime(ops.fecha), ops.neto.cumsum(), lw=2, color="#2a78d6", drawstyle="steps-post")
    ax.axvline(pd.Timestamp(corte), color="#888", lw=1, ls="--")
    ax.text(pd.Timestamp(corte), ax.get_ylim()[1] * 0.95, "  fuera de muestra →", color="#555")
    ax.set_title(f"{z.VERSION}: beneficio acumulado con 1 MNQ ($, tras costes)", loc="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color="#eee")
    fig.tight_layout()
    fig.savefig(salida / "equity_curve.png", dpi=120)
    plt.close(fig)

    md = lambda d, i=True: d.to_markdown(index=i)  # noqa: E731
    (salida / "README.md").write_text("\n".join([
        f"# {z.VERSION}: verificación en el marco actual", "",
        "Reglas: `edges/zona_ruido_mnq.md`. Código: `src/strategies/zona_ruido.py`. 1 MNQ fijo; costes: 1 tick por lado "
        "+ 1 $ por contrato y lado. Sesiones ilíquidas previsibles excluidas.", "",
        "## Auditoría de look-ahead", "",
        f"- Truncamiento (6 cortes en sábado, 2016-2026): {'OK, sin diferencias' if not probs else probs}.",
        "- Todas las entradas ocurren en un chequeo de media hora (10:00-15:30 NY) y deciden con el cierre del minuto "
        "anterior: OK.",
        "- Sigma de cada día calculada solo con los 14 días anteriores (`shift`), y cierre anterior sin hueco en los "
        "días de cambio de contrato (pruebas en `tests/test_zona_ruido.py`).", "",
        "## Resultados por periodo", "", md(periodos), "",
        "El fuera de muestra ya se había visto en el estudio original (archivo): no es virgen. La prueba honesta que "
        "queda es la prueba hacia delante en papel.", "",
        "## Por año", "", md(anual), "",
        "## Qué esperar en papel (distribución histórica, 1 MNQ)", "", md(esperado), "",
        f"Meses positivos: {pct_pos['meses positivos %']} %. Ventanas de 3 meses positivas: "
        f"{pct_pos['trimestres positivos %']} %.", "",
        "**Criterios de la prueba en papel (ver ficha):** el P&L de 3 meses no debe quedar por debajo del p5 de 3 meses "
        f"({esperado.loc['P&L de 3 meses ($)', 'p5']:.0f} $); se abandona antes si la caída desde el máximo supera el "
        f"p95 de la peor caída en 3 meses ({esperado.loc['Peor caída dentro de 3 meses ($)', 'p95']:.0f} $).", "",
        "## Motivos de salida", "", md(motivos.rename_axis("motivo").reset_index(name="n"), False), "",
        "## Entradas por hora de Italia", "", md(por_hora), "",
        "![Beneficio acumulado](equity_curve.png)", ""]))
    print("Informe en", salida)
    print(periodos.to_string())
    print(esperado.to_string())
    print(pct_pos)


if __name__ == "__main__":
    ejecutar()
