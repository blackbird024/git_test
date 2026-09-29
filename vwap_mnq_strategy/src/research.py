"""Protocolo completo de investigación (README, "Protocolo") e informe final en español.

Las listas de filtros y salidas de este archivo se fijaron antes de ejecutar la investigación completa. La selección
de la candidata es mecánica (reglas del README); el test final se ejecuta una sola vez con baseline y candidata.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import plots
from .backtester import buy_hold_intradia, run
from .metrics import bootstrap, desgloses, resumen
from .optimizer import elegir, rejilla
from .pipeline import RAIZ, barras_con_indicadores, variante
from .signals import señales
from .walk_forward import walk_forward

F = "strategy.filters."
FILTROS = {
    "A pendiente VWAP (4 velas)": {F + "vwap_slope.enabled": True},
    "B EMA 200": {F + "ema.enabled": True, F + "ema.period": 200},
    "B EMA 50": {F + "ema.enabled": True, F + "ema.period": 50},
    "C régimen ATR (p10-p90)": {F + "atr_regime.enabled": True},
    "D RSI(14) a favor de 50": {F + "rsi.enabled": True},
    "E rango inicial 15 min estrecho": {F + "initial_range.enabled": True, F + "initial_range.minutes": 15},
    "E rango inicial 30 min estrecho": {F + "initial_range.enabled": True, F + "initial_range.minutes": 30},
    "E rango inicial 60 min estrecho": {F + "initial_range.enabled": True, F + "initial_range.minutes": 60},
    "F horario 09:30-11:30": {F + "time_window.enabled": True, F + "time_window.start": "09:30", F + "time_window.end": "11:30"},
    "F horario 09:30-13:00": {F + "time_window.enabled": True, F + "time_window.start": "09:30", F + "time_window.end": "13:00"},
    "F horario 13:00-15:45": {F + "time_window.enabled": True, F + "time_window.start": "13:00", F + "time_window.end": "15:45"},
    "G distancia al VWAP 0,25-1,5 ATR": {F + "vwap_distance.enabled": True},
}
X = "strategy.exits."
SALIDAS = {
    "S0 baseline: contraria+giro, stop 2 ATR": {},
    "S1 solo señal contraria (sin stop)": {X + "sl_atr_mult": None},
    "S2 stop 1,5 ATR + TP 1R": {X + "opposite_signal": False, X + "sl_atr_mult": 1.5, X + "tp_r": 1.0},
    "S3 stop 1,5 ATR + TP 1,5R": {X + "opposite_signal": False, X + "sl_atr_mult": 1.5, X + "tp_r": 1.5},
    "S4 stop 1,5 ATR + TP 2R": {X + "opposite_signal": False, X + "sl_atr_mult": 1.5, X + "tp_r": 2.0},
    "S5 stop 1,5 ATR + TP 3R": {X + "opposite_signal": False, X + "sl_atr_mult": 1.5, X + "tp_r": 3.0},
    "S6 stop 1,5 ATR + TP 2R + contraria": {X + "sl_atr_mult": 1.5, X + "tp_r": 2.0},
    "S7 trailing 1,5 ATR + contraria": {X + "sl_atr_mult": 1.5, X + "trailing_atr_mult": 1.5},
    "S8 time stop 8 velas + stop 1,5 ATR + contraria": {X + "sl_atr_mult": 1.5, X + "time_stop_bars": 8},
}
CLAVES = ["operaciones", "expectativa_R", "expectativa_R_bruta", "t_R", "profit_factor", "win_rate_%", "neto_usd",
          "bruto_usd", "max_dd_usd", "max_dd_%", "sharpe"]


class Laboratorio:
    def __init__(self, cfg, ses):
        self.cfg, self.ses = cfg, ses
        self._barras = {}
        self.n_variantes = 0
        sp = cfg["splits"]
        self.periodos = {"train": sp["train"], "validación": sp["validation"], "test": sp["test"]}

    def barras(self, c):
        clave = json.dumps([c["session"]["vwap_session"], c["strategy"]["atr_period"], c["strategy"]["filters"]], sort_keys=True)
        if clave not in self._barras:
            self._barras[clave] = barras_con_indicadores(self.ses, c)
        return self._barras[clave]

    def correr(self, c, periodo, adverso=False, sig=None):
        d, h = self.periodos[periodo]
        r = run(self.barras(c), self.ses.sub, c, d, h, sig_override=sig, adverso=adverso)
        return r, resumen(r.trades, r.daily, r.capital_inicial)

    def comparar(self, variantes: dict, base_cfg, periodos=("train", "validación")) -> pd.DataFrame:
        filas = []
        for nombre, cambios in variantes.items():
            c = variante(base_cfg, **cambios)
            self.n_variantes += 1
            for p in periodos:
                _, m = self.correr(c, p)
                filas.append({"variante": nombre, "periodo": p, **{k: m.get(k) for k in CLAVES}})
        return pd.DataFrame(filas)


def _md(df: pd.DataFrame, **k) -> str:
    return df.to_markdown(**k) if len(df) else "(sin datos)"


def _tabla_periodos(t: pd.DataFrame) -> pd.DataFrame:
    return t.pivot(index="variante", columns="periodo", values="expectativa_R")[["train", "validación"]]


def investigacion_completa(cfg: dict, ses, inf_datos: dict) -> None:
    out = RAIZ / cfg["reports_dir"]
    out.mkdir(exist_ok=True)
    lab = Laboratorio(cfg, ses)
    base = copy.deepcopy(cfg)
    graf = {}
    print("[1] baseline")
    r_bt, m_bt = lab.correr(base, "train")
    r_bv, m_bv = lab.correr(base, "validación")
    lab.n_variantes += 1

    print("[2] variantes de entrada y VWAP extendido")
    entradas = lab.comparar({"A cruce (baseline)": {}, "B confirmación": {"strategy.entry_mode": "confirm"},
                             "A cruce con VWAP extendido (18:00)": {"session.vwap_session": "extended"}}, base)

    print("[3] filtros")
    filtros = lab.comparar({"(baseline, sin filtros)": {}, **FILTROS}, base)
    fp = filtros.pivot(index="variante", columns="periodo")
    b_tr, b_va = m_bt["expectativa_R"], m_bv["expectativa_R"]
    aceptados = [n for n in FILTROS if fp.loc[n, ("expectativa_R", "train")] > b_tr
                 and fp.loc[n, ("expectativa_R", "validación")] > b_va and fp.loc[n, ("operaciones", "train")] >= 150]

    print("[4] salidas")
    salidas = lab.comparar(SALIDAS, base)
    sp_ = salidas.pivot(index="variante", columns="periodo")
    cand_s = [n for n in SALIDAS if n != list(SALIDAS)[0] and sp_.loc[n, ("expectativa_R", "validación")] > b_va]
    salida_elegida = max(cand_s, key=lambda n: sp_.loc[n, ("expectativa_R", "train")]) if cand_s else list(SALIDAS)[0]
    if cand_s and sp_.loc[salida_elegida, ("expectativa_R", "train")] <= b_tr:
        salida_elegida = list(SALIDAS)[0]                     # tampoco mejora en train: se queda la del baseline

    print("[5] candidata")
    cambios = dict(SALIDAS[salida_elegida])
    nota_comb = ""
    if len(aceptados) > 1:
        comb = {}
        for n in aceptados:
            comb.update(FILTROS[n])
        _, mc = lab.correr(variante(base, **comb, **cambios), "validación")
        mejor_solo = max(aceptados, key=lambda n: fp.loc[n, ("expectativa_R", "validación")])
        if mc["expectativa_R"] < fp.loc[mejor_solo, ("expectativa_R", "validación")]:
            aceptados, nota_comb = [mejor_solo], f"La combinación era peor en validación; se usa solo «{mejor_solo}»."
        lab.n_variantes += 1
    for n in aceptados:
        cambios.update(FILTROS[n])
    cand = variante(base, **cambios)
    es_baseline = not cambios
    r_ct, m_ct = lab.correr(cand, "train")
    r_cv, m_cv = lab.correr(cand, "validación")

    print("[6] rejilla, walk-forward, sensibilidad")
    d_tr, h_tr = lab.periodos["train"]
    grid = rejilla(lab.barras(cand), ses.sub, cand, d_tr, h_tr)
    lab.n_variantes += len(grid)
    eleccion_grid = elegir(grid, cfg["optimization"]["min_trades"])
    graf["heatmap"] = plots.heatmap(grid, out / "sensibilidad_stop_target_train.png",
                                    "Expectativa neta (R) en train: stop x target (candidata)")
    wf, wf_ops = walk_forward(lab.barras(cand), ses.sub, cand)
    lab.n_variantes += 20 * len(wf)
    sens = []
    for nombre, c in {"ATR 10": variante(cand, **{"strategy.atr_period": 10}),
                      "ATR 20": variante(cand, **{"strategy.atr_period": 20}),
                      "cierre forzado 15:30": variante(cand, **{"strategy.eod_exit_time": "15:30"}),
                      "deslizamiento adverso (2 ticks)": cand}.items():
        for p in ("train", "validación"):
            _, m = lab.correr(c, p, adverso=nombre.startswith("deslizamiento"))
            sens.append({"variante": nombre, "periodo": p, **{k: m.get(k) for k in CLAVES}})
    sens = pd.DataFrame(sens)
    riesgo = []
    for rp in (0.25, 0.5, 1.0):
        c = variante(cand, **{"risk.risk_pct": rp})
        for p in ("train", "validación"):
            _, m = lab.correr(c, p)
            riesgo.append({"riesgo_%": rp, "periodo": p, **{k: m.get(k) for k in ("operaciones", "neto_usd", "max_dd_usd", "max_dd_%", "sharpe")}})
    riesgo = pd.DataFrame(riesgo)

    print("[7] referencias")
    rng = np.random.default_rng(cfg["montecarlo"]["seed"])
    bc = lab.barras(cand)
    s_base = señales(bc, "vwap", cand["strategy"]["entry_mode"])
    s_rand = np.where(s_base != 0, rng.choice([-1, 1], size=len(s_base)), 0)
    refs = []
    for p in ("train", "validación"):
        _, m = lab.correr(cand, p, sig=s_rand)
        refs.append({"referencia": "dirección aleatoria (mismas horas que la candidata)", "periodo": p, **{k: m.get(k) for k in CLAVES}})
        d, h = lab.periodos[p]
        bh = buy_hold_intradia(bc, cand, d, h)
        refs.append({"referencia": "comprar 09:30 y vender 15:45 (1 contrato)", "periodo": p, "operaciones": len(bh),
                     "neto_usd": round(bh.net_pnl.sum(), 0), "bruto_usd": round(bh.gross_pnl.sum(), 0)})
    refs = pd.DataFrame(refs)

    print("[8] TEST FINAL (una sola vez)")
    registro = out / "REGISTRO_TEST.md"
    huella = hashlib.sha1(json.dumps(cand, sort_keys=True, default=str).encode()).hexdigest()[:12]
    if registro.exists() and huella not in registro.read_text():
        raise SystemExit("El test ya se usó con otra candidata: no se reutiliza para elegir. Ver REGISTRO_TEST.md.")
    r_bte, m_bte = lab.correr(base, "test")
    r_cte, m_cte = lab.correr(cand, "test")
    d, h = lab.periodos["test"]
    bh_te = buy_hold_intradia(bc, cand, d, h)
    if not registro.exists():
        registro.write_text(f"# Registro de uso del test final\n\n- {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}: "
                            f"baseline y candidata `{huella}` ({'= baseline' if es_baseline else ', '.join(aceptados + [salida_elegida])}).\n",
                            encoding="utf-8")

    print("[9] desgloses, bootstrap y gráficos")
    ops_dev = pd.concat([r_ct.trades, r_cv.trades])
    daily_dev = pd.concat([r_ct.daily, r_cv.daily])
    desg = desgloses(ops_dev)
    boot_dev = bootstrap(ops_dev, cfg["montecarlo"]["n"], cfg["montecarlo"]["seed"], cfg["risk"]["initial_capital"])
    boot_te = bootstrap(r_cte.trades, cfg["montecarlo"]["n"], cfg["montecarlo"]["seed"], cfg["risk"]["initial_capital"]) if len(r_cte.trades) else {}
    cap = cfg["risk"]["initial_capital"]
    graf["equity_dev"] = plots.equity_drawdown({"baseline": pd.concat([r_bt.daily, r_bv.daily]), "candidata": daily_dev}, cap,
                                               out / "equity_train_validacion.png", "Capital y drawdown: train + validación (capital reiniciado por periodo no; acumulado)")
    graf["equity_test"] = plots.equity_drawdown({"baseline": r_bte.daily, "candidata": r_cte.daily}, cap,
                                                out / "equity_test.png", "Capital y drawdown: test final")
    graf["hist"] = plots.histograma_r(ops_dev, out / "distribucion_R.png", "Distribución de resultados (candidata, train + validación)")
    graf["hora"] = plots.barras_grupo(desg["hora_NY"], out / "por_hora_NY.png", "Expectativa por hora de entrada (NY)")
    graf["dia"] = plots.barras_grupo(desg["dia_semana"], out / "por_dia_semana.png", "Expectativa por día de la semana")
    graf["año"] = plots.barras_grupo(desg["año"], out / "por_año.png", "Expectativa por año")
    comp = pd.concat([_tabla_periodos(filtros).rename(index=lambda n: "Filtro " + n),
                      _tabla_periodos(salidas).rename(index=lambda n: "Salida " + n)])
    graf["comp"] = plots.comparacion(comp, out / "comparacion_variantes.png", "Filtros y salidas: expectativa neta por periodo")
    per = pd.DataFrame({"expectativa_R": {"train": m_ct.get("expectativa_R"), "validación": m_cv.get("expectativa_R"),
                                          "walk-forward (2018-2022)": wf_ops.r_net.mean() if len(wf_ops) else np.nan,
                                          "test final": m_cte.get("expectativa_R")}})
    graf["periodos"] = plots.comparacion(per, out / "comparacion_periodos.png", "Candidata: expectativa neta por periodo")
    if len(ops_dev):
        dias = ops_dev.groupby("session").net_pnl.sum()
        graf["dia_peor"] = plots.velas_dia(bc, ops_dev, dias.idxmin(), out / "dia_peor.png", f"Peor día de la candidata: {dias.idxmin()}")
        graf["dia_mejor"] = plots.velas_dia(bc, ops_dev, dias.idxmax(), out / "dia_mejor.png", f"Mejor día de la candidata: {dias.idxmax()}")
    r_cte.trades.to_csv(out / "operaciones_candidata_test.csv", index=False)
    ops_dev.to_csv(out / "operaciones_candidata_train_validacion.csv", index=False)

    print("[10] informe")
    _informe(out, cfg, inf_datos, lab, base, cand, es_baseline, aceptados, salida_elegida, nota_comb, m_bt, m_bv, m_ct, m_cv,
             m_bte, m_cte, bh_te, entradas, filtros, salidas, grid, eleccion_grid, wf, wf_ops, sens, riesgo, refs, desg,
             boot_dev, boot_te, graf)
    print("informe:", out / "INFORME.md")


def _veredicto(m_val: dict, m_test: dict) -> tuple[bool, str]:
    def ok(m):
        return m.get("operaciones", 0) > 1 and m.get("expectativa_R", -1) > 0 and m.get("t_R", 0) >= 2 and m.get("profit_factor", 0) > 1
    apoyo = ok(m_val) and ok(m_test)
    txt = (f"validación: R {m_val.get('expectativa_R')} (t {m_val.get('t_R')}, PF {m_val.get('profit_factor')}); "
           f"test: R {m_test.get('expectativa_R')} (t {m_test.get('t_R')}, PF {m_test.get('profit_factor')})")
    return apoyo, txt


def _informe(out, cfg, inf, lab, base, cand, es_baseline, aceptados, salida, nota_comb, m_bt, m_bv, m_ct, m_cv, m_bte,
             m_cte, bh_te, entradas, filtros, salidas, grid, eleccion, wf, wf_ops, sens, riesgo, refs, desg, boot_dev,
             boot_te, g) -> None:
    fila = lambda m: {k: m.get(k) for k in CLAVES + ["costes_usd", "recovery_factor", "sortino", "ganancia_media_usd",  # noqa: E731
                                                       "perdida_media_usd", "expectativa_usd", "duracion_media_min",
                                                       "duracion_mediana_min", "mae_medio_pts", "mfe_medio_pts",
                                                       "racha_perdedora_max", "racha_ganadora_max", "exposicion_%",
                                                       "operaciones_por_sesion", "rentabilidad_%", "largos", "cortos"]}
    tabla_bc = pd.DataFrame({"baseline train": fila(m_bt), "baseline validación": fila(m_bv), "baseline TEST": fila(m_bte),
                             "candidata train": fila(m_ct), "candidata validación": fila(m_cv), "candidata TEST": fila(m_cte)})
    apoyo_b, txt_b = _veredicto(m_bv, m_bte)
    apoyo_c, txt_c = _veredicto(m_cv, m_cte)
    ex, c = cfg["strategy"]["exits"], cfg["costs"]
    L = []
    a = L.append
    a("# Informe: VWAP direccional en MNQ, velas de 15 minutos\n")
    a(f"*Generado automáticamente el {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} por `python -m src.run_backtest report`. "
      "Todas las cifras salen de ejecuciones reales de este código sobre los datos descritos. Ninguna cifra histórica "
      "garantiza resultados futuros.*\n")
    a("## 1. La estrategia y sus reglas exactas")
    a("- **Idea:** operar en el sentido del precio respecto al VWAP de la sesión regular (09:30–16:00 NY, reiniciado cada día; "
      "precio típico (H+L+C)/3 ponderado por volumen, calculado con velas de 1 min y leído al cierre de cada vela de 15 min).")
    a("- **Señal (modo A, baseline):** al cierre de una vela de 15 min, si el cierre cruza por encima del VWAP (el último cierre "
      "no igual al VWAP estaba por debajo) → compra; cruce a la baja → venta. Cierre igual al VWAP: sin señal. La primera vela de "
      "la sesión no genera señal. **Modo B:** la vela siguiente al cruce confirma el lado.")
    a("- **Ejecución:** a mercado en la apertura de la vela de 15 min siguiente. Una sola posición. Última entrada 15:15 NY; "
      "cierre forzado 15:45 NY; nada abierto de noche.")
    a(f"- **Salida del baseline:** señal contraria (cierra y gira), stop {ex['sl_atr_mult']} × ATR(14) de 15 min de la vela de "
      "señal desde el precio de entrada, cierre de sesión. Sin objetivo.")
    a(f"- **Riesgo:** {cfg['risk']['risk_pct']} % del capital actual por operación (capital inicial {cfg['risk']['initial_capital']:,} $), "
      "contratos = floor(riesgo / (distancia al stop × 2 $)); si sale < 1, no se opera. Límite de pérdida diaria "
      f"{cfg['risk']['daily_loss_limit_pct']} %, máximo {cfg['risk']['max_trades_per_session']} operaciones por sesión, pausa tras "
      f"{cfg['risk']['pause_after_losses']} pérdidas seguidas.")
    a("")
    a("## 2. Datos")
    a(f"- Fuente: velas de 1 min de NQ (Databento GLBX.MDP3, contrato continuo por volumen), {inf['primera']} → {inf['ultima']}. "
      "NQ y MNQ cotizan el mismo índice al mismo precio; el P&L usa las especificaciones de MNQ (2 $/punto, tick 0,25).")
    a(f"- Calidad: {inf['filas_leidas']:,} filas, {inf['duplicadas_eliminadas']} duplicadas, {inf['filas_invalidas_eliminadas']} inválidas, "
      f"{inf['volumen_cero']} con volumen 0. {inf['sesiones_validas']} sesiones válidas de {inf['sesiones_rth']} "
      f"({inf['sesiones_excluidas']} excluidas por cierre anticipado o huecos). {inf['tramos_de_contrato']} contratos; "
      f"{inf['cambios_de_contrato_dentro_de_vela']} cambios de contrato dentro de una vela de 15 min.")
    sp = cfg["splits"]
    a(f"- Particiones: train {sp['train'][0]} → {sp['train'][1]}; validación {sp['validation'][0]} → {sp['validation'][1]}; "
      f"test final {sp['test'][0]} → fin de datos (usado una vez, ver `REGISTRO_TEST.md`).\n")
    a("## 3. Supuestos de ejecución y costes")
    a(f"- Comisión {c['commission_per_side']} $ por contrato y lado. Deslizamiento {c['slippage_ticks']} tick en entradas y salidas a mercado "
      f"y stops (adverso: {c['slippage_ticks_adverse']}). Target límite sin deslizamiento y solo si el precio lo supera en 1 tick.")
    a("- Stops y targets se comprueban minuto a minuto; si stop y target caen en el mismo minuto, se asume el stop. Si el minuto abre "
      "más allá del stop (hueco), se ejecuta en esa apertura.")
    a("- Resultado **bruto** = sin comisiones ni deslizamiento; **neto** = con todo. R = resultado neto / riesgo inicial en $.\n")
    a("## 4. Resultados del baseline y de la candidata")
    a(f"Candidata elegida con el protocolo: **{'igual al baseline (ningún filtro ni salida mejoró en train y validación)' if es_baseline else ', '.join(aceptados + [salida])}**. {nota_comb}\n")
    a(_md(tabla_bc))
    a("")
    a(f"![capital train+validación]({g['equity_dev']})\n\n![capital test]({g['equity_test']})\n\n![distribución R]({g['hist']})\n")
    a("### Referencias")
    a(_md(refs, index=False))
    a(f"\nComprar a las 09:30 y vender a las 15:45 en el TEST: {len(bh_te)} sesiones, neto {bh_te.net_pnl.sum():,.0f} $.\n")
    a("## 5. Comparación de entradas, filtros y salidas (train y validación, nunca test)")
    a("### Entradas")
    a(_md(entradas, index=False))
    a("\n### Filtros (uno a uno sobre el baseline)")
    a(_md(filtros, index=False))
    a(f"\nFiltros aceptados (mejoran R en train Y validación, ≥150 operaciones en train): **{', '.join(aceptados) if aceptados else 'ninguno'}**.\n")
    a("### Salidas")
    a(_md(salidas, index=False))
    a(f"\nSalida elegida: **{salida}**.\n")
    a(f"![comparación]({g['comp']})\n")
    a("## 6. Optimización, walk-forward y test final")
    a("Rejilla de stop × target en train (candidata). Se elige por expectativa suavizada con las vecinas, no por el máximo:")
    a(_md(grid, index=False))
    if eleccion is not None:
        a(f"\nElección suavizada en train: stop {eleccion.sl_atr_mult} ATR, TP {eleccion.tp_r} (R suavizado {eleccion.R_suavizado:.4f}). "
          "Solo informativa: la candidata no se cambia con esta rejilla (el walk-forward mide si elegir así funciona fuera de muestra).\n")
    a(f"![heatmap]({g['heatmap']})\n")
    a("### Walk-forward (optimiza 3 años, prueba el siguiente)")
    a(_md(wf, index=False))
    if len(wf_ops):
        r = wf_ops.r_net
        a(f"\nTotal walk-forward fuera de muestra: {len(r)} operaciones, expectativa {r.mean():.4f} R, "
          f"t {r.mean() / r.std(ddof=1) * np.sqrt(len(r)):.2f}, neto {wf_ops.net_pnl.sum():,.0f} $.\n")
    a(f"![periodos]({g['periodos']})\n")
    a("### Test final (una sola ejecución)")
    a(f"- Baseline: {txt_b}.")
    a(f"- Candidata: {txt_c}.")
    a(f"- Bootstrap de operaciones del test (candidata): {boot_te}.\n")
    a("## 7. Sensibilidad y robustez (candidata)")
    a(_md(sens, index=False))
    a("\n### Escenarios de riesgo por operación (solo investigación, no recomendación)")
    a(_md(riesgo, index=False))
    a(f"\nBootstrap (remuestreo de las operaciones de train+validación, {cfg['montecarlo']['n']} repeticiones, semilla "
      f"{cfg['montecarlo']['seed']}): {boot_dev}. Limitación: supone operaciones independientes; los periodos malos reales "
      "vienen en rachas de régimen y pueden ser peores.\n")
    a("## 8. Dónde gana y dónde pierde (candidata, train + validación)")
    for nombre in ("año", "hora_NY", "dia_semana", "mes", "direccion", "volatilidad", "motivo_salida"):
        a(f"### Por {nombre.replace('_', ' ')}")
        a(_md(desg[nombre]))
        a("")
    a(f"![año]({g['año']})\n\n![hora]({g['hora']})\n\n![día]({g['dia']})\n")
    if "dia_peor" in g:
        a(f"![peor día]({g['dia_peor']})\n\n![mejor día]({g['dia_mejor']})\n")
    a("## 9. Diferencias entre el backtest y la ejecución real")
    a("- Precio y volumen de NQ como sustituto de MNQ: el MNQ tiene menos liquidez; el deslizamiento real puede ser mayor, "
      "sobre todo en noticias (datos macro a las 08:30 y 10:00 NY, FOMC).")
    a("- Ejecución parcial: con varios contratos a mercado se suponen llenados completos al precio modelado.")
    a("- Stops: se simulan como órdenes stop a mercado; en huecos o movimientos rápidos el llenado real puede ser peor que 1 tick.")
    a("- Los datos de 1 min no dicen el orden exacto dentro del minuto: se asume el peor caso cuando stop y target coinciden.")
    a("- No se modelan caídas de conexión, rechazos de órdenes, cambios de margen ni horarios festivos del broker.\n")
    a("## 10. Conclusión descriptiva")
    a(f"Variantes evaluadas en total (incluida la rejilla y el walk-forward): **{lab.n_variantes}**. Con tantas pruebas, "
      "alguna parecerá buena por azar; por eso la candidata se eligió con reglas fijas y solo cuenta el test final.\n")
    a(f"- **Hipótesis base (baseline):** {'APOYADA' if apoyo_b else 'NO APOYADA'} por los datos ({txt_b}).")
    a(f"- **Candidata:** {'APOYADA' if apoyo_c else 'NO APOYADA'} por los datos ({txt_c}).")
    a("- Criterio: expectativa neta en R > 0 con t ≥ 2 y profit factor > 1 en validación y en test.")
    a("- Un resultado histórico positivo no convierte la estrategia en rentable ni en lista para operar en real.\n")
    a("## 11. Protocolo de paper trading propuesto")
    a("- **Solo si la candidata queda apoyada en validación y test.** Si no, no se recomienda paper trading de esta versión.")
    a("- Reglas congeladas: las de la candidata de este informe; cualquier cambio abre una versión nueva con su propio backtest.")
    a("- Duración mínima: 3 meses **y** al menos 150 operaciones (lo que llegue más tarde).")
    a("- Registrar cada operación: hora de la señal, precio del modelo, precio real, deslizamiento en ticks, resultado.")
    a("- Evaluación: deslizamiento medio real ≤ el supuesto; expectativa en R dentro del intervalo p5–p95 del bootstrap de "
      "la muestra equivalente; detener si la caída supera el p5 del drawdown del bootstrap.")
    (out / "INFORME.md").write_text("\n".join(L), encoding="utf-8")
