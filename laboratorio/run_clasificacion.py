"""Aplica mecánicamente los criterios de config/PROTOCOLO.yaml y genera reports/MATRIZ_ESTRATEGIAS.csv.

Lee los últimos experimentos con prueba final, robustez, Topstep y swing complementario.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from backtests.swing import SwingCost, simulate
from data.loaders import etf_daily
from run_sistema_b import LAST, cost_scenarios
from strategies.swing import SWING
from validation.metrics import block_bootstrap_mean

LAB = Path(__file__).resolve().parent
EXP = LAB / "experiments"


def last(pattern):
    return sorted(EXP.glob(pattern))[-1]


A_FROZEN = {  # nombre en resultados.csv → (clave robustez, nombre Topstep, descripción)
    "A1 ORB immediate principal + filtro vol": ("A1_immediate", "A1 ORB immediate + vol (2R 11:30)", "ORB 5m ruptura inmediata, stop rango, 2R, 11:30, filtro vol."),
    "A1 ORB close principal + filtro vol": ("A1_close", "A1 ORB close + vol (2R 11:30)", "ORB 5m cierre confirmado, stop rango, 2R, 11:30, filtro vol."),
    "A1 ORB retest stop=rango salida=2R_1130": ("A1_retest", "A1 ORB retest (2R 11:30)", "ORB 5m ruptura + retesteo, stop vela de retesteo, 2R, 11:30"),
    "A1 ORB immediate stop=rango salida=eod": ("A1_immediate_eod", "A1 ORB immediate salida cierre", "ORB 5m ruptura inmediata, stop rango, sin objetivo, salida 15:55"),
    "A2 Tendencia + filtro vwap": ("A2_tendencia", "A2 Tendencia + VWAP", "Continuación intradía (EMA50 diaria + retroceso 5m + VWAP), 2R, 15:50"),
    "A3 Zona de ruido (reglas originales)": ("A3_ruido", "A3 Zona de ruido", "Bandas de ruido NY (reglas originales), decisiones cada 30 min"),
}


def classify(v):
    if v["esp_val"] <= 0 or v["esp_test"] <= 0:
        return "RECHAZADA"
    cand = (v["pf_val"] > 1.10 and v["pf_test"] > 1.10 and v["ic_bajo"] > 0 and v["mejor_año_pct"] <= 0.5
            and v["top10_pct"] < 0.5 and v.get("vecinos_pos", 1.0) >= 0.7 and v["n_oos"] >= v["n_min"])
    if not cand:
        return "INCONCLUSA"
    val = (v["pf_oos"] > 1.20 and v["esp_val_alto"] > 0 and v["esp_test_alto"] > 0 and v.get("extra_ok", False))
    return "VALIDADA PARA SIMULACIÓN" if val else "CANDIDATA"


def system_a():
    ra = pd.read_csv(last("*_sistema_a_con_prueba") / "resultados.csv")
    rob = pd.read_csv(last("*_robustez_a") / "robustez.csv")
    ts = pd.read_csv(last("*_topstep_combine") / "topstep_combine.csv")
    ops_dir = last("*_sistema_a_con_prueba")
    rows = []
    for name, (rk, tsn, desc) in A_FROZEN.items():
        g = ra[ra.estrategia == name].set_index(["coste", "periodo"])
        slug = "".join(ch if ch.isalnum() else "_" for ch in name).strip("_")[:80]
        t = pd.read_csv(ops_dir / f"ops_{slug}.csv.gz", parse_dates=["date"])
        o = t[t.date >= "2022-01-01"]
        p = o.pnl
        net = p.sum()
        lo, hi = block_bootstrap_mean(p.to_numpy())
        by_year = o.groupby(o.date.dt.year).pnl.sum()
        per = rob[(rob.prueba == "parametros") & (rob.estrategia == rk)]
        vec = ((per.esp_desarrollo > 0) & (per.esp_validacion > 0)).mean() if len(per) else np.nan
        sl = rob[(rob.prueba == "costes") & (rob.estrategia == rk) & (rob.cambio == "+4 ticks/lado, fijo x2.0")]
        t2 = ts[(ts.estrategia == tsn) & ts.ventanas.str.startswith("2022")]
        best = t2.sort_values("p_aprobar").iloc[-1]
        v = dict(esp_val=g.loc[("base", "validacion"), "esperanza"], esp_test=g.loc[("base", "prueba"), "esperanza"],
                 pf_val=g.loc[("base", "validacion"), "pf"], pf_test=g.loc[("base", "prueba"), "pf"],
                 esp_val_alto=g.loc[("alto", "validacion"), "esperanza"], esp_test_alto=g.loc[("alto", "prueba"), "esperanza"],
                 ic_bajo=lo, ic_alto=hi, n_oos=len(o), n_min=100, pf_oos=p[p > 0].sum() / -p[p < 0].sum(),
                 top10_pct=p.nlargest(10).sum() / net if net > 0 else np.nan,
                 mejor_año_pct=by_year.max() / net if net > 0 else np.nan, vecinos_pos=vec,
                 extra_ok=bool(best.p_aprobar > best.p_suspender))
        rows.append(dict(
            sistema="A Topstep intradía", estrategia=name, descripcion=desc,
            datos="NQ.c.0 1 min Databento (precios de NQ, valor MNQ 2 $/punto)",
            periodos="desarrollo 2018-21 · validación 2022-24 · prueba 2025-26/10",
            n_desarrollo=g.loc[("base", "desarrollo"), "n"], n_validacion=g.loc[("base", "validacion"), "n"],
            n_prueba=g.loc[("base", "prueba"), "n"],
            neto_usd_año_desarrollo=g.loc[("base", "desarrollo"), "neto_año"],
            neto_usd_año_validacion=g.loc[("base", "validacion"), "neto_año"],
            neto_usd_año_prueba=g.loc[("base", "prueba"), "neto_año"],
            pf_desarrollo=g.loc[("base", "desarrollo"), "pf"], pf_validacion=v["pf_val"], pf_prueba=v["pf_test"],
            esperanza_usd_validacion=v["esp_val"], esperanza_usd_prueba=v["esp_test"],
            ic90_esperanza_oos=f"[{lo:.2f}, {hi:.2f}]",
            dd_max_usd_prueba=g.loc[("base", "prueba"), "dd_max"],
            coste="base: 2 ticks/lado + 0,75 $/lado (provisional)",
            esperanza_alto_val_prueba=f"{v['esp_val_alto']:.2f} / {v['esp_test_alto']:.2f}",
            esperanza_mas4ticks_fijo_x2_val=float(sl.esp_validacion.iloc[0]) if len(sl) else np.nan,
            vecinos_positivos_dev_y_val=vec, top10_ops_pct_neto_oos=v["top10_pct"], mejor_año_pct_neto_oos=v["mejor_año_pct"],
            topstep_mejor_tamaño=best.tamaño, topstep_p_aprobar=best.p_aprobar, topstep_p_suspender=best.p_suspender,
            clasificacion=classify(v)))
    return rows


def system_b():
    rb = pd.read_csv(last("*_sistema_b_con_prueba") / "resultados.csv")
    d = etf_daily("QQQ", adjusted=True, last=LAST)
    cost = cost_scenarios()["capital 10k"]
    rows = []
    bench = rb[rb.estrategia.str.startswith("Benchmark")].set_index("periodo")
    for name in ("B1 Ruptura 20 sesiones", "B3 RSI(2) Connors (reversión)", "B4 Retroceso a EMA20 en tendencia",
                 "B2 Ruptura 20 + EMA200"):
        g = rb[(rb.estrategia == name) & (rb.ejecucion == "next_open")].set_index(["coste", "periodo"])
        fn, p = SWING[name]
        t = simulate(d, fn(d, **p), cost, "next_open")
        o = t[t.entrada >= "2021-01-01"]
        r = o["ret"]
        lo, hi = block_bootstrap_mean(r.to_numpy(), block=3)
        by_year = o.groupby(o.entrada.dt.year)["ret"].sum()
        base = "capital 10k"
        mar_ok = all(g.loc[(base, k), "mar"] > bench.loc[k, "mar"] for k in ("validacion", "prueba"))
        v = dict(esp_val=g.loc[(base, "validacion"), "esperanza_pct"], esp_test=g.loc[(base, "prueba"), "esperanza_pct"],
                 pf_val=g.loc[(base, "validacion"), "pf"], pf_test=g.loc[(base, "prueba"), "pf"],
                 esp_val_alto=g.loc[("capital 10k coste x2", "validacion"), "esperanza_pct"],
                 esp_test_alto=g.loc[("capital 10k coste x2", "prueba"), "esperanza_pct"],
                 ic_bajo=lo, n_oos=len(o), n_min=30, pf_oos=r[r > 0].sum() / -r[r < 0].sum(),
                 top10_pct=r.nlargest(10).sum() / r.sum() if r.sum() > 0 else np.nan,
                 mejor_año_pct=by_year.max() / r.sum() if r.sum() > 0 else np.nan, extra_ok=mar_ok)
        cl = classify(v)
        if name.startswith("B2"):
            cl = "NO SELECCIONADA (filtro descartado en validación; informativa)"
        rows.append(dict(
            sistema="B swing capital propio", estrategia=name, descripcion=SWING[name][0].__doc__ or "",
            datos="QQQ diario ajustado (Alpaca SIP), proxy del Nasdaq-100; ejecución en la apertura siguiente",
            periodos="desarrollo 2016-20 · validación 2021-23 · prueba 2024-26/10",
            n_desarrollo=g.loc[(base, "desarrollo"), "n"], n_validacion=g.loc[(base, "validacion"), "n"],
            n_prueba=g.loc[(base, "prueba"), "n"],
            cagr_desarrollo=g.loc[(base, "desarrollo"), "cagr"], cagr_validacion=g.loc[(base, "validacion"), "cagr"],
            cagr_prueba=g.loc[(base, "prueba"), "cagr"],
            pf_desarrollo=g.loc[(base, "desarrollo"), "pf"], pf_validacion=v["pf_val"], pf_prueba=v["pf_test"],
            esperanza_pct_validacion=v["esp_val"], esperanza_pct_prueba=v["esp_test"],
            ic90_esperanza_oos=f"[{lo:.4f}, {hi:.4f}]", dd_max_pct_prueba=g.loc[(base, "prueba"), "dd_max_pct"],
            mar_prueba=g.loc[(base, "prueba"), "mar"], mar_benchmark_prueba=bench.loc["prueba", "mar"],
            coste="0,05 %/lado + 3 € por orden, capital 10.000 (provisional)",
            esperanza_coste_doble_val_prueba=f"{v['esp_val_alto']:.4f} / {v['esp_test_alto']:.4f}",
            top10_ops_pct_neto_oos=v["top10_pct"], mejor_año_pct_neto_oos=v["mejor_año_pct"],
            exposicion_prueba=g.loc[(base, "prueba"), "exposicion"],
            pct_ops_1_4_semanas_prueba=g.loc[(base, "prueba"), "pct_en_1_4_semanas"], clasificacion=cl))
    rows.append(dict(sistema="Benchmark", estrategia="Comprar y mantener QQQ (ajustado)", descripcion="pasivo",
                     datos="QQQ diario ajustado", periodos="mismos que B",
                     cagr_desarrollo=bench.loc["desarrollo", "cagr"], cagr_validacion=bench.loc["validacion", "cagr"],
                     cagr_prueba=bench.loc["prueba", "cagr"], dd_max_pct_prueba=bench.loc["prueba", "dd_max_pct"],
                     mar_prueba=bench.loc["prueba", "mar"], clasificacion="REFERENCIA"))
    return rows


def main():
    m = pd.DataFrame(system_a() + system_b())
    out = LAB / "reports" / "MATRIZ_ESTRATEGIAS.csv"
    m.to_csv(out, index=False)
    pd.set_option("display.width", 250, "display.max_columns", 12)
    print(m[["sistema", "estrategia", "clasificacion"]].to_string(index=False))
    print("→", out)


if __name__ == "__main__":
    main()
