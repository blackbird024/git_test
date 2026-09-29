"""Carga de las velas descargadas y paso a hora de Nueva York.

Por qué hora de NY: todas las reglas (apertura 9:30, cierre forzado 15:50) están en hora de NY,
y así los cambios de horario de verano quedan resueltos automáticamente.
"""
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
TZ = "America/New_York"


def load_minutes(root: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """Velas de 1 minuto de `root` ("NQ" o "GC") con índice en hora de NY."""
    files = sorted(RAW.glob(f"{root}_1m_*.parquet"))
    if not files:
        raise FileNotFoundError(f"No hay datos de {root} en {RAW}. Ejecuta scripts/download_databento.py")
    df = pd.concat(pd.read_parquet(f) for f in files).sort_index()
    df.index = df.index.tz_convert(TZ)
    df = df[~df.index.duplicated(keep="last")]
    if start:
        df = df[df.index >= pd.Timestamp(start, tz=TZ)]
    if end:
        df = df[df.index < pd.Timestamp(end, tz=TZ)]
    return df


def drop_short_sessions(df: pd.DataFrame, min_bars: int = 300) -> pd.DataFrame:
    """Quita los días cuya sesión regular (9:30-16:00) tiene menos de `min_bars` velas.

    Son festivos de la bolsa de acciones (los futuros abren unas horas) o medias jornadas.
    Se conocen de antemano por el calendario, así que filtrarlos no mira el futuro.
    """
    rth = df.between_time("09:30", "16:00", inclusive="left")
    counts = rth.groupby(rth.index.date).size()
    keep = set(counts[counts >= min_bars].index)
    return df[[d in keep for d in df.index.date]]


def drop_illiquid_sessions(df: pd.DataFrame, min_ratio: float = 0.25, window: int = 20) -> pd.DataFrame:
    """Quita los días cuyo volumen en sesión regular es menor que `min_ratio` x la mediana de los
    `window` días ANTERIORES.

    Motivo: unas 12 veces al año (a final de mes), el contrato continuo de GC apunta ese día a un
    vencimiento casi sin actividad (≈3 % del volumen normal). Esos precios no son el mercado real.
    """
    rth = df.between_time("09:30", "16:00", inclusive="left")
    vol = rth.groupby(rth.index.date).volume.sum()
    ref = vol.rolling(window, min_periods=5).median().shift(1)
    keep = set(vol[(ref.isna()) | (vol >= min_ratio * ref)].index)
    return df[[d in keep for d in df.index.date]]


def load_clean(root: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """Carga + filtros de días cortos e ilíquidos. Es lo que deben usar los backtests."""
    return drop_illiquid_sessions(drop_short_sessions(load_minutes(root, start, end)))
