"""SMC algorítmico: barrido de liquidez + desplazamiento + FVG (reglas en edges/smc_sweep_displacement_fvg.md).

Patrón en velas de 5M (solo velas ya cerradas); ejecución con orden límite y gestión en velas de 1M.
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from src.engine.costes import Costes
from src.engine.ejecucion import a_tabla, ejecutar_limite
from src.horas import LONDRES, NUEVA_YORK, hora_local_a_utc, sesion_cme


@dataclass(frozen=True)
class Config:
    # --- parámetros libres (3), fijos en esta fase ---
    k_desplazamiento: float = 1.5
    n_velas: int = 6
    m_validez: int = 12
    # --- por mercado ---
    zona: str = LONDRES
    ventana: tuple = ("08:00", "16:00")
    cierre: str = "16:30"
    tick: float = 0.10
    valor_punto: float = 10.0
    # --- fijos ---
    ticks_stop: int = 2
    rr_minimo: float = 1.0
    atr_n: int = 14
    contratos: int = 1
    costes: Costes = Costes()

    def con(self, **cambios) -> "Config":
        return replace(self, **cambios)


ORO = Config()
NASDAQ = Config(zona=NUEVA_YORK, ventana=("09:30", "15:30"), cierre="15:55", tick=0.25, valor_punto=2.0)


def velas_5m(m1: pd.DataFrame, atr_n: int) -> pd.DataFrame:
    """Velas de 5M con su ATR de referencia: media simple del rango verdadero de las `atr_n` velas ANTERIORES
    (la vela de desplazamiento no infla su propia referencia)."""
    v = m1.resample("5min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    tr = pd.concat([v.high - v.low, (v.high - v.close.shift()).abs(), (v.low - v.close.shift()).abs()], axis=1).max(axis=1)
    v["atr"] = tr.rolling(atr_n).mean().shift(1)
    return v


def buscar_patron(v5: pd.DataFrame, i0: int, i1: int, nivel: float, d: int, cfg: Config):
    """Busca el patrón completo en las velas de 5M [i0, i1). `d` = sentido de la operación (-1 = corto tras barrer
    un máximo). Devuelve (i_vela3, extremo, limite, i_barrido) o None. Todo con velas cerradas."""
    O, H, L, C, A = (v5[c].to_numpy() for c in ("open", "high", "low", "close", "atr"))
    for s in range(i0, i1):
        barre = H[s] > nivel if d == -1 else L[s] < nivel
        if not barre:
            continue
        extremo = H[s] if d == -1 else L[s]
        # 2) vuelta dentro en las N velas (contando la del barrido)
        vuelta = None
        for r in range(s, min(s + cfg.n_velas, i1)):
            extremo = max(extremo, H[r]) if d == -1 else min(extremo, L[r])
            if (C[r] < nivel if d == -1 else C[r] > nivel):
                vuelta = r
                break
        if vuelta is None:
            return None                      # el primer cruce no volvió dentro: el nivel queda barrido sin patrón
        # 3) desplazamiento + 4) FVG, en las N velas siguientes a la vuelta
        for c2 in range(vuelta, min(vuelta + cfg.n_velas, i1 - 1)):
            extremo = max(extremo, H[c2]) if d == -1 else min(extremo, L[c2])
            cuerpo = C[c2] - O[c2]
            fuerte = np.isfinite(A[c2]) and abs(cuerpo) >= cfg.k_desplazamiento * A[c2] and np.sign(cuerpo) == d
            if not fuerte or c2 - 1 < 0:
                continue
            c1, c3 = c2 - 1, c2 + 1
            if d == -1 and H[c3] < L[c1]:
                return c3, max(extremo, H[c3]), H[c3], s   # límite en el borde cercano: máximo de la vela 3
            if d == 1 and L[c3] > H[c1]:
                return c3, min(extremo, L[c3]), L[c3], s
        return None
    return None


def operar_dia(fecha, m1_dia: pd.DataFrame, v5: pd.DataFrame, previo: pd.Series, cfg: Config):
    """Una sesión: primer patrón completo en cualquiera de los dos sentidos. Devuelve (motivo, operación)."""
    tz = cfg.zona
    t0, t1 = hora_local_a_utc(fecha, cfg.ventana[0], tz), hora_local_a_utc(fecha, cfg.ventana[1], tz)
    t_cierre = hora_local_a_utc(fecha, cfg.cierre, tz)
    inicio_sesion = hora_local_a_utc(pd.Timestamp(fecha) - pd.Timedelta(days=1), "18:00", NUEVA_YORK)
    antes = m1_dia[(m1_dia.index >= inicio_sesion) & (m1_dia.index < t0)]
    idx5 = v5.index
    i0, i1 = int(np.searchsorted(idx5, t0)), int(np.searchsorted(idx5, t1))
    candidatos = []
    for d, nivel in ((-1, previo.high), (1, previo.low)):
        ya_barrido = len(antes) and (antes.high.max() > nivel if d == -1 else antes.low.min() < nivel)
        if ya_barrido:
            continue
        p = buscar_patron(v5, i0, i1, nivel, d, cfg)
        if p is not None:
            candidatos.append((p[0], d, nivel, p))
    if not candidatos:
        return "sin_patron", None
    c3, d, nivel, (_, extremo, limite, i_barrido) = min(candidatos, key=lambda x: x[0])   # el primero en completarse
    stop = extremo - d * cfg.ticks_stop * cfg.tick           # 2 ticks más allá del extremo del barrido
    # Objetivo: siguiente liquidez = extremo opuesto de la sesión actual antes del barrido; si no vale, el del día anterior.
    t_barrido = idx5[i_barrido]
    sesion_hasta = m1_dia[(m1_dia.index >= inicio_sesion) & (m1_dia.index < t_barrido)]
    objetivo = (sesion_hasta.low.min() if d == -1 else sesion_hasta.high.max()) if len(sesion_hasta) else np.nan
    if not np.isfinite(objetivo) or (objetivo - limite) * d <= 0:
        objetivo = previo.low if d == -1 else previo.high
    riesgo, premio = abs(limite - stop), (objetivo - limite) * d
    if premio <= 0 or premio < cfg.rr_minimo * riesgo:
        return "recompensa_menor_que_1R", None
    t_vela3_cierre = idx5[c3] + pd.Timedelta(minutes=5)
    t_expira = min(t_vela3_cierre + pd.Timedelta(minutes=5 * cfg.m_validez), t1)
    i_desde = int(np.searchsorted(m1_dia.index, t_vela3_cierre))
    op = ejecutar_limite(m1_dia, i_desde, d, limite, stop, objetivo, cfg.contratos, t_expira, t_cierre,
                         cfg.tick, cfg.valor_punto, cfg.costes, t_senal=t_vela3_cierre)
    if op is None:
        return "limite_no_llenado", None
    op.riesgo_usd = abs(op.entrada - stop) * cfg.valor_punto * cfg.contratos     # 1R = distancia al stop
    return "operada", op


def backtest(m1: pd.DataFrame, cfg: Config, excluir: frozenset = frozenset()):
    ses = sesion_cme(m1.index)
    g = m1.groupby(ses)
    previo = pd.DataFrame({"high": g.high.max(), "low": g.low.min()}).shift(1)
    v5 = velas_5m(m1, cfg.atr_n)
    ops, motivos = [], {}
    for fecha, dia in g:
        if fecha in excluir or fecha not in previo.index or previo.loc[fecha].isna().any():
            continue
        if pd.Timestamp(fecha).weekday() >= 5:
            continue
        motivo, op = operar_dia(fecha, dia, v5, previo.loc[fecha], cfg)
        motivos[motivo] = motivos.get(motivo, 0) + 1
        if op is not None:
            ops.append(op)
    return a_tabla(ops), motivos


def senales(m1: pd.DataFrame, cfg: Config = ORO) -> pd.DataFrame:
    ops, _ = backtest(m1, cfg)
    if ops.empty:
        return pd.DataFrame({"t_senal": pd.Series(dtype="datetime64[ns, UTC]")})
    return pd.DataFrame({"t_senal": ops.t_senal, "direccion": ops.direccion})
