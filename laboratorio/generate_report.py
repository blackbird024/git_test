"""Gráficos e informe de MNQ_ORB_RETEST_v1 a partir de los archivos que deja run_backtest.py / run_robustness.py.

  python generate_report.py --strategy MNQ_ORB_RETEST_v1
"""
import argparse
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from orb_retest.config import VERSION  # noqa: E402
from orb_retest.metrics import maxdd_quantile, ruin_probability  # noqa: E402
from orb_retest.pipeline import OUT  # noqa: E402

COL = {"desarrollo": "#3b6fb6", "validacion": "#d98a1e", "prueba": "#2a9d5c"}
plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": .3, "font.size": 9})


def fmt(x, d=3):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else (f"{x:+.{d}f}" if isinstance(x, float) else str(x))


def charts(t, daily, mon, yr, metrics, rob):
    t = t.sort_values("date")
    # 1 curva de equity en R
    fig, ax = plt.subplots(figsize=(9, 3.6))
    eq = t.R.cumsum()
    for p, c in COL.items():
        m = t.particion == p
        ax.plot(t.date[m], eq[m], ".-", color=c, label=p, ms=3, lw=1)
    ax.set_title("Curva de resultado acumulado (R, 1 contrato, coste base)")
    ax.set_ylabel("R acumulado")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "equity.png")
    plt.close(fig)
    # 2 drawdown
    fig, ax = plt.subplots(figsize=(9, 2.8))
    dd = eq - eq.cummax().clip(lower=0)
    ax.fill_between(t.date, dd, 0, color="#c0392b", alpha=.5, step="post")
    ax.set_title("Drawdown (R)")
    fig.tight_layout()
    fig.savefig(OUT / "drawdown.png")
    plt.close(fig)
    # 3 distribución de R
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.hist([t.R[t.particion == p] for p in COL], bins=np.arange(-2, 3.1, 0.25), stacked=True,
            color=list(COL.values()), label=list(COL))
    ax.set_title("Distribución del resultado por operación (R neto)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "distribucion_R.png")
    plt.close(fig)
    # 4 mensual
    fig, ax = plt.subplots(figsize=(10, 3))
    x = mon.copy()
    ax.bar(range(len(x)), x.R, color=[COL.get(p, "#999") for p in x.particion])
    ax.set_xticks(range(0, len(x), 6))
    ax.set_xticklabels(x.periodo.iloc[::6], rotation=60, fontsize=7)
    ax.set_title("Resultado mensual (R)")
    fig.tight_layout()
    fig.savefig(OUT / "mensual.png")
    plt.close(fig)
    # 5 anual
    fig, ax = plt.subplots(figsize=(6, 3))
    y = yr.groupby("periodo").agg(R=("R", "sum"), particion=("particion", "first"))
    ax.bar(y.index.astype(str), y.R, color=[COL.get(p, "#999") for p in y.particion])
    ax.set_title("Resultado anual (R)")
    fig.tight_layout()
    fig.savefig(OUT / "anual.png")
    plt.close(fig)
    # 6 comparación de particiones (E[R] e IC90, varios costes)
    fig, ax = plt.subplots(figsize=(7, 3.2))
    scs = ["sin_costes", "base", "base_2t", "estres"]
    w = .2
    for i, sc in enumerate(scs):
        for j, p in enumerate(COL):
            v = metrics["por_escenario_de_coste"][sc].get(p, {})
            er = v.get("esperanza_R", np.nan)
            ci = v.get("ic90_R", [np.nan, np.nan])
            yerr = None if any(c is None or np.isnan(c) for c in ci) else [[er - ci[0]], [ci[1] - er]]
            ax.bar(j + (i - 1.5) * w, er, w, yerr=yerr, capsize=2, label=sc if j == 0 else None,
                   color=plt.cm.viridis(i / 4))
    ax.axhline(0, color="k", lw=.8)
    ax.set_xticks(range(3))
    ax.set_xticklabels(list(COL))
    ax.set_title("Esperanza neta por operación (R) e IC90 bootstrap")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "particiones.png")
    plt.close(fig)
    # 7 sensibilidad (rejilla: desarrollo vs validación)
    g = rob[rob.variante.isin(["rejilla", "BASELINE"])]
    fig, ax = plt.subplots(figsize=(5.5, 4))
    sc = ax.scatter(g.desarrollo_ER, g.validacion_ER, c=g.tp_r, s=20 + 10 * g.tol_ticks, cmap="plasma")
    b = g[g.variante == "BASELINE"]
    ax.scatter(b.desarrollo_ER, b.validacion_ER, s=160, facecolors="none", edgecolors="k", label="baseline")
    ax.axhline(0, color="k", lw=.8)
    ax.axvline(0, color="k", lw=.8)
    ax.set_xlabel("E[R] desarrollo")
    ax.set_ylabel("E[R] validación")
    ax.set_title("36 variantes (tolerancia × ventana × objetivo)")
    plt.colorbar(sc, label="objetivo (R)")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "sensibilidad.png")
    plt.close(fig)


def table(rows, cols):
    h = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    return h + "".join("| " + " | ".join(str(c) for c in r) + " |\n" for r in rows)


def report(t, metrics, rob, conf):
    mb = metrics["por_escenario_de_coste"]["base"]
    parts = [p for p in ("desarrollo", "validacion", "prueba", "total_fuera_de_muestra") if p in mb]
    keys = [("sesiones", "Sesiones"), ("operaciones", "Operaciones"), ("ops_por_mes", "Ops/mes"),
            ("acierto", "Acierto"), ("esperanza_R", "E[R] neta"), ("ic90_R", "IC90 E[R]"),
            ("esperanza_R_bruta", "E[R] bruta"), ("profit_factor", "Profit factor"),
            ("esperanza_usd_1c", "E[$] 1 contrato"), ("ratio_ganancia_perdida", "Ganancia/pérdida media"),
            ("max_dd_R", "Máx. DD (R)"), ("duracion_max_dd_sesiones", "Duración máx. DD (sesiones)"),
            ("racha_perdedora_max", "Racha perdedora máx."), ("peor_mes_R", "Peor mes (R)"),
            ("meses_positivos", "Meses positivos"), ("riesgo_mediano_pts", "Stop mediano (pts)"),
            ("minutos_medios_en_posicion", "Minutos medios en posición"), ("ambiguas_sl_tp", "Ambiguas SL/TP"),
            ("stops_con_hueco", "Stops con hueco"), ("autocorr_lag1_R", "Autocorrelación R (1)")]

    def f(v):
        if isinstance(v, list):
            return "[" + ", ".join(fmt(x, 2) for x in v) + "]"
        if isinstance(v, float):
            return f"{v:.2f}" if abs(v) >= 10 else f"{v:.3f}"
        return str(v)
    rows = [[lbl] + [f(mb[p].get(k, "—")) for p in parts] for k, lbl in keys]
    md = [f"# {VERSION} · informe técnico\n",
          f"Ejecutado {conf['ejecutado']} · código `{conf['git']}` · reglas `{conf['strategy_hash']}` "
          f"(congeladas: {'sí' if conf.get('congelacion') else 'no'}) · prueba abierta: {conf['prueba_abierta']}\n",
          (OUT / "conclusion.md").read_text() if (OUT / "conclusion.md").exists() else "",
          "\n## Métricas por partición (coste base: 1 USD/lado + 1 tick por ejecución a mercado o stop)\n",
          table(rows, ["Métrica"] + parts),
          "\n## Sensibilidad a costes (E[R] neta por partición)\n"]
    cr = []
    for sc, v in metrics["por_escenario_de_coste"].items():
        cr.append([sc] + [fmt(v.get(p, {}).get("esperanza_R")) + f" (PF {v.get(p, {}).get('profit_factor', float('nan')):.2f})"
                          for p in parts])
    md.append(table(cr, ["Escenario"] + parts))
    md.append("\n## Tamaño por riesgo (USD; cada partición empieza de cero)\n")
    sr = []
    for b, v in metrics["tamano_por_riesgo"].items():
        for p, x in v.items():
            sr.append([f"{b} $", p, f"{x['neto_usd']:+.0f}", f"{x['contratos_medios']:.2f}", x["ops_sin_contrato"]])
    md.append(table(sr, ["Riesgo/op.", "Partición", "Neto USD", "Contratos medios", "Ops. sin contrato"]))
    # riesgo de ruina
    R = t.R.to_numpy()
    n_year = max(1, int(round(len(t) / ((t.date.max() - t.date.min()).days / 365.25))))
    rr = []
    for risk in (25, 50, 100):
        for lim in (1000, 2000):
            rr.append([f"{risk} $", f"{lim} $", f"{ruin_probability(R, risk, lim, n_year):.1%}",
                       f"{maxdd_quantile(R, n_year) * risk:.0f} $"])
    md.append(f"\n## Riesgo de ruina (Monte Carlo por bloques de 10 operaciones, {n_year} operaciones = 1 año)\n")
    md.append("Hipótesis: todas las operaciones 2018-2026 (coste base) representan el futuro; riesgo fijo por R; "
              "drawdown medido sobre el saldo tras cada operación. Con una esperanza ≈ 0 el resultado depende sobre todo "
              "de la varianza.\n\n")
    md.append(table(rr, ["Riesgo/op.", "Límite de DD", "P(alcanzar el límite en 1 año)", "DD al 95 % en 1 año"]))
    g = rob[rob.variante.isin(["rejilla", "BASELINE"])]
    both = int(((g.desarrollo_ER > 0) & (g.validacion_ER > 0)).sum())
    md.append(f"\n## Robustez\n\nVariantes evaluadas: {len(rob)} (rejilla completa de {len(g)}). Positivas en "
              f"desarrollo Y validación (coste base): **{both} de {len(g)}**. Detalle en `robustness.csv`.\n\n")
    cols = ["variante", "tol_ticks", "ventana", "tp_r", "hora_limite", "coste", "desarrollo_ops", "desarrollo_ER",
            "validacion_ops", "validacion_ER", "prueba_ops", "prueba_ER"]
    rows = [[r[c] if not isinstance(r[c], float) else (f"{r[c]:+.3f}" if "ER" in c else f"{r[c]:g}") for c in cols]
            for _, r in rob.iterrows() if r.variante != "rejilla"]
    md.append(table(rows, cols))
    for k in ("año", "lado", "or_width_pct_tercil", "vol20_prev_tercil", "roll_week"):
        p = OUT / f"desglose_{k}.csv"
        if p.exists():
            d = pd.read_csv(p)
            md.append(f"\n### Desglose por {k}\n\n")
            md.append(table([[r.particion, r[k], int(r.operaciones), f"{r.acierto:.2f}", f"{r.esperanza_R:+.3f}",
                              f"{r.R_total:+.1f}"] for _, r in d.iterrows()],
                            ["Partición", k, "Ops", "Acierto", "E[R]", "R total"]))
    md.append("\n## Gráficos\n\n" + "\n".join(f"![{x}]({x}.png)" for x in
                                              ("equity", "drawdown", "distribucion_R", "mensual", "anual",
                                               "particiones", "sensibilidad")) + "\n")
    (OUT / "report.md").write_text("".join(md))


def data_audit_md():
    a = json.loads((OUT / "data_audit.json").read_text())
    lines = ["# Auditoría de datos · MNQ_ORB_RETEST_v1\n",
             "Generada por `orb_retest/audit.py` (solo lectura). Datos en el entorno del laboratorio, no en el proyecto "
             "local descrito en el encargo (`src/engine/...`, 2015-2026, 4,1 M velas): esos archivos no existen aquí.\n"]
    for k, v in a.items():
        if isinstance(v, list) and len(v) > 12:
            v = f"{len(v)} elementos (lista completa en data_audit.json)"
        lines.append(f"- **{k}**: {v}")
    lines.append("\n**Notas**")
    lines.append("- Los ~1.800 'huecos > 60 min' son la pausa diaria de CME (17:00-18:00 ET): uno por sesión. No son "
                 "datos perdidos.")
    lines.append("- Las 3 sesiones con rango 9:30-9:44 incompleto (9, 12 y 16-mar-2020) corresponden a las suspensiones "
                 "por caída límite; el 9 y el 12 no se operan (regla: ≥ 14 de 15 minutos con datos).")
    lines.append("- NQ.c.0 es continuo por calendario SIN ajustar: cada sesión usa precios reales negociables del contrato "
                 "del día (ninguna sesión regular mezcla contratos). En la semana de vencimiento el continuo sigue en el "
                 "contrato que vence; esas sesiones se marcan (roll_week) y se desglosan, no se eliminan.")
    lines.append("- Festivos, medias jornadas y horario de verano: calendario XNYS (exchange_calendars) y conversión "
                 "UTC → America/New_York por fecha; la vela de 9:30 ET existe en todas las sesiones.")
    lines.append("- Precio de NQ usado como MNQ (mismo subyacente y misma rejilla de 0,25 pts). MNQ cotiza desde "
                 "may-2019: los años 2018-2019 son una aproximación con el contrato grande.")
    (OUT / "data_audit.md").write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default="MNQ_ORB_RETEST_v1")
    a = ap.parse_args()
    if not VERSION.startswith(a.strategy):
        raise SystemExit(f"Estrategia desconocida: {a.strategy}")
    t = pd.read_csv(OUT / "trades.csv", parse_dates=["date"])
    daily = pd.read_csv(OUT / "daily_results.csv", parse_dates=["date"])
    mon = pd.read_csv(OUT / "monthly_results.csv")
    yr = pd.read_csv(OUT / "yearly_results.csv")
    metrics = json.loads((OUT / "metrics.json").read_text())
    conf = json.loads((OUT / "backtest_config.json").read_text())
    rob = pd.read_csv(OUT / "robustness.csv")
    charts(t, daily, mon, yr, metrics, rob)
    data_audit_md()
    report(t, metrics, rob, conf)
    print("→", OUT / "report.md")


if __name__ == "__main__":
    main()
