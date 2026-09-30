"""Fases 1-4 para las dos estrategias validadas: comprobaciones empíricas del código, reproducción exacta,
ventanas anuales, sensibilidad, costes, latencia, regímenes y bootstrap por bloques."""
from __future__ import annotations

import itertools
import time

import numpy as np
import pandas as pd

from src.data.calidad import informe as informe_calidad
from src.data.cargadores import cargar_databento
from src.data.datos import excluidos, sesiones, velas_1m
from src.engine.costes import Costes
from src.engine.lookahead import comprobar
from src.strategies import nq_rsi2, zona_ruido as z

from . import metricas as mt
from . import variantes_zr

ORIGINAL = {  # cifras de los informes originales (reports/ZONA_RUIDO_MNQ_v1.0, edges/nq_rsi2.md, reports/CARTERA_ORO_v1.0)
    "zona_ruido": {"desarrollo": {"operaciones": 1924, "profit_factor": 1.194, "t_por_operacion": 2.26, "neto_$": 11034},
                   "posterior": {"operaciones": 800, "profit_factor": 1.215, "neto_$": 10472}},
    "rsi2": {"desarrollo": {"operaciones": 97, "profit_factor": 1.46}, "posterior": {"operaciones": 61, "profit_factor": 1.93}},
}


def _normalizar_zr(o: pd.DataFrame) -> pd.DataFrame:
    o = o.copy()
    o["t_entrada"] = mt.a_ny(o.t_entrada).tz_convert("UTC")
    o["t_salida"] = mt.a_ny(o.t_salida).tz_convert("UTC")
    return o


def _normalizar_rsi(o: pd.DataFrame) -> pd.DataFrame:
    o = o.copy()
    o["t_entrada"] = pd.to_datetime(o.t_entrada, utc=True)
    o["t_salida"] = pd.to_datetime(o.t_salida, utc=True)
    return o


class Contexto:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.m1 = velas_1m("NQ")
        self.ex = excluidos("NQ")
        self.corte = pd.Timestamp(cfg["corte_desarrollo"])
        ny = self.m1.index.tz_convert(mt.NY)
        rth = (ny.hour * 60 + ny.minute >= 570) & (ny.hour < 16)
        self.sesiones = pd.DatetimeIndex(sorted(set(ny[rth].date)))
        self.ses_d = sesiones(self.m1)

    def partir(self, o: pd.DataFrame):
        t = mt.a_ny(o.t_entrada).tz_localize(None)
        return o[t < self.corte], o[t >= self.corte]

    def evaluar(self, o: pd.DataFrame, capital: float, bootstrap: bool = True) -> dict:
        d = mt.diario(o, self.sesiones)
        r = mt.resumen(o, d, capital)
        if bootstrap and len(o) > 2:
            b = self.cfg["bootstrap"]
            r["IC95_bloques_$"] = mt.ic_bloques(d, b["bloque_sesiones"], b["n"], self.cfg["semilla"])
            r["IC95_iid_$"] = mt.ic_iid(o.neto)
        return r


# ------------------------------------------------------------------------------------------ fase 1: auditoría
def auditoria_empirica(ctx: Contexto) -> dict:
    res = {}
    t0 = time.time()
    bruto = cargar_databento("NQ")
    res["calidad_datos_NQ"] = {k: (str(v) if not isinstance(v, (int, float)) else v) for k, v in informe_calidad(bruto, "NQ").items()}
    res["filas_procesadas_vs_brutas"] = {"brutas": len(bruto), "procesadas": len(ctx.m1)}
    del bruto
    # Truncamiento: señales anteriores a cada corte no cambian al quitar datos posteriores (2 años, 3 cortes)
    tramo = ctx.m1[(ctx.m1.index >= "2021-01-01") & (ctx.m1.index < "2023-01-01")]
    cortes = [pd.Timestamp(x, tz="UTC") for x in ("2021-06-12", "2022-01-15", "2022-08-13")]
    res["lookahead_truncamiento_zona_ruido"] = comprobar(lambda v: z.senales(v, z.Config()), tramo, cortes) or "OK"
    tr2 = ctx.m1[(ctx.m1.index >= "2017-01-01") & (ctx.m1.index < "2020-01-01")]
    res["lookahead_truncamiento_rsi2"] = comprobar(lambda v: nq_rsi2.senales(v), tr2,
                                                   [pd.Timestamp(x, tz="UTC") for x in ("2018-03-10", "2019-02-09")]) or "OK"
    res["segundos"] = round(time.time() - t0, 1)
    return res


def comprobaciones_operaciones(nombre: str, o: pd.DataFrame) -> dict:
    """Coherencia de cada operación: sin solapes (una posición), entrada después de la señal, neto = bruto - costes."""
    o = o.sort_values("t_entrada")
    solapes = int((o.t_entrada.to_numpy()[1:] < o.t_salida.to_numpy()[:-1]).sum())
    out = {"operaciones": len(o), "solapes_de_posicion": solapes,
           "salida_antes_de_entrada": int((o.t_salida < o.t_entrada).sum())}
    if nombre == "zona_ruido":
        out["neto_distinto_de_bruto_menos_comision"] = int((~np.isclose(o.neto, o.bruto - o.comision)).sum())
        m = mt.a_ny(o.t_entrada)
        minuto = (m.hour - 9) * 60 + m.minute - 30
        out["entradas_fuera_de_chequeo"] = int((~np.isin(minuto, z.Config().chequeos)).sum())
    else:
        out["entrada_no_posterior_a_senal"] = int((pd.to_datetime(o.t_entrada, utc=True) <= pd.to_datetime(o.t_senal, utc=True)).sum())
    return out


# ------------------------------------------------------------------------------------------ fase 2-4: runs
def correr_zr(ctx: Contexto, cfg_z: z.Config | None = None, retardo: int = 0) -> pd.DataFrame:
    cfg_z = cfg_z or z.Config()
    if retardo:
        return _normalizar_zr(variantes_zr.backtest(ctx.m1, cfg_z, ctx.ex, retardo))
    o, _ = z.backtest(ctx.m1, cfg_z, ctx.ex)
    return _normalizar_zr(o)


def correr_rsi(ctx: Contexto, cfg_r: nq_rsi2.Config | None = None) -> pd.DataFrame:
    o = nq_rsi2.backtest(ctx.m1, cfg_r or nq_rsi2.Config(), ctx.ex)
    return _normalizar_rsi(o)


def vecindad_zr(ctx: Contexto) -> pd.DataFrame:
    v = ctx.cfg["zona_ruido"]["vecindad"]
    filas = []
    for dias in v["dias_ruido"]:
        base = z.Config().con(dias_ruido=dias)
        rth, daily, sigma = z.preparar(ctx.m1, base)                  # una preparación por ventana de ruido
        grupos = dict(tuple(rth.groupby("date")))
        for mult in v["mult"]:
            c = base.con(mult=mult)
            ops = []
            for fecha, dia in grupos.items():
                if fecha in ctx.ex or fecha not in sigma.index or sigma.loc[fecha].isna().all():
                    continue
                d = daily.loc[fecha]
                ops.extend(z.operar_dia(fecha, dia, d.open, d.prev_close, sigma.loc[fecha], c))
            o = pd.DataFrame(ops)
            x = o.neto
            filas.append({"dias_ruido": dias, "mult": mult, "operaciones": len(o),
                          "PF": round(x[x > 0].sum() / -x[x < 0].sum(), 3), "expectativa_$": round(x.mean(), 2),
                          "t": round(x.mean() / x.std(ddof=1) * np.sqrt(len(x)), 2)})
    return pd.DataFrame(filas)


def vecindad_rsi(ctx: Contexto) -> pd.DataFrame:
    v = ctx.cfg["rsi2"]["vecindad"]
    filas = []
    for e, s, m in itertools.product(v["entrada"], v["salida"], v["max_dias"]):
        o = nq_rsi2.backtest(ctx.m1, nq_rsi2.Config().con(entrada=e, salida=s, max_dias=m), ctx.ex)
        x = o.neto
        filas.append({"entrada": e, "salida": s, "max_dias": m, "operaciones": len(o),
                      "PF": round(x[x > 0].sum() / -x[x < 0].sum(), 3) if (x < 0).any() else np.inf,
                      "expectativa_$": round(x.mean(), 2), "t": round(x.mean() / x.std(ddof=1) * np.sqrt(len(x)), 2)})
    return pd.DataFrame(filas)


def regimenes(ctx: Contexto, o: pd.DataFrame) -> dict:
    """Clasificación descriptiva (no usada en reglas) con datos del día ANTERIOR a la entrada."""
    s = ctx.ses_d
    vol = s.ret.rolling(20).std().shift(1)
    tend = (s.close_aj > s.close_aj.rolling(200).mean()).shift(1)
    terc = pd.qcut(vol, 3, labels=["vol baja", "vol media", "vol alta"])
    dia = mt.a_ny(o.t_entrada).tz_localize(None).normalize()
    idx = s.index.searchsorted(dia, side="right") - 1                 # última sesión cerrada <= fecha de entrada
    idx = np.clip(idx, 0, len(s) - 1)
    return {"volatilidad_20d": mt.por_clave(o, terc.to_numpy()[idx], "volatilidad"),
            "tendencia_sma200": mt.por_clave(o, np.where(tend.to_numpy()[idx] == True, "sobre SMA200", "bajo SMA200"), "tendencia")}  # noqa: E712


def analizar(ctx: Contexto, nombre: str, o: pd.DataFrame, capital: float) -> dict:
    dev, pos = ctx.partir(o)
    res = {"total": ctx.evaluar(o, capital), "desarrollo": ctx.evaluar(dev, capital), "posterior (ya visto)": ctx.evaluar(pos, capital),
           "comprobaciones": comprobaciones_operaciones(nombre, o), "anual": mt.por_periodo(o, "Y"),
           "trimestral": mt.por_periodo(o, "Q"), "mensual": mt.por_periodo(o, "M"), "regimenes": regimenes(ctx, o)}
    t = mt.a_ny(o.t_entrada)
    res["dia_semana"] = mt.por_clave(o, t.dayofweek.map(dict(enumerate(["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]))), "dia")
    res["franja"] = mt.por_clave(o, t.hour.astype(str) + ":" + (t.minute // 30 * 30).astype(str).str.zfill(2), "hora_NY")
    horas = (o.t_salida - o.t_entrada).dt.total_seconds() / 3600
    if nombre == "zona_ruido":
        res["exposicion_%_tiempo_RTH"] = round(horas.sum() / (len(ctx.sesiones) * 6.5) * 100, 1)
    else:
        res["exposicion_%_tiempo_calendario"] = round(horas.sum() / ((o.t_salida.max() - o.t_entrada.min()).total_seconds() / 3600) * 100, 1)
    return res
