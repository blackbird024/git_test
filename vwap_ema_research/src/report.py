"""FINAL_REPORT.md a partir de results/backtest.pkl y results/optimization.pkl (no ejecuta backtests nuevos, salvo
recalcular variables para dibujar ejemplos). Presenta resultados; no elige "la ganadora"."""
from __future__ import annotations

import pickle
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import plotting as pl
from .common import ROOT, Lab, load_config

K = ["trades", "win_rate_%", "avg_win", "avg_loss", "avg_rr", "expectancy_usd", "expectancy_R", "expectancy_R_gross", "t_R",
     "profit_factor", "gross_profit", "gross_loss", "gross_pnl", "costs", "net_pnl", "max_dd", "max_dd_%", "sharpe", "sortino",
     "calmar", "avg_trade", "median_trade", "largest_win", "largest_loss", "max_consec_wins", "max_consec_losses",
     "avg_duration_min", "trades_per_day", "return_per_month_usd", "months_positive_%", "longs", "shorts"]
CORTAS = ["trades", "win_rate_%", "expectancy_R", "expectancy_R_gross", "t_R", "profit_factor", "net_pnl", "max_dd_%", "sharpe"]


def md(df: pd.DataFrame, **k) -> str:
    return df.to_markdown(**k) if df is not None and len(df) else "(sin datos)"


def tabla_periodos(res: dict, claves=CORTAS) -> pd.DataFrame:
    filas = []
    for etq, per in res["periodos"].items():
        for p, (_, m) in per.items():
            filas.append({"configuración": etq, "periodo": p, **{k: m.get(k) for k in claves}})
    return pd.DataFrame(filas)


def robustez(res: dict) -> pd.DataFrame:
    """Lista de comprobación del apartado 21 para la configuración final."""
    per = {p: m for p, (_, m) in res["periodos"]["final"].items()}
    tr = pd.concat([res["periodos"]["final"][p][0].trades for p in ("validation", "test")])
    t_oos = tr.r_net.mean() / tr.r_net.std(ddof=1) * np.sqrt(len(tr)) if len(tr) > 2 else np.nan
    anual = res["desgloses"]["train+validation"].get("año") if res["desgloses"]["train+validation"] else None
    franja = res["desgloses"]["train+validation"].get("franja") if res["desgloses"]["train+validation"] else None
    dev = pd.concat([res["periodos"]["final"][p][0].trades for p in ("train", "validation")])
    mejor_dia = dev.groupby("session").net_pnl.sum().max() if len(dev) else np.nan
    x2 = res["costes_x2"]
    filas = [
        ("expectativa neta > 0 en train", per["train"].get("expectancy_R", -1) > 0, per["train"].get("expectancy_R")),
        ("expectativa neta > 0 en validation", per["validation"].get("expectancy_R", -1) > 0, per["validation"].get("expectancy_R")),
        ("expectativa neta > 0 en test", per["test"].get("expectancy_R", -1) > 0, per["test"].get("expectancy_R")),
        ("t >= 2 fuera de muestra (validation + test)", t_oos >= 2, round(t_oos, 2)),
        ("años positivos (train+validation) >= 60 %", anual is not None and (anual.net_pnl > 0).mean() >= 0.6,
         None if anual is None else f"{(anual.net_pnl > 0).mean() * 100:.0f} %"),
        ("no depende de un solo día (mejor día < 10 % del neto de train+validation)",
         dev.net_pnl.sum() > 0 and mejor_dia < 0.1 * dev.net_pnl.sum(), None if not len(dev) else round(mejor_dia, 0)),
        ("más de una franja con R > 0 (train+validation)", franja is not None and (franja.expectancy_R > 0).sum() > 1,
         None if franja is None else int((franja.expectancy_R > 0).sum())),
        ("se mantiene con costes dobles (test)", x2["test"].get("expectancy_R", -1) > 0, x2["test"].get("expectancy_R")),
        ("degradación validation -> test < 50 % de la expectativa",
         per["validation"].get("expectancy_R", 0) > 0 and per["test"].get("expectancy_R", -1) >= 0.5 * per["validation"]["expectancy_R"],
         f"{per['validation'].get('expectancy_R')} -> {per['test'].get('expectancy_R')}"),
    ]
    return pd.DataFrame(filas, columns=["criterio", "cumple", "valor"])


def construir() -> None:
    cfg = load_config()
    bt = pickle.loads((ROOT / "results" / "backtest.pkl").read_bytes())
    op = pickle.loads((ROOT / "results" / "optimization.pkl").read_bytes())
    P = ROOT / "plots"
    P.mkdir(exist_ok=True)
    L = []
    a = L.append
    n_var = 0
    a("# FINAL REPORT — VWAP + EMAs, velas de 15 minutos\n")
    a(f"*Generado el {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} con `python generate_report.py` a partir de ejecuciones reales "
      "(`run_backtest.py`, `optimize.py`). Presenta resultados; no designa una estrategia ganadora. Ningún resultado histórico "
      "implica rentabilidad futura.*\n")
    # 1-2 Datos y periodos
    a("## 1. Datos utilizados")
    filas = []
    for n, i in bt["datos"].items():
        ic = cfg["instruments"][n]
        filas.append({"instrumento": n, "fuente de precio": ic["price_source"], "fuente de volumen (VWAP)": ic["volume_source"],
                      "timeframe origen": i["timeframe_detectado"], "desde": i["desde"][:10], "hasta": i["hasta"][:10],
                      "filas": i["filas"], "duplicadas": i["duplicadas"], "inválidas": i["invalidas_eliminadas"],
                      "sesiones válidas": i["sesiones_validas"], "sesiones excluidas": i["sesiones_excluidas"],
                      "% minutos presentes en sesión": i["minutos_en_sesion_presentes_%"], "contratos": i["contratos"]})
    a(md(pd.DataFrame(filas), index=False))
    for n, e in bt["faltan"].items():
        a(f"\n- **{n}: sin datos** — {e} No se ha inventado nada; ver `data/README.md` para añadirlo.")
    a("\n- MNQ/MGC usan el precio de NQ/GC (mismo subyacente y cotización). NQ/GC son referencias con 1 contrato fijo y "
      "500.000 $ de capital.\n")
    a("## 2. Período estudiado")
    a(md(pd.DataFrame({n: {k: f"{v[0]} → {v[1]}" for k, v in s.items() if k != "dev"} for n, s in bt["particiones"].items()}).T))
    a("\nParticiones por número de sesiones válidas (60/20/20). El test solo se usa en `optimize.py`; registro en `results/TEST_LOG.md`. "
      "**Aviso NQ:** en proyectos anteriores de este repositorio ya se estudiaron reglas de VWAP en NQ con datos desde 2023; "
      "el test de MNQ/NQ no es completamente \"virgen\" para la familia VWAP, aunque estas reglas concretas no se habían probado.\n")
    # 3-5
    b = cfg["baseline"]
    a("## 3. Supuestos")
    a(f"- Todo con velas de {cfg['general']['timeframe_minutes']} min (`intrabar: {cfg['general']['intrabar']}`): el VWAP se acumula con las "
      "velas de 15 min de la sesión (precio típico × volumen) y se reinicia al inicio de la sesión de cada instrumento; stop y "
      "target se comprueban con el máximo y el mínimo de cada vela de 15 min; **si una vela toca stop y target, se asume el stop**; "
      "si abre más allá del stop, se ejecuta en la apertura.")
    a("- Señal al cierre de la vela; ejecución a mercado en la apertura de la siguiente. Target = orden límite, solo si el precio lo "
      "supera en 1 tick. Una posición por instrumento; sin pyramiding, martingala ni overnight.")
    a(f"- EMAs {b['ema_fast']}/{b['ema_medium']}/{b['ema_slow']} y ATR({b['atr_period']}) sobre las velas de 15 min de la sesión, "
      "continuas entre días y reiniciadas en cada cambio de contrato (no se ajusta el continuo hacia atrás).")
    a(f"- Riesgo: {b['risk_per_trade']} % del capital actual por operación; contratos = floor(riesgo / (stop × valor del punto)); "
      f"límite diario {b['daily_loss_limit']} %, {b['max_consecutive_losses']} pérdidas seguidas, {b['max_trades_per_day']} operaciones/día.\n")
    a("## 4. Costes")
    a(md(pd.DataFrame({n: {k: cfg["instruments"][n][k] for k in ("tick_size", "point_value", "commission_per_side", "slippage_ticks", "spread_ticks", "session", "eod_exit")}
                       for n in cfg["instruments"]}).T))
    a("\nResultados siempre **netos** (bruto, costes y neto por separado). Escenario de costes dobles (deslizamiento ×2) en el apartado 16.\n")
    a("## 5. Reglas exactas")
    a("- **Modelos:** A cierre vs VWAP; B + cierre vs EMA200; C + EMA50 vs EMA200 y cierre vs EMA200; D = C + cierre vs EMA20 "
      "(EMA20 solo como filtro de timing).")
    a("- **Entradas:** `state` (condición cumplida al cierre y sin posición); `breakout` (el cierre cruza el VWAP y la vela confirma: "
      "cierre > apertura en largos); `pullback` (la vela anterior cerró del lado bueno, la actual retrocede hasta max(VWAP, EMA20) y "
      "cierra de nuevo a favor y con cuerpo a favor).")
    a("- **Filtros de tendencia (uno a uno):** pendiente de la EMA200 (4 velas) a favor; pendiente del VWAP a favor.")
    a("- **Stops:** ATR(14) × 1,0 / 1,5 / 2,0; estructura (mínimo/máximo de las últimas 5 velas ∓ 1 tick).")
    a("- **Take profit:** 1 / 1,5 / 2 / 2,5 / 3 R o sin TP.")
    a("- **Salidas:** A VWAP (cierre al otro lado), B EMA20, C trailing ATR (2 × ATR desde el mejor cierre), D TP/SL fijo (TP 2R si no "
      "se indica), E parcial 50 % en 1R + stop a la entrada + trailing, F tiempo (30/60/90/120/180 min). Todas con stop inicial y "
      "cierre forzado de sesión.")
    a(f"- **Baseline:** modelo {b['model']}, entrada {b['entry_type']}, stop {b['atr_multiplier']} × ATR, sin TP, salida {b['exit_type']}.\n")
    # 6-9 Secuencia de modelos
    a("## 6-9. Baseline VWAP → +EMA200 → +EMA50/200 → +EMA20 (mismo resto de reglas)")
    a("Train y validation salen de `run_backtest.py`; test de `optimize.py` (una ejecución). Δ = cambio de la expectativa neta en R "
      "respecto al modelo anterior de la secuencia.\n")
    comp = []
    for n, res in op["instrumentos"].items():
        t = tabla_periodos(res)
        t = t[t["configuración"].str.startswith("modelo")]
        t.insert(0, "instrumento", n)
        comp.append(t)
        a(f"### {n}")
        piv = t.pivot(index="configuración", columns="periodo", values="expectancy_R")[["train", "validation", "test"]]
        delta = piv.diff().add_prefix("Δ ")
        a(md(t.drop(columns="instrumento"), index=False))
        a("\nExpectativa neta (R) y aporte de cada paso:\n")
        a(md(pd.concat([piv, delta], axis=1).round(4)))
        a(f"\n![{n} modelos](" + pl.periodos(piv, P / f"{n}_modelos_periodos.png", f"{n}: modelos A-D, expectativa neta por periodo") + ")\n")
    a("### Comparación entre instrumentos (sin ordenar por \"mejor\")")
    a(md(pd.concat(comp).set_index(["instrumento", "configuración", "periodo"])))
    a("")
    a("### Tipos de entrada, filtros de tendencia y franjas (train y validation)")
    for n, res in bt["instrumentos"].items():
        n_var += len(res["secuencia_modelos"]) // 2 + len(res["entradas"]) // 2 + len(res["filtros"]) // 2 + len(res["ventanas"]) // 2
        a(f"#### {n}")
        a(md(res["entradas"][["variante", "periodo"] + CORTAS], index=False))
        a("")
        a(md(res["filtros"][["variante", "periodo"] + CORTAS], index=False))
        a("\nDesglose del baseline por franja horaria:\n")
        a(md(res["franjas"]))
        a("\nSolo operando en una ventana:\n")
        a(md(res["ventanas"][["variante", "periodo"] + CORTAS], index=False))
        a("")
    # 10 Salidas y etapas
    a("## 10. Optimización secuencial y salidas (train optimiza, validation selecciona)")
    for n, res in op["instrumentos"].items():
        if "etapas" not in res:
            a(f"- {n}: referencia; usa la configuración final de su micro ({res['final']['model']}, {res['final']['entry_type']}, ...).")
            continue
        et = res["etapas"]
        n_var += len(et)
        cols = ["etapa", "opcion", "trades_train", "expectancy_R_train", "t_R_train", "expectancy_R_val", "t_R_val",
                "profit_factor_val", "max_dd_%_val", "aceptada"]
        a(f"### {n}")
        a(md(et[cols], index=False))
        a("\nDecisiones: " + "; ".join(f"{k}: **{v}**" for k, v in res["decisiones"]))
        f = res["final"]
        a(f"\nConfiguración final: modelo {f['model']}, entrada {f['entry_type']}, filtros {f['trend_filters'] or 'ninguno'}, "
          f"stop {f['stop_type']}{' ' + str(f['atr_multiplier']) + '×ATR' if f['stop_type'] == 'atr' else ''}, TP {f['take_profit_R']}, "
          f"salida {f['exit_type']}{' ' + str(f['time_exit_minutes']) + ' min' if f['exit_type'] == 'time' else ''}, ventana {f['window'] or 'toda la sesión'}.\n")
    # 11 Train/val/test
    a("## 11. Train / Validation / Test (configuración final de cada instrumento)")
    labs = {}
    for n, res in op["instrumentos"].items():
        t = tabla_periodos(res, K)
        a(f"### {n}")
        a(md(t[t["configuración"] == "final"].drop(columns="configuración").set_index("periodo").T))
        piv = tabla_periodos(res).pivot(index="configuración", columns="periodo", values="expectancy_R")[["train", "validation", "test"]]
        a("\n![periodos](" + pl.periodos(piv, P / f"{n}_final_vs_modelos.png", f"{n}: final y modelos, expectativa neta por periodo") + ")")
        daily = {p: res["periodos"]["final"][p][0].daily for p in ("train", "validation", "test")}
        cap = cfg["instruments"][n].get("capital_override", cfg["general"]["initial_capital"])
        a("\n![equity](" + pl.equity_dd(daily, cap, P / f"{n}_equity_drawdown.png", f"{n}: configuración final, capital y drawdown") + ")")
        todas = pd.concat([res["periodos"]["final"][p][0].trades for p in ("train", "validation", "test")], ignore_index=True)
        dall = pd.concat(daily.values())
        if len(todas):
            a("\n![R](" + pl.hist_r(todas, P / f"{n}_distribucion_R.png", f"{n}: distribución de operaciones (final, todos los periodos)") + ")")
            a("\n![mensual](" + pl.mensual(dall, P / f"{n}_mensual.png", f"{n}: P&L mensual (final)") + ")")
            a("\n![MAE/MFE](" + pl.mae_mfe(todas, P / f"{n}_mae_mfe.png", f"{n}: MAE/MFE vs resultado") + ")")
        dg = res["desgloses"]["train+validation"]
        if dg:
            a("\n![hora](" + pl.barras(dg["hora"], "net_pnl", P / f"{n}_pnl_hora.png", f"{n}: P&L por hora (train+validation)") + ")")
            a("\n![día](" + pl.barras(dg["día semana"], "net_pnl", P / f"{n}_pnl_dia.png", f"{n}: P&L por día de la semana (train+validation)") + ")")
            for clave in ("año", "mes", "día semana", "hora", "franja", "dirección", "volatilidad (ATR entrada)", "motivo de salida"):
                a(f"\n**Por {clave} (train+validation):**\n")
                a(md(dg[clave]))
        dt = res["desgloses"]["test"]
        if dt:
            for clave in ("año", "franja", "dirección"):
                a(f"\n**Por {clave} (test):**\n")
                a(md(dt[clave]))
        # ejemplos de operaciones sobre el gráfico
        if cfg["instruments"][n].get("primary") and len(todas):
            if n not in labs:
                labs[n] = Lab(cfg, n)
            x = labs[n].features(res["final"])
            for etq, fila in (("mejor", todas.loc[todas.r_net.idxmax()]), ("peor", todas.loc[todas.r_net.idxmin()]),
                              ("mediana", todas.iloc[(todas.r_net - todas.r_net.median()).abs().argsort().iloc[0]])):
                a(f"\n![{etq}](" + pl.ejemplo(x, fila, P / f"{n}_ejemplo_{etq}.png",
                                              f"{n}: operación {etq} ({fila.session}, {fila.r_net:.2f} R)") + ")")
        a("")
    # 12 WF
    a("## 12. Walk-forward (3 años → 1, stop×TP re-optimizado con elección suavizada; dentro de train+validation)")
    for n, res in op["instrumentos"].items():
        if "wf" not in res:
            continue
        n_var += 24 * len(res["wf"])
        a(f"### {n}")
        a(md(res["wf"], index=False))
        w = res["wf_trades"]
        if len(w):
            t = w.r_net.mean() / w.r_net.std(ddof=1) * np.sqrt(len(w))
            a(f"\nTotal fuera de muestra del walk-forward: {len(w)} operaciones, {w.r_net.mean():.4f} R, t {t:.2f}, neto {w.net_pnl.sum():,.0f} $.")
            a("\n![wf](" + pl.wf_equity(w, P / f"{n}_walk_forward.png", f"{n}: walk-forward, R neto acumulado") + ")\n")
    # 13 MC
    a("## 13. Monte Carlo (configuración final; solo robustez, no cambia la estrategia)")
    a("Barajado del orden (drawdown y rachas) y remuestreo con reemplazo (retorno), "
      f"{cfg['monte_carlo']['n']} simulaciones. Supone operaciones independientes: los periodos malos reales pueden ser peores.\n")
    a(md(pd.DataFrame({f"{n} {k}": v for n, res in op["instrumentos"].items() for k, v in res["mc"].items() if v}).T))
    # 14 Sensibilidad
    a("\n## 14. Sensibilidad (train)")
    for n, res in op["instrumentos"].items():
        if "sens" not in res:
            continue
        n_var += len(res["sens"]["ema"]) + len(res["sens"]["atr"])
        s = res["sens"]
        a(f"### {n} (EMA con modelo {s['modelo_usado_ema']})")
        a("![ema](" + pl.heat(s["ema"], "ema_slow", "ema_medium", P / f"{n}_sens_ema.png", f"{n}: EMA lenta × EMA media") + ")")
        a("\n![atr](" + pl.heat(s["atr"], "atr_multiplier", "atr_period", P / f"{n}_sens_atr.png", f"{n}: multiplicador × periodo ATR") + ")")
        a(f"\nRango de expectativa en la rejilla EMA: {s['ema'].expectancy_R.min():.4f} a {s['ema'].expectancy_R.max():.4f} R; "
          f"rejilla ATR: {s['atr'].expectancy_R.min():.4f} a {s['atr'].expectancy_R.max():.4f} R.\n")
    # 15-16 Drawdown y riesgo
    a("## 15. Drawdown")
    a(md(pd.DataFrame([{"instrumento": n, "periodo": p, "max_dd": m.get("max_dd"), "max_dd_%": m.get("max_dd_%"),
                        "max_consec_losses": m.get("max_consec_losses"), "calmar": m.get("calmar")}
                       for n, res in op["instrumentos"].items() for p, (_, m) in res["periodos"]["final"].items()]), index=False))
    a("\n## 16. Riesgo por operación y costes dobles (configuración final)")
    for n, res in op["instrumentos"].items():
        a(f"### {n}")
        a(md(res["riesgo"], index=False))
        a("\nCon deslizamiento ×2: " + "; ".join(f"{p}: R {m.get('expectancy_R')} (PF {m.get('profit_factor')})" for p, m in res["costes_x2"].items()))
        a("")
    # Robustez
    a("## Lista de robustez (apartado 21) — configuración final")
    for n, res in op["instrumentos"].items():
        a(f"### {n}")
        a(md(robustez(res), index=False))
        a("")
    # 17-18
    a("## 17. Limitaciones")
    a("- Precio y volumen de NQ/GC para MNQ/MGC: el micro tiene menos liquidez; el deslizamiento real puede ser mayor.")
    a("- Con velas de 15 min no se conoce el orden de los precios dentro de la vela: stop y target en la misma vela = stop "
      "(pesimista); trailing y parcial se evalúan con la vela completa.")
    a("- Sesión del oro definida en hora de Nueva York: 2-3 semanas al año la apertura de Londres cae una hora antes o después.")
    a("- Sin ejecuciones parciales, rechazos, caídas de conexión ni cambios de margen. XAUUSD sin datos.")
    a("- NQ/GC con 1 contrato fijo: sus resultados en $ no son comparables con los micro; en R sí (salvo el peso de los costes).\n")
    a("## 18. Posibles problemas de sobreajuste")
    a(f"- Variantes evaluadas (aprox., sin contar el test): **{n_var}**. Con este número, varias parecerán buenas en train o "
      "validation por azar.")
    for n, res in op["instrumentos"].items():
        per = {p: m for p, (_, m) in res["periodos"]["final"].items()}
        a(f"- {n}: expectativa neta de la configuración final train {per['train'].get('expectancy_R')} → validation "
          f"{per['validation'].get('expectancy_R')} → test {per['test'].get('expectancy_R')} R (t test {per['test'].get('t_R')}).")
    a("- La selección por validation elige, por construcción, lo que mejor le fue en validation; la caída en test mide cuánto de "
      "eso era azar. Los modelos A–D sin optimizar sirven de control.")
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "FINAL_REPORT.md").write_text("\n".join(L), encoding="utf-8")
