"""Métricas de resultados, explicadas:

- beneficio_neto: suma de todas las operaciones, ya descontadas comisiones y deslizamiento.
- drawdown_max: la mayor caída desde un máximo de la curva de saldo (con saldos de cierre diario).
- profit_factor: ganancias brutas / pérdidas brutas. >1 gana dinero; 1,3 o más empieza a ser interesante.
- pct_dias_ganadores: de los días con operaciones, cuántos terminaron en positivo.
- expectativa_R: media de cada operación medida en "R" (unidades de riesgo). +0,10R = por cada
  100 $ arriesgados se ganan 10 $ de media.
"""
import pandas as pd


def trade_metrics(trades: pd.DataFrame, daily: pd.DataFrame) -> dict:
    if trades.empty:
        return {"operaciones": 0}
    wins = trades.pnl_net[trades.pnl_net > 0].sum()
    losses = -trades.pnl_net[trades.pnl_net < 0].sum()
    active = daily[daily.n_trades > 0]
    equity = daily.pnl.cumsum()
    drawdown = (equity - equity.cummax()).min()
    r = trades.pnl_net / trades.risk_usd
    return {
        "operaciones": len(trades),
        "beneficio_neto": round(trades.pnl_net.sum(), 2),
        "costes_totales": round(trades.costs.sum(), 2),
        "drawdown_max": round(drawdown, 2),
        "profit_factor": round(wins / losses, 2) if losses > 0 else float("inf"),
        "pct_aciertos": round((trades.pnl_net > 0).mean() * 100, 1),
        "pct_dias_ganadores": round((active.pnl > 0).mean() * 100, 1) if len(active) else None,
        "expectativa_R": round(r.mean(), 3),
        "peor_dia": round(daily.pnl.min(), 2),
        "peor_momento_intradia": round(daily.min_intraday_pnl.min(), 2),
    }


def daily_pnl_by_strategy(trades: pd.DataFrame) -> pd.DataFrame:
    """Tabla fecha x estrategia con el P&L diario, para calcular correlaciones entre estrategias."""
    t = trades.assign(date=pd.to_datetime(trades.exit_time).dt.tz_localize(None).dt.normalize())
    return t.pivot_table(index="date", columns="strategy", values="pnl_net", aggfunc="sum").fillna(0)


def longest_streak(mask) -> int:
    """Racha más larga de valores True seguidos (p. ej., operaciones perdedoras seguidas)."""
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def trade_list_stats(trades: pd.DataFrame) -> dict:
    """Métricas de una lista de operaciones con columnas pnl, gross, commission y risk_usd."""
    if trades.empty:
        return {"operaciones": 0}
    pnl = trades.pnl
    wins, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    equity = pnl.cumsum()
    return {
        "operaciones": len(trades),
        "beneficio_neto": round(pnl.sum(), 0),
        "beneficio_bruto": round(trades.gross.sum(), 0),
        "comisiones": round(trades.commission.sum(), 0),
        "profit_factor": round(wins / losses, 2) if losses > 0 else float("inf"),
        "pct_acierto": round((pnl > 0).mean() * 100, 1),
        "media_por_op": round(pnl.mean(), 1),
        "expectativa_R": round((pnl / trades.risk_usd).mean(), 3),
        "drawdown_max": round((equity - equity.cummax()).min(), 0),
        "racha_perdedora_max": longest_streak(pnl <= 0),
    }
