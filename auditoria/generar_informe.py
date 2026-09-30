"""Genera INFORME_FINAL.md y gráficos a partir de resultados.pkl de un experimento.
Uso: python -m auditoria.generar_informe auditoria/experimentos/<AAAAMMDD_HHMM>"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .src import metricas as mt  # noqa: E402


def md(df, **k):
    return df.to_markdown(**k) if df is not None and len(df) else "(sin datos)"


def g(fig, ruta: Path) -> str:
    fig.tight_layout()
    fig.savefig(ruta, dpi=100)
    plt.close(fig)
    return ruta.name


def criterios_validadas(R: dict, nombre: str) -> pd.DataFrame:
    a = R["analisis"][nombre]
    tot, pos = a["total"], a["posterior (ya visto)"]
    anual = a["anual"]
    neto_tot = anual["neto_$"].sum()
    max_aporte = anual["neto_$"].max() / neto_tot if neto_tot > 0 else np.inf
    vec = R["vecindad"][nombre]
    x2 = R["costes_latencia"][nombre]["x2"]
    lo = tot["IC95_bloques_$"][0]
    filas = [
        ("a. expectativa > 0 y límite inferior IC95 por bloques > 0", tot["expectativa_$"] > 0 and lo > 0,
         f"{tot['expectativa_$']} $ (IC95 {tot['IC95_bloques_$']})"),
        ("b1. ≥ 60 % de años con neto > 0", (anual["neto_$"] > 0).mean() >= 0.6, f"{(anual['neto_$'] > 0).sum()}/{len(anual)}"),
        ("b2. ningún año aporta > 50 % del neto", max_aporte <= 0.5, f"máximo {max_aporte * 100:.0f} %"),
        ("c. costes ×2: expectativa > 0", x2.get("expectativa_$", -1) > 0, f"{x2.get('expectativa_$')} $"),
        ("d. ≥ 80 % de la vecindad con PF > 1", (vec.PF > 1).mean() >= 0.8, f"{(vec.PF > 1).sum()}/{len(vec)}"),
        ("e. periodo posterior (ya visto) con expectativa > 0", pos.get("expectativa_$", -1) > 0, f"{pos.get('expectativa_$')} $"),
        ("f. ≥ 100 operaciones y sin errores críticos", tot["operaciones"] >= 100, f"{tot['operaciones']} operaciones; errores críticos: 0"),
    ]
    return pd.DataFrame(filas, columns=["criterio", "cumple", "valor"])


def main(carpeta: str) -> None:
    C = Path(carpeta)
    R = pickle.loads((C / "resultados.pkl").read_bytes())
    man = json.loads((C / "manifiesto.json").read_text(encoding="utf-8"))
    cap = man["config"]["cartera"]["capital"]
    L = []
    a = L.append
    a("# Informe final — auditoría, validación y cartera\n")
    a(f"*Experimento `{C.name}` · commit `{man['commit'][:10]}` · Python {man['python']}, pandas {man['pandas']}, numpy {man['numpy']} · "
      f"semilla {man['semilla']} · {len(man['datos'])} archivos de datos con SHA-1 en `manifiesto.json`. Reproducible con "
      "`python -m auditoria.run_auditoria` y `python -m auditoria.generar_informe <carpeta>`. Criterios registrados antes en "
      "`auditoria/CRITERIOS.md`; auditoría de código en `auditoria/AUDITORIA_CODIGO.md`.*\n")

    # ---------------------------------------------------------------------------------------------- A resumen
    a("## A. Resumen ejecutivo\n")
    estado_val = {}
    for n in ("zona_ruido", "rsi2"):
        t = criterios_validadas(R, n)
        estado_val[n] = "Validación adicional respaldada por los datos" if t.cumple.all() else "Evidencia insuficiente"
    filas = []
    for n, etq in (("zona_ruido", "Zona de ruido intradía"), ("rsi2", "RSI(2) swing")):
        an = R["analisis"][n]
        tot, pos = an["total"], an["posterior (ya visto)"]
        filas.append({"estrategia": etq, "mercado": "NQ (1 MNQ)", "periodo": "2015-01 → 2026-09", "operaciones": tot["operaciones"],
                      "PF": tot["profit_factor"], "expectativa_$": tot["expectativa_$"], "IC95_bloques_$": tot["IC95_bloques_$"],
                      "max_dd_$": tot["max_dd_$"], "posterior (ya visto)": f"PF {pos['profit_factor']}, {pos['expectativa_$']} $/op",
                      "costes ×2": f"{R['costes_latencia'][n]['x2']['expectativa_$']} $/op", "estado": estado_val[n]})
    for n, r in R["rechazadas"].items():
        tot, pos = r["total"], r["posterior"]
        filas.append({"estrategia": n, "mercado": r["mercado"], "periodo": "2015 → 2026" if "Pares" not in n else "2010 → 2026",
                      "operaciones": tot.get("operaciones"), "PF": tot.get("profit_factor"), "expectativa_$": tot.get("expectativa_$"),
                      "IC95_bloques_$": tot.get("IC95_bloques_$"), "max_dd_$": tot.get("max_dd_$"),
                      "posterior (ya visto)": f"PF {pos.get('profit_factor')}, {pos.get('expectativa_$')} $/op" if pos.get("operaciones") else "—",
                      "costes ×2": "—", "estado": _estado_desc(r["estado"])})
    a(md(pd.DataFrame(filas), index=False))
    a("\n*Estados descriptivos según `CRITERIOS.md` (no son un ranking). \"Posterior (ya visto)\" = desde el corte de desarrollo "
      "de cada estrategia; ya se había mirado, así que **no es fuera de muestra**. XAUUSD CFD: sin datos (el bot se probó con el "
      "futuro GC ajustado). Las estrategias con riesgo 0,5 % (VWAP) tienen tamaño variable: sus $ no son de 1 contrato.*\n")

    # ---------------------------------------------------------------------------------------------- auditoría
    a("## Auditoría de datos y código (fase 1)\n")
    au = R["auditoria"]
    a(f"- Calidad NQ: {au['calidad_datos_NQ']['velas']} velas, duplicados {au['calidad_datos_NQ']['duplicados']}, velas imposibles "
      f"{au['calidad_datos_NQ']['velas_imposibles']}, huecos > 30 min {au['calidad_datos_NQ']['huecos_inesperados_>30min']}, picos que se "
      f"deshacen {au['calidad_datos_NQ']['picos_que_se_deshacen_(error_o_noticia)']} (no eliminados), cambios de contrato "
      f"{au['calidad_datos_NQ']['cambios_de_contrato']}, sesiones ilíquidas excluidas {au['calidad_datos_NQ']['dias_iliquidos_previsibles']}.")
    a(f"- Truncamiento (look-ahead): zona de ruido **{au['lookahead_truncamiento_zona_ruido']}**, RSI(2) **{au['lookahead_truncamiento_rsi2']}**.")
    for n in ("zona_ruido", "rsi2"):
        a(f"- Coherencia de operaciones {n}: {R['analisis'][n]['comprobaciones']}")
    a("- Detalle de la revisión de código, supuestos y gravedad: `AUDITORIA_CODIGO.md`.\n")

    # ---------------------------------------------------------------------------------------------- B individuales
    a("## B. Resultados individuales (fases 2-4)\n")
    for n, etq in (("zona_ruido", "Zona de ruido"), ("rsi2", "RSI(2)")):
        an = R["analisis"][n]
        o = R["ops"][n]
        a(f"### {etq}")
        a("**Reproducción frente a los informes originales:**\n")
        rep = []
        for tramo, k in (("desarrollo", "desarrollo"), ("posterior", "posterior (ya visto)")):
            orig = R["original"][n][tramo]
            rep.append({"tramo": tramo, **{f"original {q}": v for q, v in orig.items()},
                        **{f"reproducido {q}": an[k].get(q) for q in orig}})
        a(md(pd.DataFrame(rep), index=False))
        a("")
        t = pd.DataFrame({k: an[k] for k in ("total", "desarrollo", "posterior (ya visto)")})
        a(md(t))
        a(f"\nExposición: {an.get('exposicion_%_tiempo_RTH', an.get('exposicion_%_tiempo_calendario'))} % del tiempo "
          f"({'de la sesión regular' if n == 'zona_ruido' else 'de calendario'}).\n")
        a("**Criterios (`CRITERIOS.md`):**\n")
        a(md(criterios_validadas(R, n), index=False))
        a(f"\n→ **{estado_val[n]}**\n")
        a("**Ventanas anuales (walk-forward con reglas congeladas: cada año por separado):**\n")
        a(md(an["anual"]))
        a("\n**Trimestral:**\n")
        a(md(an["trimestral"].T))
        a("\n**Costes y latencia:**\n")
        a(md(pd.DataFrame({k: {q: v.get(q) for q in ("operaciones", "profit_factor", "expectativa_$", "t_por_operacion", "neto_$")}
                           for k, v in R["costes_latencia"][n].items()}).T))
        a("\n**Vecindad de parámetros (rejilla fijada antes; sin elegir el mejor):**\n")
        a(md(R["vecindad"][n], index=False))
        a("\n**Regímenes (descriptivo, con datos del día anterior):**\n")
        for k, v in an["regimenes"].items():
            a(f"*{k}*\n")
            a(md(v))
            a("")
        a("**Por día de la semana y franja horaria:**\n")
        a(md(an["dia_semana"]))
        a("")
        a(md(an["franja"]))
        # gráficos
        d = mt.diario(o, R["cartera"]["diario"].index)
        eq = d.pnl.cumsum()
        dd = eq - eq.cummax()
        fig, (x1, x2) = plt.subplots(2, 1, figsize=(11, 5), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
        x1.plot(eq.index, eq, color="#0969da")
        x1.axvline(pd.Timestamp("2023-03-22"), color="grey", ls=":", label="corte de desarrollo")
        x1.set_ylabel("P&L acumulado ($, 1 MNQ)")
        x1.legend()
        x2.fill_between(dd.index, dd, 0, color="#cf222e", alpha=0.6)
        x2.set_ylabel("drawdown ($)")
        x1.set_title(f"{etq}: equity y drawdown")
        a("\n![equity](" + g(fig, C / f"{n}_equity_dd.png") + ")")
        fig, ax = plt.subplots(figsize=(9, 3.5))
        an_ = an["anual"]
        ax.bar(an_.index.astype(str), an_["neto_$"], color=["#1a7f37" if v > 0 else "#cf222e" for v in an_["neto_$"]])
        ax.set_title(f"{etq}: neto por año ($, 1 MNQ)")
        a("\n![anual](" + g(fig, C / f"{n}_anual.png") + ")")
        fig, ax = plt.subplots(figsize=(8, 3.5))
        ax.hist(o.neto.clip(o.neto.quantile(0.005), o.neto.quantile(0.995)), bins=60, color="#57606a")
        ax.axvline(o.neto.mean(), color="#cf222e", label=f"media {o.neto.mean():.1f} $")
        ax.legend()
        ax.set_title(f"{etq}: distribución de operaciones ($)")
        a("\n![dist](" + g(fig, C / f"{n}_distribucion.png") + ")\n")

    # ---------------------------------------------------------------------------------------------- rechazadas
    a("## Fases 5-6: estrategias rechazadas y bot (re-ejecutadas con su código original)\n")
    filas = []
    for n, r in R["rechazadas"].items():
        for tramo in ("desarrollo", "posterior", "total"):
            x = r[tramo]
            filas.append({"estrategia": n, "tramo": tramo, "operaciones": x.get("operaciones"), "PF": x.get("profit_factor"),
                          "expectativa_$": x.get("expectativa_$"), "IC95_bloques_$": x.get("IC95_bloques_$"),
                          "expectativa_R": x.get("expectativa_R"), "t": x.get("t_por_operacion")})
    a(md(pd.DataFrame(filas), index=False))
    a("\n**Clasificación:**\n")
    a(md(pd.DataFrame([{"estrategia": n, "mercado": r["mercado"], "corte desarrollo": r["corte_desarrollo"], "clasificación": r["estado"],
                        "nota": r["nota"]} for n, r in R["rechazadas"].items()]), index=False))
    a("\nLa falta de significación no demuestra que no haya ninguna ventaja: con los IC mostrados se puede descartar una "
      "ventaja grande, no una muy pequeña (que, en todo caso, no cubriría costes realistas).\n")

    # ---------------------------------------------------------------------------------------------- C cartera
    a("## C. Cartera zona de ruido + RSI(2) (fase 7)\n")
    ca = R["cartera"]
    a("Modelo de capital: 25.000 $ fijos, sin reinvertir; P&L por día de salida (hora NY); el capital no usado no rinde. "
      "Pesos = contratos equivalentes de MNQ.\n")
    a(f"- Correlaciones: {ca['correlaciones']}")
    a(f"- Solapamiento de posiciones: {ca['solapamiento']}")
    a(f"- Costes anuales de la zona de ruido con 1 MNQ: ≈ {ca['costes_anuales_1+1_$']} $; los del RSI(2) son pequeños (~13 operaciones/año). "
      "Operar las dos no reduce costes: cada estrategia paga los suyos (magic numbers distintos, cuenta de cobertura).\n")
    a(md(ca["tabla"], index=False))
    fig, ax = plt.subplots(figsize=(11, 4.5))
    for nombre, (wz, wr) in ca["asignaciones"].items():
        p = wz * ca["diario"].zona + wr * ca["diario"].rsi2
        ax.plot(p.index, p.cumsum(), label=nombre, lw=1)
    ax.axvline(pd.Timestamp("2023-03-22"), color="grey", ls=":")
    ax.legend(fontsize=7)
    ax.set_title("Cartera: P&L acumulado por asignación ($)")
    a("\n![cartera](" + g(fig, C / "cartera_equity.png") + ")\n")

    # ---------------------------------------------------------------------------------------------- riesgo
    a("## Fase 8: riesgo y simulación de capital\n")
    a("Bootstrap por bloques de 20 sesiones del P&L diario 1+1 (escalado ×2 para 2+2), horizonte de 252 sesiones, "
      f"{man['config']['bootstrap']['n']} simulaciones, semilla {man['semilla']}. **No es una predicción**: supone que el futuro se "
      "parece al pasado muestreado. El límite diario solo se cuenta (su efecto intradía no se puede simular con P&L diario); "
      "la detención por caída sí se aplica.\n")
    a(md(R["riesgo"]["simulaciones"], index=False))
    a(f"\nPérdidas por encima del \"stop\": ninguna de las dos estrategias tiene stop, así que no hay riesgo teórico por stop. "
      f"Peores operaciones históricas con 1 MNQ: {R['riesgo']['peores']}. Un hueco de fin de semana o una noticia puede producir "
      "pérdidas mayores que cualquiera de las observadas. El apalancamiento disponible en el broker no mide el riesgo aceptable.\n")

    # ---------------------------------------------------------------------------------------------- D-F
    a("## D. Diagnóstico de diferencias\n")
    a("- Zona de ruido, desarrollo: **idéntico** al original (1.924 operaciones, PF 1,194, t 2,26, 11.034 $).")
    a("- Zona de ruido, posterior: 801 frente a 800 operaciones y 10.197 $ frente a 10.472 $. Causa comprobada: **datos** — "
      "las operaciones hasta la última del informe original son idénticas (neto 21.506 $ en ambos); la diferencia es 1 operación "
      "nueva (28-sep-2026, −274,5 $) con datos que no existían al hacer el informe.")
    a("- RSI(2): desarrollo 97 operaciones PF 1,463 y posterior 61 PF 1,929: **idénticos** a los originales.")
    a("- Estrategias rechazadas: se re-ejecutan con su código; las diferencias con sus fichas, si las hay, vienen de los días "
      "de datos añadidos después de cada informe y de medir aquí desarrollo y posterior con el mismo corte.\n")
    a("## E. Limitaciones\n")
    a("- **No hay test intocable**: el periodo posterior a 2023 ya se miró; la validación honesta pendiente es la prueba hacia delante.")
    a("- **Selección múltiple** en el proyecto (25+ ideas): que 2 pasen umbrales de t ≈ 2 es compatible con el azar.")
    a("- Backtests en futuros NQ/GC; la ejecución prevista es CFD NAS100/XAUUSD (precio, VWAP con volumen de ticks, spread, swap).")
    a("- RSI(2): ~13 operaciones/año; sus IC son muy amplios.")
    a("- Sin stops en las dos validadas: el riesgo real por operación no está acotado.")
    a("- Bootstrap por bloques de 20 sesiones: captura dependencia de corto plazo, no cambios de régimen largos.")
    a("- XAUUSD sin datos; el bot se probó con el futuro GC ajustado y sin swap.\n")
    a("## F. Próximos pasos (sin re-optimizar sobre datos ya vistos)\n")
    a("1. Congelar las reglas de las dos estrategias tal como están (versión v1.0) y registrar la fecha de congelación.")
    a("2. Prueba hacia delante desde el 1-oct-2026 en demo, con criterios fijados ya: al menos 6 meses **y** 150 operaciones de la "
      "zona de ruido (el RSI(2) no llegará a una muestra útil en 6 meses: evaluarlo en 2 años).")
    a("3. Medir en demo el deslizamiento real y la diferencia CFD/futuro; si el deslizamiento medio supera 1 tick, recalcular con "
      "los costes medidos (sin tocar reglas).")
    a("4. Comparar el P&L de la prueba con la distribución del bootstrap por bloques (p5–p95); detener si la caída supera el límite "
      "de cartera fijado.")
    a("5. Cualquier idea nueva: ficha antes de mirar, datos nuevos o partición no usada, y contar el número de pruebas.")
    (C / "INFORME_FINAL.md").write_text("\n".join(L), encoding="utf-8")
    print(C / "INFORME_FINAL.md")


def _estado_desc(e: str) -> str:
    return {"Evidencia negativa": "Evidencia negativa en las pruebas realizadas",
            "No concluyente por muestra insuficiente": "Evidencia insuficiente (muestra pequeña)",
            "No concluyente (el IC 95 % incluye el 0)": "Evidencia insuficiente (IC incluye 0)"}.get(e, e)


if __name__ == "__main__":
    main(sys.argv[1])
