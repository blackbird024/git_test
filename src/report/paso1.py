"""Paso 1: versión mínima de cada ventaja, SOLO con el periodo de desarrollo (el fuera de muestra no se carga)."""
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.datos import excluidos, inicio_fuera_de_muestra, velas_1m
from src.horas import sesion_cme
from src.metrics.metricas import por_anio, resumen
from src.strategies import barrido_londres, nq_rsi2, oro_fin_de_semana

INFORMES = Path(__file__).resolve().parent.parent.parent / "reports"


def desarrollo(raiz: str) -> pd.DataFrame:
    """Velas de 1M anteriores al corte (sesiones de CME < inicio del fuera de muestra)."""
    m1 = velas_1m(raiz)
    corte = inicio_fuera_de_muestra(raiz).date()
    return m1[sesion_cme(m1.index) < corte]


def t_de(x: pd.Series) -> float:
    x = x.dropna()
    return round(x.mean() / x.std() * np.sqrt(len(x)), 2) if len(x) > 1 else float("nan")


def md(df: pd.DataFrame) -> str:
    return df.to_markdown()


def ejecutar() -> str:
    texto = ["# Paso 1 — Versión mínima de cada ventaja (solo periodo de desarrollo)", ""]

    # ------------------------------------------------------------------------------ 1. barrido
    gc = desarrollo("GC")
    ex = excluidos("GC")
    ops = barrido_londres.backtest(gc, barrido_londres.Config(), ex)
    res1 = resumen(ops)
    tipos = ops.motivo.str.split("|").str[1].value_counts().to_dict() if len(ops) else {}
    salidas = ops.motivo.str.split("|").str[0].value_counts().to_dict() if len(ops) else {}
    est = barrido_londres.estudio_ventanas(gc, barrido_londres.Config(), ex)
    comp = est.groupby("dentro").agg(setups=("r", "size"), R_medio=("r", "mean"),
                                     acierto_pct=("neto", lambda x: (x > 0).mean() * 100))
    comp["t"] = est.groupby("dentro").r.apply(t_de)
    comp.index = comp.index.map({True: "dentro de las ventanas", False: "fuera de las ventanas"})
    por_franja = est.groupby("franja").agg(setups=("r", "size"), R_medio=("r", "mean"))
    texto += ["## 1. Barrido de Londres en el oro (MGC)", "",
              f"Periodo: {gc.index.min().date()} → {gc.index.max().date()}", "",
              pd.DataFrame([res1]).to_markdown(index=False), "",
              f"Tipo de entrada: {tipos}. Salidas: {salidas}.", "", "### Por año", "", md(por_anio(ops)), "",
              "### Pregunta clave: ¿giran más los barridos dentro de las ventanas?", "",
              "Primer setup de cada franja, cada operación por separado, cierre a las 12:00.", "",
              md(comp.round(3)), "", md(por_franja.round(3)), ""]

    # ------------------------------------------------------------------------ 2. fin de semana
    pares = oro_fin_de_semana.pares(gc, excluir=ex)
    fs = pares[pares.fin_de_semana].reset_index(drop=True)
    res2 = resumen(fs)
    por_dia = pares.groupby(["fin_de_semana", "dia_entrada"]).agg(
        pares=("ret_%", "size"), ret_medio_pct=("ret_%", "mean"), pct_positivos=("ret_%", lambda x: (x > 0).mean() * 100))
    por_dia["t"] = pares.groupby(["fin_de_semana", "dia_entrada"])["ret_%"].apply(t_de)
    descom = fs[["hueco_%", "sesion_siguiente_%"]].agg(["mean"]).T
    descom["t"] = [t_de(fs["hueco_%"]), t_de(fs["sesion_siguiente_%"])]
    texto += ["## 2. Oro: comprar el viernes y vender el lunes (1 MGC)", "",
              pd.DataFrame([res2 | {"ret_medio_%": round(fs["ret_%"].mean(), 3), "t_ret": t_de(fs["ret_%"])}]).to_markdown(index=False), "",
              "### Por año", "", md(por_anio(fs)), "",
              "### Comparación con el resto de pares de sesiones (rendimiento neto de costes)", "",
              md(por_dia.round(3)), "",
              "### Descomposición del fin de semana (% medio)", "", md(descom.round(3)), ""]

    # ------------------------------------------------------------------------------- 3. RSI(2)
    nq = desarrollo("NQ")
    ops3 = nq_rsi2.backtest(nq, nq_rsi2.Config(), excluidos("NQ"))
    res3 = resumen(ops3)
    diario_bh = nq_rsi2.rendimiento_diario_medio(nq) * 100
    por_dia_op = (ops3["ret_%"] / ops3.sesiones).mean()
    texto += ["## 3. Nasdaq: RSI(2) con filtro de SMA200 (1 MNQ)", "",
              f"Primera señal posible tras 200 sesiones de historia. Periodo: {nq.index.min().date()} → {nq.index.max().date()}", "",
              pd.DataFrame([res3 | {"ret_medio_%": round(ops3["ret_%"].mean(), 3), "sesiones_medias": round(ops3.sesiones.mean(), 2)}]).to_markdown(index=False), "",
              f"Salidas: {ops3.motivo.value_counts().to_dict()}.", "",
              f"Rendimiento medio por sesión dentro de la operación: **{por_dia_op:.3f} %** frente a "
              f"**{diario_bh:.3f} %** por sesión de comprar y mantener.", "",
              "Todo el periodo es posterior a la publicación (Connors y Alvarez, 2008).", "",
              "### Por año", "", md(por_anio(ops3)), ""]

    (INFORMES / "paso1_ventajas.md").write_text("\n".join(texto), encoding="utf-8")
    return "\n".join(texto)
