"""Informe final en Markdown + gráficos a partir de los CSV de results/."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml


def _t(df, cols=None, nd=3):
    if cols:
        df = df[[c for c in cols if c in df.columns]]
    fmt = lambda v: (f"{v:,.{nd}f}" if isinstance(v, (float, np.floating)) and not np.isnan(v) else ("—" if isinstance(v, float) else str(v)))
    return "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns) + "\n" + \
        "\n".join("| " + " | ".join(fmt(v) for v in r) + " |" for r in df.itertuples(index=False))


def write(cfg, out: Path):
    frozen = yaml.safe_load((out / "reglas_congeladas.yaml").read_text())
    L = ["# Laboratorio VWAP + EMA (MNQ, MGC) — informe final", "",
         "Resultados históricos de backtest. No son una previsión. Costes: " + cfg["costs"]["nota"] + ".", ""]
    summ = []
    for key, fz in frozen.items():
        if fz.get("estado") != "OK":
            summ.append(f"- **{key}: BLOQUEADO** — {fz['motivo']}")
            continue
        c = fz["candidatos"]
        summ.append(f"- **{key}:** {'candidatos: ' + ', '.join(c) if c else 'ningún candidato (ninguna configuración con esperanza > 0 en desarrollo y ≥ 30 operaciones en validación)'}")
    L += ["## A. Resumen ejecutivo", ""] + summ + [""]
    for key, fz in frozen.items():
        if fz.get("estado") != "OK":
            continue
        d = out / key
        L += [f"## {key}", ""]
        grid = pd.read_csv(d / "rejilla_desarrollo_validacion.csv")
        L += [f"Periodos: " + ", ".join(f"{k} {a} → {b}" for k, (a, b) in fz["periodos"].items()), "",
              f"Configuraciones probadas en desarrollo + validación: {len(grid)}; con esperanza > 0 en desarrollo: "
              f"{int((grid.desarrollo_esperanza_R > 0).sum())}; en validación: {int((grid.validacion_esperanza_R > 0).sum())}; en ambas: "
              f"{int(((grid.desarrollo_esperanza_R > 0) & (grid.validacion_esperanza_R > 0)).sum())}.", ""]
        best = grid.sort_values("validacion_esperanza_R", ascending=False).groupby("estrategia").head(1)
        L += ["### B. Ranking (mejor configuración de cada estrategia según validación; solo descriptivo)", "",
              _t(best.sort_values("validacion_esperanza_R", ascending=False),
                 ["estrategia", "umbral", "objetivo_R", "desarrollo_n", "desarrollo_esperanza_R", "validacion_n",
                  "validacion_esperanza_R", "validacion_pf", "validacion_dd_usd"]), ""]
        r = pd.read_csv(d / "resultados_dev_val_oos.csv")
        part = r[r.config.str.contains("partida")]
        piv = part.pivot_table(index=["estrategia", "costes"], columns="periodo", values="esperanza_R").reset_index()
        L += ["### Configuración de partida (umbral 0,10, objetivo 2R): esperanza en R por periodo y escenario de costes", "",
              _t(piv[["estrategia", "costes", "desarrollo", "validacion", "oos"]]), ""]
        ob = part[(part.costes == "base")][["estrategia", "periodo", "n", "acierto", "esperanza_R", "esperanza_usd", "pf",
                                            "neto", "costes", "costes_pct_bruto_positivo", "dd_usd", "dd_pct", "racha_perdedora",
                                            "ops_por_sesion", "exposicion", "ambiguas", "ic90_R_bajo", "ic90_R_alto"]]
        L += ["### Métricas completas de la configuración de partida (costes base)", "", _t(ob), ""]
        a = pd.read_csv(d / "ablacion_filtro_vwap.csv")
        L += ["### D. Filtro de VWAP plano (objetivo 2R)", "", _t(a), ""]
        wf = pd.read_csv(d / "walk_forward.csv")
        wfs = wf.groupby("estrategia").agg(años=("año", "count"), operaciones=("n", "sum"), neto_usd=("neto_usd", "sum"),
                                          años_positivos=("neto_usd", lambda x: int((x > 0).sum())))
        L += ["### Walk-forward anual (configuración elegida solo con años anteriores)", "", _t(wfs.reset_index()), "",
              _t(wf), ""]
        pv = d / "pendiente_vs_resultado.csv"
        if pv.exists():
            x = pd.read_csv(pv)
            L += ["### Pendiente del VWAP a favor de la operación frente al resultado (descriptivo, sin filtro, dev + val)", "", _t(x), ""]
            fig, ax = plt.subplots(figsize=(8, 3.5))
            ax.bar(range(len(x)), x["mean"], color=["#c44" if v < 0 else "#4a4" for v in x["mean"]])
            ax.set_xticks(range(len(x))); ax.set_xticklabels(x.iloc[:, 0], rotation=45, ha="right", fontsize=7)
            ax.set_ylabel("R medio"); ax.set_title(f"{key}: pendiente del VWAP a favor vs R (descriptivo)"); ax.grid(alpha=.3)
            fig.tight_layout(); fig.savefig(d / "pendiente_vs_resultado.png", dpi=110); plt.close(fig)
            L += [f"![pendiente]({key}/pendiente_vs_resultado.png)", ""]
        ops = pd.read_csv(d / "operaciones.csv")
        fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw=dict(height_ratios=[3, 1.3]))
        for lab, g in ops[ops.config.str.contains("partida")].groupby("config"):
            x_ = pd.to_datetime(g.exit_time.str[:19]); eq = 50000 + g.net_usd.cumsum()
            a1.plot(x_, eq, lw=0.9, label=lab); a2.plot(x_, eq - eq.cummax(), lw=0.8)
        for k, (s, _) in fz["periodos"].items():
            for ax in (a1, a2):
                ax.axvline(pd.Timestamp(s), color="grey", ls="--", lw=0.8)
        a1.set_title(f"{key}: capital (configuración de partida, costes base)"); a1.legend(fontsize=7); a1.grid(alpha=.3)
        a2.set_ylabel("Drawdown USD"); a2.grid(alpha=.3)
        fig.tight_layout(); fig.savefig(d / "capital_drawdown.png", dpi=110); plt.close(fig)
        fig, ax = plt.subplots(figsize=(8, 3.5))
        ax.hist(ops[ops.config.str.contains("partida")].R.clip(-2, 3), bins=50); ax.set_title(f"{key}: distribución de R"); ax.grid(alpha=.3)
        fig.tight_layout(); fig.savefig(d / "distribucion_R.png", dpi=110); plt.close(fig)
        L += [f"![capital]({key}/capital_drawdown.png)", f"![R]({key}/distribucion_R.png)", ""]
        rb = d / "robustez.csv"
        if rb.exists() and rb.stat().st_size > 5:
            L += ["### Robustez de los candidatos", "", _t(pd.read_csv(rb)), ""]
    (out / "INFORME.md").write_text("\n".join(L))
    print("informe:", out / "INFORME.md")
