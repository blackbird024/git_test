"""Trading Bot Lab — orquestador. Uso (desde la raíz del repositorio):

    python -m bot_lab.run_lab investigacion     # etapa 1: TRAIN + VALIDATION (el TEST NO se carga en memoria)
    python -m bot_lab.run_lab test              # etapa 2: abre el TEST UNA vez para los finalistas congelados
    python -m bot_lab.generar_informe           # informe final y panel

Etapa 1 escribe research/experiments/<AAAAMMDD_HHMM>_investigacion/ y congela los finalistas en
research/finalistas.json (hay que hacer commit ANTES de la etapa 2: así queda constancia de que no se cambiaron
después de ver el TEST). La etapa 2 se niega a ejecutarse si ya existe un resultado de TEST.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from bot_lab.core import metricas as M
from bot_lab.core.datos import Contexto, cargar_config, guardar_json
from bot_lab.portfolio import cartera as CA
from bot_lab.portfolio import prop_firm as PF
from bot_lab.portfolio import sizing as SZ
from bot_lab.strategies import (momentum, orb, overnight, previous_day, pullback, regime, rsi2_extremo,
                                statistical_spread, time_of_day, trend_following, validadas, vwap_mean_reversion)
from bot_lab.validation import clasificacion as CL
from bot_lab.validation import montecarlo as MC
from bot_lab.validation import protocolo as PR
from bot_lab.validation import regimenes as RG
from bot_lab.validation import sensibilidad as SE
from bot_lab.validation import walk_forward as WF
from src.data.datos import velas_1m

RAIZ = Path(__file__).resolve().parents[1]
LAB = RAIZ / "bot_lab"
FASE1 = [vwap_mean_reversion, orb, trend_following, momentum, pullback, rsi2_extremo, regime]
FASE2 = [time_of_day, previous_day, overnight, statistical_spread]
MODULOS = {m.BOT: m for m in FASE1 + FASE2}
LOG: list[str] = []


def log(msg: str) -> None:
    linea = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(linea, flush=True)
    LOG.append(linea)


def manifiesto(cfg: dict, carpeta: Path, etapa: str) -> None:
    def git(*a):
        return subprocess.run(["git", *a], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    datos = {}
    for f in sorted((RAIZ / "data" / "processed").glob("NQ_1M.parquet")) + sorted((RAIZ / "data" / "raw" / "daily").glob("*.parquet")):
        datos[str(f.relative_to(RAIZ))] = {"bytes": f.stat().st_size, "sha1": hashlib.sha1(f.read_bytes()).hexdigest()}
    import numba
    guardar_json({"etapa": etapa, "fecha_utc": datetime.now(timezone.utc).isoformat(), "commit": git("rev-parse", "HEAD"),
                  "cambios_sin_commit": git("status", "--porcelain"), "python": sys.version.split()[0],
                  "plataforma": platform.platform(), "pandas": pd.__version__, "numpy": np.__version__,
                  "numba": numba.__version__, "semilla": cfg["semilla"], "config": cfg, "datos": datos},
                 carpeta / "manifiesto.json")


def contexto(cfg: dict, abrir_test: bool) -> Contexto:
    m1 = velas_1m("NQ")
    if not abrir_test:
        corte = pd.Timestamp(cfg["particion"]["test_desde"], tz="America/New_York").tz_convert("UTC")
        m1 = m1[m1.index < corte]
    ctx = Contexto(m1)
    if not abrir_test:
        assert ctx.tramo.max() <= 1, "el TEST no debe estar en memoria en la etapa de investigación"
    return ctx


def evaluar_finalista(mod, params: dict, ctx: Contexto, cfg: dict, tramos, ops_variantes: dict, fija: str,
                      etiqueta: str) -> dict:
    """Evaluación completa de una variante sobre los tramos indicados (métricas, costes, walk-forward, sensibilidad,
    regímenes, bootstrap y Monte Carlo)."""
    b = cfg["bootstrap"]
    ses = ctx.sesiones_rth
    ses = ses[np.isin(PR.tramo_de_fecha(ses), list(tramos))]
    filtro = lambda o: PR.de_tramo(o, tramos)  # noqa: E731
    ops = filtro(ops_variantes[fija])
    ev = {"variante": fija, "params": params, "tramos": etiqueta}
    ev["metricas"] = M.completas(ops, ses, cfg["cartera"]["capital"])
    ev["IC95_bloques_$"] = M.ic_bloques(ops, ses, b["bloque_sesiones"], b["n"], cfg["semilla"])
    ev["costes"] = {"BASE": M.rapidas(ops)}
    for k in ("STRESS_1", "STRESS_2"):
        ev["costes"][k] = M.rapidas(filtro(mod.ejecutar(ctx, params, mult=cfg["costes"][k])))
    controles = {k for k, p in mod.VARIANTES.items() if p.get("control")}
    ini = pd.Timestamp(ses[0])
    ev["walk_forward"] = WF.ejecutar({k: filtro(o) for k, o in ops_variantes.items()}, controles, mod.BASE, fija, ini,
                                     pd.Timestamp(ses[-1]), cfg["walk_forward"]["meses_train"],
                                     cfg["walk_forward"]["meses_test"], cfg["walk_forward"]["min_ops_train"],
                                     cfg["cribado"]["empate_t"])
    ev["vecindad"] = SE.vecindad(mod, ctx, params, filtro)
    et = RG.etiquetar(ops, ctx, cfg["regimenes"])
    ev["regimenes"] = {"vol": RG.por_grupo(et, "vol", ["BAJA", "NORMAL", "ALTA", "sin dato"]),
                       "tendencia": RG.por_grupo(et, "tendencia", ["TENDENCIA", "RANGO", "sin dato"]),
                       "franja": RG.por_grupo(et, "franja", RG.ORDEN_FRANJAS),
                       "dia": RG.por_grupo(et, "dia", RG.DIAS), "año": RG.por_grupo(et, "año"),
                       "direccion": RG.por_grupo(et.assign(lado=np.where(et.direccion == 1, "LARGO", "CORTO")), "lado")}
    ev["estabilidad"] = SE.estabilidad(ev["vecindad"], ev["metricas"]["anual_$"], ev["regimenes"]["vol"],
                                       ev["costes"]["STRESS_1"]["expectativa_$"])
    diario = M.diario(ops, ses)
    ev["montecarlo"] = MC.distribucion(diario, cfg["cartera"]["capital"], b["bloque_sesiones"], b["n"],
                                       b["horizonte_sesiones"], cfg["semilla"])
    ev["diario"] = diario
    ev["ops"] = ops
    return ev


def validadas_eval(ctx: Contexto, cfg: dict, tramos, etiqueta: str) -> dict:
    """BOT 01 y BOT 02 con su código original, evaluados con las mismas métricas (sin selección: ya validadas)."""
    b = cfg["bootstrap"]
    ses = ctx.sesiones_rth
    ses = ses[np.isin(PR.tramo_de_fecha(ses), list(tramos))]
    out = {}
    for bot, fn in (("01", validadas.rsi2), ("02", validadas.zona_ruido)):
        ops = PR.de_tramo(fn(ctx), tramos)
        ev = {"metricas": M.completas(ops, ses, cfg["cartera"]["capital"]),
              "IC95_bloques_$": M.ic_bloques(ops, ses, b["bloque_sesiones"], b["n"], cfg["semilla"]),
              "costes": {"BASE": M.rapidas(ops), "STRESS_1": M.rapidas(PR.de_tramo(fn(ctx, 2.0), tramos)),
                         "STRESS_2": M.rapidas(PR.de_tramo(fn(ctx, 3.0), tramos))}}
        et = RG.etiquetar(ops, ctx, cfg["regimenes"])
        ev["regimenes"] = {"vol": RG.por_grupo(et, "vol", ["BAJA", "NORMAL", "ALTA", "sin dato"]),
                           "tendencia": RG.por_grupo(et, "tendencia", ["TENDENCIA", "RANGO", "sin dato"]),
                           "franja": RG.por_grupo(et, "franja", RG.ORDEN_FRANJAS),
                           "dia": RG.por_grupo(et, "dia", RG.DIAS), "año": RG.por_grupo(et, "año")}
        ev["diario"] = M.diario(ops, ses)
        ev["montecarlo"] = MC.distribucion(ev["diario"], cfg["cartera"]["capital"], b["bloque_sesiones"], b["n"],
                                           b["horizonte_sesiones"], cfg["semilla"])
        ev["ops"] = ops
        ev["tramos"] = etiqueta
        out[bot] = ev
    return out


# ------------------------------------------------------------------------------------------------ etapa 1
def investigacion(cfg: dict) -> None:
    carpeta = LAB / "research" / "experiments" / (datetime.now().strftime("%Y%m%d_%H%M") + "_investigacion")
    carpeta.mkdir(parents=True, exist_ok=False)
    manifiesto(cfg, carpeta, "investigacion")
    log(f"experimento en {carpeta.relative_to(RAIZ)} (TEST fuera de memoria)")
    ctx = contexto(cfg, abrir_test=False)
    R = {"etapa": "investigacion", "cribado": {}, "finalistas": {}, "analisis": {}}
    for fase, mods in (("FASE 1", FASE1), ("FASE 2", FASE2)):
        log(f"{fase}: cribado en TRAIN y validación de la variante elegida")
        for mod in mods:
            R["cribado"][mod.BOT] = PR.cribar(mod, ctx, cfg, log)
    log("Análisis de regímenes, hora y día (BOT 20-22) sobre la variante elegida de cada BOT, solo TRAIN")
    an = {}
    for bot, res in R["cribado"].items():
        sel = res["seleccionada"]
        if sel is None:
            continue
        et = RG.etiquetar(PR.de_tramo(res["ops_variantes"][sel], [0]), ctx, cfg["regimenes"])
        an[bot] = {"vol": RG.por_grupo(et, "vol", ["BAJA", "NORMAL", "ALTA", "sin dato"]),
                   "tendencia": RG.por_grupo(et, "tendencia", ["TENDENCIA", "RANGO", "sin dato"]),
                   "franja": RG.por_grupo(et, "franja", RG.ORDEN_FRANJAS), "dia": RG.por_grupo(et, "dia", RG.DIAS)}
    for bot, fn in (("01", validadas.rsi2), ("02", validadas.zona_ruido)):
        et = RG.etiquetar(PR.de_tramo(fn(ctx), [0]), ctx, cfg["regimenes"])
        an[bot] = {"vol": RG.por_grupo(et, "vol", ["BAJA", "NORMAL", "ALTA", "sin dato"]),
                   "tendencia": RG.por_grupo(et, "tendencia", ["TENDENCIA", "RANGO", "sin dato"]),
                   "franja": RG.por_grupo(et, "franja", RG.ORDEN_FRANJAS), "dia": RG.por_grupo(et, "dia", RG.DIAS)}
    R["analisis"]["por_bot_train"] = an
    R["analisis"]["deriva_franja_train"] = RG.deriva_por_franja(ctx, 0)
    R["analisis"]["deriva_dia_train"] = RG.deriva_por_dia(ctx, 0)
    finalistas = {bot: r for bot, r in R["cribado"].items() if r.get("estado_validacion") == "finalista"}
    log(f"Finalistas: {list(finalistas) or 'ninguno'}")
    for bot, r in finalistas.items():
        mod = MODULOS[bot]
        log(f"  evaluación completa (TRAIN+VALIDATION) de BOT {bot}: {r['seleccionada']}")
        R["finalistas"][bot] = evaluar_finalista(mod, mod.VARIANTES[r["seleccionada"]], ctx, cfg, (0, 1),
                                                 r["ops_variantes"], r["seleccionada"], "TRAIN+VALIDATION")
    R["validadas"] = validadas_eval(ctx, cfg, (0, 1), "TRAIN+VALIDATION")
    R["n_variantes"] = sum(r["n_variantes"] for r in R["cribado"].values())
    congelar = {bot: {"variante": r["seleccionada"], "params": MODULOS[bot].VARIANTES[r["seleccionada"]]}
                for bot, r in finalistas.items()}
    guardar_json({"fecha": datetime.now(timezone.utc).isoformat(), "experimento": carpeta.name,
                  "finalistas": congelar, "n_variantes_cribado": R["n_variantes"]}, LAB / "research" / "finalistas.json")
    for r in R["cribado"].values():
        r["tabla_train"].to_csv(carpeta / f"cribado_bot{r['bot']}_train.csv")
    (carpeta / "resultados.pkl").write_bytes(pickle.dumps(R))
    (carpeta / "log.txt").write_text("\n".join(LOG), encoding="utf-8")
    log("fin de la etapa 1. Haz commit de research/finalistas.json antes de abrir el TEST.")


# ------------------------------------------------------------------------------------------------ etapa 2
def abrir_test(cfg: dict) -> None:
    ya = sorted((LAB / "research" / "experiments").glob("*_test"))
    if ya:
        raise SystemExit(f"El TEST ya se abrió ({ya[0].name}). No se vuelve a abrir.")
    congelado = json.loads((LAB / "research" / "finalistas.json").read_text(encoding="utf-8"))
    estado = subprocess.run(["git", "status", "--porcelain", "bot_lab/research/finalistas.json"], cwd=RAIZ,
                            capture_output=True, text=True).stdout.strip()
    if estado:
        raise SystemExit("research/finalistas.json tiene cambios sin commit: congélalo antes de abrir el TEST.")
    previo = sorted((LAB / "research" / "experiments").glob("*_investigacion"))[-1]
    R1 = pickle.loads((previo / "resultados.pkl").read_bytes())
    carpeta = LAB / "research" / "experiments" / (datetime.now().strftime("%Y%m%d_%H%M") + "_test")
    carpeta.mkdir(parents=True, exist_ok=False)
    manifiesto(cfg, carpeta, "test")
    log(f"ABRIENDO EL TEST (una sola vez). Finalistas congelados: {list(congelado['finalistas']) or 'ninguno'}")
    ctx = contexto(cfg, abrir_test=True)
    R = {"etapa": "test", "finalistas": {}, "congelado": congelado, "experimento_investigacion": previo.name}
    for bot, f in congelado["finalistas"].items():
        mod = MODULOS[bot]
        ops_var = {k: mod.ejecutar(ctx, p) for k, p in mod.VARIANTES.items()}
        ev = evaluar_finalista(mod, f["params"], ctx, cfg, (0, 1, 2), ops_var, f["variante"], "TRAIN+VALIDATION+TEST")
        test_ops = PR.de_tramo(ops_var[f["variante"]], [2])
        ses_t = ctx.sesiones_rth[PR.tramo_de_fecha(ctx.sesiones_rth) == 2]
        ev["test"] = {**M.rapidas(test_ops),
                      "IC95_bloques_$": M.ic_bloques(test_ops, ses_t, cfg["bootstrap"]["bloque_sesiones"],
                                                     cfg["bootstrap"]["n"], cfg["semilla"]) if len(test_ops) > 2 else (np.nan, np.nan)}
        ev["tramos_detalle"] = {n: M.rapidas(PR.de_tramo(ops_var[f["variante"]], [k]))
                                for k, n in enumerate(("TRAIN", "VALIDATION", "TEST"))}
        ev["clase"], ev["criterios"] = CL.clase(ev, cfg, mod.FRECUENCIA == "diaria")
        log(f"  BOT {bot}: TEST {ev['test']['operaciones']} op., expectativa {ev['test']['expectativa_$']} $ -> {ev['clase']}")
        R["finalistas"][bot] = ev
    R["validadas"] = validadas_eval(ctx, cfg, (0, 1, 2), "2015-2026 completo")
    ses_t = ctx.sesiones_rth[PR.tramo_de_fecha(ctx.sesiones_rth) == 2]
    for bot, ev in R["validadas"].items():
        ev["test"] = M.rapidas(PR.de_tramo(ev["ops"], [2]))
    # ----- cartera
    log("Cartera, correlaciones, tamaño y prop firm")
    ses = ctx.sesiones_rth
    diarios = pd.DataFrame({"BOT01 RSI2": R["validadas"]["01"]["diario"], "BOT02 Zona ruido": R["validadas"]["02"]["diario"]})
    for bot, ev in R["finalistas"].items():
        diarios[f"BOT{bot} {MODULOS[bot].NOMBRE}"] = ev["diario"]
    diarios = diarios.fillna(0.0)
    R["correlaciones"] = CA.matriz(diarios)
    utiles = [(f"BOT{b} {MODULOS[b].NOMBRE}", ev["metricas"].get("sharpe", 0))
              for b, ev in R["finalistas"].items() if ev["clase"][0] in "AB"]
    utiles.sort(key=lambda x: -(x[1] if np.isfinite(x[1]) else -9))
    base_cols = ["BOT01 RSI2", "BOT02 Zona ruido"]
    nuevas = CA.elegir_nuevas(utiles, diarios, base_cols, cfg["cartera"]["correlacion_max"])
    carteras = {"A: BOT01 + BOT02": base_cols}
    if nuevas:
        carteras["B: A + " + nuevas[0]] = base_cols + nuevas[:1]
    if len(nuevas) > 1:
        carteras["C: B + " + nuevas[1]] = base_cols + nuevas[:2]
    cap = cfg["cartera"]["capital"]
    b = cfg["bootstrap"]
    R["carteras"] = {}
    for nombre, cols in carteras.items():
        p = diarios[cols].sum(axis=1)
        R["carteras"][nombre] = {**CA.evaluar(p, cap), **MC.distribucion(p, cap, b["bloque_sesiones"], b["n"],
                                                                        b["horizonte_sesiones"], cfg["semilla"])}
    pf = cfg["prop_firm"]
    R["prop_firm"] = {}
    for nombre, cols in carteras.items():
        p = diarios[cols].sum(axis=1)
        R["prop_firm"][nombre] = [PF.simular(p, k, pf["capital"], pf["limite_diario"], pf["trailing_dd"], pf["objetivo"],
                                             pf["sesiones_max"], b["bloque_sesiones"], 2000, cfg["semilla"])
                                  for k in (1, 2, 3) if k * len(cols) <= pf["max_contratos"]]
    R["tamano"] = {}
    for bot, ev in R["finalistas"].items():
        if "riesgo_pts" not in ev["ops"] or ev["ops"].riesgo_pts.isna().all():
            continue
        filas = {}
        for rp in cfg["tamano"]["riesgo_pct"]:
            o = SZ.aplicar(ev["ops"], cap, rp, cfg["tamano"]["max_contratos"])
            d = M.diario(o, ses)
            filas[f"{rp}%"] = {**CA.evaluar(d, cap), **MC.distribucion(d, cap, b["bloque_sesiones"], b["n"],
                                                                     b["horizonte_sesiones"], cfg["semilla"]),
                               "operaciones": len(o), "contratos_medios": round(o.contratos.mean(), 2) if len(o) else 0}
        R["tamano"][bot] = pd.DataFrame(filas).T
    R["cribado_etapa1"] = {bot: {k: v for k, v in r.items() if k != "ops_variantes"} for bot, r in R1["cribado"].items()}
    R["n_variantes"] = R1["n_variantes"]
    (carpeta / "resultados.pkl").write_bytes(pickle.dumps(R))
    diarios.to_csv(carpeta / "pnl_diario_bots.csv")
    (carpeta / "log.txt").write_text("\n".join(LOG), encoding="utf-8")
    log("fin de la etapa 2")


if __name__ == "__main__":
    t0 = time.time()
    cfg = cargar_config()
    etapa = sys.argv[1] if len(sys.argv) > 1 else "investigacion"
    {"investigacion": investigacion, "test": abrir_test}[etapa](cfg)
    print(f"{time.time() - t0:.0f} s")
