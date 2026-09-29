"""Backtest de GOLD_LONDON_FALSE_BREAK_v1.0 (GC, 15m). Reglas: edges/gold_london_false_break.md.

1) Auditoría de look-ahead (si falla, se detiene).  2) v1.0 exacta en DESARROLLO, escenarios A/B/C.
3) Diagnóstico (no cambia la v1.0): lados, rango, profundidad, hora, sensibilidad.  El fuera de muestra NO se ejecuta.
Uso: python -m src.report.gold_london   →   reports/GOLD_LONDON_FALSE_BREAK_v1.0/ (nunca se sobrescribe).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.datos import excluidos
from src.engine.lookahead import comprobar
from src.horas import LONDRES, hora_local_a_utc
from src.report.gold_swing import MUESTRA_MIN, agrupar, graficos, md, metricas, periodos
from src.strategies import gold_london_false_break as g
from src.strategies.gold_swing_simple import ESCENARIOS, atr_wilder

RAIZ = Path(__file__).resolve().parent.parent.parent


def auditoria(m1, cfg, prep, ops, excl):
    v, n = prep["v15"], cfg.atr_n
    h, l, c, o = (v[x].to_numpy() for x in ("high", "low", "close", "open"))
    fallos = {k: 0 for k in ("rango", "primer", "entrada", "sl", "tp", "tiempo")}
    for _, op in ops.iterrows():
        f, d = op.fecha, op.direccion
        t = lambda hh: hora_local_a_utc(f, hh, LONDRES)  # noqa: E731
        rango = v[(v.index >= t("08:00")) & (v.index < t("09:00"))]
        RH, RL = rango.high.max(), rango.low.min()
        # Rango: 4 velas 08:00-08:45, todas cerradas (fin <= 09:00) antes de la falsa ruptura
        if not (len(rango) == 4 and rango.fin.max() <= t("09:00") <= op.t_false_break and np.isclose(RH - RL, op.range_usd)):
            fallos["rango"] += 1
        # Falsa ruptura recalculada SOLO con velas hasta la de señal (incluida): es la primera y la misma
        j = v.index.get_loc(op.t_false_break)
        ventana = np.flatnonzero((v.index >= t("09:00")) & (v.index <= op.t_false_break))
        est, js, dd, _, _ = g.buscar_falsa_ruptura(h, l, c, ventana, RH, RL)
        if not (est == "SIGNAL" and js == j and dd == d and op.t_false_break <= t("11:30")):
            fallos["primer"] += 1
        # Entrada: apertura de la vela siguiente, antes de las 12:00
        if not (v.index[j + 1] == op.t_entrada and o[j + 1] == op.entrada and op.t_entrada < t("12:00")):
            fallos["entrada"] += 1
        atr = atr_wilder(v.iloc[: j + 1], n)[-1]
        sl = h[j] + cfg.buffer_atr * atr if d == -1 else l[j] - cfg.buffer_atr * atr
        if not np.isclose(sl, op.sl):
            fallos["sl"] += 1
        if not np.isclose(op.tp, op.entrada + d * cfg.tp_r * abs(op.entrada - op.sl)):
            fallos["tp"] += 1
        # Salida por tiempo: cierre de la última vela que empieza antes de las 12:00; nada después de las 12:00
        if op.t_salida > t("12:00") or (op.resultado == "TIME" and not (
                op.salida == c[v.index.get_loc(op.t_salida - pd.Timedelta(minutes=15))]
                and v.index[v.index.get_loc(op.t_salida - pd.Timedelta(minutes=15)) + 1] >= t("12:00"))):
            fallos["tiempo"] += 1
    textos = {
        "rango": "Rango: 4 velas 08:00-08:45 de Londres, congelado a las 09:00 (antes de cualquier señal)",
        "primer": "Primer break / falsa ruptura recalculados con datos cortados en la vela de señal (<= 11:30)",
        "entrada": "Entrada: apertura de la vela 15m siguiente, antes de las 12:00",
        "sl": "SL: extremo de la vela de la falsa ruptura ± 0,10 × ATR(14) calculado hasta su cierre",
        "tp": "TP = entrada ± 2R con la entrada real",
        "tiempo": "Salida por tiempo: cierre de la última vela anterior a las 12:00; nada abierto después",
    }
    res = [(txt, "OK" if fallos[k] == 0 else "FALLO", f"{len(ops)} operaciones; fallos: {fallos[k]}")
           for k, txt in textos.items()]
    sabados = [pd.Timestamp(x, tz="UTC") for x in ("2016-06-11", "2017-09-16", "2019-01-12", "2020-05-16",
                                                    "2021-08-14", "2022-10-15")]
    probs = comprobar(lambda x: g.senales(x, cfg), m1, sabados)
    res.append(("Truncamiento global (6 cortes en sábado): entradas anteriores idénticas",
                "OK" if not probs else "FALLO", "; ".join(probs) or "sin diferencias"))
    return res


def carpeta() -> Path:
    out, k = RAIZ / "reports" / g.VERSION, 2
    while out.exists():
        out, k = RAIZ / "reports" / f"{g.VERSION}_v{k}", k + 1
    return out


def ejecutar():
    dev, _ = periodos()                                   # el fuera de muestra no se usa
    excl = excluidos("GC")
    base = g.Config()
    prep = g.preparar(dev, base)
    anios = (dev.index.max() - dev.index.min()).days / 365.25
    salida = carpeta()
    salida.mkdir(parents=True)

    ops_b, dias_b = g.backtest(dev, base, excl, prep)
    audit = auditoria(dev, base, prep, ops_b, excl)
    tabla_audit = md(pd.DataFrame(audit, columns=["punto", "resultado", "detalle"]))
    if any(r[1] == "FALLO" for r in audit):
        (salida / "diagnostics.md").write_text("# LOOK-AHEAD DETECTADO — BACKTEST DETENIDO\n\n" + tabla_audit)
        print("LOOK-AHEAD: detenido")
        sys.exit(1)

    resumen, trades, anual, lados, horas, curvas = [], [], [], [], [], {}
    for esc, costes in ESCENARIOS.items():
        cfg = base.con(costes=costes)
        ops, _ = g.backtest(dev, cfg, excl, prep)
        m = metricas(ops, cfg.saldo_inicial)
        resumen.append({"scenario": esc, "trades_per_year": round(m["trades"] / anios, 1), **m,
                        "pct_exit_TP": round((ops.resultado == "TP").mean() * 100, 1),
                        "pct_exit_SL": round((ops.resultado == "SL").mean() * 100, 1),
                        "pct_exit_TIME": round((ops.resultado == "TIME").mean() * 100, 1)})
        curvas[esc] = ops
        loc = pd.DatetimeIndex(ops.t_false_break).tz_convert(LONDRES)
        o = ops.assign(scenario=esc, anio=pd.DatetimeIndex(ops.t_entrada).year,
                       hora_fb=[f"{x:%H:%M}" for x in loc],
                       false_break=np.where(ops.direccion == -1, "HIGH→SHORT", "LOW→LONG"))
        trades.append(o)
        anual.append(agrupar(o, "anio", "year", cfg.saldo_inicial).assign(scenario=esc))
        lados.append(agrupar(o, "false_break", "false_break", cfg.saldo_inicial).assign(scenario=esc))
        horas.append(agrupar(o, "hora_fb", "false_break_time_london", cfg.saldo_inicial).assign(scenario=esc))
    resumen = pd.DataFrame(resumen)
    b = resumen.set_index("scenario").loc["B"]
    prometedor = b.trades >= MUESTRA_MIN and b.profit_factor > 1 and b.expectancy_R > 0 and b.t_stat_R >= 2

    # Rango → profundidad → resultado (escenario B, solo descriptivo)
    ob = trades[1].copy()
    ob["range_quintile"] = pd.qcut(ob.range_pct, 5, labels=[f"Q{i}" for i in range(1, 6)])
    ob["depth_quintile"] = pd.qcut(ob.break_depth_ratio, 5, labels=[f"Q{i}" for i in range(1, 6)])
    rq = agrupar(ob, "range_quintile", "range_pct_quintile", base.saldo_inicial)
    rq["range_pct_min"] = ob.groupby("range_quintile", observed=True).range_pct.min().round(3).to_numpy()
    rq["range_pct_max"] = ob.groupby("range_quintile", observed=True).range_pct.max().round(3).to_numpy()
    dq = agrupar(ob, "depth_quintile", "depth_ratio_quintile", base.saldo_inicial)
    dq["depth_ratio_min"] = ob.groupby("depth_quintile", observed=True).break_depth_ratio.min().round(3).to_numpy()
    dq["depth_ratio_max"] = ob.groupby("depth_quintile", observed=True).break_depth_ratio.max().round(3).to_numpy()
    ob["range_tercile"] = pd.qcut(ob.range_pct, 3, labels=["rango bajo", "rango medio", "rango alto"])
    ob["depth_tercile"] = pd.qcut(ob.break_depth_ratio, 3, labels=["prof. baja", "prof. media", "prof. alta"])
    cruz_r = ob.pivot_table(index="range_tercile", columns="depth_tercile", values="r", aggfunc="mean",
                            observed=True).round(3)
    cruz_n = ob.pivot_table(index="range_tercile", columns="depth_tercile", values="r", aggfunc="size", observed=True)
    corr = ob[["range_pct", "break_depth_ratio", "r"]].corr(method="spearman").round(3)

    sens = []
    for nombre, cambios in {"v1.0 (oficial)": {}, "TP 1,5R": {"tp_r": 1.5}, "TP 2,5R": {"tp_r": 2.5},
                            "buffer 0": {"buffer_atr": 0.0}}.items():
        for esc, costes in ESCENARIOS.items():
            m = metricas(g.backtest(dev, base.con(**cambios, costes=costes), excl, prep)[0], base.saldo_inicial)
            sens.append({"variant": nombre, "scenario": esc, **{k: m.get(k) for k in
                         ["trades", "win_rate_%", "profit_factor", "expectancy_R", "expectancy_R_gross", "t_stat_R",
                          "net_$", "max_dd_%", "sample_flag"]}})
    sens = pd.DataFrame(sens)

    cols = ["scenario", "fecha", "lado", "t_false_break", "t_entrada", "t_salida", "entrada", "sl", "tp", "salida",
            "resultado", "r", "r_bruto", "neto_usd", "bruto_usd", "costes_usd", "onzas", "riesgo_usd", "saldo_antes",
            "duracion_h", "mae_r", "mfe_r", "range_high", "range_low", "range_usd", "range_pct", "stop_distance_usd",
            "break_depth", "break_depth_ratio", "atr_15m", "entrada_real", "sl_real", "tp_real"]
    pd.concat(trades)[cols].to_csv(salida / "trades.csv", index=False)
    dias_b.to_csv(salida / "daily_range_stats.csv", index=False)
    resumen.to_csv(salida / "summary.csv", index=False)
    pd.concat(anual).to_csv(salida / "yearly.csv", index=False)
    pd.concat(lados).to_csv(salida / "false_break_side.csv", index=False)
    pd.concat(horas).to_csv(salida / "false_break_time.csv", index=False)
    pd.concat([rq.assign(tabla="range_pct"), dq.assign(tabla="depth_ratio")]).to_csv(
        salida / "range_depth_analysis.csv", index=False)
    sens.to_csv(salida / "sensitivity.csv", index=False)
    (salida / "signals.txt").write_text("\n\n".join(g.alerta(op) for _, op in ops_b.iterrows()) + "\n")
    graficos(curvas, salida, base.saldo_inicial, g.VERSION)
    (salida / "diagnostics.md").write_text("\n".join([
        f"# Diagnóstico: {g.VERSION} (desarrollo, {anios:.2f} años)", "", "## Auditoría de look-ahead", "", tabla_audit,
        "", "## Estado de cada día (escenario B)", "",
        md(dias_b.estado.value_counts().rename_axis("estado").reset_index(name="n")), "",
        "## Primer extremo atacado (días con rango válido)", "",
        md(dias_b.first_extreme_attacked.value_counts(dropna=False).rename_axis("extremo").reset_index(name="n")), "",
        "## Rango × profundidad: R medio (escenario B)", "", cruz_r.to_markdown(), "", "Número de operaciones:", "",
        cruz_n.to_markdown(), "", "## Correlación de Spearman (escenario B)", "", corr.to_markdown(), "",
        "## Fuera de muestra", "", "BLOQUEADO: no se ha ejecutado (decisión del usuario).", ""]))
    print("Informe en", salida, "| criterios de desarrollo:", "CUMPLE" if prometedor else "NO CUMPLE")


if __name__ == "__main__":
    ejecutar()
