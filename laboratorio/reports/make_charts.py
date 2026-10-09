"""Gráficos de equity, drawdown, distribución y estabilidad anual a partir de los últimos experimentos."""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))
OUT = LAB / "reports" / "graficos"
EXP = LAB / "experiments"

A = {
    "A3 Zona de ruido (reglas originales)": "Zona de ruido",
    "A1 ORB immediate stop=rango salida=eod": "ORB inmediato, salida cierre",
    "A1 ORB close principal + filtro vol": "ORB cierre confirmado + vol",
    "A1 ORB retest stop=rango salida=2R_1130": "ORB ruptura + retesteo",
    "A1 ORB immediate principal + filtro vol": "ORB inmediato 2R + vol",
    "A2 Tendencia + filtro vwap": "Tendencia + VWAP",
}
SPLITS = [("2022-01-01", "validación"), ("2025-01-01", "prueba")]


def last(p):
    return sorted(EXP.glob(p))[-1]


def slug(s):
    return "".join(ch if ch.isalnum() else "_" for ch in s).strip("_")[:80]


def mark(ax):
    for d, lab in SPLITS:
        ax.axvline(pd.Timestamp(d), color="grey", ls="--", lw=0.8)
        ax.text(pd.Timestamp(d), ax.get_ylim()[1], " " + lab, va="top", fontsize=8, color="grey")


def system_a():
    d = last("*_sistema_a_con_prueba")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True, gridspec_kw=dict(height_ratios=[3, 1.4]))
    years = {}
    for name, lab in A.items():
        t = pd.read_csv(d / f"ops_{slug(name)}.csv.gz", parse_dates=["date"])
        daily = t.groupby("date").pnl.sum()
        eq = daily.cumsum()
        ax1.plot(eq.index, eq.values, label=lab, lw=1.3 if "ruido" in lab else 0.9)
        ax2.plot(eq.index, (eq - eq.cummax()).values, lw=0.8)
        years[lab] = t.groupby(t.date.dt.year).pnl.sum()
    ax1.set_title("Sistema A · P&L acumulado por 1 MNQ, coste base (2 ticks/lado + 0,75 $/lado)")
    ax1.set_ylabel("USD"); ax1.legend(fontsize=8); ax1.grid(alpha=.3); mark(ax1)
    ax2.set_ylabel("Drawdown USD"); ax2.grid(alpha=.3)
    ax2.axhline(-2000, color="red", lw=0.8); ax2.text(ax2.get_xlim()[0], -2000, " MLL Topstep 2.000 $", color="red", fontsize=8, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "A_equity_drawdown.png", dpi=110); plt.close(fig)
    y = pd.DataFrame(years).fillna(0)
    ax = y.plot.bar(figsize=(11, 4.5), width=0.8)
    ax.set_title("Sistema A · resultado por año civil (1 MNQ, coste base; 2026 hasta el 2 de octubre)")
    ax.set_ylabel("USD"); ax.grid(alpha=.3, axis="y"); ax.legend(fontsize=7)
    plt.tight_layout(); plt.savefig(OUT / "A_por_año.png", dpi=110); plt.close()
    t = pd.read_csv(d / f"ops_{slug('A3 Zona de ruido (reglas originales)')}.csv.gz", parse_dates=["date"])
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(t.pnl.clip(-600, 1200), bins=80, color="steelblue")
    ax.set_title(f"Zona de ruido · distribución del P&L por operación (n={len(t)}, recortado a [-600, 1200])")
    ax.set_xlabel("USD por operación, 1 MNQ"); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(OUT / "A_ruido_distribucion.png", dpi=110); plt.close(fig)


def topstep():
    r = pd.read_csv(last("*_topstep_combine") / "topstep_combine.csv")
    r = r[r.ventanas.str.startswith("2022")]
    r = r[~r.estrategia.str.startswith("Control") | r.estrategia.str.contains("semilla 2")]
    r["etq"] = r.estrategia.str.replace("Control: ruido con dirección aleatoria (semilla 2)", "CONTROL aleatorio", regex=False) + " · " + r["tamaño"]
    r = r[(r.p_aprobar + r.p_suspender) > 0]
    fig, ax = plt.subplots(figsize=(10, 0.32 * len(r) + 1.5))
    yy = np.arange(len(r))
    ax.barh(yy, r.p_aprobar, color="seagreen", label="aprueba")
    ax.barh(yy, r.p_suspender, left=r.p_aprobar, color="indianred", label="pierde la cuenta")
    ax.barh(yy, r.p_sin_resolver, left=r.p_aprobar + r.p_suspender, color="lightgrey", label="sin resolver en 250 días")
    ax.set_yticks(yy); ax.set_yticklabels(r.etq, fontsize=7); ax.invert_yaxis()
    ax.set_title("Topstep 50K Combine simulado, inicios 2022-2026 (fuera de muestra)"); ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout(); fig.savefig(OUT / "A_topstep_combine.png", dpi=110); plt.close(fig)


def system_b():
    from backtests.swing import equity, simulate
    from data.loaders import etf_daily
    from run_sistema_b import LAST, cost_scenarios
    from strategies.swing import SWING
    d = etf_daily("QQQ", adjusted=True, last=LAST)
    cost = cost_scenarios()["capital 10k"]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True, gridspec_kw=dict(height_ratios=[3, 1.4]))
    start = pd.Timestamp("2016-10-20")
    bh = d.loc[start:, "close"]; bh = bh / bh.iloc[0]
    ax1.plot(bh.index, bh.values, color="black", lw=1.4, label="Comprar y mantener QQQ")
    ax2.plot(bh.index, (bh / bh.cummax() - 1).values, color="black", lw=0.9)
    for name in ("B1 Ruptura 20 sesiones", "B3 RSI(2) Connors (reversión)", "B4 Retroceso a EMA20 en tendencia"):
        fn, p = SWING[name]
        t = simulate(d, fn(d, **p), cost, "next_open")
        eq, _ = equity(d, t, start)
        ax1.plot(eq.index, eq.values, lw=1, label=name)
        ax2.plot(eq.index, (eq / eq.cummax() - 1).values, lw=0.8)
    ax1.set_yscale("log"); ax1.set_title("Sistema B · capital (escala log, 1 = oct-2016), QQQ ajustado, antes de impuestos")
    ax1.legend(fontsize=8); ax1.grid(alpha=.3)
    for dd, lab in (("2021-01-01", "validación"), ("2024-01-01", "prueba")):
        for ax in (ax1, ax2):
            ax.axvline(pd.Timestamp(dd), color="grey", ls="--", lw=0.8)
        ax1.text(pd.Timestamp(dd), ax1.get_ylim()[1], " " + lab, va="top", fontsize=8, color="grey")
    ax2.set_ylabel("Drawdown"); ax2.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(OUT / "B_equity_drawdown.png", dpi=110); plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    system_a(); topstep(); system_b()
    print(sorted(p.name for p in OUT.glob("*.png")))
