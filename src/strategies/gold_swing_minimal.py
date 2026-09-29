"""GOLD_SWING_MINIMAL_v1.0: 4H cierre vs EMA 50 → 1H retroceso + recuperación → entrada → 2R.

Reglas en edges/gold_swing_minimal.md. Solo genera señales y simula; nunca ejecuta órdenes.
Usa velas de 1H y 4H (desde 1M, ajustadas por cambios de contrato); cada vela solo desde su cierre nominal.
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from src.risk.position_sizing import contratos
from src.strategies.gold_swing_simple import ESCENARIOS, CostesOro, ajustar_rolls, atr_wilder, velas_4h, velas_reloj

VERSION = "GOLD_SWING_MINIMAL_v1.0"


@dataclass(frozen=True)
class Config:
    version: str = VERSION
    ema: int = 50
    tp_r: float = 2.0
    buffer_atr: float = 0.10
    atr_n: int = 14
    ventana: int = 5                 # velas 1H para la señal después del retroceso vigente
    riesgo_pct: float = 0.005
    saldo_inicial: float = 50_000.0
    costes: CostesOro = ESCENARIOS["B"]

    def con(self, **cambios) -> "Config":
        return replace(self, **cambios)


def direccion_4h(v4: pd.DataFrame, n: int) -> np.ndarray:
    """+1 si el cierre 4H > EMA n, -1 si <, 0 si igual o durante las n primeras velas (calentamiento).
    La EMA de la vela j solo usa cierres hasta j."""
    c = v4.close
    ema = c.ewm(span=n, adjust=False).mean().to_numpy()
    d = np.sign(c.to_numpy() - ema).astype(int)
    d[:n] = 0
    return d


def direccion_en_1h(v1: pd.DataFrame, v4: pd.DataFrame, dir4: np.ndarray) -> np.ndarray:
    """Dirección vigente al cierre de cada vela 1H: la de la última vela 4H cerrada (fin 4H <= fin 1H)."""
    j = np.searchsorted(pd.DatetimeIndex(v4.fin).asi8, pd.DatetimeIndex(v1.fin).asi8, side="right") - 1
    return np.where(j >= 0, dir4[np.clip(j, 0, None)], 0)


def gestionar_1h(o, h, l, c, e, d, E, SL, TP):
    """Gestión desde la vela e (entrada en su apertura; la vela cuenta entera). Stop y objetivo en la misma vela:
    pérdida. Hueco más allá del stop: salida en la apertura. Devuelve (m, salida, motivo, mae, mfe) en precio."""
    mae = mfe = 0.0
    for m in range(e, len(o)):
        peor, mejor = (l[m], h[m]) if d == 1 else (h[m], l[m])
        if (peor <= SL) if d == 1 else (peor >= SL):
            salida = (min(SL, o[m]) if d == 1 else max(SL, o[m])) if m > e else SL
            mfe = max(mfe, min((mejor - E) * d, (TP - E) * d))
            return m, salida, "SL", min(mae, (salida - E) * d), mfe
        mae = min(mae, (peor - E) * d)
        mfe = max(mfe, min((mejor - E) * d, (TP - E) * d))
        if (mejor >= TP) if d == 1 else (mejor <= TP):
            return m, TP, "TP", mae, mfe
    return len(o) - 1, c[-1], "END_OF_DATA", mae, mfe


def preparar(m1: pd.DataFrame, cfg: Config) -> dict:
    m = ajustar_rolls(m1)
    v1, v4 = velas_reloj(m, 60), velas_4h(m)
    return {"v1": v1, "v4": v4, "rolls": m.attrs["rolls"], "atr": atr_wilder(v1, cfg.atr_n)}


def backtest(m1: pd.DataFrame, cfg: Config = Config(), prep: dict | None = None):
    """Devuelve (operaciones, señales). `señales` incluye las ignoradas por operación abierta."""
    P = prep or preparar(m1, cfg)
    v1, v4, atr = P["v1"], P["v4"], P["atr"]
    dir4 = direccion_4h(v4, cfg.ema)
    dir1 = direccion_en_1h(v1, v4, dir4)
    o, h, l, c = (v1[x].to_numpy() for x in ("open", "high", "low", "close"))
    aj = v1.ajuste.to_numpy() if "ajuste" in v1 else np.zeros(len(v1))
    ini, fin = v1.index, pd.DatetimeIndex(v1.fin)
    rolls = pd.DatetimeIndex(P["rolls"], tz="UTC")
    saldo, libre = cfg.saldo_inicial, 0
    pb = pb_d = None
    ops, senales_ = [], []
    for s in range(1, len(v1)):
        if s == libre:
            pb = None                                    # tras cerrar una operación, se empieza de cero
        d = dir1[s]
        if pb is not None and (d != pb_d or s - pb > cfg.ventana):
            pb = None                                    # cambio de dirección 4H o caducidad
        if pb is not None and ((c[s] > h[s - 1]) if pb_d == 1 else (c[s] < l[s - 1])):
            k = pb
            pb = None
            SL = (l[k] - cfg.buffer_atr * atr[s]) if pb_d == 1 else (h[k] + cfg.buffer_atr * atr[s])
            fila = {"t_senal": fin[s], "lado": "LONG" if pb_d == 1 else "SHORT", "direccion": pb_d,
                    "t_retroceso": ini[k], "sl": SL}
            senales_.append(fila)
            if s < libre:
                fila["estado"] = "IGNORED_TRADE_OPEN"
                continue
            e = s + 1
            if e >= len(v1):
                fila["estado"] = "NO_DATA"
                continue
            E = o[e]
            R = (E - SL) * pb_d
            TP = E + pb_d * cfg.tp_r * R
            fila.update(entrada=E, tp=TP, entrada_real=E - aj[e], sl_real=SL - aj[e], tp_real=TP - aj[e])
            if R <= 0:
                fila["estado"] = "ENTRY_BEYOND_STOP"
                continue
            oz = contratos(saldo, cfg.riesgo_pct, R, 1.0)
            if oz < 1:
                fila["estado"] = "POSITION_SIZE_BELOW_MINIMUM"
                continue
            m, X, mot, mae, mfe = gestionar_1h(o, h, l, c, e, pb_d, E, SL, TP)
            bruto = (X - E) * pb_d
            neto = bruto - cfg.costes.por_onza(mot)
            t_ent, t_sal = ini[e], fin[m]
            ops.append({"t_senal": fin[s], "t_entrada": t_ent, "t_salida": t_sal, "direccion": pb_d,
                        "lado": fila["lado"], "entrada": E, "sl": SL, "tp": TP, "salida": X, "resultado": mot,
                        "onzas": oz, "riesgo_pts": R, "riesgo_usd": R * oz, "bruto_usd": bruto * oz,
                        "costes_usd": (bruto - neto) * oz, "neto_usd": neto * oz, "r": neto / R, "r_bruto": bruto / R,
                        "mae_r": mae / R, "mfe_r": mfe / R, "duracion_h": (t_sal - t_ent).total_seconds() / 3600,
                        "saldo_antes": saldo, "t_retroceso": ini[k], "atr_1h": atr[s],
                        "cruza_roll": bool(((rolls > t_ent) & (rolls < t_sal)).any()),
                        "entrada_real": E - aj[e], "sl_real": SL - aj[e], "tp_real": TP - aj[e]})
            fila["estado"] = "TAKEN"
            saldo += ops[-1]["neto_usd"]
            libre = m + 1
            continue
        if d != 0 and ((c[s] < c[s - 1]) if d == 1 else (c[s] > c[s - 1])):
            pb, pb_d = s, d                              # retroceso nuevo (o reinicio del setup)
    return pd.DataFrame(ops), pd.DataFrame(senales_)


def senales(m1: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    """Para la auditoría de look-ahead: instantes y distancias (el ajuste por rolls desplaza niveles, no distancias)."""
    ops, _ = backtest(m1, cfg)
    if ops.empty:
        return pd.DataFrame({"t_senal": pd.Series(dtype="datetime64[ns, UTC]")})
    return pd.DataFrame({"t_senal": ops.t_entrada, "direccion": ops.direccion, "riesgo": ops.riesgo_pts.round(6),
                         "t_retroceso": ops.t_retroceso}).reset_index(drop=True)


def alerta(op) -> str:
    """Texto de la señal con precios REALES del contrato GC (el sistema nunca ejecuta órdenes)."""
    E, SL, TP = op["entrada_real"], op["sl_real"], op["tp_real"]
    return (f"{'LONG' if op['direccion'] == 1 else 'SHORT'} — {VERSION}\n"
            f"Time (UTC): {pd.Timestamp(op['t_senal']):%Y-%m-%d %H:%M}\n"
            f"Entry (GC): {E:.2f}\nSL: {SL:.2f}\nTP: {TP:.2f}\nRR: {abs(TP - E) / abs(E - SL):.1f}")
