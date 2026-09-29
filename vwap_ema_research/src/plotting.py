"""Gráficos en plots/. Muestran también los periodos malos, no solo los buenos."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

COL = {"train": "#57606a", "validation": "#0969da", "test": "#cf222e"}


def _save(fig, path: Path) -> str:
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)
    return path.name


def equity_dd(periodos: dict, capital: float, path: Path, titulo: str) -> str:
    """periodos: {nombre: daily DataFrame}; se encadenan en orden (el capital sigue de un periodo al siguiente)."""
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    base = capital
    for nombre, d in periodos.items():
        if d is None or d.empty:
            continue
        x = pd.to_datetime(d.session.astype(str))
        eq = base + d.pnl.cumsum().to_numpy()
        pk = np.maximum.accumulate(np.r_[base, eq])[1:]
        a1.plot(x, eq, color=COL.get(nombre, "black"), label=nombre)
        a2.fill_between(x, (eq - pk) / pk * 100, 0, color=COL.get(nombre, "black"), alpha=0.5)
        base = eq[-1]
    a1.axhline(capital, color="grey", lw=0.8)
    a1.set_ylabel("Capital ($)")
    a2.set_ylabel("Drawdown (%)")
    a1.legend()
    a1.set_title(titulo)
    return _save(fig, path)


def hist_r(tr: pd.DataFrame, path: Path, titulo: str) -> str:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(tr.r_net.clip(-3, 5), bins=60, color="#57606a")
    ax.axvline(0, color="black", lw=0.8)
    ax.axvline(tr.r_net.mean(), color="#cf222e", label=f"media {tr.r_net.mean():.3f} R (n={len(tr)})")
    ax.set_xlabel("R neto por operación (recortado a [-3, 5])")
    ax.legend()
    ax.set_title(titulo)
    return _save(fig, path)


def mensual(daily: pd.DataFrame, path: Path, titulo: str) -> str:
    m = daily.groupby(pd.to_datetime(daily.session.astype(str)).dt.to_period("M").to_numpy()).pnl.sum()
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.bar(range(len(m)), m.to_numpy(), color=["#1a7f37" if v > 0 else "#cf222e" for v in m])
    paso = max(1, len(m) // 20)
    ax.set_xticks(range(0, len(m), paso), [str(p) for p in m.index[::paso]], rotation=45)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("P&L neto mensual ($)")
    ax.set_title(f"{titulo} — meses positivos {(m > 0).mean() * 100:.0f} %")
    return _save(fig, path)


def barras(t: pd.DataFrame, col: str, path: Path, titulo: str) -> str:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar([str(i) for i in t.index], t[col], color=["#1a7f37" if v > 0 else "#cf222e" for v in t[col]])
    for i, (v, n) in enumerate(zip(t[col], t.trades)):
        ax.text(i, v, f"n={n}", ha="center", va="bottom" if v >= 0 else "top", fontsize=7)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel(col)
    ax.set_title(titulo)
    plt.setp(ax.get_xticklabels(), rotation=30)
    return _save(fig, path)


def mae_mfe(tr: pd.DataFrame, path: Path, titulo: str) -> str:
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4))
    col = np.where(tr.net_pnl > 0, "#1a7f37", "#cf222e")
    a.scatter(tr.mae_pts / tr.stop_pts, tr.r_net, s=4, c=col)
    a.set_xlabel("MAE / distancia al stop")
    a.set_ylabel("R neto")
    b.scatter(tr.mfe_pts / tr.stop_pts, tr.r_net, s=4, c=col)
    b.set_xlabel("MFE / distancia al stop")
    fig.suptitle(titulo)
    return _save(fig, path)


def heat(t: pd.DataFrame, fila: str, colm: str, path: Path, titulo: str) -> str:
    piv = t.pivot(index=fila, columns=colm, values="expectancy_R")
    fig, ax = plt.subplots(figsize=(6, 4))
    lim = np.nanmax(np.abs(piv.to_numpy())) or 1
    im = ax.imshow(piv.to_numpy(float), cmap="RdYlGn", vmin=-lim, vmax=lim, aspect="auto")
    ax.set_xticks(range(piv.shape[1]), [str(c) for c in piv.columns])
    ax.set_yticks(range(piv.shape[0]), [str(i) for i in piv.index])
    ax.set_xlabel(colm)
    ax.set_ylabel(fila)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            ax.text(j, i, f"{piv.iloc[i, j]:.3f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, label="expectativa neta (R), train")
    ax.set_title(titulo)
    return _save(fig, path)


def periodos(t: pd.DataFrame, path: Path, titulo: str) -> str:
    """t: índice = configuración; columnas = train/validation/test (expectativa R)."""
    fig, ax = plt.subplots(figsize=(10, 4))
    x = np.arange(len(t))
    w = 0.8 / t.shape[1]
    for i, c in enumerate(t.columns):
        ax.bar(x + i * w, t[c], width=w, label=c, color=COL.get(c))
    ax.set_xticks(x + w * (t.shape[1] - 1) / 2, t.index, rotation=15)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("expectativa neta (R)")
    ax.legend()
    ax.set_title(titulo)
    return _save(fig, path)


def wf_equity(tr: pd.DataFrame, path: Path, titulo: str) -> str:
    t = tr.sort_values("exit_time")
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(pd.to_datetime(t.exit_time), t.r_net.cumsum(), color="#0969da")
    for y in sorted(t.wf_year.unique()):
        ax.axvline(pd.Timestamp(f"{y}-01-01"), color="grey", lw=0.5, ls=":")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("R neto acumulado")
    ax.set_title(titulo)
    return _save(fig, path)


def ejemplo(x: pd.DataFrame, op: pd.Series, path: Path, titulo: str) -> str:
    """Vela a vela de la sesión de la operación con VWAP, EMA20/50/200, entrada, stop, TP y salida."""
    d = x[x.session == op.session].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(12, 5))
    for i, r in d.iterrows():
        c = "#1a7f37" if r.close >= r.open else "#cf222e"
        ax.plot([i, i], [r.low, r.high], color=c, lw=1)
        ax.add_patch(plt.Rectangle((i - 0.3, min(r.open, r.close)), 0.6, max(abs(r.close - r.open), 1e-9), color=c))
    for col, nombre, color in (("vwap", "VWAP", "#0969da"), ("ema_fast", "EMA20", "#bf8700"),
                               ("ema_medium", "EMA50", "#8250df"), ("ema_slow", "EMA200", "#57606a")):
        ax.plot(range(len(d)), d[col], label=nombre, color=color, lw=1.3)
    t0 = d.start.dt.tz_localize(None).to_numpy()
    ie = int(np.searchsorted(t0, np.datetime64(op.entry_time), "right") - 1)
    ix = int(np.searchsorted(t0, np.datetime64(op.exit_time), "right") - 1)
    ax.scatter(ie, op.entry_price, marker="^" if op.direction == 1 else "v", s=120, color="black", zorder=5, label="entrada")
    ax.scatter(ix, op.exit_price, marker="X", s=100, color="#cf222e", zorder=5, label=f"salida ({op.exit_reason})")
    ax.hlines(op.stop_initial, ie, ix, colors="#cf222e", linestyles="dotted", label="stop inicial")
    if pd.notna(op.take_profit):
        ax.hlines(op.take_profit, ie, ix, colors="#1a7f37", linestyles="dotted", label="take profit")
    ax.set_xticks(range(0, len(d), 2), d.start.dt.tz_convert("America/New_York").dt.strftime("%H:%M")[::2], rotation=45)
    ax.legend(fontsize=7, loc="best")
    ax.set_title(titulo)
    return _save(fig, path)
