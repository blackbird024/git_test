"""Seguimiento de tendencia en futuros ("time-series momentum"), como en Hurst, Ooi y Pedersen (AQR, 2017).

Metodología (config/tsmom.yaml):
  - Rendimientos diarios de cada mercado SIN el salto del cambio de contrato: el día del roll se usa
    cierre / apertura del contrato nuevo (se pierde solo el hueco de esa noche).
  - Señal = media del signo del rendimiento de los últimos 1, 3 y 12 meses (valores de -1 a +1).
  - Peso = señal x (vol objetivo por mercado / vol anualizada de 60 días) / número de mercados.
  - Rebalanceo mensual: la señal del último día del mes se aplica desde el día siguiente (sin mirar el futuro).
  - Costes: `coste_bps` sobre el nominal negociado al rebalancear y en cada cambio de contrato.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
DAILY = ROOT / "data" / "raw" / "daily"


def load_returns(markets: list[str]) -> pd.DataFrame:
    """Rendimientos diarios sin saltos de roll, un mercado por columna; y matriz de días de roll."""
    rets, rolls = {}, {}
    for m in markets:
        f = DAILY / f"{m}.parquet"
        if not f.exists():
            continue
        df = pd.read_parquet(f)
        df.index = pd.to_datetime(df.index).tz_convert(None).normalize()
        df = df[~df.index.duplicated(keep="last")].sort_index()
        roll = df.instrument_id != df.instrument_id.shift()
        r = df.close / df.close.shift() - 1
        r[roll] = (df.close / df.open - 1)[roll]
        rets[m], rolls[m] = r, roll
    return pd.DataFrame(rets).sort_index(), pd.DataFrame(rolls).sort_index().fillna(False)


def weights(rets: pd.DataFrame, lookbacks=(21, 63, 252), vol_days=60, vol_target=0.40) -> pd.DataFrame:
    """Pesos diarios (fracción del capital en nominal) con rebalanceo mensual."""
    price = (1 + rets.fillna(0)).cumprod().where(rets.notna().cumsum() > 0)
    signal = sum(np.sign(price / price.shift(lb) - 1) for lb in lookbacks) / len(lookbacks)
    vol = rets.rolling(vol_days, min_periods=40).std() * np.sqrt(252)
    n = rets.notna().sum(axis=1).clip(lower=1)
    raw = (signal * vol_target / vol).div(n, axis=0)
    month_end = raw.index.to_series().groupby(raw.index.to_period("M")).transform("max") == raw.index.to_series()
    held = raw.where(month_end).ffill()
    return held.shift(1).fillna(0)          # la posición decidida al cierre se aplica desde el día siguiente


def portfolio(rets: pd.DataFrame, rolls: pd.DataFrame, w: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    gross = (w * rets.fillna(0)).sum(axis=1)
    turnover = w.diff().abs().sum(axis=1) + (w.abs() * rolls.reindex_like(w).fillna(False)).sum(axis=1)
    cost = turnover * cost_bps / 1e4
    return pd.DataFrame({"bruto": gross, "coste": cost, "neto": gross - cost})


def stats(r: pd.Series) -> dict:
    r = r.dropna()
    if r.empty:
        return {}
    eq = (1 + r).cumprod()
    monthly = (1 + r).groupby(r.index.to_period("M")).prod() - 1
    wins, losses = monthly[monthly > 0].sum(), -monthly[monthly < 0].sum()
    return {
        "rend_anual_%": round(((eq.iloc[-1]) ** (252 / len(r)) - 1) * 100, 2),
        "vol_anual_%": round(r.std() * np.sqrt(252) * 100, 2),
        "sharpe": round(r.mean() / r.std() * np.sqrt(252), 2),
        "t": round(r.mean() / r.std() * np.sqrt(len(r)), 2),
        "drawdown_max_%": round((eq / eq.cummax() - 1).min() * 100, 1),
        "pf_mensual": round(wins / losses, 2) if losses > 0 else float("inf"),
        "pct_meses_ganadores": round((monthly > 0).mean() * 100, 1),
    }
