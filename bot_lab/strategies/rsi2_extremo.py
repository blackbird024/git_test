"""BOT 18 — RSI(2) EXTREMO + FILTRO DE TENDENCIA (NQ diario, largos y cortos). Variante NUEVA y separada: no toca
src/strategies/nq_rsi2.py (BOT 01, en forward test).

Hipótesis: la reversión a la media tras un extremo de RSI(2) funciona mejor cuando el mercado no está en una
tendencia extrema en contra.

Reglas (mismo cálculo y ejecución que el BOT 01: sesiones de CME, cierres ajustados por cambio de contrato, señal al
cierre y entrada en la reapertura de Globex con 2 ticks de deslizamiento):
  - Largo si RSI(2) < L; corto si RSI(2) > 100 − L (L = 5 o 3).
  - Salida: largo si RSI(2) > 70, corto si RSI(2) < 30, o tras 5 sesiones; en la apertura siguiente.
  - Filtros (A, B, C, D):
      A: ninguno.
      B: EMA200 diaria (largos solo con cierre > EMA200; cortos solo con cierre < EMA200).
      C: VWAP de 20 sesiones (media de los VWAP de sesión ponderada por volumen): largos por encima, cortos debajo.
      D: B y C.
Se informa cuánto mejora o empeora cada filtro respecto a A, y largos/cortos por separado.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot_lab.core import indicadores as ind
from bot_lab.strategies import base as B
from src.data.datos import sesiones
from src.engine.costes import Costes

BOT = "18"
NOMBRE = "RSI(2) extremo + filtro de tendencia"
HIPOTESIS = ("La reversión tras un extremo de RSI(2) funciona mejor cuando el mercado no está en una tendencia "
             "extrema en contra.")
MARCO, SESION, FRECUENCIA = "1D", "sesión CME completa", "diaria"

VARIANTES = {}
for _l in (5, 3):
    for _f, _nom in (("A", "puro"), ("B", "EMA200"), ("C", "VWAP20"), ("D", "EMA200+VWAP20")):
        VARIANTES[f"18.{'1' if _l == 5 else '2'}{_f} RSI<{_l}/>{100 - _l} {_nom}"] = dict(umbral=_l, filtro=_f, max_dias=5)
BASE = "18.1B RSI<5/>95 EMA200"


def vecindad(p: dict) -> dict:
    u = p["umbral"]
    out = {f"umbral={x}": {**p, "umbral": x} for x in sorted({max(1, u - 2), u + 2})}
    out.update({f"max_dias={x}": {**p, "max_dias": x} for x in (4, 6)})
    return out


def preparar(ctx) -> pd.DataFrame:
    def f():
        s = sesiones(ctx.m1)
        tp = (ctx.H + ctx.L + ctx.C) / 3
        g = pd.DataFrame({"s": ctx.ses_fecha, "pv": tp * ctx.V, "v": ctx.V}).groupby("s").sum()
        g.index = pd.to_datetime(g.index)
        vw_ses = (g.pv / g.v).reindex(s.index)
        vol = g.v.reindex(s.index)
        vw_aj = vw_ses * s.close_aj / s.close
        s["vwap20"] = (vw_aj * vol).rolling(20).sum() / vol.rolling(20).sum()
        s["ema200"] = ind.ema(s.close_aj.to_numpy(), 200)
        s["rsi"] = ind.rsi(s.close_aj.to_numpy(), 2)
        s["vol20"] = s.ret.rolling(20, min_periods=10).std()
        return s
    return B.cache(ctx, "sesiones_rsi", f)


def senales(s: pd.DataFrame, p: dict) -> np.ndarray:
    u = p["umbral"]
    largo = (s.rsi < u).to_numpy().copy()
    corto = (s.rsi > 100 - u).to_numpy().copy()
    if p["filtro"] in ("B", "D"):
        largo &= (s.close_aj > s.ema200).to_numpy()
        corto &= (s.close_aj < s.ema200).to_numpy()
    if p["filtro"] in ("C", "D"):
        largo &= (s.close_aj > s.vwap20).to_numpy()
        corto &= (s.close_aj < s.vwap20).to_numpy()
    return np.where(largo, 1, np.where(corto, -1, 0))


def ejecutar(ctx, p: dict, mult: float = 1.0) -> pd.DataFrame:
    s = preparar(ctx)
    d_sig = senales(s, p)
    c = Costes(multiplicador=mult)
    tick, pv = 0.25, 2.0
    n, i, ops = len(s), 0, []
    op_aj, op, rsi_ = s.open_aj.to_numpy(), s.open.to_numpy(), s.rsi.to_numpy()
    t0 = [pd.Timestamp(x) for x in s.t_primera]
    t1 = [pd.Timestamp(x) for x in s.t_ultima]
    vol20 = s.vol20.to_numpy()
    excl = ctx.excluir
    while i < n - 1:
        d = d_sig[i]
        if d == 0 or s.index[i + 1].date() in excl:
            i += 1
            continue
        e = i + 1
        k = e
        motivo = "fin_datos"
        while k < n - 1:
            if (d == 1 and rsi_[k] > 70) or (d == -1 and rsi_[k] < 30):
                motivo = "rsi"
                break
            if k - e + 1 >= p["max_dias"]:
                motivo = "tiempo"
                break
            k += 1
        x = min(k + 1, n - 1)
        ret = d * (op_aj[x] / op_aj[e] - 1)
        desl = (c.ticks(t0[e]) + c.ticks(t0[x])) * tick
        bruto = op[e] * ret * pv
        neto = bruto - desl * pv - c.comision(1)
        ops.append({"t_senal": t1[i], "t_entrada": t0[e], "t_salida": t0[x], "direccion": d, "entrada": op[e],
                    "sesiones": x - e, "bruto": bruto, "comision": c.comision(1), "neto": neto,
                    "r": (neto / (op[e] * pv)) / vol20[i] if vol20[i] > 0 else np.nan, "motivo": motivo})
        i = x
    o = pd.DataFrame(ops, columns=["t_senal", "t_entrada", "t_salida", "direccion", "entrada", "sesiones", "bruto",
                                   "comision", "neto", "r", "motivo"])
    if len(o):
        o["t_entrada"] = pd.to_datetime(o.t_entrada, utc=True)
        o["t_salida"] = pd.to_datetime(o.t_salida, utc=True)
    return o
