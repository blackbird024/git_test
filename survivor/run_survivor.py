"""SURVIVOR ANALYSIS v1.0 — ejecución completa (reglas congeladas; todo NOT OUT-OF-SAMPLE).

    python -m survivor.run_survivor          -> survivor/experimentos/<AAAAMMDD_HHMM>/ (resultados.pkl, CSV, manifiesto)
    python -m survivor.generar_informe       -> reports/SURVIVOR_ANALYSIS_FINAL.md + gráficos
"""
from __future__ import annotations

import hashlib
import json
import pickle
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from auditoria.src import metricas as mt
from bot_lab.core.datos import Contexto
from forward_testing.src import deriva
from src.data.datos import excluidos, velas_1m
from src.strategies import nq_rsi2

from .src import caracteristicas as CA
from .src import cartera as CT
from .src import congeladas as K
from .src import estres as ES
from .src import falsacion as FA
from .src import temporal as TE
from .src import trayectorias as TR

RAIZ = Path(__file__).resolve().parents[1]
SEMILLA, NB, NB_CELDA = 20260930, 5000, 2000
CORTE_DEV = pd.Timestamp("2023-03-22")
CAPITAL = 25000
LOG = []


def log(m):
    linea = f"[{datetime.now():%H:%M:%S}] {m}"
    print(linea, flush=True)
    LOG.append(linea)


def resumen(o: pd.DataFrame, ses) -> dict:
    x = o.neto.to_numpy()
    d = mt.diario(o, ses)
    return {"operaciones": len(x), "PF": TE._pf(x), "expectativa_$": round(x.mean(), 2), "neto_$": round(x.sum(), 0),
            "t": round(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))), 2) if len(x) > 2 else np.nan,
            "IC95_bloques_$": mt.ic_bloques(d, 20, NB, SEMILLA) if len(x) > 2 else (np.nan, np.nan),
            "acierto_%": round((x > 0).mean() * 100, 1)}


def veredicto_umbral(exp_por_nivel: list[tuple[str, float]], conf: str, weak: str) -> str:
    """exp_por_nivel en orden creciente de estrés. conf/weak = nombre del nivel que debe ser > 0."""
    e = dict(exp_por_nivel)
    if e[conf] > 0:
        return "CONFIRMATION"
    if e[weak] > 0:
        return "WEAK EVIDENCE"
    return "CONTRADICTION"


def main():
    t0 = time.time()
    K.comprobar_integridad()
    carpeta = RAIZ / "survivor" / "experimentos" / datetime.now().strftime("%Y%m%d_%H%M")
    carpeta.mkdir(parents=True, exist_ok=False)
    git = lambda *a: subprocess.run(["git", *a], cwd=RAIZ, capture_output=True, text=True).stdout.strip()  # noqa: E731
    f = RAIZ / "data" / "processed" / "NQ_1M.parquet"
    (carpeta / "manifiesto.json").write_text(json.dumps({
        "fecha_utc": datetime.now(timezone.utc).isoformat(), "commit": git("rev-parse", "HEAD"),
        "cambios_sin_commit": git("status", "--porcelain"), "python": sys.version.split()[0], "pandas": pd.__version__,
        "numpy": np.__version__, "semilla": SEMILLA, "sha256_fuentes": K.SHA256,
        "datos": {str(f.relative_to(RAIZ)): hashlib.sha1(f.read_bytes()).hexdigest()},
        "fuera_de_muestra": "NO: todo el periodo 2015-2026 ya se había visto (TEST_CONTAMINATION_LOG.md)"}, indent=2), encoding="utf-8")
    m1, ex = velas_1m("NQ"), excluidos("NQ")
    ctx = Contexto(m1, ex)
    ses = ctx.sesiones_rth
    R = {"carpeta": carpeta.name}
    log("Reglas congeladas: reproducción")
    zr, rs = K.zona_ruido(m1, ex), K.rsi2(m1, ex)
    a_r = pd.read_csv(K.AUDITORIA / "operaciones_rsi2.csv")
    a_z = pd.read_csv(K.AUDITORIA / "operaciones_zona_ruido.csv")
    R["reproduccion"] = {"RSI2": bool(len(rs) == len(a_r) and np.allclose(rs.neto, a_r.neto)),
                         "NOISE_ZONE": bool(len(zr) == len(a_z) and np.allclose(zr.neto, a_z.neto))}
    s_rsi = nq_rsi2.preparar(m1, K.RSI2_SURVIVOR_V1)
    ops = {"RSI2": rs, "NOISE_ZONE": zr}
    R["base"] = {k: resumen(o, ses) for k, o in ops.items()}

    log("Rasgos previos a la entrada y trayectorias")
    d = CA.tabla_diaria(ctx)
    feats = {"NOISE_ZONE": CA.zona_ruido(ctx, zr, d), "RSI2": CA.rsi2(ctx, rs, d, s_rsi)}
    tray = {"NOISE_ZONE": TR.zona_ruido(ctx, zr), "RSI2": TR.rsi2(rs, s_rsi)}
    for k in ops:
        feats[k].assign(neto=ops[k].neto.to_numpy()).to_csv(carpeta / f"rasgos_{k}.csv", index=False)
    # normalización por precio y ATR
    norm = {}
    norm["NOISE_ZONE"] = pd.DataFrame({"pts": zr.neto / 2.0, "%_precio": zr.neto / 2.0 / zr.entrada * 100,
                                       "ATR_d": zr.neto / 2.0 / feats["NOISE_ZONE"].atr14})
    norm["RSI2"] = pd.DataFrame({"pts": rs.neto / 2.0, "%_precio": rs["ret_%"], "ATR_d": rs.neto / 2.0 / feats["RSI2"].atr14,
                                 "R_proyecto": rs.r})
    R["normalizado"] = {k: pd.DataFrame({"media": v.mean(), "mediana": v.median(),
                                         "t": v.mean() / (v.std() / np.sqrt(v.count()))}).round(4) for k, v in norm.items()}
    # por año de la versión normalizada (¿el edge crece con el precio?)
    R["normalizado_anual"] = {k: v.groupby(TE.fechas_salida(ops[k]).year).mean().round(4) for k, v in norm.items()}

    log("Regímenes (Q1-Q4)")
    minimo = {"NOISE_ZONE": 30, "RSI2": 15}
    variables = {"NOISE_ZONE": ["VOL_ATR", "VOL_REAL", "TENDENCIA", "VWAP", "HUECO", "apertura", "NOCHE_RET", "NOCHE_RANGO",
                                "RANGO_PREVIO", "DIST_CIERRE_ANT", "HORA", "DIA", "LADO"],
                 "RSI2": ["VOL_ATR", "VOL_REAL", "TENDENCIA", "RSI_NIVEL", "MOV_PREVIO", "DIST_SMA200", "VWAP", "HUECO",
                          "apertura", "NOCHE_RET", "NOCHE_RANGO", "RANGO_PREVIO", "DIA"]}
    ordenes = {"VOL_ATR": ["BAJA", "NORMAL", "ALTA"], "VOL_REAL": ["baja", "media", "alta"],
               "TENDENCIA": ["TREND UP", "RANGE", "TREND DOWN"], "RANGO_PREVIO": ["contracción", "normal", "expansión"],
               "DIA": ["lunes", "martes", "miércoles", "jueves", "viernes"],
               "HORA": ["10:00", "10:30-11:00", "11:30-13:30 mediodía", "14:00-15:30 tarde"]}
    R["regimenes"], R["veredictos_regimen"] = {}, {}
    for k, o in ops.items():
        R["regimenes"][k] = {}
        for v in variables[k]:
            t = TE.celdas(o, feats[k][v].to_numpy(), ses, minimo[k], NB_CELDA, SEMILLA, ordenes.get(v))
            R["regimenes"][k][v] = t
        R["veredictos_regimen"][k] = {v: TE.veredicto_regimen(R["regimenes"][k][v]) for v in ("VOL_ATR", "VOL_REAL", "TENDENCIA")}
    # rasgos cruzados entre bots: régimen de un día aplicado al otro (Q9)
    log("Q5: ganadoras frente a perdedoras (rasgos previos)")
    R["q5"] = {}
    num = {"NOISE_ZONE": ["dist_vwap_atr", "dist_cierre_ant_atr", "hueco_atr", "noche_ret_atr", "noche_rango_atr", "rango_previo_atr", "atr14"],
           "RSI2": ["rsi_senal", "dist_sma200_%", "ret_dia_atr", "dist_vwap_atr", "hueco_atr", "noche_ret_atr", "noche_rango_atr", "rango_previo_atr", "atr14"]}
    for k, o in ops.items():
        g = o.neto.to_numpy() > 0
        filas = {}
        for c in num[k]:
            x = feats[k][c].astype(float).to_numpy()
            a, b = x[g & np.isfinite(x)], x[~g & np.isfinite(x)]
            p = mannwhitneyu(a, b).pvalue if len(a) > 5 and len(b) > 5 else np.nan
            filas[c] = {"mediana_ganadoras": round(np.median(a), 3), "mediana_perdedoras": round(np.median(b), 3),
                        "p_MannWhitney": round(p, 4), "p_Bonferroni": round(min(1, p * len(num[k])), 4)}
        R["q5"][k] = pd.DataFrame(filas).T

    log("MAE/MFE, horizontes y tiempo hasta fallar")
    R["mae_mfe"] = {"NOISE_ZONE": TR.resumen_mae_mfe(zr, tray["NOISE_ZONE"], "mae_pts", "mfe_pts"),
                    "RSI2": TR.resumen_mae_mfe(rs, tray["RSI2"], "mae_%", "mfe_%")}
    tz = tray["NOISE_ZONE"]
    R["horizontes"] = {"NOISE_ZONE": pd.DataFrame({h: {"media_pts_sin_costes": round(tz[f"pts_a_{h}min"].mean(), 3),
                                                       "t": round(tz[f"pts_a_{h}min"].mean() / (tz[f"pts_a_{h}min"].std() / np.sqrt(tz[f"pts_a_{h}min"].count())), 2),
                                                       "n": int(tz[f"pts_a_{h}min"].count())} for h in (5, 15, 30, 60)}).T,
                       "RSI2": pd.DataFrame({h: {"media_%": round(tray["RSI2"][f"ret_%_a_{h}ses"].mean(), 3),
                                                 "t": round(tray["RSI2"][f"ret_%_a_{h}ses"].mean() / (tray["RSI2"][f"ret_%_a_{h}ses"].std() / np.sqrt(tray["RSI2"][f"ret_%_a_{h}ses"].count())), 2)}
                                             for h in range(1, 6)}).T}
    R["horizontes"]["NOISE_ZONE_salida_real_pts"] = round((zr.neto / 2 + 2 * 0.25 + 1.0).mean(), 3)   # bruto sin costes aprox.
    R["captura_mfe"] = {"NOISE_ZONE": round(float((zr.neto[zr.neto > 0] / 2 / tz.mfe_pts[zr.neto > 0]).median()), 3),
                        "RSI2": round(float((rs["ret_%"][rs.neto > 0] / tray["RSI2"]["mfe_%"][rs.neto > 0]).median()), 3)}
    R["tiempo_fallo"] = {"NOISE_ZONE": TR.tiempo_hasta_fallar(zr, tz)}
    b30 = tz.en_beneficio_a_30min
    R["tiempo_fallo"]["NOISE_ZONE_estado_30min"] = pd.DataFrame({
        est: {"operaciones": int((b30 == v).sum()), "acierto_final_%": round((zr.neto[b30 == v] > 0).mean() * 100, 1),
              "expectativa_final_$": round(zr.neto[b30 == v].mean(), 2)} for est, v in (("en beneficio a +30 min", 1.0), ("sin beneficio a +30 min", 0.0))}).T
    g = rs.groupby("sesiones")
    R["tiempo_fallo"]["RSI2"] = pd.DataFrame({"operaciones": g.size(), "acierto_%": g.neto.apply(lambda s: round((s > 0).mean() * 100, 1)),
                                              "expectativa_$": g.neto.mean().round(2), "neto_$": g.neto.sum().round(0)})
    R["tiempo_fallo"]["RSI2_motivo"] = rs.groupby("motivo").neto.agg(["size", "mean", "sum"]).round(2)

    log("Temporal: años, meses, móviles, walk-forward congelado, subperiodos, concentración, atípicos, rachas")
    R["temporal"] = {}
    for k, o in ops.items():
        dia = mt.diario(o, ses)
        anual = TE.por_ventana(o, "Y")
        top = anual["P&L_$"].max() / anual["P&L_$"].sum() * 100
        frac = (anual["P&L_$"] > 0).mean()
        ver_anual = ("CONFIRMATION" if frac >= 0.6 and top <= 50 else "CONTRADICTION" if frac < 0.6 and top > 50 else "WEAK EVIDENCE")
        trim = TE.por_ventana(o, "Q")
        wf_fr = (trim["P&L_$"] > 0).mean() if k == "NOISE_ZONE" else (anual["P&L_$"] > 0).mean()
        sub = TE.subperiodos(o)
        npos = int((sub["P&L_$"] > 0).sum())
        R["temporal"][k] = {
            "anual": anual, "trimestral": trim, "mensual": TE.mensual(dia.pnl), "moviles": TE.moviles(dia.pnl, dia.n),
            "subperiodos": sub, "concentracion": TE.concentracion(o, dia.pnl), "sin_mejores": TE.sin_mejores(o),
            "rachas_mc": TE.rachas_vs_mc(o, NB, SEMILLA), "rachas_dist": TE.distribucion_rachas(o.neto.to_numpy()),
            "año_top_%": round(top, 1), "años_positivos_frac": round(frac, 2),
            "veredicto_años": ver_anual,
            "veredicto_wf": "CONFIRMATION" if wf_fr >= 0.6 else "WEAK EVIDENCE" if wf_fr >= 0.45 else "CONTRADICTION",
            "wf_frac_positivas": round(wf_fr, 3), "wf_ventana": "trimestral" if k == "NOISE_ZONE" else "anual",
            "veredicto_subperiodos": "CONFIRMATION" if npos == 4 else "WEAK EVIDENCE" if npos == 3 else "CONTRADICTION"}
        sm = R["temporal"][k]["sin_mejores"]
        e5, e1 = sm.loc["sin los 5 mejores", "expectativa_$"], sm.loc["sin los 1 mejores", "expectativa_$"]
        R["temporal"][k]["veredicto_atipicos"] = "CONFIRMATION" if e5 > 0 else "WEAK EVIDENCE" if e1 > 0 else "CONTRADICTION"
        rm = R["temporal"][k]["rachas_mc"]
        dentro = [(rm.loc[i, "observada"] >= rm.loc[i, "p5_MC"]) and (rm.loc[i, "observada"] <= rm.loc[i, "p95_MC"]) for i in rm.index]
        R["temporal"][k]["veredicto_rachas"] = "CONFIRMATION" if all(dentro) else "WEAK EVIDENCE"

    log("Crisis / extremos")
    R["crisis"] = {}
    for k, o in ops.items():
        filas = {}
        for c in ("CRISIS_VOL", "CRISIS_CRASH", "CRISIS_TENDENCIA"):
            m = feats[k][c].astype(bool).to_numpy()
            for etiqueta, mask in ((f"{c} (sí)", m), (f"{c} (no)", ~m)):
                g_ = o[mask]
                ic = mt.ic_bloques(mt.diario(g_, ses), 20, NB_CELDA, SEMILLA) if len(g_) >= 15 else (np.nan, np.nan)
                filas[etiqueta] = {"operaciones": len(g_), "expectativa_$": round(g_.neto.mean(), 2) if len(g_) else np.nan,
                                   "P&L_$": round(g_.neto.sum(), 0), "PF": TE._pf(g_.neto) if len(g_) else np.nan, "IC95_$": ic}
        t = pd.DataFrame(filas).T
        ver = {}
        for c in ("CRISIS_VOL", "CRISIS_CRASH", "CRISIS_TENDENCIA"):
            f_ = t.loc[f"{c} (sí)"]
            if f_.operaciones < 15:
                ver[c] = "INCONCLUSIVE"
            elif f_["expectativa_$"] >= 0:
                ver[c] = "CONFIRMATION"
            elif f_["IC95_$"][1] < 0:
                ver[c] = "CONTRADICTION"
            else:
                ver[c] = "WEAK EVIDENCE"
        R["crisis"][k] = {"tabla": t, "veredictos": ver}

    log("Estrés: costes, deslizamiento, retraso, sensibilidad")
    R["estres"] = {"NOISE_ZONE": {}, "RSI2": {}}
    for mult, et in ((1.0, "BASE"), (1.5, "1.5x"), (2.0, "2x"), (3.0, "3x")):
        R["estres"]["NOISE_ZONE"][f"costes {et}"] = resumen(K.zona_ruido(m1, ex, K.cfg_zr_costes(mult)), ses)
        R["estres"]["RSI2"][f"costes {et}"] = resumen(K.rsi2(m1, ex, K.RSI2_SURVIVOR_V1.con(costes=K.costes_rsi2(mult))), ses)
    for tk in (1, 2, 3):
        R["estres"]["NOISE_ZONE"][f"+{tk} tick"] = resumen(K.zona_ruido(m1, ex, K.cfg_zr_costes(1.0, tk)), ses)
        R["estres"]["RSI2"][f"+{tk} tick"] = resumen(K.rsi2(m1, ex, K.RSI2_SURVIVOR_V1.con(costes=K.costes_rsi2(1.0, tk))), ses)
    for r in (1, 2, 3, 5):
        R["estres"]["NOISE_ZONE"][f"retraso +{r}m"] = resumen(ES.zr_retardo(m1, ex, r), ses)
        R["estres"]["RSI2"][f"retraso +{r}m"] = resumen(ES.rsi2_retardo(m1, ex, r), ses)
    R["sensibilidad"] = {"RSI2": pd.DataFrame({k: resumen(K.rsi2(m1, ex, c), ses) for k, c in ES.sensibilidad_rsi2().items()}).T,
                         "NOISE_ZONE": pd.DataFrame({k: resumen(K.zona_ruido(m1, ex, c), ses) for k, c in ES.sensibilidad_zr().items()}).T}
    R["veredictos_estres"] = {}
    for k in ops:
        e = {n: v["expectativa_$"] for n, v in R["estres"][k].items()}
        sen = R["sensibilidad"][k]["expectativa_$"].astype(float)
        fr = (sen > 0).mean()
        R["veredictos_estres"][k] = {
            "costes": veredicto_umbral(list(e.items()), "costes 2x", "costes 1.5x"),
            "deslizamiento": veredicto_umbral(list(e.items()), "+2 tick", "+1 tick"),
            "retraso": veredicto_umbral(list(e.items()), "retraso +3m", "retraso +1m"),
            "sensibilidad": "CONFIRMATION" if fr == 1 else "WEAK EVIDENCE" if fr >= 2 / 3 else "CONTRADICTION"}
        if e["costes 1.5x"] > 0 >= e["costes 2x"]:
            R["veredictos_estres"][k]["costes"] += " (COST FRAGILITY)"

    log("Aleatorización (1.000 réplicas por prueba)")
    R["aleatorizacion"] = {"NOISE_ZONE dirección aleatoria (N1)": FA.zr_direccion(zr, 1000, SEMILLA),
                           "NOISE_ZONE momento aleatorio (N2)": FA.zr_momento(ctx, zr, 1000, SEMILLA),
                           "RSI2 días al azar con SMA200 (N1)": FA.rsi2_dias(rs, s_rsi, 1000, SEMILLA, True, ex),
                           "RSI2 días al azar sin filtro (N2)": FA.rsi2_dias(rs, s_rsi, 1000, SEMILLA, False, ex)}
    for v in R["aleatorizacion"].values():
        p = v["p_valor"]
        v["veredicto"] = "CONFIRMATION" if p <= 0.05 else "WEAK EVIDENCE" if p <= 0.20 else "CONTRADICTION"

    log("NQ frente a MNQ")
    pts_z, pts_r = zr.bruto / 2.0, (rs.neto + 2.0) / 2.0          # puntos brutos (con deslizamiento), sin comisión
    R["nq_mnq"] = pd.DataFrame({
        "NOISE_ZONE": {"puntos_medios_con_desl": round(pts_z.mean(), 3), "MNQ_neto_$ (2 $/pt, 1 $/lado)": round((pts_z * 2 - 2).mean(), 2),
                       "NQ_neto_$ (20 $/pt, 2,5 $/lado supuesto)": round((pts_z * 20 - 5).mean(), 2),
                       "comisión/bruto medio MNQ_%": round(2 / abs(pts_z.mean() * 2) * 100, 1),
                       "comisión/bruto medio NQ_%": round(5 / abs(pts_z.mean() * 20) * 100, 1)},
        "RSI2": {"puntos_medios_con_desl": round(pts_r.mean(), 3), "MNQ_neto_$ (2 $/pt, 1 $/lado)": round((pts_r * 2 - 2).mean(), 2),
                 "NQ_neto_$ (20 $/pt, 2,5 $/lado supuesto)": round((pts_r * 20 - 5).mean(), 2),
                 "comisión/bruto medio MNQ_%": round(2 / abs(pts_r.mean() * 2) * 100, 1),
                 "comisión/bruto medio NQ_%": round(5 / abs(pts_r.mean() * 20) * 100, 1)}})

    log("Cartera a igual riesgo, correlaciones y Monte Carlo")
    mtm = CT.rsi2_mtm(rs, s_rsi, None)
    zr_d = mt.diario(zr, ses).pnl
    idx = zr_d.index.union(mtm.index)
    dd = pd.DataFrame({"zr": zr_d.reindex(idx, fill_value=0.0), "rsi2": mtm.reindex(idx, fill_value=0.0)})
    dd = dd[(dd.index >= ses[0]) & (dd.index <= ses[-1])]
    R["mtm_check"] = {"suma_mtm": round(mtm.sum(), 2), "suma_neto": round(rs.neto.sum(), 2)}
    rs_salida = mt.diario(rs, ses).pnl
    R["rsi2_dd_mtm_vs_salida"] = {"DD_mtm_$": TE._dd(dd.rsi2), "DD_por_dia_de_salida_$": TE._dd(rs_salida)}
    R["correlaciones"] = CT.correlaciones(dd)
    et = pd.DataFrame(index=dd.index)
    reg = CA.clases_regimen(d.shift(1)).set_index(d.index)          # régimen del día anterior
    et["VOL_ATR"] = reg.VOL_ATR.reindex(dd.index).fillna("sin dato").to_numpy()
    et["TENDENCIA"] = reg.TENDENCIA.reindex(dd.index).fillna("sin dato").to_numpy()
    R["corr_condicionadas"] = CT.condicionadas(dd, et)
    # por franja de la ZR
    zt = pd.DatetimeIndex(zr.t_entrada).tz_convert("America/New_York")
    mins = zt.hour * 60 + zt.minute
    for nombre, m in (("ZR entradas 10:00-11:00", (mins < 690)), ("ZR entradas 14:00-15:30", (mins >= 840))):
        z_ = mt.diario(zr[np.asarray(m)], ses).pnl.reindex(dd.index, fill_value=0.0)
        both = (z_ != 0) & (dd.rsi2 != 0)
        R["corr_condicionadas"].loc[nombre] = {"dias": int((z_ != 0).sum()), "corr_todos_los_dias": round(z_.corr(dd.rsi2), 3),
                                               "dias_con_ambas": int(both.sum()),
                                               "corr_dias_con_ambas": round(z_[both].corr(dd.rsi2[both]), 3) if both.sum() > 20 else np.nan}
    cc = R["corr_condicionadas"]
    glob = abs(R["correlaciones"]["diaria"])
    mx = np.nanmax(np.abs(cc.corr_todos_los_dias.astype(float)))
    R["veredicto_q7"] = "CONFIRMATION" if glob < 0.2 and mx < 0.3 else "WEAK EVIDENCE" if glob < 0.2 else "CONTRADICTION"
    R["solapamiento"] = CT.solapamiento(zr, rs)
    R["cartera"] = {}
    for rep in (1.0, 0.75, 0.5, 0.25, 0.0):
        wz, wr = CT.pesos(dd, CORTE_DEV, rep)
        p = wz * dd.zr + wr * dd.rsi2
        R["cartera"][f"{int(rep * 100)}/{int(round((1 - rep) * 100))}"] = {"pesos (ZR, RSI2) en MNQ": (wz, wr),
                                                                           "vol_diaria_$": round(p.std(), 1),
                                                                           **CT.metricas(p, CAPITAL), **CT.montecarlo(p, NB, SEMILLA)}
    p11 = dd.zr + dd.rsi2
    R["cartera"]["1+1 MNQ (EA actual, MÁS riesgo)"] = {"pesos (ZR, RSI2) en MNQ": (1.0, 1.0), "vol_diaria_$": round(p11.std(), 1),
                                                       **CT.metricas(p11, CAPITAL), **CT.montecarlo(p11, NB, SEMILLA)}
    tc = pd.DataFrame(R["cartera"]).T
    dd95 = tc["MC_DD_p95_$"].astype(float)
    mezclas = dd95[["75/25", "50/50", "25/75"]]
    R["veredicto_q8"] = ("CONFIRMATION" if (mezclas > max(dd95["100/0"], dd95["0/100"])).any() else
                         "WEAK EVIDENCE" if (mezclas > min(dd95["100/0"], dd95["0/100"])).any() else "CONTRADICTION")
    # Q9: expectativa de cada bot por régimen del mismo día
    R["q9"] = {k: {v: R["regimenes"][k][v][["operaciones", "expectativa_$"]] for v in ("VOL_ATR", "TENDENCIA")} for k in ops}
    # Monte Carlo individual (1 MNQ) para la tabla de evidencia
    R["mc_individual"] = {"NOISE_ZONE": CT.montecarlo(dd.zr, NB, SEMILLA), "RSI2": CT.montecarlo(dd.rsi2, NB, SEMILLA)}
    for k in ops:
        pdd = R["mc_individual"][k]["P(DD ≥ 5000 $)_%"]
        R["mc_individual"][k]["veredicto"] = "CONFIRMATION" if pdd < 10 else "WEAK EVIDENCE" if pdd <= 25 else "CONTRADICTION"

    log("Forward: bandas de deriva y referencia del backtest")
    R["bandas_deriva"] = {k: deriva.bandas(o.neto.to_numpy(), {"NOISE_ZONE": 50, "RSI2": 15}[k]) for k, o in ops.items()}
    ref = {}
    for k, o in ops.items():
        meses = (o.t_salida.max() - o.t_entrada.min()).days / 30.4
        ref[k] = {"operaciones_mes": round(len(o) / meses, 1), "acierto_%": round((o.neto > 0).mean() * 100, 1),
                  "expectativa_$": round(o.neto.mean(), 2), "dd_p95_1_año_$": R["mc_individual"][k]["MC_DD_p95_$"]}
    (RAIZ / "forward_testing" / "config" / "referencia_backtest.json").write_text(json.dumps(ref, indent=2), encoding="utf-8")
    R["referencia_forward"] = ref
    R["series"] = {"diario": dd, "zr": zr, "rsi2": rs, "rsi2_salida": rs_salida}
    zr.to_csv(carpeta / "operaciones_NOISE_ZONE.csv", index=False)
    rs.to_csv(carpeta / "operaciones_RSI2.csv", index=False)
    dd.to_csv(carpeta / "pnl_diario_mtm.csv")
    (carpeta / "resultados.pkl").write_bytes(pickle.dumps(R))
    (carpeta / "log.txt").write_text("\n".join(LOG), encoding="utf-8")
    log(f"fin ({time.time() - t0:.0f} s) -> {carpeta.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
