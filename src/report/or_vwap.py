"""Backtest de DESARROLLO de OR_VWAP_v1.0 (MNQ): 3 variantes del tope x 3 escenarios de costes.

Reglas: edges/mnq_or_vwap.md (no se cambian aquí). El fuera de muestra NO se carga: los datos se cortan antes
del 22-mar-2023 y ninguna vela posterior entra en la estrategia.

Uso: python -m src.report.or_vwap
Salida: reports/OR_VWAP_v1.0/ (si ya existe, se crea una carpeta nueva _v2, _v3...; nunca se sobrescribe).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.datos import excluidos, inicio_fuera_de_muestra, velas_1m
from src.engine.costes import Costes
from src.engine.lookahead import comprobar
from src.horas import NUEVA_YORK, ROMA, hora_local_a_utc
from src.metrics.metricas import racha
from src.risk import position_sizing
from src.strategies import mnq_or_vwap as est

RAIZ = Path(__file__).resolve().parent.parent.parent
DESDE = pd.Timestamp("2015-01-01")
MUESTRA_MIN, GRUPO_MIN = 100, 30

VARIANTES = {
    "REL_0.45PCT": dict(tope_puntos=None, tope_pct=0.0045),     # OFICIAL
    "FIXED_40PTS": dict(tope_puntos=40.0, tope_pct=None),       # control
    "NO_CAP": dict(tope_puntos=None, tope_pct=None),            # control
}
ESCENARIOS = {
    0: Costes(comision_lado=0.0, ticks_normal=0, ticks_apertura=0),
    1: Costes(comision_lado=1.0, ticks_normal=1, ticks_apertura=1),
    2: Costes(comision_lado=1.0, ticks_normal=2, ticks_apertura=2),
}
ESTADOS = {  # nombres del informe
    "operada": "TRADED", "sin_senal": "NO_SIGNAL", "rango_incompleto": "OR_INCOMPLETE",
    "riesgo_mayor_que_tope": "RISK_ABOVE_CAP", "cero_contratos": "POSITION_SIZE_BELOW_MINIMUM",
    "entrada_mas_alla_del_stop": "ENTRY_BEYOND_STOP", "sin_vela_de_entrada": "NO_ENTRY_BAR",
}


# ------------------------------------------------------------------------------------------ datos
def datos_desarrollo() -> pd.DataFrame:
    m1 = velas_1m("NQ")
    corte = pd.Timestamp(inicio_fuera_de_muestra("NQ")).tz_localize("UTC")
    return m1[(m1.index >= DESDE.tz_localize("UTC")) & (m1.index < corte)]


def correr(m1, variante, escenario):
    cfg = est.Config(**VARIANTES[variante], costes=ESCENARIOS[escenario])
    registro = []
    ops, estados = est.backtest(m1, cfg, excluir=excluidos("NQ"), registro=registro)
    return cfg, ops, estados, pd.DataFrame(registro)


# ---------------------------------------------------------------------------------------- métricas
def metricas(ops: pd.DataFrame, saldo0: float = 50_000.0) -> dict:
    n = len(ops)
    if n == 0:
        return {"trades": 0, "sample_flag": "INSUFFICIENT_SAMPLE"}
    neto, r = ops.neto, ops.r
    gan, per = neto[neto > 0], neto[neto < 0]
    eq = saldo0 + neto.cumsum()
    pico = np.maximum.accumulate(np.r_[saldo0, eq.to_numpy()])[1:]
    dd = eq.to_numpy() - pico
    i_dd = int(dd.argmin())
    eq_r = r.cumsum().to_numpy()
    dd_r = eq_r - np.maximum.accumulate(np.r_[0.0, eq_r])[1:]
    pf = gan.sum() / -per.sum() if per.sum() < 0 else np.inf
    t = r.mean() / r.std() * np.sqrt(n) if n > 1 and r.std() > 0 else np.nan
    return {
        "trades": n,
        "winners": int((neto > 0).sum()), "losers": int((neto < 0).sum()), "breakeven": int((neto == 0).sum()),
        "win_rate_%": round((neto > 0).mean() * 100, 1),
        "gross_profit_$": round(gan.sum(), 0), "gross_loss_$": round(per.sum(), 0), "net_$": round(neto.sum(), 0),
        "profit_factor": round(pf, 3),
        "expectancy_$": round(neto.mean(), 2), "expectancy_R": round(r.mean(), 4),
        "avg_winner_$": round(gan.mean(), 2) if len(gan) else 0.0,
        "avg_loser_$": round(per.mean(), 2) if len(per) else 0.0,
        "avg_winner_R": round(r[neto > 0].mean(), 3) if len(gan) else 0.0,
        "avg_loser_R": round(r[neto < 0].mean(), 3) if len(per) else 0.0,
        "payoff": round(gan.mean() / -per.mean(), 3) if len(gan) and len(per) else np.nan,
        "max_dd_$": round(dd.min(), 0), "max_dd_%": round(dd[i_dd] / pico[i_dd] * 100, 2), "max_dd_R": round(dd_r.min(), 2),
        "max_consec_losses": racha(neto < 0), "max_consec_wins": racha(neto > 0),
        "avg_risk_$": round(ops.riesgo_usd.mean(), 2), "max_risk_$": round(ops.riesgo_usd.max(), 2),
        "avg_contracts": round(ops.contratos.mean(), 2), "max_contracts": int(ops.contratos.max()),
        "largest_win_$": round(neto.max(), 2), "largest_loss_$": round(neto.min(), 2),
        "t_stat_R": round(t, 2), "median_R": round(r.median(), 3), "std_R": round(r.std(), 3),
        "pct_exit_target": round((ops.motivo == "objetivo").mean() * 100, 1),
        "pct_exit_stop": round((ops.motivo == "stop").mean() * 100, 1),
        "pct_exit_time": round((ops.motivo == "tiempo").mean() * 100, 1),
        "final_balance_$": round(eq.iloc[-1], 0),
        "sample_flag": "OK" if n >= MUESTRA_MIN else "INSUFFICIENT_SAMPLE",
    }


def enriquecer(ops: pd.DataFrame) -> pd.DataFrame:
    o = ops.copy()
    ny = pd.DatetimeIndex(o.t_entrada).tz_convert(NUEVA_YORK)
    o["fecha_ny"] = ny.date
    o["anio"] = ny.year
    o["hora_entrada_ny"] = ny.hour
    o["t_entrada_ny"] = ny.strftime("%Y-%m-%d %H:%M")
    o["t_entrada_roma"] = pd.DatetimeIndex(o.t_entrada).tz_convert(ROMA).strftime("%Y-%m-%d %H:%M")
    o["lado"] = o.direccion.map({1: "LONG", -1: "SHORT"})
    o["or_range_pts"] = o.or_high - o.or_low
    o["or_range_pct"] = o.or_range_pts / o.entrada * 100
    o["r_pts"] = (o.entrada - o.stop).abs()
    o["r_pct"] = o.r_pts / o.entrada * 100
    return o


CORTOS = ["trades", "win_rate_%", "net_$", "profit_factor", "expectancy_$", "expectancy_R", "median_R",
          "t_stat_R", "max_dd_$"]


def agrupar(o: pd.DataFrame, clave, etiqueta: str) -> pd.DataFrame:
    filas = []
    for k, g in o.groupby(clave, observed=True):
        m = metricas(g.reset_index(drop=True))
        fila = {etiqueta: k, **{c: m.get(c) for c in CORTOS}}
        fila["sample_flag"] = "OK" if m["trades"] >= GRUPO_MIN else "INSUFFICIENT_SAMPLE"
        filas.append(fila)
    return pd.DataFrame(filas)


CUBOS_PCT = [0, 0.20, 0.30, 0.45, 0.60, 0.80, 1.00, np.inf]


def robustez(o: pd.DataFrame) -> dict:
    neto, r = o.neto, o.r
    orden = neto.sort_values(ascending=False)
    orden_r = r.sort_values(ascending=False)
    anual = o.groupby("anio").neto.sum()
    mensual = o.groupby(pd.DatetimeIndex(o.t_entrada).tz_convert(NUEVA_YORK).strftime("%Y-%m")).neto.sum()
    lados = o.groupby("lado").agg(net=("neto", "sum"), expR=("r", "mean"), n=("r", "size"))
    top10 = orden.iloc[: max(1, len(o) // 10)].sum()
    # Rachas (Wald-Wolfowitz) sobre ganadora/perdedora: z muy negativo = resultados agrupados (clustering)
    w = (neto > 0).to_numpy()
    n1, n2 = w.sum(), (~w).sum()
    rachas_obs = 1 + int((w[1:] != w[:-1]).sum())
    mu = 2 * n1 * n2 / (n1 + n2) + 1
    var = 2 * n1 * n2 * (2 * n1 * n2 - n1 - n2) / ((n1 + n2) ** 2 * (n1 + n2 - 1))
    ac1 = pd.Series(r.to_numpy()).autocorr(1)
    return {
        "net_$": round(neto.sum(), 0), "sum_R": round(r.sum(), 2),
        "net_without_top1_$": round(neto.sum() - orden.iloc[:1].sum(), 0),
        "net_without_top5_$": round(neto.sum() - orden.iloc[:5].sum(), 0),
        "sumR_without_top1": round(r.sum() - orden_r.iloc[:1].sum(), 2),
        "sumR_without_top5": round(r.sum() - orden_r.iloc[:5].sum(), 2),
        "expR_without_top5": round(orden_r.iloc[5:].mean(), 4),
        "top10pct_trades_share_of_gross_profit_%": round(top10 / neto[neto > 0].sum() * 100, 1),
        "years_positive": f"{int((anual > 0).sum())}/{len(anual)}",
        "best_year": int(anual.idxmax()), "best_year_net_$": round(anual.max(), 0),
        "net_without_best_year_$": round(neto.sum() - anual.max(), 0),
        "best_month": mensual.idxmax(), "best_month_net_$": round(mensual.max(), 0),
        "net_without_best_month_$": round(neto.sum() - mensual.max(), 0),
        "long_trades": int(lados.n.get("LONG", 0)), "long_net_$": round(lados.net.get("LONG", 0), 0),
        "long_expR": round(lados.expR.get("LONG", np.nan), 4),
        "short_trades": int(lados.n.get("SHORT", 0)), "short_net_$": round(lados.net.get("SHORT", 0), 0),
        "short_expR": round(lados.expR.get("SHORT", np.nan), 4),
        "runs_test_z": round((rachas_obs - mu) / np.sqrt(var), 2) if var > 0 else np.nan,
        "autocorr_R_lag1": round(ac1, 3),
    }


# -------------------------------------------------------------------------------------- look-ahead
def auditoria(m1: pd.DataFrame, cfg, ops: pd.DataFrame) -> list[tuple[str, str, str]]:
    """Comprobaciones de look-ahead y de coherencia. Devuelve (punto, resultado, detalle)."""
    res = []
    ny = m1.index.tz_convert(NUEVA_YORK)
    rth = m1[(ny.hour * 60 + ny.minute >= 570) & (ny.hour < 16)]
    por_dia = dict(tuple(rth.groupby(rth.index.tz_convert(NUEVA_YORK).date)))
    corte = pd.Timestamp(inicio_fuera_de_muestra("NQ")).tz_localize("UTC")

    res.append(("Datos: nada del fuera de muestra", "OK" if m1.index.max() < corte else "FALLO",
                f"última vela cargada {m1.index.max()} < {corte}"))

    fallos = {k: 0 for k in ("or", "vwap", "senal", "entrada", "stop_obj", "salida", "sizing", "saldo")}
    ejemplos = {}
    saldo = cfg.saldo_inicial
    cortas = 0
    for _, op in ops.iterrows():
        f = pd.Timestamp(op.t_entrada).tz_convert(NUEVA_YORK).date()
        dia = por_dia[f]
        t_or0, t_or1 = hora_local_a_utc(f, "09:30", NUEVA_YORK), hora_local_a_utc(f, "09:45", NUEVA_YORK)
        rango = dia[(dia.index >= t_or0) & (dia.index < t_or1)]
        # OR: solo velas 09:30-09:44 y todas anteriores a la señal
        if not (rango.high.max() == op.or_high and rango.low.min() == op.or_low and rango.index.max() < op.t_senal):
            fallos["or"] += 1; ejemplos.setdefault("or", f)
        # Señal y VWAP recalculados SOLO con velas hasta la de señal (incluida): deben coincidir
        hasta = dia[dia.index <= op.t_senal]
        s = est.senal(hasta, f, cfg)
        vw_trunc = est.vwap_sesion(hasta).iloc[-1]
        if not (s.get("t_senal") == op.t_senal and s.get("direccion") == op.direccion):
            fallos["senal"] += 1; ejemplos.setdefault("senal", f)
        if not np.isclose(vw_trunc, op.vwap_senal):
            fallos["vwap"] += 1; ejemplos.setdefault("vwap", f)
        # Entrada: apertura de la vela inmediatamente siguiente a la señal, con deslizamiento en contra
        j = dia.index.get_loc(op.t_senal)
        esperado = dia.open.iloc[j + 1] + op.direccion * cfg.costes.ticks(dia.index[j + 1]) * cfg.tick
        if not (dia.index[j + 1] == op.t_entrada and np.isclose(op.entrada, esperado)):
            fallos["entrada"] += 1; ejemplos.setdefault("entrada", f)
        # Stop y objetivo fijados con información disponible en la entrada
        stop = op.or_low if op.direccion == 1 else op.or_high
        r = (op.entrada - stop) * op.direccion
        if not (op.stop == stop and np.isclose(op.objetivo, op.entrada + op.direccion * 2 * r)):
            fallos["stop_obj"] += 1; ejemplos.setdefault("stop_obj", f)
        # Salida: ninguna vela anterior a la de salida tocó stop u objetivo; la salida es la primera que lo hace
        tramo = dia[(dia.index >= op.t_entrada) & (dia.index < op.t_salida)]
        d = op.direccion
        toca = ((tramo.low <= stop) | (tramo.high >= op.objetivo)) if d == 1 else \
               ((tramo.high >= stop) | (tramo.low <= op.objetivo))
        v = dia.loc[op.t_salida]
        t_lim = hora_local_a_utc(f, "15:55", NUEVA_YORK)
        ok = not toca.any()
        if op.motivo == "objetivo":
            ok &= op.salida == op.objetivo and (v.high >= op.objetivo if d == 1 else v.low <= op.objetivo)
            ok &= not (v.low <= stop if d == 1 else v.high >= stop)          # misma vela = pérdida
        elif op.motivo == "stop":
            ok &= bool(v.low <= stop if d == 1 else v.high >= stop)
        elif op.motivo == "tiempo":
            ok &= op.t_salida >= t_lim and tramo.index.max() < t_lim if len(tramo) else op.t_salida >= t_lim
        elif op.motivo == "fin_de_datos":
            # Sesión recortada (festivo de EE. UU., CME cierra a las 13:00 NY): cierre en la última vela del día,
            # hora conocida de antemano. Válido solo si es la última vela y la sesión acaba antes de las 15:55.
            ok &= op.t_salida == dia.index[-1] and dia.index[-1] < t_lim
            cortas += 1
        else:
            ok = False
        if not ok:
            fallos["salida"] += 1; ejemplos.setdefault("salida", f)
        # Tamaño: position_sizing con el saldo ANTERIOR a la operación
        if not np.isclose(op.saldo_antes, saldo):
            fallos["saldo"] += 1; ejemplos.setdefault("saldo", f)
        if op.contratos != position_sizing.contratos(op.saldo_antes, cfg.riesgo_pct, r, cfg.valor_punto):
            fallos["sizing"] += 1; ejemplos.setdefault("sizing", f)
        saldo += op.neto

    nombres = {
        "or": "OR: máximo/mínimo de 09:30-09:44 NY, cerrado antes de la señal",
        "vwap": "VWAP: recalculado solo con velas hasta la señal = VWAP usado",
        "senal": "Señal: idéntica con los datos cortados en la vela de señal",
        "entrada": "Entrada: apertura de la vela siguiente + deslizamiento",
        "stop_obj": "Stop (extremo opuesto del OR) y objetivo (2R) fijados en la entrada",
        "salida": "Salida: primera vela que toca stop/objetivo; misma vela = pérdida; tiempo en 15:55",
        "saldo": "Saldo usado para el tamaño = saldo antes de la operación",
        "sizing": "Tamaño = position_sizing.contratos(saldo, 0,5 %, R, 2 $)",
    }
    for k, txt in nombres.items():
        res.append((txt, "OK" if fallos[k] == 0 else "FALLO",
                    f"{len(ops)} operaciones revisadas; fallos: {fallos[k]}"
                    + (f" (primer caso {ejemplos[k]})" if k in ejemplos else "")))

    res.append(("Sesiones recortadas (cierre a las 13:00 NY): salida en la última vela", "AVISO" if cortas else "OK",
                f"{cortas} operaciones; no es look-ahead (horario publicado de antemano), pero las reglas no lo prevén"))
    # Truncamiento global: las señales anteriores a cada corte no cambian al añadir datos posteriores
    sabados = [pd.Timestamp(f"{a}-{m}", tz="UTC") for a, m in
               [(2016, "04-09"), (2017, "07-15"), (2018, "10-13"), (2020, "03-14"), (2021, "06-12"), (2022, "11-12")]]
    problemas = comprobar(lambda v: est.senales(v, cfg), m1, sabados)
    res.append(("Truncamiento global (6 cortes en sábado, 2016-2022)", "OK" if not problemas else "FALLO",
                "; ".join(problemas) or "señales anteriores a cada corte idénticas"))
    res.append(("Estado de Apex", "N/A",
                "este backtest no usa estado de Apex (la simulación de Apex es una fase posterior)"))
    return res


# ------------------------------------------------------------------------------------------ salida
def carpeta_salida() -> Path:
    base = RAIZ / "reports" / est.VERSION
    if not base.exists():
        return base
    k = 2
    while (RAIZ / "reports" / f"{est.VERSION}_v{k}").exists():
        k += 1
    return RAIZ / "reports" / f"{est.VERSION}_v{k}"


def md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def ejecutar():
    m1 = datos_desarrollo()
    salida = carpeta_salida()

    # 1) Auditoría de look-ahead ANTES de mirar resultados (variante oficial, escenario 1)
    cfg, ops, _, _ = correr(m1, "REL_0.45PCT", 1)
    audit = auditoria(m1, cfg, ops)
    salida.mkdir(parents=True)
    if any(r[1] == "FALLO" for r in audit):
        (salida / "diagnostics.md").write_text("# LOOK-AHEAD DETECTADO — BACKTEST DETENIDO\n\n"
                                               + md(pd.DataFrame(audit, columns=["punto", "resultado", "detalle"])))
        print("LOOK-AHEAD: backtest detenido. Ver", salida / "diagnostics.md")
        sys.exit(1)

    # 2) Las 9 combinaciones
    resumen, trades, anual, horas, lados, rangos, robs, dias = [], [], [], [], [], [], [], []
    for var in VARIANTES:
        for esc in ESCENARIOS:
            cfg, ops, estados, reg = correr(m1, var, esc)
            o = enriquecer(ops)
            clave = {"variant": var, "scenario": esc}
            est_nom = {ESTADOS.get(k, k): v for k, v in estados.items()}
            resumen.append({**clave, **metricas(ops), **{f"days_{k}": v for k, v in sorted(est_nom.items())}})
            trades.append(o.assign(**clave))
            a = agrupar(o, "anio", "year")
            reg["anio"] = pd.to_datetime(reg.fecha).dt.year
            cuentas = reg.groupby("anio").estado.value_counts().unstack(fill_value=0).rename(columns=ESTADOS)
            cuentas["days_evaluated"] = cuentas.sum(axis=1)
            anual.append(a.merge(cuentas, left_on="year", right_index=True, how="outer").assign(**clave))
            horas.append(agrupar(o, "hora_entrada_ny", "entry_hour_NY").assign(**clave))
            lados.append(agrupar(o, "lado", "side").assign(**clave))
            o["bucket"] = pd.cut(o.or_range_pct, CUBOS_PCT, right=False).astype(str)
            rangos.append(agrupar(o, "bucket", "or_range_pct_bucket").assign(**clave))
            robs.append({**clave, **robustez(o)})
            dias.append(reg.assign(**clave))

    resumen = pd.DataFrame(resumen)
    front = ["variant", "scenario"]
    reorden = lambda df: df[front + [c for c in df.columns if c not in front]]  # noqa: E731
    trades = pd.concat(trades)
    cols_t = ["variant", "scenario", "fecha_ny", "lado", "contratos", "t_entrada_ny", "t_entrada_roma", "entrada", "stop",
              "objetivo", "t_salida", "salida", "motivo", "or_high", "or_low", "or_range_pts", "or_range_pct", "r_pts",
              "r_pct", "vwap_senal", "riesgo_usd", "saldo_antes", "bruto", "comision", "neto", "r", "t_senal",
              "t_entrada"]
    anual, horas, lados, rangos = (reorden(pd.concat(x)) for x in (anual, horas, lados, rangos))
    robs = pd.DataFrame(robs)
    # Deterioro con costes, respecto al escenario 0 y al 1
    for var in VARIANTES:
        base = resumen[(resumen.variant == var)].set_index("scenario")
        for esc in ESCENARIOS:
            m = (robs.variant == var) & (robs.scenario == esc)
            robs.loc[m, "expR_change_vs_scn0"] = round(base.expectancy_R[esc] - base.expectancy_R[0], 4)
            robs.loc[m, "net_change_vs_scn1_$"] = round(base["net_$"][esc] - base["net_$"][1], 0)
            robs.loc[m, "PF_change_vs_scn1"] = round(base.profit_factor[esc] - base.profit_factor[1], 3)

    resumen.to_csv(salida / "summary.csv", index=False)
    trades[cols_t].to_csv(salida / "trades.csv", index=False)
    anual.to_csv(salida / "yearly.csv", index=False)
    horas.to_csv(salida / "hourly.csv", index=False)
    lados.to_csv(salida / "long_short.csv", index=False)
    rangos.to_csv(salida / "range_analysis.csv", index=False)
    robs.to_csv(salida / "robustness.csv", index=False)

    # Distribución de R (variante oficial) para diagnostics
    of = trades[(trades.variant == "REL_0.45PCT")]
    cubos_r = [-np.inf, -1.25, -1.0, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 1.0, 1.5, 1.9, np.inf]
    dist = pd.concat({f"escenario {e}": pd.cut(g.r, cubos_r, right=False).value_counts(sort=False)
                      for e, g in of.groupby("scenario")}, axis=1)
    dist.index = dist.index.astype(str)
    pct = of.groupby("scenario").r.describe(percentiles=[.05, .25, .5, .75, .95]).round(3)

    diag = ["# Diagnóstico — OR_VWAP_v1.0 (desarrollo 2015-01-01 → 2023-03-21)", "",
            "## Auditoría de look-ahead (variante oficial REL_0.45PCT, escenario 1)", "",
            md(pd.DataFrame(audit, columns=["punto", "resultado", "detalle"])), "",
            "## Estados por día (todas las combinaciones)", "",
            md(resumen[["variant", "scenario"] + [c for c in resumen.columns if c.startswith("days_")]].fillna(0)), "",
            "## Distribución de R (variante oficial)", "", dist.to_markdown(), "", pct.to_markdown(), ""]
    (salida / "diagnostics.md").write_text("\n".join(diag))
    print("Informe en", salida)
    return salida


if __name__ == "__main__":
    ejecutar()
