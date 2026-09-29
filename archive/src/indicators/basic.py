"""Indicadores sencillos.

ATR diario "limpio": media del rango (máximo - mínimo) de la sesión regular de los últimos N días.
No usamos los huecos entre días porque, con el contrato continuo sin ajustar, el día del cambio
de contrato hay un salto artificial de precio que inflaría el ATR.
"""
import pandas as pd


def daily_rth_range(df: pd.DataFrame, start: str = "09:30", end: str = "16:00") -> pd.Series:
    """Rango (máximo - mínimo) de cada sesión regular, indexado por fecha."""
    rth = df.between_time(start, end, inclusive="left")
    g = rth.groupby(rth.index.date)
    return (g.high.max() - g.low.min()).rename("range")


def prior_atr(df: pd.DataFrame, n: int = 14) -> dict:
    """ATR conocido ANTES de empezar cada día: media de los n días anteriores (sin mirar el futuro)."""
    atr = daily_rth_range(df).rolling(n).mean().shift(1)
    return atr.dropna().to_dict()
