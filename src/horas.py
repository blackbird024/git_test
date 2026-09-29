"""Manejo de horas. Regla del proyecto: TODO se guarda en UTC; las reglas de sesión se escriben en la
zona horaria donde tienen sentido (Italia para tu operativa, Nueva York para CME) y se convierten aquí.

Por qué importa: EE. UU. y Europa cambian al horario de verano en fechas distintas (EE. UU. el 2.º domingo
de marzo y el 1.er domingo de noviembre; Europa el último domingo de marzo y de octubre). Durante esas
2-3 semanas al año la diferencia entre Nueva York e Italia es de 5 horas en vez de 6. Si se trabajara con
horas fijas, las reglas se desplazarían una hora esas semanas.
"""
import numpy as np
import pandas as pd

UTC = "UTC"
ROMA = "Europe/Rome"
NUEVA_YORK = "America/New_York"
LONDRES = "Europe/London"


def a_zona(indice: pd.DatetimeIndex, zona: str) -> pd.DatetimeIndex:
    """Convierte un índice en UTC a otra zona horaria (solo para leer horas, no para guardar)."""
    return indice.tz_convert(zona)


def hora_local_a_utc(fecha, hhmm: str, zona: str) -> pd.Timestamp:
    """'08:50' del día `fecha` en `zona` -> instante en UTC."""
    return pd.Timestamp(f"{pd.Timestamp(fecha).date()} {hhmm}", tz=zona).tz_convert(UTC)


def sesion_cme(indice: pd.DatetimeIndex) -> np.ndarray:
    """Fecha de sesión de CME Globex para cada instante. La sesión de un día empieza a las 18:00 de
    Nueva York del día anterior y termina a las 17:00 (por eso se suma 6 horas y se toma la fecha)."""
    return (indice.tz_convert(NUEVA_YORK) + pd.Timedelta(hours=6)).date


def en_ventana(indice: pd.DatetimeIndex, desde: str, hasta: str, zona: str) -> np.ndarray:
    """True si la hora local (en `zona`) está en [desde, hasta)."""
    local = indice.tz_convert(zona)
    minutos = local.hour * 60 + local.minute
    h0, m0 = map(int, desde.split(":"))
    h1, m1 = map(int, hasta.split(":"))
    return (minutos >= h0 * 60 + m0) & (minutos < h1 * 60 + m1)
