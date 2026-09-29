"""Cartera de las dos estrategias validadas en el Nasdaq: ZONA_RUIDO_MNQ_v1.0 (intradía) + RSI(2) (swing), 1 MNQ cada una.

Solo combina resultados ya obtenidos con las reglas registradas; no cambia ninguna regla.
Uso: python -m src.report.cartera   →   reports/CARTERA_NQ_v1.0/ (nunca se sobrescribe).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.data.datos import excluidos, velas_1m  # noqa: E402
from src.horas import NUEVA_YORK  # noqa: E402
from src.metrics.metricas import racha  # noqa: E402
from src.strategies import nq_rsi2, zona_ruido  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent.parent
RECIENTE = pd.Period("2023-04", "M")          # precios parecidos a los actuales (fuera de muestra de ambas)


def mensual():
    m1 = velas_1m("NQ")
    excl = excluidos("NQ")
    zo, _ = zona_ruido.backtest(m1, zona_ruido.Config(), excl)
    rs = nq_rsi2.backtest(m1, nq_rsi2.Config(), excl)
    mz = zo.groupby(pd.to_datetime(zo.fecha).dt.to_period("M")).neto.sum()
    mr = rs.groupby(pd.DatetimeIndex(rs.t_salida).tz_convert(NUEVA_YORK).tz_localize(None).to_period("M")).neto.sum()
    idx = pd.period_range(min(mz.index.min(), mr.index.min()), max(mz.index.max(), mr.index.max()), freq="M")
    return pd.DataFrame({"zona_ruido": mz.reindex(idx, fill_value=0.0), "rsi2": mr.reindex(idx, fill_value=0.0)})


def resumen(s: pd.Series) -> dict:
    eq = s.cumsum()
    tri = s.rolling(3).sum().dropna()
    return {"meses": len(s), "meses_positivos_%": round((s > 0).mean() * 100, 1), "media_mes_usd": round(s.mean(), 0),
            "mediana_mes_usd": round(s.median(), 0), "p10_mes_usd": round(np.percentile(s, 10), 0),
            "peor_mes_usd": round(s.min(), 0), "mejor_mes_usd": round(s.max(), 0),
            "trimestres_positivos_%": round((tri > 0).mean() * 100, 1),
            "drawdown_max_usd": round((eq - eq.cummax()).min(), 0),
            "racha_meses_negativos": racha(s <= 0)}


def ejecutar():
    m = mensual()
    m["cartera"] = m.zona_ruido + m.rsi2
    out, k = RAIZ / "reports" / "CARTERA_NQ_v1.0", 2
    while out.exists():
        out, k = RAIZ / "reports" / f"CARTERA_NQ_v1.0_v{k}", k + 1
    out.mkdir(parents=True)
    todo = pd.DataFrame({c: resumen(m[c]) for c in m}).T
    rec = pd.DataFrame({c: resumen(m.loc[m.index >= RECIENTE, c]) for c in m}).T
    anual = m.groupby(m.index.year).sum().round(0)
    m.to_csv(out / "monthly.csv")
    fig, ax = plt.subplots(figsize=(9, 4))
    colores = {"zona_ruido": "#2a78d6", "rsi2": "#1a9e77", "cartera": "#222222"}
    for c in m:
        ax.plot(m.index.to_timestamp(), m[c].cumsum(), lw=2.5 if c == "cartera" else 1.5, color=colores[c], label=c)
    ax.set_title("Beneficio acumulado, 1 MNQ por estrategia ($, tras costes)", loc="left")
    ax.legend(frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color="#eee")
    fig.tight_layout()
    fig.savefig(out / "equity.png", dpi=120)
    plt.close(fig)
    corr = round(np.corrcoef(m.zona_ruido, m.rsi2)[0, 1], 2)
    (out / "README.md").write_text("\n".join([
        "# Cartera NQ: zona de ruido + RSI(2) (1 MNQ cada una)", "",
        "Combina los resultados de las dos estrategias validadas, con sus reglas registradas y sin ningún cambio "
        "(`edges/zona_ruido_mnq.md`, `edges/nq_rsi2.md`).", "",
        "- **Costes:** los de cada estudio.",
        "- **Mes:** el de la salida de cada operación.",
        "- **Días excluidos:** las sesiones ilíquidas previsibles.", "",
        f"**Correlación mensual entre las dos: {corr}.** Casi nula: los meses malos de una no coinciden con los de la "
        "otra.", "",
        "## 2015-2026", "", todo.to_markdown(), "",
        f"## Desde {RECIENTE} (precios parecidos a los actuales)", "", rec.to_markdown(), "",
        "## Por año ($)", "", anual.to_markdown(), "",
        "![Beneficio acumulado](equity.png)", "",
        "Aviso: en las dos estrategias el fuera de muestra ya se ha mirado. La prueba que falta es la prueba en papel "
        "(ver `PLAN_OPERATIVO.md`)."]) + "\n")
    print(todo.to_string())
    print(rec.to_string())
    print("correlación", corr)
    print(anual.to_string())


if __name__ == "__main__":
    ejecutar()
