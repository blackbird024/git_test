"""Paso 3: validación del RSI(2) con los criterios fijados en edges/nq_rsi2.md, e informes HTML.
El fuera de muestra se evalúa aquí por primera y única vez."""
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.datos import excluidos, inicio_fuera_de_muestra, sesiones_diarias_databento, velas_1m
from src.engine.costes import Costes
from src.metrics.metricas import por_anio, resumen
from src.metrics.montecarlo import drawdowns, resumen_mc
from src.report import html
from src.report.paso1 import desarrollo
from src.strategies import barrido_londres, nq_rsi2, oro_fin_de_semana

INFORMES = Path(__file__).resolve().parent.parent.parent / "reports"


def validar_rsi2(cfg: nq_rsi2.Config) -> dict:
    nq_total, ex = velas_1m("NQ"), excluidos("NQ")
    corte = inicio_fuera_de_muestra("NQ")
    ops = nq_rsi2.backtest(nq_total, cfg, ex)
    sesion_ent = pd.DatetimeIndex(ops.t_entrada).tz_convert("America/New_York") + pd.Timedelta(hours=6)
    es_oos = sesion_ent.tz_localize(None).normalize() >= corte
    dev, oos = ops[~es_oos], ops[es_oos]
    r_dev, r_oos, r_tot = resumen(dev), resumen(oos), resumen(ops)

    # Sensibilidad (solo desarrollo): 27 combinaciones de ±20 %
    nq_dev = desarrollo("NQ")
    prep = {}
    filas = []
    for e_, s_, d_ in itertools.product((16, 20, 24), (56, 70, 84), (4, 5, 6)):
        c = cfg.con(entrada=e_, salida=s_, max_dias=d_)
        o = nq_rsi2.backtest(nq_dev, c, ex)
        filas.append({"entrada": e_, "salida": s_, "max_dias": d_, "pf": resumen(o)["profit_factor"],
                      "operaciones": len(o)})
    sens = pd.DataFrame(filas)
    del prep

    # Otro mercado: ES (diario de Databento, periodo completo)
    es = sesiones_diarias_databento("ES")
    cfg_es = cfg.con(valor_punto=5.0)                       # MES
    ops_es = nq_rsi2.backtest_sesiones(nq_rsi2.preparar_sesiones(es, cfg_es), cfg_es)
    r_es = resumen(ops_es)

    # Costes duplicados (periodo completo)
    ops_x2 = nq_rsi2.backtest(nq_total, cfg.con(costes=Costes(multiplicador=2.0)), ex)
    r_x2 = resumen(ops_x2)

    mc = resumen_mc(ops.neto, 1000)
    dd = drawdowns(ops.neto, 1000)

    criterios = [
        ("PF fuera de muestra ≥ 1,3", f"{r_oos.get('profit_factor')}", r_oos.get("profit_factor", 0) >= 1.3),
        ("Operaciones totales ≥ 100", f"{r_tot['operaciones']}", r_tot["operaciones"] >= 100),
        ("R medio fuera ≥ 50 % del de desarrollo", f"{r_oos.get('R_medio')} vs mínimo {round(0.5 * r_dev['R_medio'], 3)}",
         r_oos.get("R_medio", -9) >= 0.5 * r_dev["R_medio"]),
        ("Sensibilidad ±20 %: las 27 combinaciones con PF > 1", f"mínimo PF {sens.pf.min()}", bool((sens.pf > 1).all())),
        ("ES (otro mercado): PF > 1", f"{r_es.get('profit_factor')} ({r_es['operaciones']} operaciones)",
         r_es.get("profit_factor", 0) > 1),
        ("Costes duplicados: neto > 0", f"{r_x2['neto_$']:,.0f} $", r_x2["neto_$"] > 0),
    ]
    aprobada = all(ok for _, _, ok in criterios)
    tabla_crit = pd.DataFrame([{"criterio": c, "resultado": v, "¿cumple?": "SÍ" if ok else "NO"} for c, v, ok in criterios])
    periodos = pd.DataFrame({"desarrollo": r_dev, "fuera de muestra": r_oos, "total": r_tot}).T

    ver = "APROBADA" if aprobada else "RECHAZADA"
    pag = html.pagina(
        "RSI(2) en el Nasdaq (MNQ)", f"Connors (2008): largo si RSI(2) &lt; 20 y cierre &gt; SMA200; salida si RSI(2) &gt; 70 o a las 5 sesiones. "
        f"Datos: sesiones de CME 2015-2026. Fuera de muestra desde {corte.date()}. Tamaño: 1 MNQ.",
        f"Veredicto: {ver}", aprobada,
        [("Criterios del paso 3 (fijados antes de mirar el fuera de muestra)", html.tabla(tabla_crit, False)),
         ("Resultados por periodo", html.tabla(periodos)),
         ("Curva de capital", html.curva(ops, corte)),
         ("Resultados por año", html.barras_anuales(por_anio(ops)) + html.tabla(por_anio(ops))),
         ("Sensibilidad de los parámetros (±20 %, periodo de desarrollo)",
          html.mapas_calor(sens, "entrada", "salida", "max_dias") +
          "<p>Una meseta (todos los valores parecidos) indica robustez; un pico aislado, sobreajuste.</p>"),
         ("Otro mercado: S&amp;P 500 (ES), 2010-2026", html.tabla(pd.DataFrame([r_es]), False)),
         ("Costes duplicados", html.tabla(pd.DataFrame([r_x2]), False)),
         ("Monte Carlo", html.histograma_mc(dd, mc["dd_p95_$"]) + html.tabla(pd.DataFrame([mc]), False)),
         ("Walk-forward", "<p>No aplica: ningún parámetro se ha optimizado (son los de la especificación).</p>"),
         ("Compatibilidad con Apex", "<p><b>No compatible:</b> mantiene posiciones de un día para otro, y Apex exige "
          "cerrar antes del final de cada sesión. Solo para cuenta propia.</p>")])
    (INFORMES / "nq_rsi2.html").write_text(pag, encoding="utf-8")
    return {"aprobada": aprobada, "criterios": tabla_crit, "periodos": periodos, "anios": por_anio(ops),
            "sens": sens, "es": r_es, "x2": r_x2, "mc": mc, "ops": ops}


def informes_rechazadas() -> None:
    gc, ex = desarrollo("GC"), excluidos("GC")
    ops = barrido_londres.backtest(gc, barrido_londres.Config(), ex)
    est = barrido_londres.estudio_ventanas(gc, barrido_londres.Config(), ex)
    comp = est.groupby("dentro").agg(setups=("r", "size"), R_medio=("r", "mean"))
    comp.index = comp.index.map({True: "dentro de las ventanas", False: "fuera de las ventanas"})
    pag = html.pagina("Barrido de Londres en el oro (MGC)", "Versión mínima del paso 1, periodo de desarrollo 2015-2023.",
                      "Veredicto: RECHAZADA en el paso 1 (sin ventaja)", False,
                      [("Resultados", html.tabla(pd.DataFrame([resumen(ops)]), False)),
                       ("Curva de capital", html.curva(ops)),
                       ("Por año", html.barras_anuales(por_anio(ops)) + html.tabla(por_anio(ops))),
                       ("¿Giran más los barridos dentro de las ventanas?", html.tabla(comp))])
    (INFORMES / "barrido_londres.html").write_text(pag, encoding="utf-8")
    fs = oro_fin_de_semana.backtest(gc, excluir=ex)
    pag = html.pagina("Oro: viernes → lunes (MGC)", "Versión mínima del paso 1, periodo de desarrollo 2015-2023.",
                      "Veredicto: RECHAZADA en el paso 1 (sin ventaja)", False,
                      [("Resultados", html.tabla(pd.DataFrame([resumen(fs)]), False)),
                       ("Curva de capital", html.curva(fs)),
                       ("Por año", html.barras_anuales(por_anio(fs)) + html.tabla(por_anio(fs)))])
    (INFORMES / "oro_fin_de_semana.html").write_text(pag, encoding="utf-8")
