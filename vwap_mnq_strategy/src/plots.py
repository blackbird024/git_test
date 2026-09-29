"""Gráficos (matplotlib, sin pantalla). Pensados para ver pérdidas y dependencias, no solo lo bueno."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

NY = "America/New_York"


def _guardar(fig, ruta: Path) -> str:
    fig.tight_layout()
    fig.savefig(ruta, dpi=110)
    plt.close(fig)
    return ruta.name


def velas_dia(b: pd.DataFrame, trades: pd.DataFrame, sesion, ruta: Path, titulo: str) -> str:
    d = b[b.session == sesion].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(11, 5))
    for i, r in d.iterrows():
        color = "#1a7f37" if r.close >= r.open else "#cf222e"
        ax.plot([i, i], [r.low, r.high], color=color, lw=1)
        ax.add_patch(plt.Rectangle((i - 0.3, min(r.open, r.close)), 0.6, max(abs(r.close - r.open), 0.25), color=color))
    ax.plot(range(len(d)), d.vwap, color="#0969da", lw=1.5, label="VWAP (sesión)")
    t = trades[trades.session == sesion]
    inicio = d.start.dt.tz_localize(None)
    for _, op in t.iterrows():
        ie = int(np.searchsorted(inicio.to_numpy(), np.datetime64(op.entry_time), side="right") - 1)
        ix = int(np.searchsorted(inicio.to_numpy(), np.datetime64(op.exit_time), side="right") - 1)
        ax.scatter(ie, op.entry_price, marker="^" if op.direction == 1 else "v", s=90, color="black", zorder=5)
        ax.scatter(ix, op.exit_price, marker="x", s=70, color="#8250df", zorder=5)
        if pd.notna(op.stop_initial):
            ax.hlines(op.stop_initial, ie, ix, colors="#cf222e", linestyles="dotted")
    etiquetas = d.start.dt.tz_convert(NY).dt.strftime("%H:%M")
    ax.set_xticks(range(0, len(d), 2), etiquetas[::2], rotation=45)
    ax.set_title(titulo)
    ax.legend(loc="best")
    return _guardar(fig, ruta)


def equity_drawdown(series: dict[str, pd.DataFrame], capital: float, ruta: Path, titulo: str) -> str:
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    for nombre, d in series.items():
        if d.empty:
            continue
        x = pd.to_datetime(d.session.astype(str))
        eq = capital + d.pnl.cumsum()
        a1.plot(x, eq, label=nombre, lw=1.2)
        a2.plot(x, eq - np.maximum.accumulate(np.r_[capital, eq.to_numpy()])[1:], lw=1)
    a1.axhline(capital, color="grey", lw=0.8)
    a1.set_ylabel("Capital ($)")
    a2.set_ylabel("Drawdown ($)")
    a1.set_title(titulo)
    a1.legend()
    return _guardar(fig, ruta)


def histograma_r(trades: pd.DataFrame, ruta: Path, titulo: str) -> str:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(trades.r_net.clip(-3, 6), bins=60, color="#57606a")
    ax.axvline(0, color="black", lw=0.8)
    ax.axvline(trades.r_net.mean(), color="#cf222e", lw=1.5, label=f"media {trades.r_net.mean():.3f} R")
    ax.set_xlabel("Resultado neto por operación (R, recortado a [-3, 6])")
    ax.set_title(titulo)
    ax.legend()
    return _guardar(fig, ruta)


def barras_grupo(tabla: pd.DataFrame, ruta: Path, titulo: str, col: str = "expectativa_R") -> str:
    fig, ax = plt.subplots(figsize=(8, 4))
    colores = ["#1a7f37" if v > 0 else "#cf222e" for v in tabla[col]]
    ax.bar([str(i) for i in tabla.index], tabla[col], color=colores)
    for i, (v, n) in enumerate(zip(tabla[col], tabla.operaciones)):
        ax.text(i, v, f"n={n}", ha="center", va="bottom" if v >= 0 else "top", fontsize=8)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel(col)
    ax.set_title(titulo)
    return _guardar(fig, ruta)


def heatmap(tabla: pd.DataFrame, ruta: Path, titulo: str) -> str:
    piv = tabla.pivot(index="sl_atr_mult", columns="tp_r", values="expectativa_R")
    fig, ax = plt.subplots(figsize=(7, 4))
    lim = np.nanmax(np.abs(piv.to_numpy()))
    im = ax.imshow(piv.to_numpy(), cmap="RdYlGn", vmin=-lim, vmax=lim, aspect="auto")
    ax.set_xticks(range(piv.shape[1]), [str(c) for c in piv.columns])
    ax.set_yticks(range(piv.shape[0]), [str(i) for i in piv.index])
    ax.set_xlabel("Take profit (R)")
    ax.set_ylabel("Stop (x ATR)")
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            ax.text(j, i, f"{piv.iloc[i, j]:.3f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, label="Expectativa neta (R)")
    ax.set_title(titulo)
    return _guardar(fig, ruta)


def comparacion(tabla: pd.DataFrame, ruta: Path, titulo: str) -> str:
    """tabla: índice = variante; columnas = periodos con expectativa R."""
    fig, ax = plt.subplots(figsize=(11, max(4, 0.35 * len(tabla))))
    y = np.arange(len(tabla))
    ancho = 0.8 / tabla.shape[1]
    for i, c in enumerate(tabla.columns):
        ax.barh(y + i * ancho, tabla[c], height=ancho, label=c)
    ax.set_yticks(y + ancho * (tabla.shape[1] - 1) / 2, tabla.index)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("Expectativa neta por operación (R)")
    ax.set_title(titulo)
    ax.legend()
    ax.invert_yaxis()
    return _guardar(fig, ruta)
