"""GOLD_LONDON_FALSE_BREAK_v1.0: falsa ruptura del rango 08:00-09:00 de Londres → entrada hacia el otro lado → 2R.

Reglas en edges/gold_london_false_break.md. Solo genera señales y simula; nunca ejecuta órdenes.
La estrategia SOLO ve velas de 15m (construidas desde 1M, ajustadas por cambios de contrato).
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from src.horas import LONDRES, hora_local_a_utc
from src.risk.position_sizing import contratos
from src.strategies.gold_swing_simple import ESCENARIOS, CostesOro, ajustar_rolls, atr_wilder, velas_reloj

VERSION = "GOLD_LONDON_FALSE_BREAK_v1.0"
VERSION_NQ = "NQ_LONDON_FALSE_BREAK_v1.0"

# MNQ: costes estándar del proyecto, en PUNTOS por contrato (1 $/lado = 1 punto por operación completa a 2 $/punto;
# 1 tick = 0,25 puntos). Mismo formato que CostesOro: comisión + deslizamiento de entrada + de salida a mercado.
ESCENARIOS_MNQ = {
    "A": CostesOro(0.0, 0.0, 0.0, 0.0),
    "B": CostesOro(0.0, 1.0, 0.25, 0.25),
    "C": CostesOro(0.0, 1.0, 0.50, 0.50),
}


@dataclass(frozen=True)
class Config:
    version: str = VERSION
    rango: tuple = ("08:00", "09:00")
    ultima_senal: str = "11:30"          # la vela de señal empieza como tarde a esta hora (entrada 11:45)
    cierre: str = "12:00"
    tp_r: float = 2.0
    buffer_atr: float = 0.10
    atr_n: int = 14
    riesgo_pct: float = 0.005
    saldo_inicial: float = 50_000.0
    valor_punto: float = 1.0             # $ por punto y unidad: oro 1 (onzas); MNQ 2 (contratos)
    costes: CostesOro = ESCENARIOS["B"]

    def con(self, **cambios) -> "Config":
        return replace(self, **cambios)


def coste_onza(c: CostesOro, motivo: str) -> float:
    """Igual que en los estudios anteriores; la salida por tiempo es a mercado y lleva el deslizamiento del stop."""
    return c.spread + c.comision + c.desliz_entrada + (c.desliz_stop if motivo in ("SL", "TIME") else 0.0)


def preparar(m1: pd.DataFrame, cfg: Config) -> dict:
    v15 = velas_reloj(ajustar_rolls(m1), 15)
    return {"v15": v15, "atr": atr_wilder(v15, cfg.atr_n)}


def buscar_falsa_ruptura(h, l, c, js, RH, RL):
    """Recorre las velas de la ventana (posiciones `js`). Devuelve (estado, j_señal, d, primer_ataque, j_primer_ataque).
    La primera vela que ataca un extremo decide: si cierra dentro es falsa ruptura; si cierra fuera, el extremo se
    gasta. Una vela que ataca a la vez los dos extremos disponibles hace el día ambiguo."""
    gast_alto = gast_bajo = False
    primero = j_primero = None
    for j in js:
        if primero is None and (h[j] > RH or l[j] < RL):
            primero = "BOTH" if (h[j] > RH and l[j] < RL) else ("HIGH" if h[j] > RH else "LOW")
            j_primero = j
        alto = not gast_alto and h[j] > RH
        bajo = not gast_bajo and l[j] < RL
        if alto and bajo:
            return "BOTH_SIDES_SAME_BAR", None, 0, primero, j_primero
        if alto:
            if c[j] < RH:
                return "SIGNAL", j, -1, primero, j_primero
            gast_alto = True
        if bajo:
            if c[j] > RL:
                return "SIGNAL", j, 1, primero, j_primero
            gast_bajo = True
    return "NO_FALSE_BREAK", None, 0, primero, j_primero


def gestionar(o, h, l, c, js, d, E, SL, TP):
    """Gestión en las velas `js` (desde la de entrada; la última es la anterior a las 12:00). La vela de entrada cuenta
    entera. Stop y objetivo en la misma vela: pérdida. Hueco más allá del stop: apertura. Si no toca nada: cierre de
    la última vela (salida por tiempo). Devuelve (j_salida, salida, motivo, mae, mfe) en precio."""
    mae = mfe = 0.0
    for n, m in enumerate(js):
        peor, mejor = (l[m], h[m]) if d == 1 else (h[m], l[m])
        if (peor <= SL) if d == 1 else (peor >= SL):
            salida = (min(SL, o[m]) if d == 1 else max(SL, o[m])) if n > 0 else SL
            mfe = max(mfe, min((mejor - E) * d, (TP - E) * d))
            return m, salida, "SL", min(mae, (salida - E) * d), mfe
        mae = min(mae, (peor - E) * d)
        mfe = max(mfe, min((mejor - E) * d, (TP - E) * d))
        if (mejor >= TP) if d == 1 else (mejor <= TP):
            return m, TP, "TP", mae, mfe
    m = js[-1]
    return m, c[m], "TIME", mae, mfe


def backtest(m1: pd.DataFrame, cfg: Config = Config(), excluir: frozenset = frozenset(), prep: dict | None = None):
    """Devuelve (operaciones, días). `días` tiene una fila por día evaluado con las estadísticas del rango."""
    P = prep or preparar(m1, cfg)
    v, atr = P["v15"], P["atr"]
    o, h, l, c = (v[x].to_numpy() for x in ("open", "high", "low", "close"))
    aj = v.ajuste.to_numpy() if "ajuste" in v else np.zeros(len(v))
    ini, fin = v.index, pd.DatetimeIndex(v.fin)
    ns = ini.as_unit("ns").asi8
    fechas = pd.Index(ini.tz_convert(LONDRES).date).unique()
    saldo, ops, dias = cfg.saldo_inicial, [], []
    vp = cfg.valor_punto
    for f in fechas:
        if pd.Timestamp(f).weekday() >= 5 or f in excluir:
            continue
        t = lambda hh: hora_local_a_utc(f, hh, LONDRES).value  # noqa: E731
        pos = lambda a, b: np.arange(np.searchsorted(ns, a), np.searchsorted(ns, b))  # noqa: E731
        jr = pos(t(cfg.rango[0]), t(cfg.rango[1]))
        dia = {"fecha": f}
        dias.append(dia)
        if len(jr) != 4 or h[jr].max() <= l[jr].min():
            dia["estado"] = "RANGE_INCOMPLETE"
            continue
        RH, RL = h[jr].max(), l[jr].min()
        a0 = aj[jr[-1]]
        medio_real = (RH + RL) / 2 - a0
        dia.update(range_high=RH - a0, range_low=RL - a0, range_usd=RH - RL, range_pct=(RH - RL) / medio_real * 100)
        jw = pos(t(cfg.rango[1]), t(cfg.ultima_senal) + 1)        # velas que empiezan de 09:00 a 11:30
        estado, j, d, primero, jp = buscar_falsa_ruptura(h, l, c, jw, RH, RL)
        dia.update(estado=estado, first_extreme_attacked=primero,
                   t_first_attack=ini[jp] if jp is not None else None)
        if estado != "SIGNAL":
            continue
        prof = (h[j] - RH) if d == -1 else (RL - l[j])
        dia.update(side="SHORT" if d == -1 else "LONG", t_false_break=ini[j], break_depth=prof,
                   break_depth_ratio=prof / (RH - RL))
        jm = np.arange(j + 1, np.searchsorted(ns, t(cfg.cierre)))   # de la vela de entrada a la última antes de 12:00
        if len(jm) == 0:
            dia["estado"] = "NO_ENTRY_BAR"
            continue
        e = jm[0]
        E = o[e]
        SL = (h[j] + cfg.buffer_atr * atr[j]) if d == -1 else (l[j] - cfg.buffer_atr * atr[j])
        R = (E - SL) * d
        if R <= 0:
            dia["estado"] = "ENTRY_BEYOND_STOP"
            continue
        oz = contratos(saldo, cfg.riesgo_pct, R, cfg.valor_punto)
        if oz < 1:
            dia["estado"] = "POSITION_SIZE_BELOW_MINIMUM"
            continue
        TP = E + d * cfg.tp_r * R
        m, X, mot, mae, mfe = gestionar(o, h, l, c, jm, d, E, SL, TP)
        bruto = (X - E) * d
        neto = bruto - coste_onza(cfg.costes, mot)
        op = {"fecha": f, "t_senal": fin[j], "t_entrada": ini[e], "t_salida": fin[m], "direccion": d,
              "lado": dia["side"], "entrada": E, "sl": SL, "tp": TP, "salida": X, "resultado": mot, "onzas": oz,
              "riesgo_pts": R, "riesgo_usd": R * oz * vp, "bruto_usd": bruto * oz * vp,
              "costes_usd": (bruto - neto) * oz * vp, "neto_usd": neto * oz * vp, "r": neto / R, "r_bruto": bruto / R, "mae_r": mae / R, "mfe_r": mfe / R,
              "duracion_h": (fin[m] - ini[e]).total_seconds() / 3600, "saldo_antes": saldo,
              "range_high": RH - a0, "range_low": RL - a0, "range_usd": RH - RL, "range_pct": dia["range_pct"],
              "stop_distance_usd": R, "break_depth": prof, "break_depth_ratio": prof / (RH - RL),
              "t_false_break": ini[j], "atr_15m": atr[j], "cruza_roll": False,
              "entrada_real": E - aj[e], "sl_real": SL - aj[e], "tp_real": TP - aj[e]}
        ops.append(op)
        dia.update(estado="TRADED", result=mot, r=op["r"])
        saldo += op["neto_usd"]
    return pd.DataFrame(ops), pd.DataFrame(dias)


def senales(m1: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    """Para la auditoría de look-ahead: instantes y distancias (independientes del ajuste por rolls)."""
    ops, _ = backtest(m1, cfg)
    if ops.empty:
        return pd.DataFrame({"t_senal": pd.Series(dtype="datetime64[ns, UTC]")})
    return pd.DataFrame({"t_senal": ops.t_entrada, "direccion": ops.direccion, "riesgo": ops.riesgo_pts.round(6),
                         "rango": ops.range_usd.round(6), "prof": ops.break_depth.round(6)}).reset_index(drop=True)


def alerta(op, version: str = VERSION, activo: str = "GC") -> str:
    E, SL, TP = op["entrada_real"], op["sl_real"], op["tp_real"]
    return (f"{'LONG' if op['direccion'] == 1 else 'SHORT'} — {version}\n"
            f"Time (London): {pd.Timestamp(op['t_entrada']).tz_convert(LONDRES):%Y-%m-%d %H:%M}\n"
            f"Entry ({activo}): {E:.2f}\nSL: {SL:.2f}\nTP: {TP:.2f}\nRR: {abs(TP - E) / abs(E - SL):.1f}\n"
            f"Reason: London range false break of the {'HIGH' if op['direccion'] == -1 else 'LOW'}")
