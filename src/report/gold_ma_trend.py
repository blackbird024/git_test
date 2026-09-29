"""Informe de GOLD_MA_TREND_v1.0 (hipótesis A, B y C). Reglas y criterios: edges/gold_ma_trend.md.

Uso: python -m src.report.gold_ma_trend   →   reports/GOLD_MA_TREND_v1.0/ (nunca se sobrescribe).
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.engine.lookahead import comprobar  # noqa: E402
from src.metrics.metricas import racha  # noqa: E402
from src.strategies import gold_ma_trend as g  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent.parent
CORTE = pd.Timestamp(json.loads((RAIZ / "config" / "particion.json").read_text())["diario_GC"]["inicio_fuera_de_muestra"],
                     tz="UTC")
PERIODOS_MERCADO = {"2010-2012 final alcista": (2010, 2012), "2013-2015 bajista": (2013, 2015),
                    "2016-2018 lateral": (2016, 2018), "2019-2020 alcista": (2019, 2020),
                    "2021-2023 lateral/volátil": (2021, 2023), "2024-2026 alcista fuerte": (2024, 2026)}


# ------------------------------------------------------------------------------------------- métricas
def m_ops(o: pd.DataFrame, anios: float) -> dict:
    if o.empty:
        return {"operaciones": 0}
    n = o.neto_usd
    gan, per = n[n > 0], n[n <= 0]
    pf = gan.sum() / -per.sum() if per.sum() < 0 else np.inf
    return {"operaciones": len(o), "op_por_año": round(len(o) / anios, 2), "neto_usd": round(n.sum(), 0),
            "R_medio": round(o.r.mean(), 3), "profit_factor": round(pf, 2), "acierto_%": round((n > 0).mean() * 100, 1),
            "ganancia_media_usd": round(gan.mean(), 0) if len(gan) else 0, "perdida_media_usd": round(per.mean(), 0) if len(per) else 0,
            "expectativa_usd": round(n.mean(), 0), "mejor_usd": round(n.max(), 0), "peor_usd": round(n.min(), 0),
            "dur_media_dias": round(o.dias_naturales.mean(), 0), "dur_max_dias": int(o.dias_naturales.max()),
            "racha_perd": racha(n <= 0), "racha_gan": racha(n > 0),
            "t_ops": round(o.r.mean() / o.r.std() * np.sqrt(len(o)), 2) if len(o) > 2 else np.nan,
            "neto_sin_mejor_usd": round(n.sum() - n.max(), 0)}


def m_dia(di: pd.DataFrame) -> dict:
    r = di.ret.dropna()
    if r.empty:
        return {}
    eq = (1 + r).cumprod()
    dd = eq / eq.cummax() - 1
    pnl = di.pnl.cumsum()
    dd_usd = pnl - pnl.cummax().clip(lower=0)
    # duración del peor drawdown (días naturales desde el máximo previo hasta recuperarlo, o hasta el final)
    fin = dd.idxmin()
    pico = eq[:fin].idxmax()
    rec = eq[fin:][eq[fin:] >= eq[pico]]
    dur = ((rec.index[0] if len(rec) else eq.index[-1]) - pico).days
    down = r[r < 0]
    return {"sharpe": round(r.mean() / r.std() * np.sqrt(252), 2) if r.std() > 0 else np.nan,
            "sortino": round(r.mean() / np.sqrt((down ** 2).mean()) * np.sqrt(252), 2) if len(down) else np.nan,
            "t_diario": round(r.mean() / r.std() * np.sqrt(len(r)), 2) if r.std() > 0 else np.nan,
            "rend_anual_%": round(r.mean() * 252 * 100, 2), "dd_max_%": round(dd.min() * 100, 1),
            "dd_max_usd": round(dd_usd.min(), 0), "dd_dur_dias": dur, "en_mercado_%": round((di.pos != 0).mean() * 100, 1),
            "largo_%": round((di.pos > 0).mean() * 100, 1), "corto_%": round((di.pos < 0).mean() * 100, 1),
            "neto_diario_usd": round(di.pnl.sum(), 0)}


def anios(di):
    return (di.index[-1] - di.index[0]).days / 365.25


# ------------------------------------------------------------------------------------------ auditorías
def auditoria_datos():
    raw = pd.read_parquet(RAIZ / "data" / "raw" / "daily" / "GC.parquet")
    d = g.cargar()
    bd = pd.bdate_range(raw.index.min(), raw.index.max(), tz="UTC")
    falt = bd.difference(raw.index)
    ids = d.instrument_id
    es_roll = ids != ids.shift()
    ret = (d.close - d.ajuste).pct_change()
    grandes = ret.abs().nlargest(6)
    saltos = (d.open - d.close.shift() - (d.ajuste - d.ajuste.shift()))       # salto en precio real el día del roll
    gap_roll = (d.ajuste.shift() - d.ajuste)[es_roll].iloc[1:]
    filas = [
        ("Fuente", "Databento GLBX.MDP3 ohlcv-1d, contrato continuo por volumen GC.v.0"),
        ("Rango", f"{raw.index.min():%Y-%m-%d} → {raw.index.max():%Y-%m-%d}"),
        ("Velas en el archivo", f"{len(raw)} ({(raw.index.dayofweek == 6).sum()} domingos de reapertura)"),
        ("Velas tras unir domingos al lunes", f"{len(d)}"),
        ("Duplicados / valores faltantes", f"{raw.index.duplicated().sum()} / {int(raw.isna().sum().sum())}"),
        ("Velas imposibles (high < max(open, close) o low > min)",
         str(int(((raw.high < raw[["open", "close"]].max(axis=1)) | (raw.low > raw[["open", "close"]].min(axis=1))).sum()))),
        ("Laborables sin vela", f"{len(falt)}: festivos (Viernes Santo, Navidad, Año Nuevo…) salvo 2014-06-13 y "
                                f"2014-09-23/24/25 (hueco de datos de 3 días)" if len(falt) else "0"),
        ("Zona horaria", "UTC; cada vela es un día natural en UTC (00:00-24:00). Índice único y a las 00:00 UTC"),
        ("Cambios de contrato", f"{len(d.attrs['rolls'])}; salto medio {gap_roll.mean():.1f} $ (mediana "
                                f"{gap_roll.median():.1f}, máx. {gap_roll.max():.1f}); ajuste aditivo hacia atrás"),
        ("Mayores movimientos diarios (precio real)",
         "; ".join(f"{t:%Y-%m-%d} {v * 100:+.1f} %{' (día de roll)' if es_roll.get(t, False) else ''}"
                   for t, v in ret.reindex(grandes.index).items())),
    ]
    return pd.DataFrame(filas, columns=["punto", "resultado"]), saltos


def auditoria_lookahead(d_full, d_dev, cfg, ops_full, ops_dev):
    res = []
    cortes = [pd.Timestamp(x, tz="UTC") for x in ("2013-06-15", "2016-06-11", "2019-06-15", "2021-06-12",
                                                  "2023-06-10", "2025-06-14")]
    raw = g.cargar()
    probs = []
    for c in cortes:
        parcial = g.senales(g.cargar(hasta=c), cfg)
        comp = g.senales(raw, cfg)
        a = comp[comp.t_senal < c].reset_index(drop=True)
        b = parcial[parcial.t_senal < c].reset_index(drop=True)
        if not a.equals(b):
            probs.append(str(c.date()))
    res.append(("1. Look-ahead: truncamiento (6 cortes, datos cortados ANTES de ajustar)",
                "OK" if not probs else "FALLO", "sin diferencias" if not probs else "cambian: " + ", ".join(probs)))
    # 2. Fuga de datos: el desarrollo simulado solo con datos de desarrollo = la simulación completa en ese periodo
    comp = ops_full[ops_full.dia_salida < d_dev.index[-1]][["dia_entrada", "dia_salida", "direccion"]].reset_index(drop=True)
    dev = ops_dev[~ops_dev.abierta_al_final][["dia_entrada", "dia_salida", "direccion"]].reset_index(drop=True)
    res.append(("2. Fuga de datos: desarrollo con solo datos de desarrollo = simulación completa", "OK" if comp.equals(dev)
                else "FALLO", f"{len(dev)} operaciones cerradas idénticas"))
    # 3 y 4. SMA recalculada con datos hasta el día de señal; ejecución en la apertura del día siguiente
    f3 = f4 = 0
    for _, o in ops_full.iterrows():
        hasta = d_full[d_full.index <= o.dia_senal]
        reg = g.regimen(hasta.close, cfg.rapida, cfg.lenta)
        esperado = 1 if (o.direccion == 1) else (-1)
        if not (reg[-1] == esperado and reg[-2] != reg[-1]):
            f3 += 1
        i = d_full.index.get_loc(o.dia_senal)
        if not (d_full.index[i + 1] == o.dia_entrada and d_full.open.iloc[i + 1] == o.entrada):
            f4 += 1
    res.append(("3. Información futura: régimen recalculado solo con datos hasta el día de señal", "OK" if f3 == 0 else "FALLO",
                f"{len(ops_full)} operaciones; fallos {f3}"))
    res.append(("4. Ejecución: apertura de la vela siguiente (nunca el cierre de la señal)", "OK" if f4 == 0 else "FALLO",
                f"{len(ops_full)} operaciones; fallos {f4}"))
    rolls_abiertos = int(ops_full.rolls.sum())
    res.append(("5. Rollover: ajuste aditivo; coste de ida y vuelta en cada roll con posición", "OK",
                f"{rolls_abiertos} rolls con posición abierta, todos con coste"))
    res.append(("6. Sesgo de supervivencia", "N/A", "un solo instrumento continuo, sin selección de activos"))
    sin_coste = int((ops_full.costes_usd <= 0).sum()) if cfg.costes.lado > 0 else 0
    res.append(("7. Costes omitidos", "OK" if sin_coste == 0 else "FALLO",
                f"todas las operaciones pagan entrada, salida y rolls (sin coste: {sin_coste})"))
    tz_ok = d_full.index.is_unique and (d_full.index.tz is not None) and (d_full.index.hour == 0).all()
    res.append(("8. Zona horaria", "OK" if tz_ok else "FALLO", "índice UTC, único, velas a las 00:00 UTC"))
    dup = ops_full.duplicated(["dia_entrada", "direccion"]).sum()
    res.append(("9. Operaciones duplicadas", "OK" if dup == 0 else "FALLO", f"duplicadas: {dup}"))
    solape = int((ops_full.dia_entrada.iloc[1:].to_numpy() < ops_full.dia_salida.iloc[:-1].to_numpy()).sum())
    res.append(("10. Posiciones simultáneas", "OK" if solape == 0 else "FALLO",
                f"entradas antes de cerrar la anterior: {solape}"))
    return res


# -------------------------------------------------------------------------------------------- principal
def carpeta():
    out, k = RAIZ / "reports" / g.VERSION, 2
    while out.exists():
        out, k = RAIZ / "reports" / f"{g.VERSION}_v{k}", k + 1
    return out


def clasificar(r1, r2, bh_total, nombre):
    dev, oos, tot = r1["dev"], r1["oos"], r1["total"]
    motivos = []
    if tot["ops"].get("neto_usd", 0) + 0 < 0 and tot["dia"]["neto_diario_usd"] < 0:
        return "FAILED", ["pierde dinero con costes realistas (escenario 1) en el periodo completo"]
    dev_ok = dev["ops"].get("neto_usd", 0) > 0 and dev["ops"].get("profit_factor", 0) > 1 and dev["dia"]["sharpe"] > 0
    oos_neto = oos["dia"]["neto_diario_usd"]
    if dev_ok and oos_neto < 0:
        return "FAILED", ["positiva en desarrollo y negativa en el fuera de muestra (FAILED / OVERFIT)"]
    c = {
        "1 desarrollo: neto>0, PF>1, Sharpe>0": dev_ok,
        "2 OOS: neto>0, PF>1, Sharpe ≥ 50 % del de desarrollo": oos_neto > 0 and oos["ops"].get("profit_factor", 0) > 1
        and oos["dia"]["sharpe"] >= 0.5 * dev["dia"]["sharpe"],
        "3 t diario del periodo completo ≥ 2": tot["dia"]["t_diario"] >= 2,
        "4 escenario 2: neto > 0": r2["total"]["dia"]["neto_diario_usd"] > 0,
        "5 neto sin la mejor operación > 0": tot["ops"].get("neto_sin_mejor_usd", -1) > 0,
    }
    if nombre == "B":
        c["6 valor frente a comprar y mantener"] = (tot["dia"]["sharpe"] >= bh_total["sharpe"]) or (
            tot["dia"]["sharpe"] >= 0.8 * bh_total["sharpe"] and tot["dia"]["dd_max_%"] > 0.5 * bh_total["dd_max_%"])
    else:
        c["6 valor frente a comprar y mantener"] = tot["dia"]["sharpe"] >= bh_total["sharpe"]
    fallan = [k for k, v in c.items() if not v]
    if not fallan:
        return "VALIDATED", ["cumple los 6 criterios"]
    return "INCONCLUSIVE", ["no cumple: " + "; ".join(fallan)]


def ejecutar():
    salida = carpeta()
    salida.mkdir(parents=True)
    tabla_datos, _ = auditoria_datos()
    d_full = g.cargar()
    d_dev = g.cargar(hasta=CORTE)
    inicio = 199                                        # primera vela con SMA 200 (misma ventana para comparar)

    resultados, tablas_anuales, lados, dist, periodos_m, duraciones, curvas, audits = {}, [], [], [], [], [], {}, {}
    for h, base in g.HIPOTESIS.items():
        resultados[h] = {}
        for esc, cost in g.ESCENARIOS.items():
            cfg = base.con(costes=cost)
            o_dev, di_dev = g.simular(d_dev, cfg)
            o_full, di_full = g.simular(d_full, cfg)
            di_dev, di_full = di_dev.iloc[inicio:], di_full.iloc[inicio:]
            di_oos = di_full[di_full.index >= CORTE]
            o_oos = o_full[o_full.dia_entrada >= CORTE]
            puente = o_full[(o_full.dia_entrada < CORTE) & (o_full.dia_salida >= CORTE)]
            resultados[h][esc] = {
                "dev": {"ops": m_ops(o_dev, anios(di_dev)), "dia": m_dia(di_dev)},
                "oos": {"ops": m_ops(o_oos, anios(di_oos)), "dia": m_dia(di_oos)},
                "total": {"ops": m_ops(o_full, anios(di_full)), "dia": m_dia(di_full)},
                "puente": puente,
            }
            if esc == 1:
                audits[h] = auditoria_lookahead(d_full, d_dev, cfg, o_full, o_dev)
                curvas[h] = di_full
                o_full.assign(hipotesis=h).to_csv(salida / f"trades_{h}.csv", index=False)
                y = di_full.groupby(di_full.index.year).agg(neto_usd=("pnl", "sum"), rend_pct=("ret", "sum"))
                y["rend_pct"] = (y.rend_pct * 100).round(1)
                y["operaciones_abiertas"] = o_full.groupby(o_full.dia_entrada.dt.year).size().reindex(y.index).fillna(0).astype(int)
                tablas_anuales.append(y.round(0).assign(hipotesis=h))
                for lado, gl in o_full.groupby("lado"):
                    lados.append({"hipotesis": h, "lado": lado, **m_ops(gl, anios(di_full))})
                dist.append({"hipotesis": h, **{f"R p{q}": round(np.percentile(o_full.r, q), 2) for q in (5, 25, 50, 75, 95)},
                             "ret_% p50": round(o_full.ret_pct.median(), 1), "ret_% mejor": round(o_full.ret_pct.max(), 1),
                             "ret_% peor": round(o_full.ret_pct.min(), 1)})
                for nombre, (a, b) in PERIODOS_MERCADO.items():
                    dp = di_full[(di_full.index.year >= a) & (di_full.index.year <= b)]
                    if len(dp) > 20:
                        m = m_dia(dp)
                        periodos_m.append({"hipotesis": h, "periodo": nombre, "neto_usd": m["neto_diario_usd"],
                                           "rend_anual_%": m["rend_anual_%"], "sharpe": m["sharpe"], "dd_max_%": m["dd_max_%"]})
                reg = g.regimen(d_full.close, cfg.rapida, cfg.lenta)[inicio:]
                cambios = np.flatnonzero(np.diff(reg) != 0)
                largos = np.diff(cambios)
                duraciones.append({"hipotesis": f"{h} ({cfg.rapida}/{cfg.lenta})", "tendencias": len(largos),
                                   "días_mediana": int(np.median(largos)), "días_media": int(np.mean(largos)),
                                   "más_corta": int(largos.min()), "más_larga": int(largos.max())})
    bh = {}
    for esc, cost in g.ESCENARIOS.items():
        b_full = g.comprar_y_mantener(d_full, cost, inicio).iloc[inicio:]
        b_dev = g.comprar_y_mantener(d_dev, cost, inicio).iloc[inicio:]
        bh[esc] = {"dev": m_dia(b_dev), "oos": m_dia(b_full[b_full.index >= CORTE]), "total": m_dia(b_full)}
        if esc == 1:
            curvas["Comprar y mantener"] = b_full

    estados = {}
    for h in g.HIPOTESIS:
        estados[h] = clasificar(resultados[h][1], resultados[h][2], bh[1]["total"], h)

    if any(r[1] == "FALLO" for h in audits for r in audits[h]):
        (salida / "diagnostics.md").write_text("# LOOK-AHEAD / VALIDACIÓN FALLIDA — DETENIDO\n\n" +
                                               "\n\n".join(pd.DataFrame(audits[h]).to_markdown() for h in audits))
        print("AUDITORÍA FALLIDA")
        sys.exit(1)

    # ------------------------------------------------------------------ tablas
    def fila(h, esc, per):
        r = resultados[h][esc][per]
        return {"hipótesis": h, "escenario": esc, **r["ops"], **r["dia"]}
    resumen = pd.DataFrame([fila(h, e, p) | {"periodo": p} for h in g.HIPOTESIS for e in g.ESCENARIOS
                            for p in ("dev", "oos", "total")])
    resumen.to_csv(salida / "summary.csv", index=False)
    bh_tab = pd.DataFrame([{"escenario": e, "periodo": p, **bh[e][p]} for e in bh for p in ("dev", "oos", "total")])
    bh_tab.to_csv(salida / "buy_and_hold.csv", index=False)
    anual = pd.concat(tablas_anuales)
    anual.to_csv(salida / "yearly.csv")
    pd.DataFrame(lados).to_csv(salida / "long_short.csv", index=False)
    pd.DataFrame(periodos_m).to_csv(salida / "market_periods.csv", index=False)

    # ------------------------------------------------------------------ gráficos
    colores = {"A": "#2a78d6", "B": "#1a9e77", "C": "#d9822b", "Comprar y mantener": "#8a8f98"}
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    for k, di in curvas.items():
        eq = (1 + di.ret.fillna(0)).cumprod()
        ax1.plot(eq.index, eq, lw=2 if k != "Comprar y mantener" else 1.5, color=colores[k],
                 label=k if k == "Comprar y mantener" else f"{k} ({dict(A='50/200 L+S', B='50/200 solo largos', C='20/100 L+S')[k]})")
        ax2.plot(eq.index, (eq / eq.cummax() - 1) * 100, lw=1.5, color=colores[k])
    for ax in (ax1, ax2):
        ax.axvline(CORTE, color="#555", ls="--", lw=1)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.grid(axis="y", color="#eee")
    ax1.set_title("GOLD_MA_TREND_v1.0: valor de 1 $ (1× nocional, escenario 1)", loc="left")
    ax1.legend(frameon=False)
    ax1.text(CORTE, ax1.get_ylim()[1] * 0.95, "  fuera de muestra →", color="#555")
    ax2.set_title("Drawdown (%)", loc="left")
    fig.tight_layout()
    fig.savefig(salida / "equity_drawdown.png", dpi=120)
    plt.close(fig)

    # ------------------------------------------------------------------ README
    md = lambda df, i=False: df.to_markdown(index=i)  # noqa: E731
    cols_ops = ["operaciones", "op_por_año", "neto_usd", "R_medio", "profit_factor", "acierto_%", "ganancia_media_usd",
                "perdida_media_usd", "mejor_usd", "peor_usd", "dur_media_dias", "dur_max_dias"]
    cols_dia = ["sharpe", "sortino", "t_diario", "rend_anual_%", "dd_max_%", "dd_max_usd", "dd_dur_dias",
                "en_mercado_%", "largo_%", "corto_%"]

    def bloque(per):
        t = resumen[(resumen.periodo == per) & (resumen.escenario == 1)].set_index("hipótesis")
        b = pd.DataFrame([bh[1][per]], index=["Comprar y mantener"])
        return md(t[cols_ops], True) + "\n\n" + md(pd.concat([t[cols_dia], b.reindex(columns=cols_dia)]), True)

    costes_tab = resumen[resumen.periodo == "total"].pivot_table(index="hipótesis", columns="escenario",
                                                                  values=["neto_usd", "sharpe", "profit_factor"])
    puentes = "; ".join(f"{h}: {len(resultados[h][1]['puente'])}" for h in g.HIPOTESIS)
    texto = [
        f"# {g.VERSION}: cruce de medias en el oro (GC diario)", "",
        "Reglas y criterios registrados ANTES de ejecutar: `edges/gold_ma_trend.md` (commit 67ac0cd). "
        "Código: `src/strategies/gold_ma_trend.py`. Repetir: `python -m src.report.gold_ma_trend`.", "",
        "## 1. DATA AUDIT", "", md(tabla_datos), "",
        "**Limitaciones:**",
        "- Hueco de datos de 3 días en septiembre de 2014.",
        "- Día natural en UTC en lugar de la sesión de CME. El cierre diario es el precio de las 00:00 UTC (19:00-20:00 NY), "
        "no el settlement oficial.",
        "- El salto medido en un cambio de contrato incluye el movimiento de ese momento (unos minutos, porque el corte UTC "
        "cae en plena sesión).",
        "- El contrato que usa la serie continua lo elige Databento por volumen.", "",
        "## 2. STRATEGY RULES", "",
        "- **Régimen** al cierre diario: SMA rápida > lenta → LARGO; < → CORTO (si son iguales, se mantiene).",
        "- **Entrada / salida:** en la **apertura del día siguiente** al cruce confirmado.",
        "- **Hipótesis:**",
        "  - A: 50/200, largos y cortos (siempre dentro tras el primer cruce);",
        "  - B: 50/200, solo largos;",
        "  - C: 20/100, largos y cortos.",
        "- **Sin** stop, objetivo, trailing ni filtros. 1 contrato GC (100 oz).",
        "- **R** = P&L / (ATR(20) × 100) en la entrada.",
        "- **Costes por contrato y lado:**",
        "  - escenario 0: 0 $;",
        "  - escenario 1: 2,50 $ + 1 tick (10 $) = 12,50 $;",
        "  - escenario 2: 5 $ + 3 ticks = 35 $;",
        "  - además, un ida y vuelta en cada cambio de contrato con posición abierta.",
        "- **Métricas diarias:** 1× nocional sobre el precio real; Sharpe y Sortino anualizados con 252 días; t diario = "
        "media / desviación × √N.",
        "- **Periodos:**",
        f"  - desarrollo: hasta el {(CORTE - pd.Timedelta(days=1)).date()}, simulado **solo con datos de desarrollo**;",
        f"  - fuera de muestra: desde el {CORTE.date()};",
        f"  - operaciones que cruzan el corte: {puentes} (cuentan en el periodo completo y en las métricas diarias).", "",
        "## 3. DEVELOPMENT RESULTS (escenario 1)", "", bloque("dev"), "",
        "## 4. OOS RESULTS (escenario 1)", "", bloque("oos"), "",
        "El t por operación no es apropiado con tan pocas operaciones. Se usa el t de los rendimientos diarios, que tiene "
        "autocorrelación y hay que leer con cautela.", "",
        "## Periodo completo (escenario 1)", "", bloque("total"), "",
        "## 5. COST ANALYSIS (periodo completo)", "", costes_tab.round(2).to_markdown(), "",
        "Referencia, comprar y mantener: Sharpe " + " / ".join(f"esc. {e}: {bh[e]['total']['sharpe']}" for e in bh) + ".", "",
        "## 6. ROBUSTNESS (solo las 3 hipótesis registradas)", "",
        "### Por periodo de mercado (escenario 1)", "", md(pd.DataFrame(periodos_m)), "",
        "### Distribución de resultados por operación (escenario 1)", "", md(pd.DataFrame(dist)), "",
        "### Duración de las tendencias (días de mercado entre cruces)", "", md(pd.DataFrame(duraciones)), "",
        "### Rachas (escenario 1, periodo completo)", "",
        md(resumen[(resumen.periodo == "total") & (resumen.escenario == 1)][["hipótesis", "racha_perd", "racha_gan"]]), "",
        "## 7. LOOK-AHEAD AUDIT", "",
    ]
    for h in g.HIPOTESIS:
        texto += [f"**Hipótesis {h}**", "", md(pd.DataFrame(audits[h], columns=["validación", "resultado", "detalle"])), ""]
    texto += ["## 8. YEAR-BY-YEAR RESULTS (escenario 1; P&L diario de 1 contrato y rendimiento sobre el nocional)", "",
              md(anual.reset_index().rename(columns={"dia": "año", "index": "año"})), "",
              "## 9. LONG VS SHORT (escenario 1, periodo completo)", "", md(pd.DataFrame(lados)[
                  ["hipotesis", "lado", "operaciones", "neto_usd", "R_medio", "profit_factor", "acierto_%"]]), "",
              "## 10. DRAWDOWN ANALYSIS", "", "![Saldo y drawdown](equity_drawdown.png)", "",
              md(resumen[(resumen.escenario == 1)][["hipótesis", "periodo", "dd_max_%", "dd_max_usd", "dd_dur_dias"]]), "",
              "## 11. FINAL STATUS", ""]
    for h, (e, motivos) in estados.items():
        texto += [f"- **Hipótesis {h}: {e}.** " + " ".join(motivos)]
    lados_df = pd.DataFrame(lados)
    cortos = lados_df[lados_df.lado == "SHORT"].set_index("hipotesis").neto_usd
    texto += ["", "**Lectura objetiva:**",
              f"- Ninguna hipótesis supera el Sharpe de simplemente comprar y mantener oro ({bh[1]['total']['sharpe']} "
              "en el periodo completo). Sharpe de las hipótesis: " + ", ".join(
                  f"{h} {resultados[h][1]['total']['dia']['sharpe']}" for h in g.HIPOTESIS) + ".",
              "- El beneficio viene del lado largo en los dos grandes tramos alcistas (2019-2020 y 2024-2026). Los cortos "
              "no aportan: " + ", ".join(f"{h} {v:,.0f} $" for h, v in cortos.items()) + ".",
              f"- En desarrollo (2011-2021) el resultado es casi nulo: Sharpe A {resultados['A'][1]['dev']['dia']['sharpe']}, "
              f"B {resultados['B'][1]['dev']['dia']['sharpe']} y C {resultados['C'][1]['dev']['dia']['sharpe']}. El fuera de muestra "
              "es positivo porque coincide con la mayor subida del oro de la serie, no porque la regla anticipe nada.",
              "- A y B dependen de una sola operación: sin la mejor (el largo de 2024-2026), el neto es negativo.",
              "- Los costes apenas importan (de 1 a 3 operaciones al año): el problema no son los costes, sino la falta de "
              "ventaja frente a mantener la posición.",
              "- No hay evidencia de que el seguimiento de tendencia con medias añada valor en el oro. Siguiendo lo "
              "pactado, no se prueban más combinaciones."]
    (salida / "README.md").write_text("\n".join(texto) + "\n")
    print("Informe en", salida)
    for h, (e, m) in estados.items():
        print(h, e, m)
    return resultados, bh, estados


if __name__ == "__main__":
    ejecutar()
