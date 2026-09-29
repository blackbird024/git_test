"""Ventaja 1 — Barrido de Londres en el oro (reglas en edges/barrido_londres.md).

Flujo por día (horas de Italia; datos en UTC):
  1. Niveles: máximo/mínimo de Asia (01:00-08:50) y de la sesión anterior de CME (ya cerrada).
  2. En cada ventana se buscan barridos en los dos sentidos. Un barrido arriba (candidato a corto):
     una vela supera un nivel superior; el nivel barrido es el más exterior superado por el extremo.
  3. Confirmación: una vela cierra de vuelta dentro (por debajo del nivel barrido). Si después el precio
     hace un nuevo extremo, hay que volver a confirmar.
  4. Disparo (desde la confirmación): IFVG — cierre al otro lado del FVG más reciente formado en los 30 min
     previos al extremo — o, si no hubo FVG, breaker — cierre al otro lado de la vela del extremo.
  5. Entrada en la apertura de la vela siguiente; stop = extremo ± margen; objetivo = 2R; cierre a las 12:00.
Solo se usan velas ya cerradas (el disparo es un cierre) y la entrada es siempre la vela siguiente.
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from src.engine.costes import Costes
from src.engine.ejecucion import a_tabla, contratos_por_riesgo, ejecutar
from src.horas import ROMA, hora_local_a_utc, sesion_cme


@dataclass(frozen=True)
class Config:
    # --- parámetros libres (3) ---
    margen_stop: float = 1.5            # dólares de precio detrás del extremo del barrido
    objetivo_r: float = 2.0
    cierre: str = "12:00"
    # --- fijados por la especificación ---
    asia: tuple = ("01:00", "08:50")
    ventanas: tuple = (("08:50", "09:10"), ("10:03", "10:30"))
    tramo_fvg_min: int = 30
    max_ops_dia: int = 2
    riesgo_usd: float = 250.0           # 0,5 % de 50.000 $
    max_contratos: int = 50
    tick: float = 0.10
    valor_punto: float = 10.0           # MGC
    costes: Costes = Costes()

    def con(self, **cambios) -> "Config":
        return replace(self, **cambios)


# ------------------------------------------------------------------------------- preparación
def preparar(m1: pd.DataFrame, cfg: Config):
    """Velas de 1M de cada mañana (00:00-12:30 Italia) y niveles del día anterior, por fecha de Italia."""
    roma = m1.index.tz_convert(ROMA)
    manana = m1[(roma.hour < 12) | ((roma.hour == 12) & (roma.minute < 30))]
    fechas = manana.index.tz_convert(ROMA).date
    ses = sesion_cme(m1.index)
    g = m1.groupby(ses)
    diario = pd.DataFrame({"high": g.high.max(), "low": g.low.min()})
    anterior = diario.shift(1)          # sesión anterior: cerrada a las 17:00 NY (23:00 Italia) del día previo
    return dict(tuple(manana.groupby(fechas))), anterior


def niveles(dia: pd.DataFrame, fecha, anterior: pd.DataFrame, cfg: Config):
    t0, t1 = hora_local_a_utc(fecha, cfg.asia[0], ROMA), hora_local_a_utc(fecha, cfg.asia[1], ROMA)
    asia = dia[(dia.index >= t0) & (dia.index < t1)]
    if len(asia) < 300 or fecha not in anterior.index or anterior.loc[fecha].isna().any():
        return None
    pd_ = anterior.loc[fecha]
    return {"arriba": [asia.high.max(), pd_.high], "abajo": [asia.low.min(), pd_.low], "fin_asia": t1}


# ------------------------------------------------------------------------------ búsqueda
def buscar_setup(dia: pd.DataFrame, lv: dict, desde: pd.Timestamp, hasta: pd.Timestamp, cfg: Config):
    """Primer setup (en cualquiera de los dos sentidos) con barrido, confirmación y disparo en [desde, hasta).
    Devuelve (i_senal, direccion, extremo) o None."""
    idx = dia.index
    H, L, C = dia.high.to_numpy(), dia.low.to_numpy(), dia.close.to_numpy()
    ventana = np.flatnonzero((idx >= desde) & (idx < hasta))
    lookback = cfg.tramo_fvg_min
    # Un nivel ya superado entre el fin de Asia y el inicio de la búsqueda ya está barrido: no cuenta.
    previo = dia[(idx >= lv["fin_asia"]) & (idx < desde)]
    hi_prev = previo.high.max() if len(previo) else -np.inf
    lo_prev = previo.low.min() if len(previo) else np.inf
    vivos = {-1: [x for x in lv["arriba"] if hi_prev <= x], 1: [x for x in lv["abajo"] if lo_prev >= x]}
    estado = {-1: None, 1: None}        # -1: barrido arriba (corto); +1: barrido abajo (largo)
    for j in ventana:
        for d in (-1, 1):
            lvls = vivos[d]
            if not lvls:
                continue
            extremo_vela = H[j] if d == -1 else L[j]
            st = estado[d]
            supera = [x for x in lvls if (extremo_vela > x if d == -1 else extremo_vela < x)]
            if st is None:
                if supera:
                    estado[d] = st = {"ext": extremo_vela, "i_ext": j, "confirmado": False}
                else:
                    continue
            elif (d == -1 and H[j] > st["ext"]) or (d == 1 and L[j] < st["ext"]):
                st.update(ext=extremo_vela, i_ext=j, confirmado=False)
            barridos = [x for x in lvls if (st["ext"] > x if d == -1 else st["ext"] < x)]
            nivel = max(barridos) if d == -1 else min(barridos)          # el más exterior superado
            if not st["confirmado"] and (C[j] < nivel if d == -1 else C[j] > nivel):
                st["confirmado"] = True
            if not st["confirmado"]:
                continue
            fvg = _fvg(H, L, max(2, st["i_ext"] - lookback), st["i_ext"], d)
            if fvg is not None:
                dispara = C[j] < fvg if d == -1 else C[j] > fvg
            else:
                dispara = C[j] < L[st["i_ext"]] if d == -1 else C[j] > H[st["i_ext"]]
            if dispara:
                return j, d, st["ext"], ("IFVG" if fvg is not None else "breaker")
    return None


def _fvg(H, L, k0, k1, d):
    """Límite del FVG más reciente (tercera vela en [k0, k1]) a favor del barrido.
    Barrido arriba: FVG alcista L[k] > H[k-2] -> se invierte con un cierre por debajo de H[k-2].
    Barrido abajo:  FVG bajista H[k] < L[k-2] -> se invierte con un cierre por encima de L[k-2]."""
    for k in range(k1, k0 - 1, -1):
        if d == -1 and L[k] > H[k - 2]:
            return H[k - 2]
        if d == 1 and H[k] < L[k - 2]:
            return L[k - 2]
    return None


def operar_setup(dia, setup, fecha, cfg: Config, t_limite=None):
    """Convierte un setup en una operación simulada (o None si no cabe ni un contrato)."""
    j, d, ext, tipo = setup
    if j + 1 >= len(dia):
        return None
    t_limite = t_limite or hora_local_a_utc(fecha, cfg.cierre, ROMA)
    entrada = dia.open.iloc[j + 1] + d * cfg.costes.ticks(dia.index[j + 1]) * cfg.tick
    stop = ext - d * cfg.margen_stop
    dist = (entrada - stop) * d
    n = contratos_por_riesgo(cfg.riesgo_usd, dist, cfg.valor_punto, cfg.max_contratos)
    if n < 1:
        return None
    objetivo = entrada + d * cfg.objetivo_r * dist
    op = ejecutar(dia, j, d, stop, objetivo, n, t_limite, cfg.tick, cfg.valor_punto, cfg.costes)
    if op is not None:
        op.motivo = f"{op.motivo}|{tipo}"
    return op


# ------------------------------------------------------------------------------ estrategia
def backtest(m1: pd.DataFrame, cfg: Config, excluir: frozenset = frozenset()) -> pd.DataFrame:
    mananas, anterior = preparar(m1, cfg)
    ops = []
    for fecha, dia in mananas.items():
        if fecha in excluir:
            continue
        lv = niveles(dia, fecha, anterior, cfg)
        if lv is None:
            continue
        hechas, desde = 0, None
        for w0, w1 in cfg.ventanas:
            inicio = hora_local_a_utc(fecha, w0, ROMA)
            fin = hora_local_a_utc(fecha, w1, ROMA)
            if desde is not None:
                inicio = max(inicio, desde)
            while hechas < cfg.max_ops_dia:
                s = buscar_setup(dia, lv, inicio, fin, cfg)
                if s is None:
                    break
                op = operar_setup(dia, s, fecha, cfg)
                if op is None:
                    inicio = dia.index[s[0] + 1] if s[0] + 1 < len(dia) else fin
                    continue
                ops.append(op)
                hechas += 1
                if op.neto < 0:
                    hechas = cfg.max_ops_dia          # tras una pérdida se acaba el día
                    break
                desde = inicio = op.t_salida
            if hechas >= cfg.max_ops_dia:
                break
    return a_tabla(ops)


def senales(m1: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    """Solo las señales (para la prueba de look-ahead)."""
    ops = backtest(m1, cfg)
    return pd.DataFrame({"t_senal": ops.t_senal, "direccion": ops.direccion}) if len(ops) else \
        pd.DataFrame({"t_senal": pd.Series(dtype="datetime64[ns, UTC]")})


# -------------------------------------------------------------------- pregunta clave: ventanas
FRANJAS_FUERA = (("09:10", "09:40"), ("09:40", "10:03"), ("10:30", "11:00"), ("11:00", "11:30"))


def estudio_ventanas(m1: pd.DataFrame, cfg: Config, excluir: frozenset = frozenset()) -> pd.DataFrame:
    """Primer setup de cada franja (dentro y fuera de las ventanas), cada operación por separado y sin
    límites diarios, todas con cierre a las 12:00. Permite comparar el R medio dentro vs fuera."""
    mananas, anterior = preparar(m1, cfg)
    filas = []
    franjas = [(w, True) for w in cfg.ventanas] + [(w, False) for w in FRANJAS_FUERA]
    for fecha, dia in mananas.items():
        if fecha in excluir:
            continue
        lv = niveles(dia, fecha, anterior, cfg)
        if lv is None:
            continue
        for (w0, w1), dentro in franjas:
            s = buscar_setup(dia, lv, hora_local_a_utc(fecha, w0, ROMA), hora_local_a_utc(fecha, w1, ROMA), cfg)
            if s is None:
                continue
            op = operar_setup(dia, s, fecha, cfg)
            if op is not None:
                filas.append({"franja": f"{w0}-{w1}", "dentro": dentro, "t_entrada": op.t_entrada,
                              "neto": op.neto, "r": op.r})
    return pd.DataFrame(filas)
