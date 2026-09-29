"""Control de calidad y limpieza de velas de 1 minuto (en UTC).

Qué se revisa:
  - duplicados (misma hora dos veces);
  - velas imposibles: máximo < mínimo, apertura o cierre fuera del rango, precios <= 0;
  - huecos: minutos seguidos sin vela. En futuros de CME es NORMAL que falten minutos sueltos de madrugada
    (si nadie negocia, no hay vela). Se separan los huecos esperados (pausa diaria 17:00-18:00 de Nueva York,
    fines de semana) de los inesperados de más de 30 minutos dentro de la sesión;
  - saltos de precio anómalos (fuera de los cambios de contrato);
  - cambios de contrato (roll) y, en futuros, días ilíquidos PREVISIBLES (ver dias_iliquidos).
"""
import numpy as np
import pandas as pd

from src.horas import NUEVA_YORK, sesion_cme


def velas_imposibles(df: pd.DataFrame) -> pd.Series:
    precios = df[["open", "high", "low", "close"]]
    return ((df.high < df.low) | (df.open > df.high) | (df.open < df.low) | (df.close > df.high)
            | (df.close < df.low) | (precios <= 0).any(axis=1) | precios.isna().any(axis=1))


def huecos(df: pd.DataFrame, minimo_min: int = 30) -> pd.DataFrame:
    """Huecos INESPERADOS de más de `minimo_min` minutos (se excluyen la pausa diaria y el fin de semana)."""
    t = df.index
    gap = pd.Series(t[1:] - t[:-1], index=t[:-1])
    grandes = gap[gap > pd.Timedelta(minutes=minimo_min)]
    ny_ini = grandes.index.tz_convert(NUEVA_YORK)
    ny_fin = (grandes.index + pd.to_timedelta(grandes.to_numpy())).tz_convert(NUEVA_YORK)
    # Esperado: el hueco empieza entre las 16:00 y las 17:00 de NY (cierre diario / viernes) y termina
    # en la reapertura de las 18:00 (o el domingo), o dura un fin de semana / festivo completo.
    esperado = (ny_ini.hour >= 16) & (ny_ini.hour < 18) & (ny_fin.hour >= 17) & (ny_fin.hour <= 19)
    esperado |= grandes > pd.Timedelta(hours=40)
    # Cierres anticipados y festivos: el hueco termina en una reapertura de Globex (17:55-18:15 de NY).
    min_fin = ny_fin.hour * 60 + ny_fin.minute
    esperado |= (min_fin >= 17 * 60 + 55) & (min_fin <= 18 * 60 + 15)
    out = pd.DataFrame({"inicio_utc": grandes.index, "duracion": grandes.to_numpy(), "esperado": esperado})
    return out[~out.esperado].drop(columns="esperado").reset_index(drop=True)


def saltos(df: pd.DataFrame, n_mad: float = 25.0, reversion: float = 0.8) -> pd.DataFrame:
    """Picos de 1 minuto que se deshacen: pueden ser DATOS ERRÓNEOS o latigazos reales de noticias (con
    velas de 1 minuto no se pueden distinguir, así que solo se informan y NO se borran). Pico = cambio enorme (más de `n_mad` veces la desviación absoluta
    mediana) que se deshace casi entero en el minuto siguiente. Un movimiento grande que NO se deshace
    (una noticia, una reapertura) es real y no se marca. No se cuentan los cambios de contrato."""
    r = np.log(df.close).diff()
    if "instrument_id" in df:
        r[df.instrument_id != df.instrument_id.shift()] = np.nan
    mad = (r - r.median()).abs().median()
    grande = (r - r.median()).abs() > n_mad * mad
    siguiente = r.shift(-1)
    se_deshace = (np.sign(siguiente) == -np.sign(r)) & (siguiente.abs() > reversion * r.abs())
    raros = r[grande & se_deshace]
    return pd.DataFrame({"tiempo_utc": raros.index, "rendimiento_%": (raros * 100).round(3).to_numpy()})


def movimientos_extremos(df: pd.DataFrame, n_mad: float = 25.0) -> int:
    """Movimientos de 1 minuto muy grandes pero REALES (no se deshacen): solo informativo."""
    r = np.log(df.close).diff()
    mad = (r - r.median()).abs().median()
    return int(((r - r.median()).abs() > n_mad * mad).sum()) - len(saltos(df, n_mad))


def dias_iliquidos(df: pd.DataFrame, ratio: float = 0.5, ventana: int = 20, velas_completa: int = 1200) -> set:
    """Sesiones en las que el contrato continuo probablemente sigue en un vencimiento que se está quedando
    sin actividad (en el oro, el contrato que expira se desploma en volumen días antes del cambio).

    Regla CAUSAL (solo información de la sesión anterior, conocida antes de operar):
      - la sesión anterior fue COMPLETA (no un festivo o media jornada),
      - tuvo menos de `ratio` x la mediana de volumen de las `ventana` sesiones previas,
      - y el contrato NO ha cambiado todavía (la sesión actual empieza con el mismo contrato).
    """
    ses = sesion_cme(df.index)
    g = df.groupby(ses)
    vol, velas = g.volume.sum(), g.volume.size()
    ref = vol.rolling(ventana, min_periods=5).median().shift(1)
    bajo = (vol < ratio * ref) & (velas >= velas_completa)
    if "instrument_id" in df:
        mismo = g.instrument_id.first() == g.instrument_id.last().shift(1)
    else:
        mismo = pd.Series(True, index=vol.index)
    marcados = bajo.shift(1, fill_value=False) & mismo
    return set(vol.index[marcados])


def informe(df: pd.DataFrame, nombre: str) -> dict:
    ses = pd.Series(sesion_cme(df.index))
    por_sesion = ses.value_counts()
    h = huecos(df)
    info = {
        "mercado": nombre,
        "desde_utc": df.index.min(), "hasta_utc": df.index.max(),
        "velas": len(df),
        "duplicados": int(df.index.duplicated().sum()),
        "velas_imposibles": int(velas_imposibles(df).sum()),
        "sesiones": int(ses.nunique()),
        "sesiones_cortas_(<600_velas)": int((por_sesion < 600).sum()),
        "huecos_inesperados_>30min": len(h),
        "hueco_mayor": h.duracion.max() if len(h) else pd.Timedelta(0),
        "picos_que_se_deshacen_(error_o_noticia)": len(saltos(df)),
        "movimientos_extremos_reales": movimientos_extremos(df),
    }
    if "instrument_id" in df:
        info["cambios_de_contrato"] = int((df.instrument_id != df.instrument_id.shift()).sum() - 1)
        info["dias_iliquidos_previsibles"] = len(dias_iliquidos(df))
    return info


def limpiar(df: pd.DataFrame) -> pd.DataFrame:
    """Quita duplicados (se queda con la última) y velas imposibles."""
    df = df[~df.index.duplicated(keep="last")]
    return df[~velas_imposibles(df)]
