"""Informe final del Trading Bot Lab: reports/FINAL_REPORT.md, RESEARCH_LOG.md, reports/dashboard.html y gráficos.

    python -m bot_lab.generar_informe
"""
from __future__ import annotations

import html
import json
import pickle
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import norm  # noqa: E402

from bot_lab.core.datos import cargar_config  # noqa: E402
from bot_lab.run_lab import MODULOS  # noqa: E402

LAB = Path(__file__).resolve().parent
REP = LAB / "reports"
AZUL, NARANJA, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
TINTA, TINTA2, MUTED, SUPERFICIE = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"


def limpio(x):
    if isinstance(x, (np.floating, float)):
        return "—" if not np.isfinite(x) else f"{float(x):,.2f}".replace(",", " ")
    if isinstance(x, (np.integer, int)):
        return f"{int(x):,}".replace(",", " ")
    if isinstance(x, (tuple, list)):
        return "(" + ", ".join(limpio(v) for v in x) + ")"
    if isinstance(x, (np.bool_, bool)):
        return "sí" if x else "no"
    return str(x)


def tabla(df: pd.DataFrame, indice=True) -> str:
    if df is None or len(df) == 0:
        return "_(sin datos)_\n"
    d = df.copy()
    cols = ([d.index.name or ""] if indice else []) + [str(c) for c in d.columns]
    filas = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for k, r in d.iterrows():
        celdas = ([limpio(k)] if indice else []) + [limpio(v) for v in r.to_numpy()]
        filas.append("| " + " | ".join(celdas) + " |")
    return "\n".join(filas) + "\n"


def estilo(ax):
    ax.set_facecolor(SUPERFICIE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=TINTA2, labelsize=8)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
    ax.set_axisbelow(True)


def cargar():
    exp = LAB / "research" / "experiments"
    r1 = pickle.loads((sorted(exp.glob("*_investigacion"))[-1] / "resultados.pkl").read_bytes())
    t = sorted(exp.glob("*_test"))
    r2 = pickle.loads((t[-1] / "resultados.pkl").read_bytes()) if t else None
    return r1, r2, sorted(exp.glob("*_investigacion"))[-1].name, (t[-1].name if t else None)


# ------------------------------------------------------------------------------------------------ gráficos
def grafico_embudo(r1: dict, t_bonf: float, t_min: float):
    filas = []
    for bot, r in r1["cribado"].items():
        for k, f in r["tabla_train"].iterrows():
            filas.append((bot, k, f.t, k == r["seleccionada"], r.get("estado_validacion") == "finalista" and k == r["seleccionada"]))
    df = pd.DataFrame(filas, columns=["bot", "var", "t", "sel", "fin"]).dropna(subset=["t"])
    fig, ax = plt.subplots(figsize=(9, 11), dpi=130)
    fig.patch.set_facecolor(SUPERFICIE)
    estilo(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color="#e6e5e0", linewidth=0.6)
    y = np.arange(len(df))[::-1]
    col = np.where(df.fin, NARANJA, AZUL)
    ax.barh(y, df.t, color=col, height=0.62)
    for x, lab, c in ((0, "0", MUTED), (t_min, f"cribado t={t_min}", TINTA2), (t_bonf, f"Bonferroni t={t_bonf:.2f}", TINTA2)):
        ax.axvline(x, color=c, linewidth=0.8, linestyle="-" if x == 0 else "--")
        if x:
            ax.text(x, len(df) + 0.3, lab, fontsize=7, color=TINTA2, ha="center")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{v[:38]}" for v in df["var"]], fontsize=6.5, color=TINTA2)
    ax.set_xlabel("t de la expectativa por operación en TRAIN (2015-2022, costes BASE)", fontsize=8, color=TINTA2)
    ax.set_title(f"Las {len(df)} variantes con operaciones del laboratorio (naranja = único finalista)", fontsize=10,
                 color=TINTA, loc="left")
    ax.set_ylim(-1, len(df) + 1.5)
    fig.tight_layout()
    fig.savefig(REP / "embudo_variantes_train.png", facecolor=SUPERFICIE)
    plt.close(fig)


def grafico_finalista(ev: dict, cfg: dict, nombre: str, archivo: str):
    o = ev["ops"].sort_values("t_salida")
    t = pd.DatetimeIndex(o.t_salida).tz_convert("America/New_York").tz_localize(None)
    eq = o.neto.cumsum().to_numpy()
    fig, ax = plt.subplots(figsize=(9, 3.6), dpi=130)
    fig.patch.set_facecolor(SUPERFICIE)
    estilo(ax)
    p = cfg["particion"]
    for a, b, lab in ((p["train_desde"], p["validation_desde"], "TRAIN"), (p["validation_desde"], p["test_desde"], "VALIDATION"),
                      (p["test_desde"], p["fin"], "TEST")):
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color="#f0efec" if lab != "VALIDATION" else "#e6e5e0", zorder=0)
        ax.text(pd.Timestamp(a) + (pd.Timestamp(b) - pd.Timestamp(a)) / 2, 0.97, lab, ha="center", va="top",
                fontsize=7, color=TINTA2, transform=ax.get_xaxis_transform())
    ax.plot(t, eq, color=AZUL, linewidth=2)
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.set_ylabel("$ acumulados (1 MNQ, costes BASE)", fontsize=8, color=TINTA2)
    ax.set_title(nombre, fontsize=10, color=TINTA, loc="left")
    fig.tight_layout()
    fig.savefig(REP / archivo, facecolor=SUPERFICIE)
    plt.close(fig)


def grafico_carteras(r2: dict, archivo: str):
    import pandas as pd
    exp = LAB / "research" / "experiments"
    d = pd.read_csv(sorted(exp.glob("*_test"))[-1] / "pnl_diario_bots.csv", index_col=0, parse_dates=True)
    fig, ax = plt.subplots(figsize=(9, 3.6), dpi=130)
    fig.patch.set_facecolor(SUPERFICIE)
    estilo(ax)
    base = ["BOT01 RSI2", "BOT02 Zona ruido"]
    series = [("A: BOT01 + BOT02", d[base].sum(axis=1), AZUL)]
    extra = [c for c in d.columns if c not in base]
    if extra:
        series.append((f"A + {extra[0]}", d[base + extra[:1]].sum(axis=1), NARANJA))
    for nombre, p, c in series:
        eq = p.cumsum()
        ax.plot(eq.index, eq, color=c, linewidth=2, label=nombre)
        ax.text(eq.index[-1], eq.iloc[-1], "  " + nombre.split(":")[0], color=TINTA2, fontsize=7, va="center")
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.legend(frameon=False, fontsize=8, labelcolor=TINTA2, loc="upper left")
    ax.set_ylabel("$ acumulados (1 MNQ por estrategia)", fontsize=8, color=TINTA2)
    ax.set_title("Carteras A y B, 2015-2026 (el periodo ya se había usado en investigaciones previas)", fontsize=10,
                 color=TINTA, loc="left")
    fig.tight_layout()
    fig.savefig(REP / archivo, facecolor=SUPERFICIE)
    plt.close(fig)


# ------------------------------------------------------------------------------------------------ texto
def anios_para_evidencia(ops: pd.DataFrame, por_anio: float, t_obj: float = 2.0) -> tuple[float, float]:
    x = ops.neto
    if len(x) < 3 or x.mean() <= 0:
        return np.inf, np.inf
    n = (t_obj * x.std(ddof=1) / x.mean()) ** 2
    return n, n / por_anio


def research_log(r1: dict, r2: dict | None, cfg: dict, n_total: int) -> str:
    p = cfg["particion"]
    out = ["# RESEARCH_LOG — Trading Bot Lab", "",
           "Registro de todas las hipótesis probadas en el laboratorio: las negativas no se ocultan.",
           "",
           "Todas se registraron el 30-sep-2026 (ver `CRITERIOS.md` y `research/hypotheses/`) y usan esta partición:",
           "",
           "| Tramo | Periodo |",
           "|---|---|",
           f"| TRAIN | {p['train_desde']} → {p['validation_desde']} (excluido) |",
           f"| VALIDATION | {p['validation_desde']} → {p['test_desde']} (excluido) |",
           f"| TEST | {p['test_desde']} → {p['fin']} |",
           "",
           "El TEST está reservado para estas reglas, pero **no es fuera de muestra puro**.",
           "",
           f"**Variantes ejecutadas en el cribado: {n_total}** (más las vecindades y el walk-forward del finalista).",
           "",
           "**Hipótesis previas del proyecto sobre NQ** (auditoría y `archive/`): unas 25 ideas y más de 60 variantes.", ""]
    for bot, r in r1["cribado"].items():
        mod = MODULOS[bot]
        v = r.get("validacion")
        estado = {"E": "E — NEGATIVE", "C": "C — INSUFFICIENT"}.get(r["estado_cribado"], "")
        if r["estado_cribado"] == "pasa":
            estado = "finalista" if r.get("estado_validacion") == "finalista" else "E — NEGATIVE (falla VALIDATION)"
        if r2 and bot in r2.get("finalistas", {}):
            estado = r2["finalistas"][bot]["clase"] + " (clasificación automática tras abrir el TEST)"
        datos = "NQ 1 min Databento 2015-2026" if bot != "26" else "GC/SI diarios Databento 2010-2026"
        partes = [f"## BOT {bot} — {mod.NOMBRE}", "```text",
                  f"strategy_id:        BOT{bot}",
                  f"hypothesis:         {mod.HIPOTESIS}",
                  "date_created:       2026-09-30",
                  f"parameters_tested:  {', '.join(sorted({k for p_ in mod.VARIANTES.values() for k in p_ if k != 'control'}))}",
                  f"number_of_variants: {len(mod.VARIANTES)}",
                  f"data_period:        {datos}",
                  f"train_period:       {p['train_desde']} → {p['validation_desde']}",
                  f"validation_period:  {p['validation_desde']} → {p['test_desde']}",
                  f"test_period:        {p['test_desde']} → {p['fin']} ({'abierto solo para el finalista' if bot in (r2 or {}).get('finalistas', {}) else 'no abierto: no pasó a finalista'})",
                  f"result:             {estado}. {r['detalle']}" + (f"; VALIDATION: {v['operaciones']} op., expectativa {v['expectativa_$']:.2f} $, PF {v['profit_factor']:.2f}" if v else ""),
                  f"selected_variant:   {r['seleccionada']}",
                  f"reason_for_selection: {r['motivo_seleccion']}", "```", ""]
        out += partes
    out += ["## BOT 20 / 21 (parte 1) / 22 — investigación sin estrategia",
            "Regímenes, deriva por franja horaria y por día de la semana. Solo TRAIN y solo informativo: no se ha creado ninguna estrategia a partir de estos resultados. Ver `reports/FINAL_REPORT.md`.", "",
            "## BOT 25 y BOT 26 (NQ/ES) — pendientes",
            "No hay datos de 1 min de ES en el proyecto. Descargarlos cuesta 15,06 $ en Databento (consultado el 30-sep, sin descargar), por encima del límite de 0,50 $ que exige preguntar. Quedan sin probar.", ""]
    return "\n".join(out)


def generar():
    cfg = cargar_config()
    r1, r2, exp1, exp2 = cargar()
    REP.mkdir(exist_ok=True)
    n_var = r1["n_variantes"]
    t_bonf = float(norm.ppf(1 - 0.05 / (2 * n_var)))
    grafico_embudo(r1, t_bonf, cfg["cribado"]["t_min"])
    (LAB / "RESEARCH_LOG.md").write_text(research_log(r1, r2, cfg, n_var), encoding="utf-8")
    L = []
    w = L.append
    fin = (r2 or {}).get("finalistas", {})
    robustas = [b for b, ev in fin.items() if ev["clase"].startswith("A")]
    w("# TRADING BOT LAB — FINAL REPORT")
    w("")
    w(f"30-sep-2026 · experimentos `{exp1}` (investigación, sin TEST en memoria) y `{exp2}` (apertura única del TEST) · "
      "reproducible con `python -m bot_lab.run_lab investigacion`, `python -m bot_lab.run_lab test` y `python -m bot_lab.generar_informe`.")
    w("")
    w("## Veredicto")
    w("")
    if not robustas:
        w("### NO HAY NUEVO EDGE ROBUSTO.")
    else:
        w(f"### Estrategias robustas nuevas: {', '.join(robustas)}")
    w("")
    w(f"- Se probaron **{n_var} variantes pre-registradas** de 11 familias nuevas (BOT 13-19, 21, 23, 24 y 26), con las reglas fijadas y guardadas en git antes de ejecutar.")
    if fin:
        for b, ev in fin.items():
            te = ev["test"]
            w(f"- Solo **1 variante** pasó el cribado en TRAIN y la VALIDATION: **BOT {b} — {ev['variante']}**.")
            w(f"  - En el TEST (abierto una sola vez con la variante congelada) dio **{te['expectativa_$']:+.2f} $ por operación** en {te['operaciones']} operaciones (t = {te['t']:.2f}, PF {te['profit_factor']:.2f}). Es decir, **cero**.")
            w(f"  - La clasificación automática la deja en **{ev['clase']}**, pero solo porque {te['expectativa_$']:.2f} > 0 de forma técnica.")
            w("  - **Lectura del analista:** no hay evidencia de ventaja. El IC 95 % incluye el 0, el walk-forward no es positivo, empeora la cartera actual y en 2026 pierde. Lo más probable es que sea **ruido seleccionado**: 1 de 70 variantes con t ≈ 1,7 es lo que se espera por azar.")
    w("- La mayoría de las familias intradía pierden aproximadamente lo que cuestan los costes (≈ 3 $ por operación con 1 MNQ). Es la firma de un mercado sin ventaja explotable con esas reglas, y coincide con la prueba de control del motor con entradas aleatorias.")
    w("- **BOT 01 (RSI(2)) y BOT 02 (zona de ruido) siguen siendo las únicas estrategias con evidencia.** Ninguna idea nueva mejora su cartera.")
    w("")
    w("**Advertencias que condicionan todo lo anterior:**")
    w("1. 2015-2026 ya se había usado en investigaciones anteriores del proyecto, así que ningún tramo es fuera de muestra puro. El único dato nuevo es el forward test que empezó el 30-sep-2026.")
    w(f"2. **Pruebas múltiples.** El laboratorio tiene {n_var} variantes y el proyecto, unas 25 ideas anteriores. Con {n_var} variantes, la t que exigiría Bonferroni es **{t_bonf:.2f}**, y ninguna variante nueva se acerca.")
    w("3. BOT 25/26 NQ-ES **no se han probado**: faltan los datos de ES (15,06 $ en Databento; pendiente de tu autorización).")
    w("")
    w("![Embudo](embudo_variantes_train.png)")
    w("")
    # ---------------- dashboard
    w("## Panel (dashboard)")
    w("")
    w("Las cifras son de la variante elegida de cada BOT:")
    w("- **No finalistas:** solo TRAIN.")
    w("- **Finalista:** 2015-2026 completo.")
    w("- **BOT 01/02:** su código original, 2015-2026.")
    w("")
    w("Nota: el P&L del BOT 26 va en $ por 25.000 $ nocionales por pata; el resto, en $ por 1 MNQ.")
    w("")
    filas = []
    for bot in ("01", "02"):
        ev = (r2 or r1)["validadas"][bot]
        m = ev["metricas"]
        filas.append({"BOT": bot, "Hipótesis": "RSI(2) Connors diario" if bot == "01" else "Zona de ruido (Zarattini)",
                      "Marco": "1D" if bot == "01" else "1m", "Sesión": "CME" if bot == "01" else "NY 10:00-15:30",
                      "Ops": m["operaciones"], "PF": m["profit_factor"], "Expect. $": m["expectativa_$"],
                      "IC95 $": ev["IC95_bloques_$"], "Max DD $": m["max_dd_$"], "Sharpe": m["sharpe"],
                      "Walk-forward": "— (ya validada)", "Costes ×2": ev["costes"]["STRESS_1"]["expectativa_$"],
                      "Estabilidad": "ver auditoría", "MC P(año<0) %": ev["montecarlo"]["prob_año_negativo_%"],
                      "Régimen": "", "Estado": "Validada (auditoría 30-sep), en forward test"})
    for bot, r in r1["cribado"].items():
        mod = MODULOS[bot]
        if bot in fin:
            ev = fin[bot]
            m = ev["metricas"]
            vol = ev["regimenes"]["vol"]
            mejor = vol.drop(index="sin dato", errors="ignore")["expectativa_$"].idxmax() if len(vol) else ""
            filas.append({"BOT": bot, "Hipótesis": mod.NOMBRE, "Marco": mod.MARCO, "Sesión": mod.SESION,
                          "Ops": m["operaciones"], "PF": m["profit_factor"], "Expect. $": m["expectativa_$"],
                          "IC95 $": ev["IC95_bloques_$"], "Max DD $": m["max_dd_$"], "Sharpe": m["sharpe"],
                          "Walk-forward": f"{ev['walk_forward']['reseleccion']['expectativa_$']:.2f} $/op, {ev['walk_forward']['reseleccion']['ventanas_positivas_%']:.0f} % ventanas +",
                          "Costes ×2": ev["costes"]["STRESS_1"]["expectativa_$"], "Estabilidad": ev["estabilidad"]["estabilidad"],
                          "MC P(año<0) %": ev["montecarlo"]["prob_año_negativo_%"], "Régimen": f"mejor en vol. {mejor}",
                          "Estado": ev["clase"] + " (analista: sin evidencia)"})
        else:
            f = r["tabla_train"].loc[r["seleccionada"]]
            est = "E — NEGATIVE" if r["estado_cribado"] in ("E", "pasa") else "C — INSUFFICIENT"
            if r["estado_cribado"] == "pasa":
                est += " (falla VALIDATION)"
            filas.append({"BOT": bot, "Hipótesis": mod.NOMBRE, "Marco": mod.MARCO, "Sesión": mod.SESION,
                          "Ops": f.operaciones, "PF": f.profit_factor, "Expect. $": f["expectativa_$"], "IC95 $": "—",
                          "Max DD $": "—", "Sharpe": "—", "Walk-forward": "no llega", "Costes ×2": "no llega",
                          "Estabilidad": "no llega", "MC P(año<0) %": "no llega", "Régimen": "—", "Estado": est})
    filas.append({"BOT": "25/26 NQ-ES", "Hipótesis": "Divergencia / spread NQ-ES", "Marco": "—", "Sesión": "—", "Ops": "—",
                  "PF": "—", "Expect. $": "—", "IC95 $": "—", "Max DD $": "—", "Sharpe": "—", "Walk-forward": "—",
                  "Costes ×2": "—", "Estabilidad": "—", "MC P(año<0) %": "—", "Régimen": "—",
                  "Estado": "PENDIENTE (sin datos de ES)"})
    dash = pd.DataFrame(filas).set_index("BOT")
    w(tabla(dash))
    # ---------------- 12 preguntas
    w("## Respuestas a las 12 preguntas")
    w("")
    w("**1. ¿Qué hipótesis nuevas muestran evidencia de edge?**")
    w("")
    w("Ninguna con evidencia suficiente. La única finalista (BOT 24.3) desaparece en el TEST.")
    w("")
    w("**2. ¿Cuáles son probablemente ruido?**")
    w("")
    w("Todas las nuevas:")
    w("- **Negativas con claridad** (t en TRAIN entre −2 y −8): la reversión al VWAP (13), el momentum de ruptura (16), los niveles del día anterior (23) y la ruptura o reversión del rango nocturno (24.1 y 24.2).")
    w("- **Nulas** (|t| < 1,2): ORB (14), tendencia (15), retroceso (17) y régimen + VWAP (19).")
    w("- **Positivas en TRAIN pero caen después:** RSI(2) extremo (18), con t 1,4 e insuficiente; deriva nocturna (21), que falla la VALIDATION; y 24.3, que falla el TEST.")
    w("- **Spread oro/plata (26):** negativo.")
    w("")
    w("**3. ¿Cuáles sobreviven a costes ×2 y ×3?**")
    w("")
    if fin:
        for b, ev in fin.items():
            c = ev["costes"]
            w(f"BOT {b}: ×2 → {c['STRESS_1']['expectativa_$']:+.2f} $/op (casi cero); ×3 → {c['STRESS_2']['expectativa_$']:+.2f} $/op (negativa). Es frágil ante los costes.")
    w("")
    w("Las demás no llegaron a esta prueba: ya pierden con costes BASE.")
    w("")
    w("La auditoría del 30-sep comprobó que BOT 01 y 02 sobreviven con ×2 y ×3.")
    w("")
    w("**4. ¿Cuáles sobreviven al walk-forward?**")
    w("")
    if fin:
        for b, ev in fin.items():
            wf = ev["walk_forward"]
            w(f"BOT {b}:")
            w(f"- **Con re-selección:** {wf['reseleccion']['expectativa_$']:+.2f} $/op, t {wf['reseleccion']['t']:.2f}, {wf['reseleccion']['ventanas_positivas_%']:.0f} % de {wf['reseleccion']['ventanas']} ventanas positivas. **No pasa** (hace falta ≥ 50 % de ventanas positivas y expectativa > 0).")
            w(f"- **Con parámetros fijos:** {wf['fija']['ventanas_positivas_%']:.0f} % de ventanas positivas, pero concentrado en 2020-2022.")
    w("")
    w("**5. ¿Cuáles tienen estabilidad de parámetros?**")
    w("")
    if fin:
        for b, ev in fin.items():
            e = ev["estabilidad"]
            w(f"BOT {b}: estabilidad {e['estabilidad']:.2f}. Hay meseta en el stop (1,6 / 2 / 2,4 ATR dan resultados parecidos), pero los años positivos son solo {e['años_positivos']:.0%}. Una meseta sobre una ventaja que no existe no ayuda.")
    w("")
    w("**6. ¿Cuáles funcionan solo en determinados regímenes?**")
    w("")
    if fin:
        for b, ev in fin.items():
            t_ = ev["regimenes"]["tendencia"]
            w(f"BOT {b}: todo su resultado viene de los días **RANGO** (ER20 ≤ 0,3): {t_.loc['RANGO', 'expectativa_$']:+.2f} $/op frente a {t_.loc['TENDENCIA', 'expectativa_$']:+.2f} en TENDENCIA. Por años, de 2020-2021 y 2024. No se filtra por régimen a posteriori, porque sería ajustar al pasado.")
    w("")
    w("**7. ¿Cuáles diversifican mejor RSI2 y Noise Zone?**")
    w("")
    if r2:
        c = r2["correlaciones"]["diaria"]
        for col in c.columns[2:]:
            w(f"{col}: correlación diaria {c.loc[col, 'BOT01 RSI2']:+.2f} con RSI(2) y {c.loc[col, 'BOT02 Zona ruido']:+.2f} con la zona de ruido. **No diversifica**: también es una estrategia de apertura de NY en la dirección del VWAP, como la zona de ruido.")
    w("")
    w("**8. ¿Cuál sería la cartera histórica más robusta?**")
    w("")
    if r2:
        ca = pd.DataFrame(r2["carteras"]).T
        a = ca.iloc[0]
        w(f"La **cartera A (BOT01 + BOT02, 1+1 MNQ)**: Sharpe {a['sharpe']:.2f}, DD máximo {a['max_dd_$']:,.0f} $ y {a['años_positivos']} años positivos.")
        if len(ca) > 1:
            b_ = ca.iloc[1]
            w(f"Añadir el BOT 24 la **empeora**: Sharpe {b_['sharpe']:.2f}, DD {b_['max_dd_$']:,.0f} $ y P(DD ≥ 5.000 $ en un año) del {b_['prob_dd_≥5000_%']:.1f} % frente al {a['prob_dd_≥5000_%']:.1f} %.")
    w("")
    w("**9. ¿Cuál es el drawdown máximo histórico y el de Monte Carlo?**")
    w("")
    if r2:
        w("Cartera A (1+1 MNQ, capital de 25.000 $):")
        w(f"- **Histórico:** {a['max_dd_$']:,.0f} $.")
        w(f"- **Monte Carlo a 1 año** (bootstrap por bloques): mediana {a['max_dd_p50_$']:,.0f} $, p95 {a['max_dd_p95_$']:,.0f} $, p99 {a['max_dd_p99_$']:,.0f} $.")
        w(f"- **Probabilidades:** año negativo {a['prob_año_negativo_%']:.1f} %; DD ≥ 5.000 $ {a['prob_dd_≥5000_%']:.1f} %.")
    w("")
    w("**10. ¿Cuántas operaciones produce cada bot?**")
    w("")
    w("Ver la columna Ops del panel.")
    w("- **Referencia por año:** BOT 01 ≈ 13; BOT 02 ≈ 230; BOT 24.3 ≈ 185.")
    w("- **Familias nuevas intradía:** 100-1.100 al año según la variante.")
    w("")
    w("**11. ¿Cuánto habría que esperar para tener evidencia suficiente?**")
    w("")
    w("Número de operaciones para t = 2 con la expectativa y la dispersión observadas, dividido entre las operaciones al año:")
    w("")
    filas = []
    for nombre, ev in ((f"BOT 01 RSI(2)", (r2 or r1)["validadas"]["01"]), ("BOT 02 zona de ruido", (r2 or r1)["validadas"]["02"])) + tuple(
            (f"BOT {b} (finalista)", ev) for b, ev in fin.items()):
        n, anios = anios_para_evidencia(ev["ops"], ev["metricas"]["operaciones_por_año"])
        filas.append({"estrategia": nombre, "operaciones/año": ev["metricas"]["operaciones_por_año"],
                      "operaciones para t=2": round(n) if np.isfinite(n) else "∞", "años": round(anios, 1) if np.isfinite(anios) else "∞"})
    w(tabla(pd.DataFrame(filas).set_index("estrategia")))
    w("Son cifras con la ventaja histórica. Si la ventaja real es la mitad, hace falta el cuádruple. Para el forward test, lo razonable sigue siendo:")
    w("- **Zona de ruido:** ~150 operaciones (≈ 6-8 meses) para comprobar que se comporta como el backtest. Confirmarla estadísticamente lleva años.")
    w("- **RSI(2):** años, porque opera muy poco.")
    w("")
    w("**12. ¿Qué debería pasar a forward testing?**")
    w("")
    w("**Ninguna estrategia nueva.**")
    w("- BOT 01 y BOT 02 siguen en su forward test en la demo, sin cambios.")
    w("- Si quieres, el BOT 24.3 se puede **observar en papel** (sin dinero ni demo), solo para ver si reaparece. Mi recomendación es no dedicarle recursos.")
    w("")
    # ---------------- detalle cribado
    w("## Detalle del cribado (TRAIN 2015-01 → 2022-01, costes BASE, 1 MNQ)")
    w("")
    w("La regla de selección es fija: gana la variante con mayor t y muestra suficiente, y en empate gana la base. Así, la \"elegida\" de una familia negativa es simplemente su variante menos mala.")
    w("")
    for bot, r in r1["cribado"].items():
        mod = MODULOS[bot]
        w(f"### BOT {bot} — {mod.NOMBRE}")
        w(f"_Hipótesis: {mod.HIPOTESIS}_")
        w("")
        t = r["tabla_train"][["operaciones", "expectativa_$", "t", "profit_factor", "acierto_%", "neto_$"]].copy()
        t.index.name = "variante"
        w(tabla(t))
        w(f"Elegida: **{r['seleccionada']}** ({r['motivo_seleccion']}). Resultado: **{r['estado_cribado']}**"
          + (f"; VALIDATION: {r['validacion']['operaciones']} op., {r['validacion']['expectativa_$']:+.2f} $/op, PF {r['validacion']['profit_factor']:.2f} → **{r['estado_validacion']}**" if "validacion" in r else "") + ".")
        w("")
    # ---------------- finalista
    for bot, ev in fin.items():
        mod = MODULOS[bot]
        grafico_finalista(ev, cfg, f"BOT {bot} — {ev['variante']}: P&L acumulado", f"bot{bot}_equity.png")
        w(f"## Finalista BOT {bot} — {ev['variante']} (evaluación completa, 2015-2026)")
        w("")
        w(f"![BOT {bot}](bot{bot}_equity.png)")
        w("")
        w("**Por tramo:**")
        w(tabla(pd.DataFrame(ev["tramos_detalle"]).T))
        m = {k: v for k, v in ev["metricas"].items() if k != "anual_$"}
        w("**Métricas completas** (1 MNQ, capital de referencia 25.000 $):")
        w("")
        w(tabla(pd.DataFrame({"valor": m}).rename_axis("métrica")))
        w("**Resultado por año ($):** " + ", ".join(f"{k}: {v:+,.0f}" for k, v in ev["metricas"]["anual_$"].items()))
        w("")
        w(f"**IC 95 % de la expectativa por bloques de 20 sesiones:** {limpio(ev['IC95_bloques_$'])} $. **TEST:** {limpio(ev['test']['IC95_bloques_$'])} $.")
        w("")
        w("**Costes:**")
        w(tabla(pd.DataFrame(ev["costes"]).T))
        w("**Walk-forward (12 meses de entrenamiento, 3 de prueba):**")
        w(tabla(pd.DataFrame({k: ev["walk_forward"][k] for k in ("reseleccion", "fija")}).T))
        w("**Sensibilidad (vecindad pre-registrada):**")
        w(tabla(ev["vecindad"].rename_axis("variante")))
        w(f"**Estabilidad:** {ev['estabilidad']}")
        w("")
        for k in ("vol", "tendencia", "dia", "año", "direccion"):
            w(f"**Por {k}:**")
            w(tabla(ev["regimenes"][k]))
        w("**Monte Carlo (1 año, bloques de 20 sesiones):**")
        w(tabla(pd.DataFrame({"valor": ev["montecarlo"]}).rename_axis("medida")))
        w("**Criterios de clasificación:**")
        w(tabla(pd.DataFrame({"cumple": ev["criterios"]}).rename_axis("criterio")))
        w(f"**Clase automática: {ev['clase']}.**")
        w("")
        w("**Lectura del analista: sin evidencia.**")
        w(f"- El TEST da {ev['test']['expectativa_$']:+.2f} $/op.")
        w(f"- La t de 2015-2026 es {ev['metricas']['t']:.2f}, lejos de la de Bonferroni ({t_bonf:.2f}).")
        w("- El walk-forward no pasa y hay 2026 negativo.")
        w("- Se correlaciona con la zona de ruido y empeora la cartera.")
        w("")
    # ---------------- 01/02
    w("## BOT 01 y BOT 02 con las mismas métricas (código original, 2015-2026)")
    w("")
    for bot, nombre in (("01", "RSI(2)"), ("02", "zona de ruido")):
        ev = (r2 or r1)["validadas"][bot]
        m = ev["metricas"]
        w(f"**BOT {bot} {nombre}:**")
        w(f"- {m['operaciones']} operaciones, PF {m['profit_factor']:.2f}, {m['expectativa_$']:+.2f} $/op, t {m['t']:.2f}.")
        w(f"- IC 95 % por bloques {limpio(ev['IC95_bloques_$'])}; Sharpe {m['sharpe']:.2f}; DD máximo {m['max_dd_$']:,.0f} $.")
        w(f"- Costes ×2: {ev['costes']['STRESS_1']['expectativa_$']:+.2f} $/op; ×3: {ev['costes']['STRESS_2']['expectativa_$']:+.2f} $/op.")
        if "test" in ev:
            w(f"- Tramo 2024-05 → 2026-09: {ev['test']['operaciones']} op., {ev['test']['expectativa_$']:+.2f} $/op. No es fuera de muestra: sus reglas se eligieron viendo ese periodo.")
        w("")
        w("Por régimen de volatilidad:")
        w(tabla(ev["regimenes"]["vol"]))
    # ---------------- 20-22
    w("## BOT 20, 21 y 22 — regímenes, hora y día (investigación, solo TRAIN)")
    w("")
    w("**BOT 20. Expectativa ($/op) de la variante elegida de cada BOT por régimen de volatilidad** (ATR14/ATR250 del día anterior):")
    w("")
    filas = {}
    for bot, a in r1["analisis"]["por_bot_train"].items():
        v = a["vol"]
        filas[f"BOT {bot}"] = {k: (f"{v.loc[k, 'expectativa_$']:+.2f} ({int(v.loc[k, 'operaciones'])})" if k in v.index else "—")
                               for k in ("BAJA", "NORMAL", "ALTA")}
    w(tabla(pd.DataFrame(filas).T.rename_axis("BOT")))
    w("Lectura:")
    w("- Ninguna familia negativa se vuelve positiva de forma consistente en algún régimen.")
    w("- La zona de ruido (BOT 02) gana más en volatilidad ALTA, lo que confirma la dependencia de régimen que ya señaló la auditoría.")
    w("- No se crean filtros de régimen a posteriori.")
    w("")
    w("**BOT 21 (parte 1). Cambio medio de NQ por franja** ($ por 1 MNQ comprado, **sin costes**, TRAIN):")
    w(tabla(r1["analisis"]["deriva_franja_train"]))
    w("Lectura:")
    w("- La **noche** (18:00-03:00 NY) concentra la deriva alcista (t ≈ 3,5), como describe la literatura sobre la deriva nocturna. La estrategia pre-registrada 21.1 (comprado de 18:00 a 09:25) pasó el TRAIN, pero **falló la VALIDATION** 2022-2024.")
    w("- La franja 16:00-17:00 también sale alta (t ≈ 3,3), pero **no estaba en ninguna hipótesis previa**. Queda anotada para pre-registrarla en el futuro, no para operarla. Además, su media (≈ 3 $) no cubre los costes de ida y vuelta (≈ 3 $).")
    w("- **La apertura de NY no es superior** a las demás franjas.")
    w("")
    w("**BOT 22. Apertura→cierre RTH por día de la semana** ($ por 1 MNQ, sin costes, TRAIN):")
    w(tabla(r1["analisis"]["deriva_dia_train"]))
    w("Lectura: ningún día es significativo (|t| < 1,5). **No se crea ninguna estrategia por día de la semana.**")
    w("")
    # ---------------- cartera
    if r2:
        w("## Correlaciones y carteras (2015-2026)")
        w("")
        for k, t in r2["correlaciones"].items():
            w(f"**Correlación {k}:**")
            w(tabla(t))
        w("**Carteras** (1 MNQ por estrategia, capital de 25.000 $, sin reinversión; Monte Carlo a 1 año):")
        w(tabla(pd.DataFrame(r2["carteras"]).T.rename_axis("cartera")))
        w("No hay cartera C: no existe una segunda estrategia nueva de clase A o B que no esté correlacionada.")
        w("")
        grafico_carteras(r2, "carteras.png")
        w("![Carteras](carteras.png)")
        w("")
        w("## Tamaño (solo para el finalista, separado de la señal)")
        w("")
        for b, t in r2["tamano"].items():
            w(f"**BOT {b}**, arriesgando un % fijo de 25.000 $ por operación (contratos enteros, máximo 10 MNQ):")
            w(tabla(t[["operaciones", "contratos_medios", "neto_anual_$", "max_dd_$", "max_dd_%", "sharpe", "prob_año_negativo_%", "prob_dd_≥5000_%"]].rename_axis("riesgo")))
        w("Sin ventaja, aumentar el tamaño solo agranda el drawdown. Con un 1 % por operación, el DD histórico sería del 79 % del capital.")
        w("")
        w("## Modo prop firm (módulo aparte; estrategias sin adaptar)")
        w("")
        pf = cfg["prop_firm"]
        w(f"Reglas simuladas:")
        w(f"- Cuenta de {pf['capital']:,} $.")
        w(f"- Límite diario de {pf['limite_diario']:,} $.")
        w(f"- Trailing de {pf['trailing_dd']:,} $ sobre el cierre diario.")
        w(f"- Objetivo de {pf['objetivo']:,} $, con un máximo de {pf['sesiones_max']} sesiones.")
        w("")
        w("Método: bootstrap del P&L diario, 2.000 trayectorias.")
        w("")
        w("**Aviso:** el trailing intradía real (con ganancias no realizadas) es más duro que esta simulación.")
        w("")
        for nombre, lista in r2["prop_firm"].items():
            w(f"**{nombre}**")
            w(tabla(pd.DataFrame(lista).set_index("contratos_por_estrategia")))
    w("## Qué NO se ha hecho (y por qué)")
    w("")
    w("- **BOT 25/26 NQ-ES:** faltan los datos de ES, que cuestan 15,06 $ en Databento. Si lo autorizas, se prueban con el mismo protocolo, pero ya no podrán tener un TEST reservado, porque todo el periodo quedará visto.")
    w("- **SMC/ICT:** no se optimizó, como pediste.")
    w("- **Ninguna estrategia se ha ajustado después de ver resultados.** El único cambio, el BOT 24.2, se hizo antes de ver resultados, por un error de definición (ver `CRITERIOS.md`).")
    w("- **No se ha construido ningún EA nuevo.** No hay nada nuevo que merezca ejecución.")
    w("")
    w("## Archivos")
    w("")
    w("| Archivo | Contenido |")
    w("|---|---|")
    w("| `bot_lab/PROJECT_AUDIT.md` | Mapa del proyecto |")
    w("| `bot_lab/CRITERIOS.md` | Criterios pre-registrados |")
    w("| `bot_lab/research/hypotheses/` | Fichas de cada BOT |")
    w("| `bot_lab/RESEARCH_LOG.md` | Registro de todas las hipótesis |")
    w("| `bot_lab/research/finalistas.json` | Congelado antes del TEST |")
    w("| `bot_lab/research/experiments/` | Manifiestos (commit, versiones, SHA-1 de los datos, semilla), logs y tablas |")
    w("| `bot_lab/research/experiments/*_investigacion/control_entradas_aleatorias.md` | Control del motor |")
    (REP / "FINAL_REPORT.md").write_text("\n".join(L), encoding="utf-8")
    dashboard_html(dash, robustas, n_var, t_bonf, fin)
    print("ok", REP / "FINAL_REPORT.md")


def dashboard_html(dash: pd.DataFrame, robustas, n_var, t_bonf, fin):
    filas = []
    for bot, r in dash.iterrows():
        est = str(r["Estado"])
        clase = "neg" if est.startswith(("E", "C", "D")) else ("pend" if "PENDIENTE" in est else ("ok" if "Validada" in est else "warn"))
        celdas = "".join(f"<td>{html.escape(limpio(v))}</td>" for v in r.to_numpy()[:-1])
        filas.append(f"<tr><th scope='row'>{html.escape(str(bot))}</th>{celdas}<td><span class='tag {clase}'>{html.escape(est)}</span></td></tr>")
    cab = "".join(f"<th scope='col'>{html.escape(c)}</th>" for c in ["BOT"] + list(dash.columns))
    veredicto = "NO HAY NUEVO EDGE ROBUSTO" if not robustas else "Estrategias robustas: " + ", ".join(robustas)
    txt = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trading Bot Lab</title>
<style>
:root{{--bg:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--line:#e6e5e0;--ok:#0ca30c;--warn:#fab219;--neg:#d03b3b;--pend:#898781}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--line:#383835}}}}
:root[data-theme="dark"]{{--bg:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--line:#383835}}
body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:1200px;margin:0 auto;padding:24px 16px}}
h1{{font-size:22px;margin:0 0 4px}} p{{color:var(--ink2);margin:4px 0 16px}}
.hero{{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:16px}}
.hero strong{{font-size:20px}}
.wrap{{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:10px}}
table{{border-collapse:collapse;width:100%;font-size:12.5px}}
th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}
thead th{{color:var(--ink2);font-weight:600;position:sticky;top:0;background:var(--surface)}}
.tag{{display:inline-block;padding:2px 8px;border-radius:999px;border:1px solid var(--line);font-size:12px}}
.tag::before{{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;background:var(--pend)}}
.tag.ok::before{{background:var(--ok)}} .tag.warn::before{{background:var(--warn)}} .tag.neg::before{{background:var(--neg)}}
</style></head><body><main>
<h1>Trading Bot Lab — panel</h1>
<p>NQ/MNQ · 2015-2026 · {n_var} variantes pre-registradas · t de Bonferroni {t_bonf:.2f} · TEST abierto una sola vez para el finalista congelado</p>
<div class="hero"><strong>{html.escape(veredicto)}</strong><p>La única finalista (BOT 24.3) dio {fin['24']['test']['expectativa_$']:+.2f} $/op en el TEST. BOT 01 (RSI(2)) y BOT 02 (zona de ruido) siguen siendo las únicas con evidencia. Ningún tramo es fuera de muestra puro: el periodo ya se había usado antes.</p></div>
<div class="wrap"><table><thead><tr>{cab}</tr></thead><tbody>{''.join(filas)}</tbody></table></div>
<p>Cifras: no finalistas = variante elegida en TRAIN; finalista y BOT 01/02 = 2015-2026 completo. 1 MNQ, costes BASE (1 $/lado + 1-2 ticks). Detalle en FINAL_REPORT.md.</p>
</main></body></html>"""
    (REP / "dashboard.html").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    generar()
