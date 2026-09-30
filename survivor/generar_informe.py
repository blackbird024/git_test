"""Informe final: reports/SURVIVOR_ANALYSIS_FINAL.md (+ gráficos en reports/survivor/).

    python -m survivor.generar_informe
"""
from __future__ import annotations

import pickle
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from bot_lab.generar_informe import AZUL, MUTED, NARANJA, SUPERFICIE, TINTA, TINTA2, estilo, limpio, tabla  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
REP = RAIZ / "reports"
FIG = REP / "survivor"
N = {"RSI2": "RSI(2)", "NOISE_ZONE": "Zona de ruido"}


def graficos(R):
    FIG.mkdir(parents=True, exist_ok=True)
    d = R["series"]["diario"]
    # 1. curvas acumuladas
    fig, ax = plt.subplots(figsize=(9, 3.6), dpi=130)
    fig.patch.set_facecolor(SUPERFICIE)
    estilo(ax)
    for col, nombre, c in (("zr", "Zona de ruido", AZUL), ("rsi2", "RSI(2) (mark-to-market)", NARANJA)):
        eq = d[col].cumsum()
        ax.plot(eq.index, eq, color=c, linewidth=2, label=nombre)
        ax.text(eq.index[-1], eq.iloc[-1], "  " + nombre.split(" (")[0], color=TINTA2, fontsize=7, va="center")
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.legend(frameon=False, fontsize=8, labelcolor=TINTA2, loc="upper left")
    ax.set_ylabel("$ acumulados, 1 MNQ", fontsize=8, color=TINTA2)
    ax.set_title("P&L acumulado 2015-2026 (NOT OUT-OF-SAMPLE)", fontsize=10, color=TINTA, loc="left")
    fig.tight_layout()
    fig.savefig(FIG / "equity.png", facecolor=SUPERFICIE)
    plt.close(fig)
    # 2. P&L móvil de 12 meses
    fig, ax = plt.subplots(figsize=(9, 3.2), dpi=130)
    fig.patch.set_facecolor(SUPERFICIE)
    estilo(ax)
    for col, nombre, c in (("zr", "Zona de ruido", AZUL), ("rsi2", "RSI(2)", NARANJA)):
        s = d[col].resample("ME").sum().rolling(12).sum()
        ax.plot(s.index, s, color=c, linewidth=2, label=nombre)
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.legend(frameon=False, fontsize=8, labelcolor=TINTA2, loc="upper left")
    ax.set_ylabel("P&L de los 12 meses anteriores, $", fontsize=8, color=TINTA2)
    ax.set_title("P&L móvil de 12 meses: periodos en los que el edge desaparece", fontsize=10, color=TINTA, loc="left")
    fig.tight_layout()
    fig.savefig(FIG / "movil_12m.png", facecolor=SUPERFICIE)
    plt.close(fig)
    # 3. aleatorización
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.0), dpi=130)
    fig.patch.set_facecolor(SUPERFICIE)
    for ax, (clave, nombre) in zip(axs, (("NOISE_ZONE momento aleatorio (N2)", "Zona de ruido: momento aleatorio"),
                                         ("RSI2 días al azar con SMA200 (N1)", "RSI(2): días al azar con SMA200"))):
        estilo(ax)
        a = R["aleatorizacion"][clave]
        lo, hi = a["p5_aleatoria_$"], a["p95_aleatoria_$"]
        ax.barh([0], [hi - lo], left=[lo], color="#cde2fb", height=0.4)
        ax.plot([a["media_aleatoria_$"]], [0], "o", color=AZUL, markersize=8)
        ax.plot([a["expectativa_real_$"]], [0], "D", color=NARANJA, markersize=9)
        ax.set_yticks([])
        ax.set_title(f"{nombre}\n(banda p5-p95 aleatoria; ◆ real, p {'< 0.001' if a['p_valor'] < 0.001 else '= ' + format(a['p_valor'], '.3f')})", fontsize=8, color=TINTA, loc="left")
        ax.set_xlabel("expectativa neta $/op", fontsize=8, color=TINTA2)
    fig.tight_layout()
    fig.savefig(FIG / "aleatorizacion.png", facecolor=SUPERFICIE)
    plt.close(fig)


def celdas_md(t: pd.DataFrame) -> str:
    t = t[t.operaciones.astype(float) > 0].drop(columns=["con_muestra"])
    return tabla(t)


def generar():
    exp = sorted((RAIZ / "survivor" / "experimentos").glob("*"))[-1]
    R = pickle.loads((exp / "resultados.pkl").read_bytes())
    graficos(R)
    B, T, E, VE = R["base"], R["temporal"], R["estres"], R["veredictos_estres"]
    A, C = R["aleatorizacion"], R["cartera"]
    L = []
    w = L.append
    w("# SURVIVOR ANALYSIS v1.0")
    w("")
    w(f"30-sep-2026 · experimento `survivor/experimentos/{exp.name}` · reglas **congeladas** (RSI2_SURVIVOR_V1, NOISE_ZONE_SURVIVOR_V1; "
      "SHA-256 del código comprobado; reproducen operación a operación la auditoría) · **todo NOT OUT-OF-SAMPLE** (2015-2026 ya estaba visto) · "
      "pre-registro: `survivor/SURVIVOR_ANALYSIS_PRE_REGISTRATION.md` (commit anterior a los cálculos).")
    w("")
    w("## EXECUTIVE SUMMARY")
    w("")
    w("Resultado global: **A — ambas sobreviven a las pruebas de falsación, pero con debilidades concretas y medidas**. Ninguna está probada fuera de muestra; el forward test es el único juez limpio.")
    w("")
    w("### RSI(2)")
    b = B["RSI2"]
    w("**Evidencia**")
    w(f"- {b['operaciones']} operaciones, PF {b['PF']}, {b['expectativa_$']:+.2f} $/op, IC 95 % por bloques {limpio(b['IC95_bloques_$'])}.")
    w("- **Fortalezas:** casi inmune a los costes (×3 → +117 $/op), al deslizamiento y al retraso. Todos los parámetros vecinos son positivos. El 75 % de los años es positivo y ninguno aporta más del 34 %. En % del precio no crece con los años; el aumento en $ se debe sobre todo a que el NQ vale 4-6 veces más que en 2015.")
    w(f"- **Debilidad principal:** la **aleatorización solo da WEAK EVIDENCE**. Comprar el NQ en días al azar (con la misma duración y con el filtro SMA200) gana de media {A['RSI2 días al azar con SMA200 (N1)']['media_aleatoria_$']:+.0f} $/op; el RSI(2) gana {b['expectativa_$']:+.0f}. La señal aporta unos +60 $/op, pero p = {A['RSI2 días al azar con SMA200 (N1)']['p_valor']:.2f}. **Buena parte de su resultado es la deriva alcista del Nasdaq 2015-2026.**")
    w("- **Otras debilidades:** muestra pequeña (13 op/año); sin los 10 mejores trades la t baja a 1,0; los años 2018 y 2022 son negativos.")
    w("- **Regímenes favorables:** positivo en las tres clases de volatilidad; mejor en TREND UP.")
    w("- **Regímenes desfavorables:** ninguno con evidencia (las celdas son pequeñas).")
    w("- **Fragilidad:** no ante costes ni ejecución; sí ante un cambio de régimen del mercado de fondo (años bajistas como 2022).")
    w("")
    w("### ZONA DE RUIDO")
    b = B["NOISE_ZONE"]
    w("**Evidencia**")
    w(f"- {b['operaciones']} operaciones, PF {b['PF']}, {b['expectativa_$']:+.2f} $/op, IC {limpio(b['IC95_bloques_$'])}.")
    w(f"- **Fortalezas:** la aleatorización la **confirma** (dirección y momento aleatorios pierden los costes, p < 0,001). Resiste 2× costes, +3 ticks y 5 min de retraso. Los parámetros vecinos son positivos. Correlación diaria con el RSI(2) de {R['correlaciones']['diaria']:+.2f}.")
    w(f"- **Debilidad 1 — TAIL DEPENDENCE:** el 1 % de las mejores operaciones (27) aporta el {T['NOISE_ZONE']['concentracion']['top 1% operaciones (27)']:.0f} % del beneficio neto. Sin ellas, pierde. Es la naturaleza de un seguidor de tendencia intradía, pero hace que un año sin días de tendencia fuerte sea plano o negativo.")
    w("- **Debilidad 2 — depende de la volatilidad:** con ATR relativo BAJO, ≈ 0 $/op; con ALTO, +20 $/op. 2015-2017 fue negativo (PF 0,91).")
    w("- **Debilidad 3 — tras días de crash:** después de un día de crash (retorno ≤ percentil 2) **pierde** (−47 $/op, IC por debajo de 0). Es CONTRADICTION en esa condición.")
    w("- **Fragilidad ante costes:** moderada. La comisión es el 20 % del resultado bruto con MNQ; con 3× costes, la expectativa ≈ 0.")
    w("")
    w("### CARTERA")
    w(f"- **Correlación:** diaria {R['correlaciones']['diaria']:+.2f}; mensual {R['correlaciones']['mensual']:+.2f}; de drawdown {R['correlaciones']['drawdown']:+.2f}. Las correlaciones condicionadas son todas |ρ| < 0,15 contando todos los días, pero los días en que ambas operan con volatilidad BAJA llegan a +0,43.")
    w(f"- **Diversificación real:** a igual riesgo, la mezcla 75/25 tiene menos DD95 de Monte Carlo ({C['75/25']['MC_DD_p95_$']:,.0f} $) que la ZR sola ({C['100/0']['MC_DD_p95_$']:,.0f} $) y que el RSI(2) solo ({C['0/100']['MC_DD_p95_$']:,.0f} $), con Sharpe {C['75/25']['sharpe']} frente a {C['100/0']['sharpe']} y {C['0/100']['sharpe']}. La mejora es **modesta**.")
    w(f"- **Riesgo:** el EA actual (1+1 MNQ) **no es igual riesgo**: tiene un 59 % más de volatilidad que la ZR sola, un DD95 de {C['1+1 MNQ (EA actual, MÁS riesgo)']['MC_DD_p95_$']:,.0f} $, P(DD ≥ 5.000 $ en un año) = {C['1+1 MNQ (EA actual, MÁS riesgo)']['P(DD ≥ 5000 $)_%']} % y P(algún día ≤ −1.000 $) = {C['1+1 MNQ (EA actual, MÁS riesgo)']['P(algún día ≤ −1000 $)_%']} %. Ese último riesgo viene casi entero del mark-to-market nocturno del RSI(2).")
    w("")
    w("### FORWARD TEST — qué observar")
    w("- **Zona de ruido:** la expectativa móvil de 50 operaciones frente a la banda histórica (percentil 5 = −20,5 $); el deslizamiento real frente al tick supuesto; su resultado en días de volatilidad baja y tras días de crash.")
    w("- **RSI(2):** frecuencia (≈ 1,2 op/mes) y DD mark-to-market. Con 15 operaciones solo se detecta un fallo grosero (p5 = −71 $/op).")
    w("- **Cartera:** cuántas veces salta el límite diario de 1.000 $ por el RSI(2) abierto de noche.")
    w("")
    graf = ["![Equity](survivor/equity.png)", "", "![Móvil 12m](survivor/movil_12m.png)", "", "![Aleatorización](survivor/aleatorizacion.png)", ""]
    L.extend(graf)
    # --------------------------- tabla final
    w("## TABLA FINAL DE EVIDENCIA")
    w("")
    w("Veredictos con las reglas pre-registradas. Sin puntuación, sin ranking y sin ganador.")
    w("")
    vr = R["veredictos_regimen"]
    filas = {
        "Historical evidence": (f"{B['RSI2']['expectativa_$']:+.0f} $/op, IC {limpio(B['RSI2']['IC95_bloques_$'])}; aleatorización p={A['RSI2 días al azar con SMA200 (N1)']['p_valor']:.2f} → WEAK EVIDENCE",
                                f"{B['NOISE_ZONE']['expectativa_$']:+.2f} $/op, IC {limpio(B['NOISE_ZONE']['IC95_bloques_$'])}; aleatorización p<0,001 → CONFIRMATION"),
        "Sample size": ("158 op. (13/año): pequeña", "2.725 op. (230/año): suficiente"),
        "Temporal stability": (f"años: {T['RSI2']['veredicto_años']} (75 % +); subperiodos: {T['RSI2']['veredicto_subperiodos']}",
                               f"años: {T['NOISE_ZONE']['veredicto_años']} (67 % +); subperiodos: {T['NOISE_ZONE']['veredicto_subperiodos']} (2015-17 < 0)"),
        "Regime stability": (f"VOL {vr['RSI2']['VOL_ATR']}, TEND {vr['RSI2']['TENDENCIA']} (celdas pequeñas)",
                             f"VOL {vr['NOISE_ZONE']['VOL_ATR']} por regla, pero el edge es ≈ 0 en vol BAJA; tras crash: CONTRADICTION"),
        "Cost robustness": (f"{VE['RSI2']['costes']} (3× → {E['RSI2']['costes 3x']['expectativa_$']:+.0f} $)",
                            f"{VE['NOISE_ZONE']['costes']} (2× → {E['NOISE_ZONE']['costes 2x']['expectativa_$']:+.2f}; 3× → {E['NOISE_ZONE']['costes 3x']['expectativa_$']:+.2f})"),
        "Slippage robustness": (VE["RSI2"]["deslizamiento"], f"{VE['NOISE_ZONE']['deslizamiento']} (+3 ticks → {E['NOISE_ZONE']['+3 tick']['expectativa_$']:+.2f})"),
        "Parameter stability": (VE["RSI2"]["sensibilidad"], VE["NOISE_ZONE"]["sensibilidad"]),
        "Outlier dependence": (f"{T['RSI2']['veredicto_atipicos']} (sin los 10 mejores: t 1,0)",
                               f"{T['NOISE_ZONE']['veredicto_atipicos']}, pero TAIL DEPENDENCE (top 1 % = 107 % del neto)"),
        "Walk-forward": (f"anual congelado: {T['RSI2']['veredicto_wf']} ({T['RSI2']['wf_frac_positivas']:.0%} ventanas +)",
                         f"trimestral congelado: {T['NOISE_ZONE']['veredicto_wf']} ({T['NOISE_ZONE']['wf_frac_positivas']:.0%} ventanas +)"),
        "Monte Carlo": (f"{R['mc_individual']['RSI2']['veredicto']} (P(DD≥5k)={R['mc_individual']['RSI2']['P(DD ≥ 5000 $)_%']} %; DD95 {R['mc_individual']['RSI2']['MC_DD_p95_$']:,.0f} $)",
                        f"{R['mc_individual']['NOISE_ZONE']['veredicto']} (P(DD≥5k)={R['mc_individual']['NOISE_ZONE']['P(DD ≥ 5000 $)_%']} %; DD95 {R['mc_individual']['NOISE_ZONE']['MC_DD_p95_$']:,.0f} $)"),
        "Forward status": ("Iniciado el 30-sep-2026 (demo). Sin operaciones todavía", "Iniciado el 30-sep-2026 (demo). Sin operaciones todavía"),
    }
    w("| Test | RSI2 | Noise Zone |")
    w("|---|---|---|")
    for k, (a, bb) in filas.items():
        w(f"| {k} | {a} | {bb} |")
    w("")
    # --------------------------- cartera
    w("## TABLA DE CARTERAS (igual riesgo: volatilidad diaria = ZR sola con 1 MNQ; σ estimadas con datos hasta 2023-03-21)")
    w("")
    w("| Cartera (reparto de riesgo ZR/RSI2) | Pesos en MNQ | Sharpe | Max DD $ | Peor año $ | MC DD95 $ | % años negativos | P(año negativo) MC | P(DD ≥ 5.000 $) |")
    w("|---|---|---|---|---|---|---|---|---|")
    for k, v in C.items():
        nombre = {"100/0": "Noise (100/0)", "0/100": "RSI2 (0/100)"}.get(k, k)
        w(f"| {nombre} | {limpio(v['pesos (ZR, RSI2) en MNQ'])} | {v['sharpe']} | {v['max_dd_$']:,.0f} | {v['peor_año_$']:,.0f} | {v['MC_DD_p95_$']:,.0f} | {v['años_negativos_%']} | {v['P(año negativo)_%']} % | {v['P(DD ≥ 5000 $)_%']} % |")
    w("")
    w("No se elige ninguna cartera. La última fila **no** es igual riesgo: tiene más riesgo total. Tabla completa (Sortino, Calmar, peor mes, DD p50/p99, P(día ≤ −1.000 $)):")
    w(tabla(pd.DataFrame(C).T.rename_axis("cartera")))
    # --------------------------- Q1..Q10
    w("## RESPUESTAS A LAS 10 PREGUNTAS")
    w("")
    w("**Q1 — ¿Persiste el edge del RSI(2) al descomponerlo por régimen?**")
    w("")
    w(f"Los datos son **compatibles**: VOL_ATR {vr['RSI2']['VOL_ATR']}, VOL_REAL {vr['RSI2']['VOL_REAL']}, TENDENCIA {vr['RSI2']['TENDENCIA']}. Positivo en todas las celdas, pero con 22-130 operaciones por celda; solo BAJA y TREND UP tienen IC > 0.")
    w("")
    w("**Q2 — ¿Y el de la zona de ruido?**")
    w("")
    w(f"Por la regla pre-registrada, CONFIRMATION en las tres variables. En sustancia, **el edge vive en la volatilidad normal-alta**: BAJA ≈ −0,7 $/op; ALTA +19,9 $/op, IC {limpio(R['regimenes']['NOISE_ZONE']['VOL_ATR'].loc['ALTA', 'IC95_$'])}. En tendencia es parecido en las tres clases.")
    w("")
    w("**Q3 — ¿Cuándo funcionan?**")
    w("- **ZR:** días con volatilidad relativa normal/alta; tras un rango previo normal; cuando el precio ya se ha alejado del cierre anterior a favor.")
    w("- **RSI(2):** en casi cualquier condición del régimen alcista. Mejor en TREND UP.")
    w("")
    w("**Q4 — ¿Cuándo fallan?**")
    w("- **ZR:** con volatilidad baja (≈ 0); tras días de crash (−47 $/op, IC < 0); tras un día de expansión de rango (−4,5 $/op, exploratorio); en 2015-2017 y 2019.")
    w("- **RSI(2):** en años de mercado bajista o de corrección prolongada (2018, 2022). La salida por tiempo (5 sesiones sin RSI > 70) concentra todas las pérdidas grandes (−593 $/op de media).")
    w("")
    w("**Q5 — ¿Difieren las ganadoras de las perdedoras antes de entrar?**")
    w("- **RSI(2): no.** Ningún rasgo previo las separa (todas las p de Bonferroni = 1).")
    w("- **ZR: sí, aunque débilmente.** Las ganadoras tienen más ATR, más distancia al cierre anterior a favor, un hueco y una noche a favor (p de Bonferroni < 0,03). Es compatible con la hipótesis de momentum. Las diferencias de mediana son pequeñas y **no se convierten en filtros**.")
    w("")
    w(tabla(R["q5"]["NOISE_ZONE"].rename_axis("rasgo (ZR)")))
    w("**Q6 — ¿Estructural o concentrado en el tiempo?**")
    w("- **RSI(2):** ningún año aporta más del 34 % y los subperiodos son todos positivos → compatible con algo estructural. Pero la aleatorización indica que una parte grande es beta del Nasdaq, no señal.")
    w("- **ZR:** ningún año aporta más del 25 % y el 64 % de los trimestres es positivo. Pero 2015-2017 fue negativo, y el resultado depende de pocos días de tendencia fuerte (cola).")
    w("")
    w("**Q7 — ¿Explotan fenómenos distintos?**")
    w("")
    w(f"Veredicto: **{R['veredicto_q7']}**. Uno es momentum intradía (continuación del desequilibrio del día, largos y cortos) y el otro reversión a la media diaria en tendencia alcista (solo largos). La correlación diaria es {R['correlaciones']['diaria']:+.2f}. Correlaciones condicionadas:")
    w(tabla(R["corr_condicionadas"]))
    so = R["solapamiento"]
    w(f"**Solapamiento:** {so['ZR_con_RSI2_abierto']} de {so['operaciones_ZR']} operaciones de la ZR ocurren con un RSI(2) abierto. En {so['mismo_sentido (ZR largo)']} van en el mismo sentido y en {so['sentido_opuesto (ZR corto)']} en el opuesto. Hay {so['dias_con_ambas']} días con ambas.")
    w("")
    w(f"**Q8 — ¿La combinación reduce el drawdown sin aumentar el riesgo?** Veredicto: **{R['veredicto_q8']}**, con una mejora pequeña. Ver la tabla de carteras: a igual volatilidad, las mezclas 75/25 y 50/50 tienen mejor Sharpe que cualquiera de las dos solas, pero la 50/50 ya tiene más DD95 que la ZR sola.")
    w("")
    w("**Q9 — ¿Lo que ayuda a una perjudica a la otra?**")
    w("")
    w("Parcialmente, y solo de forma **exploratoria**:")
    w(f"- Las operaciones de la ZR mientras hay un RSI(2) abierto rinden {so['neto_medio_ZR_mismo_sentido_$']:+.2f} (mismo sentido) y {so['neto_medio_ZR_sentido_opuesto_$']:+.2f} (opuesto) $/op, frente a {so['neto_medio_ZR_sin_RSI2_$']:+.2f} sin RSI(2) abierto. Los días tras una caída en tendencia alcista, que son los del RSI(2), son malos para la ZR.")
    w("- Por volatilidad, la ZR necesita volatilidad y el RSI(2) funciona en todas.")
    w("")
    w("Esto va a `POST_HOC_OBSERVATIONS.md` y **no** se usa como regla.")
    w("")
    w("**Q10 — ¿Qué vigilar en el forward?** Ver el árbol de decisión y `forward_testing/`.")
    w("")
    # --------------------------- detalle
    for k in ("RSI2", "NOISE_ZONE"):
        w(f"## Detalle — {N[k]}")
        w("")
        w("**Año a año:**")
        w(tabla(T[k]["anual"][["operaciones", "PF", "expectativa_$", "P&L_$", "max_dd_$", "acierto_%"]]))
        w(f"Año con más peso: {T[k]['año_top_%']} % del neto; años positivos: {T[k]['años_positivos_frac']:.0%}. Veredicto: **{T[k]['veredicto_años']}**.")
        w("")
        w("**Normalizado** (media por operación; la columna t es la de la media):")
        w(tabla(R["normalizado"][k]))
        w("**Normalizado por año** (¿crece el edge solo por el precio?):")
        w(tabla(R["normalizado_anual"][k]))
        w("**Meses:** " + ", ".join(f"{a}: {limpio(b)}" for a, b in T[k]["mensual"].items()))
        w("")
        w("**Ventanas móviles:**")
        w(tabla(T[k]["moviles"]["tabla"]))
        w("**Subperiodos:**")
        w(tabla(T[k]["subperiodos"]))
        w(f"Veredicto: **{T[k]['veredicto_subperiodos']}**.")
        w("")
        w(f"**Walk-forward congelado ({T[k]['wf_ventana']}):** {T[k]['wf_frac_positivas']:.0%} de ventanas positivas → **{T[k]['veredicto_wf']}**.")
        if k == "NOISE_ZONE":
            w(tabla(T[k]["trimestral"][["inicio", "fin", "operaciones", "PF", "expectativa_$", "P&L_$", "max_dd_$", "acierto_%"]]))
        if k == "RSI2":
            w("Nota: el RSI(2) entra a las 18:00 NY, así que las señales del viernes entran el domingo por la tarde (sesión del lunes). \"domingo\" en la tabla DIA = sesión del lunes.")
            w("")
        w("**Regímenes y rasgos previos** (IC 95 % por bloques de 20 sesiones; celdas de rasgos descriptivos = terciles de la propia muestra):")
        for v, t in R["regimenes"][k].items():
            w(f"*{v}*")
            w(celdas_md(t))
        w("**Crisis y extremos** (clasificación causal, percentiles expansivos):")
        w(tabla(R["crisis"][k]["tabla"]))
        w(f"Veredictos: {R['crisis'][k]['veredictos']}")
        w("")
        w("**MAE / MFE:**")
        w(tabla(R["mae_mfe"][k]))
        w(f"Captura mediana del MFE en las ganadoras: {R['captura_mfe'][k]:.0%}.")
        w("")
        w("**Horizontes fijos** (¿el edge está en la entrada o en la salida?):")
        w(tabla(R["horizontes"][k]))
        if k == "NOISE_ZONE":
            w(f"Lectura: a +5 min, la entrada ya tiene un sesgo a favor (+1,3 pts brutos, t 3,3), que se diluye a 15-60 min (t < 1,6). La salida real (trailing VWAP/banda) obtiene de media ≈ {R['horizontes']['NOISE_ZONE_salida_real_pts']:.1f} pts brutos. **El edge está en la entrada más la salida que deja correr las ganadoras**; con salidas fijas sería mucho menor. La salida es parte esencial de la estrategia, no un detalle arbitrario.")
            w("")
            w("**Tiempo hasta fallar:**")
            w(tabla(R["tiempo_fallo"]["NOISE_ZONE"]))
            w(tabla(R["tiempo_fallo"]["NOISE_ZONE_estado_30min"]))
            w("Lectura: por construcción, las operaciones que no avanzan salen en el primer chequeo, a los 30 min, y son las perdedoras. Las que siguen abiertas después de 60 min ganan el 66 % de las veces. Es coherente con un seguidor de tendencia. No se crea un stop por tiempo.")
        else:
            w("Lectura: el sesgo existe desde la primera sesión (+0,26 %, t 3,0). La salida por RSI > 70 cierra casi siempre en beneficio; la salida por tiempo a las 5 sesiones concentra las pérdidas:")
            w(tabla(R["tiempo_fallo"]["RSI2"]))
            w(tabla(R["tiempo_fallo"]["RSI2_motivo"]))
        w("**Estrés** (reglas congeladas):")
        w(tabla(pd.DataFrame(E[k]).T[["operaciones", "PF", "expectativa_$", "neto_$", "t", "IC95_bloques_$"]]))
        w(f"Veredictos: {VE[k]}")
        w("")
        w("**Sensibilidad** (perturbaciones pequeñas, una a una; no se elige ninguna):")
        w(tabla(R["sensibilidad"][k][["operaciones", "PF", "expectativa_$", "t", "IC95_bloques_$"]]))
        w("**Concentración:** " + ", ".join(f"{a}: {limpio(b)}" for a, b in T[k]["concentracion"].items()))
        w("")
        w("**Sin los mejores trades** (diagnóstico, no un backtest nuevo):")
        w(tabla(T[k]["sin_mejores"]))
        w(f"Veredicto: **{T[k]['veredicto_atipicos']}**.")
        w("")
        w("**Rachas frente a Monte Carlo** (5.000 permutaciones):")
        w(tabla(T[k]["rachas_mc"]))
        w(f"Distribución de rachas: {T[k]['rachas_dist']}. Veredicto: **{T[k]['veredicto_rachas']}**.")
        w("")
    w("## Aleatorización (falsación)")
    w("")
    w(tabla(pd.DataFrame(A).T.rename_axis("prueba")))
    w("Lectura:")
    w("- **ZR:** la señal importa. Quitarla (dirección o momento al azar) deja la expectativa en −3 $/op, es decir, los costes.")
    w("- **RSI(2):** estar largo en el Nasdaq al azar ya gana unos +60 $/op con la misma duración. La señal RSI(2) añade unos +60 $/op, pero solo 1 de cada 9-10 réplicas aleatorias la iguala o supera (p ≈ 0,10). Los datos son **compatibles** con un edge modesto sobre la deriva del mercado y **no permiten** descartar que el resultado sea mayoritariamente beta.")
    w("")
    w("## NQ frente a MNQ (sección 27) y normalización (sección 28)")
    w("")
    w(tabla(R["nq_mnq"]))
    w("Los puntos por operación son idénticos (mismo mercado). En NQ la comisión pesa proporcionalmente menos. Para la ZR, eso hace que el NQ sea económicamente algo más favorable por unidad de riesgo. Supuesto de comisión del NQ: 2,50 $ por lado.")
    w("")
    w(f"**RSI(2), drawdown por día de salida frente a mark-to-market:** {R['rsi2_dd_mtm_vs_salida']}. La auditoría subestimaba algo el drawdown al contar el P&L el día de salida.")
    w("")
    # --------------------------- árbol de decisión
    w("## DECISION TREE FINAL")
    w("")
    w("### RSI2")
    w("```text")
    w("STATUS:        SOBREVIVE (validación adicional respaldada por los datos; NO fuera de muestra)")
    w("CONFIDENCE:    BAJA-MEDIA. Robusto ante costes, ejecución y parámetros; pero con muestra pequeña y aleatorización")
    w("               p ≈ 0,10: una parte grande del resultado es la deriva alcista del Nasdaq.")
    w("MAIN RISK:     Régimen bajista prolongado (2018, 2022) y la salida por tiempo (5 sesiones) en caídas que continúan.")
    w("               Sin stop: DD mark-to-market 1 año p95 ≈ 4.500 $ con 1 MNQ.")
    w("WHAT WOULD FALSIFY IT:  En forward, expectativa media de 15 operaciones < −71 $ (p5 histórico) o < −136 $ (p1);")
    w("               o, con ≥ 50 operaciones forward, una expectativa no mejor que la de entradas aleatorias en tendencia (~+60 $).")
    w("WHAT TO MONITOR LIVE:   Frecuencia (≈ 1,2 op/mes), % de salidas por tiempo (históricamente el 29 %, todas las pérdidas grandes),")
    w("               P&L nocturno (huecos del lunes), coincidencia de señales del EA (CFD) con las del futuro.")
    w("```")
    w("")
    w("### NOISE ZONE")
    w("```text")
    w("STATUS:        SOBREVIVE (la aleatorización la distingue claramente del azar; NO fuera de muestra)")
    w("CONFIDENCE:    MEDIA. Muestra grande y señal no aleatoria; pero con dependencia de cola (1 % de las operaciones =")
    w("               107 % del neto) y de la volatilidad (≈ 0 en vol baja), 2015-2017 negativo y fragilidad a 3× costes.")
    w("MAIN RISK:     Periodos largos de volatilidad baja o sin días de tendencia: 12 meses móviles negativos en el 24 % de las")
    w("               ventanas (peor −1.883 $). Días tras un crash (−47 $/op). Deslizamiento real mayor que 1 tick por lado.")
    w("WHAT WOULD FALSIFY IT:  Expectativa media de las últimas 50 operaciones < −20,5 $ (p5) o < −33 $ (p1); o deslizamiento")
    w("               medio real ≥ 4-5 ticks por lado (cada tick extra por lado cuesta 1 $/op; la expectativa histórica se")
    w("               anula hacia ~5 ticks/lado); o, con ≥ 500 operaciones forward,")
    w("               un IC 95 % por bloques completamente por debajo de 0.")
    w("WHAT TO MONITOR LIVE:   Deslizamiento por ejecución; operaciones por mes (≈ 19); expectativa por régimen de vol (etiquetando")
    w("               cada día con el ATR relativo); presencia de días de cola (> +200 $), sin los que es normal perder.")
    w("```")
    w("")
    w("### PORTFOLIO")
    w("```text")
    w("STATUS:        Dos fuentes distintas (correlación diaria −0,06; mecanismos distintos). La combinación mejora algo el")
    w("               Sharpe a igual riesgo. El EA actual (1+1 MNQ) es MÁS riesgo que una sola estrategia, no igual riesgo.")
    w("MAIN RISK:     Con 1+1 MNQ: P(DD ≥ 5.000 $ en 1 año) ≈ 3 %, P(algún día ≤ −1.000 $) ≈ 37 % (sobre todo huecos del")
    w("               RSI(2) de noche) -> el freno diario del EA saltará con cierta frecuencia y bloqueará entradas de la ZR.")
    w("DIVERSIFICATION EVIDENCE:  Correlación diaria −0,06, mensual −0,06, de drawdown +0,05; condicionada ≤ 0,15 (todos los")
    w("               días); +0,43 en días con ambas y volatilidad BAJA (62 días; observación). La ZR rinde peor cuando el")
    w("               RSI(2) está abierto (observación post hoc).")
    w("WHAT TO MONITOR LIVE:   Correlación móvil de 60 días entre ambas; días en que salta el freno diario y por qué estrategia;")
    w("               DD combinado frente al p95 de Monte Carlo (≈ 4.600 $ con 1+1 MNQ).")
    w("```")
    w("")
    w("## Anexos")
    w("")
    w("| Documento | Contenido |")
    w("|---|---|")
    w("| `survivor/SURVIVOR_PROJECT_AUDIT.md` | Diagnóstico inicial, incluida la petición de datos de ES (15,06 $, **no descargados**) |")
    w("| `survivor/SURVIVOR_ANALYSIS_PRE_REGISTRATION.md` | Preguntas, pruebas y umbrales fijados antes de ejecutar |")
    w("| `survivor/POST_HOC_OBSERVATIONS.md` | Patrones vistos después; no validados |")
    w("| `survivor/TEST_CONTAMINATION_LOG.md` | Qué datos se han visto y cuándo |")
    w("| `forward_testing/` | `survivors.csv`, `deriva.py` (bandas, sin apagar nada), `comparar.py` (importa el `APEX_registro.csv` del EA) |")
    w("")
    w("**Sobre NQ/ES:** no merece la pena ahora.")
    w("- No hay forma de reservar un TEST limpio, así que sería EXPLORATORY ONLY.")
    w("- El laboratorio no encontró edge en ideas intradía parecidas.")
    w("- El objetivo actual es observar las dos supervivientes, no buscar una tercera.")
    (REP / "SURVIVOR_ANALYSIS_FINAL.md").write_text("\n".join(L), encoding="utf-8")
    print("ok", REP / "SURVIVOR_ANALYSIS_FINAL.md")


if __name__ == "__main__":
    generar()
