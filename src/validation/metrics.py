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
