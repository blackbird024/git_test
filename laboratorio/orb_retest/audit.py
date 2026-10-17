"""Auditoría de los datos de 1 min usados por MNQ_ORB_RETEST (solo lectura)."""
import numpy as np
import pandas as pd

from data.loaders import ET, SRC, nq_1m, sessions


def audit():
    df = nq_1m()
    idx = df.index
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    bad_ohlc = int(((h < np.maximum(o, c)) | (l > np.minimum(o, c)) | (h < l)).sum())
    off_tick = int((np.abs(np.round(df[["open", "high", "low", "close"]].to_numpy() / 0.25) * 0.25 -
                           df[["open", "high", "low", "close"]].to_numpy()) > 1e-6).any(axis=1).sum())
    ids = df.instrument_id
    rolls = [str(t) for t in ids.index[ids.ne(ids.shift())][1:]]
    S = sessions()
    mins = (idx.hour * 60 + idx.minute)
    rth = df[(mins >= 570) & (mins < 960)]
    multi = rth.groupby(rth.index.date).instrument_id.nunique()
    or_missing, rth_missing, half = [], [], []
    for s in S:
        n_or = int((~np.isnan(s.m[:15, 0])).sum())
        if n_or < 15:
            or_missing.append((str(s.date.date()), n_or))
        n = int((~np.isnan(s.m[: s.close_min, 0])).sum())
        if n < s.close_min:
            rth_missing.append((str(s.date.date()), s.close_min - n))
        if s.close_min < 390:
            half.append(str(s.date.date()))
    # DST: la primera vela de cada sesión debe ser las 9:30 ET tanto en invierno como en verano
    first = pd.Series([s.date for s in S if not np.isnan(s.m[0, 0])])
    gaps = idx.to_series().diff().dt.total_seconds().div(60)
    return dict(
        fuente=[str(SRC / "databento_nq_1m_2018_2024.pkl"), str(SRC / "databento_glbx_1m.pkl")],
        simbolo="NQ.c.0 (Databento GLBX.MDP3, ohlcv-1m): E-mini Nasdaq-100 continuo por CALENDARIO, SIN ajuste de "
                "rollover. MNQ tiene el mismo precio (índice NDX × 0,1 de multiplicador); se usa el precio de NQ.",
        zona_horaria_original="UTC; convertida a America/New_York con tz_convert (respeta los cambios de horario)",
        convencion_timestamp="hora de INICIO de cada vela de 1 min (Databento ts_event)",
        primer_timestamp_ET=str(idx[0]), ultimo_timestamp_ET=str(idx[-1]), filas=int(len(df)),
        duplicados=int(idx.duplicated().sum()), indice_ordenado=bool(idx.is_monotonic_increasing),
        nan_ohlc=int(df[["open", "high", "low", "close"]].isna().sum().sum()), velas_imposibles=bad_ohlc,
        precios_fuera_de_rejilla_0_25=off_tick, volumen_cero=int((df.volume == 0).sum()),
        huecos_mayores_de_60_min_fuera_de_fines_de_semana=int(((gaps > 60) & (gaps < 2 * 24 * 60)).sum()),
        contratos_distintos=int(ids.nunique()), cambios_de_contrato=rolls,
        sesiones_XNYS_con_datos=len(S), primera_sesion=str(S[0].date.date()), ultima_sesion=str(S[-1].date.date()),
        medias_jornadas=half, sesiones_con_mas_de_un_contrato_en_RTH=int((multi > 1).sum()),
        sesiones_con_rango_9_30_9_44_incompleto=or_missing,
        sesiones_RTH_con_minutos_sin_operaciones=len(rth_missing),
        minutos_RTH_sin_operaciones_total=int(sum(x[1] for x in rth_missing)),
        sesiones_sin_vela_09_30=int(len(S) - len(first)),
    )
