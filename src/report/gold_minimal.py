"""Backtest de GOLD_SWING_MINIMAL_v1.0 (GC). Reglas: edges/gold_swing_minimal.md.

1) Auditoría de look-ahead (si falla, se detiene).  2) v1.0 exacta en DESARROLLO, escenarios A/B/C.
3) Fuera de muestra SOLO si el desarrollo cumple los criterios registrados.  4) Sensibilidad EMA x TP (diagnóstico).
Uso: python -m src.report.gold_minimal   →   reports/GOLD_SWING_MINIMAL_v1.0/ (nunca se sobrescribe).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.engine.lookahead import comprobar
from src.report.gold_swing import MUESTRA_MIN, agrupar, graficos, md, metricas, periodos
from src.strategies import gold_swing_minimal as g
from src.strategies.gold_swing_simple import ESCENARIOS, atr_wilder

RAIZ = Path(__file__).resolve().parent.parent.parent
ANTERIOR = {"version": "GOLD_SWING_SIMPLE_v1.0", "trades": 41}


def anios(m1: pd.DataFrame) -> float:
    return (m1.index.max() - m1.index.min()).days / 365.25


def auditoria(m1, cfg, prep, ops):
    v1, v4, n = prep["v1"], prep["v4"], cfg.ema
    c, h, l = v1.close.to_numpy(), v1.high.to_numpy(), v1.low.to_numpy()
    fallos = {k: 0 for k in ("ema", "retroceso", "senal", "entrada", "sl", "tp")}
    for _, op in ops.iterrows():
        d = op.direccion
        s = v1.index.get_loc(op.t_senal - pd.Timedelta(hours=1))
        k = v1.index.get_loc(op.t_retroceso)
        # EMA y dirección 4H recalculadas solo con velas 4H cerradas al cierre de la señal y del retroceso
        dir_s = g.direccion_4h(v4[v4.fin <= op.t_senal], n)
        dir_k = g.direccion_4h(v4[v4.fin <= v1.fin.iloc[k]], n)
        if not (len(dir_s) and dir_s[-1] == d and len(dir_k) and dir_k[-1] == d):
            fallos["ema"] += 1
        # Retroceso: cierre contra la dirección; sin otro retroceso ni señal entre retroceso y señal; ventana <= 5
        es_pb = lambda j: (c[j] < c[j - 1]) if d == 1 else (c[j] > c[j - 1])  # noqa: E731
        es_sen = lambda j: (c[j] > h[j - 1]) if d == 1 else (c[j] < l[j - 1])  # noqa: E731
        if not (es_pb(k) and 0 < s - k <= cfg.ventana and not any(es_pb(j) or es_sen(j) for j in range(k + 1, s))):
            fallos["retroceso"] += 1
        if not es_sen(s):
            fallos["senal"] += 1
        # Entrada: apertura de la vela 1H siguiente a la señal
        if not (v1.index[s + 1] == op.t_entrada and v1.open.iloc[s + 1] == op.entrada and op.t_entrada >= op.t_senal):
            fallos["entrada"] += 1
        # Stop con la vela de retroceso y el ATR calculado solo hasta el cierre de la señal
        atr = atr_wilder(v1.iloc[: s + 1], cfg.atr_n)[-1]
        sl = l[k] - cfg.buffer_atr * atr if d == 1 else h[k] + cfg.buffer_atr * atr
        if not np.isclose(sl, op.sl):
            fallos["sl"] += 1
        if not np.isclose(op.tp, op.entrada + d * cfg.tp_r * abs(op.entrada - op.sl)):
            fallos["tp"] += 1
    textos = {
        "ema": "EMA 50 y dirección 4H recalculadas solo con velas 4H cerradas (en el retroceso y en la señal)",
        "retroceso": "Retroceso válido, vigente (sin otro retroceso ni señal antes) y dentro de las 5 velas",
        "senal": "Señal: cierre 1H más allá del máximo/mínimo de la vela anterior",
        "entrada": "Entrada: apertura de la vela 1H siguiente a la señal",
        "sl": "SL: extremo del retroceso ± 0,10 × ATR(14) calculado hasta el cierre de la señal",
        "tp": "TP = entrada ± 2R con la entrada real",
    }
    res = [(t, "OK" if fallos[k] == 0 else "FALLO", f"{len(ops)} operaciones; fallos: {fallos[k]}")
           for k, t in textos.items()]
    sabados = [pd.Timestamp(x, tz="UTC") for x in ("2016-06-11", "2017-09-16", "2019-01-12", "2020-05-16",
                                                    "2021-08-14", "2022-10-15")]
    probs = comprobar(lambda v: g.senales(v, cfg), m1, sabados)
    res.append(("Truncamiento global (6 cortes en sábado): entradas anteriores idénticas",
                "OK" if not probs else "FALLO", "; ".join(probs) or "sin diferencias"))
    return res


def carpeta() -> Path:
    out, k = RAIZ / "reports" / g.VERSION, 2
    while out.exists():
        out, k = RAIZ / "reports" / f"{g.VERSION}_v{k}", k + 1
    return out


def ejecutar():
    dev, oos = periodos()
    base = g.Config()
    prep = g.preparar(dev, base)
    anios_dev = anios(dev)
    salida = carpeta()
    salida.mkdir(parents=True)

    ops_b, sen_b = g.backtest(dev, base, prep)
    audit = auditoria(dev, base, prep, ops_b)
    tabla_audit = md(pd.DataFrame(audit, columns=["punto", "resultado", "detalle"]))
    if any(r[1] == "FALLO" for r in audit):
        (salida / "diagnostics.md").write_text("# LOOK-AHEAD DETECTADO — BACKTEST DETENIDO\n\n" + tabla_audit)
        print("LOOK-AHEAD: detenido")
        sys.exit(1)

    resumen, trades, anual, lados, curvas = [], [], [], [], {}
    for esc, costes in ESCENARIOS.items():
        cfg = base.con(costes=costes)
        ops, _ = g.backtest(dev, cfg, prep)
        m = metricas(ops, cfg.saldo_inicial)
        resumen.append({"scenario": esc, "trades_per_year": round(m["trades"] / anios_dev, 1), **m})
        curvas[esc] = ops
        o = ops.assign(scenario=esc, anio=pd.DatetimeIndex(ops.t_entrada).year)
        trades.append(o)
        anual.append(agrupar(o, "anio", "year", cfg.saldo_inicial).assign(scenario=esc))
        lados.append(agrupar(o, "lado", "side", cfg.saldo_inicial).assign(scenario=esc))
    resumen = pd.DataFrame(resumen)
    b = resumen.set_index("scenario").loc["B"]
    pasa = b.trades >= MUESTRA_MIN and b.profit_factor > 1 and b.expectancy_R > 0 and b.t_stat_R >= 2

    sens = []
    for ema in (20, 50, 100):
        for tp in (1.5, 2.0, 2.5):
            for esc, costes in ESCENARIOS.items():
                cfg = base.con(ema=ema, tp_r=tp, costes=costes)
                m = metricas(g.backtest(dev, cfg, prep)[0], cfg.saldo_inicial)
                sens.append({"ema": ema, "tp_r": tp, "scenario": esc,
                             "official": ema == 50 and tp == 2.0, **{k: m.get(k) for k in
                             ["trades", "win_rate_%", "profit_factor", "expectancy_R", "expectancy_R_gross",
                              "t_stat_R", "net_$", "max_dd_%", "sample_flag"]}})
    sens = pd.DataFrame(sens)

    oos_txt = "NO EJECUTADO: el desarrollo no cumple los criterios registrados."
    if pasa:
        ops_o, _ = g.backtest(oos, base)
        pd.DataFrame([{"scenario": "B", **metricas(ops_o, base.saldo_inicial)}]).to_csv(salida / "oos_summary.csv",
                                                                                         index=False)
        oos_txt = "Ejecutado: ver oos_summary.csv"

    cols = ["scenario", "t_senal", "t_entrada", "t_salida", "lado", "entrada", "sl", "tp", "salida", "resultado", "r",
            "r_bruto", "neto_usd", "bruto_usd", "costes_usd", "onzas", "riesgo_pts", "riesgo_usd", "saldo_antes",
            "duracion_h", "mae_r", "mfe_r", "t_retroceso", "atr_1h", "cruza_roll", "entrada_real", "sl_real", "tp_real"]
    pd.concat(trades)[cols].to_csv(salida / "trades.csv", index=False)
    resumen.to_csv(salida / "summary.csv", index=False)
    pd.concat(anual).to_csv(salida / "yearly.csv", index=False)
    pd.concat(lados).to_csv(salida / "long_short.csv", index=False)
    sens.to_csv(salida / "sensitivity.csv", index=False)
    sen_b.to_csv(salida / "signals.csv", index=False)
    (salida / "signals.txt").write_text("\n\n".join(g.alerta(op) for _, op in ops_b.iterrows()) + "\n")
    graficos(curvas, salida, base.saldo_inicial, g.VERSION)
    (salida / "diagnostics.md").write_text("\n".join([
        f"# Diagnóstico: {g.VERSION} (desarrollo, {anios_dev:.2f} años)", "", "## Auditoría de look-ahead", "",
        tabla_audit, "", "## Señales (escenario B)", "",
        md(sen_b.estado.value_counts().rename_axis("estado").reset_index(name="n")), "",
        "## Fuera de muestra", "", oos_txt, ""]))
    print("Informe en", salida, "| criterios de desarrollo:", "CUMPLE" if pasa else "NO CUMPLE")


if __name__ == "__main__":
    ejecutar()
