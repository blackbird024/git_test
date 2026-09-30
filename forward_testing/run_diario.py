"""FORWARD_TESTING v1.0 — ejecución diaria (un solo comando). Desde la raíz del repositorio:

    python -m forward_testing.run_diario                         # descarga datos nuevos, calcula, compara e informa
    python -m forward_testing.run_diario --ea RUTA/APEX_registro_v2.csv   # además importa el registro del EA
    python -m forward_testing.run_diario --sin-descarga          # sin llamar a Databento
    python -m forward_testing.run_diario --semanal               # fuerza el informe semanal (se hace solo los viernes)

Pasos: (1) verificar congelación (hashes y parámetros) -> (2) descargar datos (coste <= 0,50 $) -> (3) calidad de datos
-> (4) forward teórico con el código congelado -> (5) integridad (append-only, precios posibles, costes, noche...) ->
(6) registrar operaciones -> (7) EA -> (8) comparación y deriva -> (9) informes. Si algo GRAVE falla, el día queda
INVALID con el motivo, y las operaciones de ese cálculo NO se añaden al registro.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from forward_testing.src import comparar as CP
from forward_testing.src import congelado as CG
from forward_testing.src import datos as DT
from forward_testing.src import deriva as DV
from forward_testing.src import ea as EA
from forward_testing.src import informes as IN
from forward_testing.src import integridad as IG
from forward_testing.src import teorico as TE

RAIZ = Path(__file__).resolve().parents[1]
FT = RAIZ / "forward_testing"
LOGS, ALERTAS, DAILY, WEEKLY, REPORTS = FT / "logs", FT / "alerts", FT / "daily", FT / "weekly", FT / "reports"
REG_TEO = LOGS / "trades_teorico.csv"
REF = RAIZ / "survivor" / "experimentos" / "20260930_0939"


def log(msg: str):
    linea = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {msg}"
    print(linea, flush=True)
    with open(LOGS / "ejecuciones.log", "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def cargar_registro() -> pd.DataFrame:
    if not REG_TEO.exists():
        return pd.DataFrame()
    r = pd.read_csv(REG_TEO)
    r["t_entrada_utc"] = pd.to_datetime(r.t_entrada_utc, utc=True)
    r["t_salida_utc"] = pd.to_datetime(r.t_salida_utc, utc=True)
    return r


def referencia() -> dict:
    return {"NOISE_ZONE": pd.read_csv(REF / "operaciones_NOISE_ZONE.csv"), "RSI2": pd.read_csv(REF / "operaciones_RSI2.csv")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ea", type=Path)
    ap.add_argument("--sin-descarga", action="store_true")
    ap.add_argument("--semanal", action="store_true")
    ap.add_argument("--fecha", help="día a informar (AAAA-MM-DD, NY); por defecto el último día RTH completo")
    a = ap.parse_args(argv)
    for d in (LOGS, ALERTAS, DAILY, WEEKLY, REPORTS):
        d.mkdir(parents=True, exist_ok=True)
    cfg = CG.cargar()
    cfg_hash = CG.HUELLA.read_text().strip()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    log(f"inicio | commit {commit[:10]} | config {cfg_hash[:12]}")
    motivos, avisos = [], []
    # (1) congelación
    motivos += [f"CONGELACIÓN: {p}" for p in CG.verificar()]
    motivos += [f"DATOS DESCARGADOS: {p}" for p in DT.verificar_raw()]
    # (2) datos
    if not a.sin_descarga:
        r = DT.descargar(log=log)
        log(f"descarga: {r['estado']} — {r['detalle']}")
        if r["estado"] == "NO DESCARGADO":
            avisos.append(f"datos no descargados: {r['detalle']}")
    m1 = DT.conjunto()
    inicio = pd.Timestamp(cfg["inicio_forward"]["fecha"])
    inicio_utc = inicio.tz_localize("America/New_York").tz_convert("UTC")
    # (4) teórico
    t = TE.calcular(m1, inicio)
    fecha = pd.Timestamp(a.fecha) if a.fecha else (t["ultimo_dia_completo"] or inicio)
    # (3) calidad del día informado
    for grav, txt in DT.calidad_dia(m1, fecha):
        (motivos if grav == "GRAVE" else avisos).append(f"DATOS {fecha.date()}: {txt}")
    todas = pd.concat([t[k] for k in ("NOISE_ZONE", "RSI2") if len(t[k])], ignore_index=True) if any(len(t[k]) for k in ("NOISE_ZONE", "RSI2")) else pd.DataFrame()
    # (5) integridad
    for k in ("NOISE_ZONE", "RSI2"):
        motivos += [f"INTEGRIDAD {k}: {p}" for p in IG.operaciones(t[k], m1, inicio_utc, k)]
    registradas = cargar_registro()
    motivos += [f"APPEND-ONLY: {p}" for p in IG.append_only(registradas, todas)]
    estado = {"estado": "INVALID" if motivos else "VALID", "motivos": motivos + [f"(aviso) {x}" for x in avisos], "ea_leido": False}
    # (6) registrar (solo si el día es válido)
    if len(todas) and not motivos:
        cerradas_nuevas = todas[todas.estado == "CERRADA"]
        ya = set(registradas.id) if len(registradas) else set()
        nuevas = cerradas_nuevas[~cerradas_nuevas.id.isin(ya)]
        if len(nuevas):
            nuevas.assign(registrado_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"), config_sha256=cfg_hash) \
                  .to_csv(REG_TEO, mode="a", header=not REG_TEO.exists(), index=False)
            log(f"registradas {len(nuevas)} operaciones nuevas")
        todas[todas.estado == "ABIERTA"].to_csv(LOGS / "posiciones_abiertas.csv", index=False)
    registradas = cargar_registro()
    cerradas = {k: (registradas[registradas.estrategia == k].sort_values("t_salida_utc").reset_index(drop=True)
                    if len(registradas) else pd.DataFrame()) for k in ("NOISE_ZONE", "RSI2")}
    abiertas = todas[todas.estado == "ABIERTA"] if len(todas) else pd.DataFrame()
    # (7) EA
    ea, emp = pd.DataFrame(), pd.DataFrame()
    if a.ea:
        destino = FT / "raw" / "ea" / f"APEX_registro_v2_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.csv"
        shutil.copy(a.ea, destino)
        with open(FT / "raw" / "ea" / "MANIFIESTO.csv", "a", encoding="utf-8") as f:
            f.write(f"{destino.name},{hashlib.sha256(destino.read_bytes()).hexdigest()}\n")
        ea, prob = EA.operaciones(EA.leer(destino))
        estado["ea_leido"] = True
        estado["motivos"] += [f"(aviso EA) {p}" for p in prob]
        ea.to_csv(LOGS / "trades_ea.csv", index=False)
        if len(ea):
            teo = pd.concat([v for v in cerradas.values() if len(v)] + ([abiertas] if len(abiertas) else []), ignore_index=True) \
                if any(len(v) for v in cerradas.values()) or len(abiertas) else pd.DataFrame()
            emp = EA.emparejar(teo, ea) if len(teo) else pd.DataFrame()
            emp.to_csv(LOGS / "emparejamiento.csv", index=False)
    # (8) comparación y deriva
    ref = referencia()
    mm = pd.read_csv(FT / "config" / "referencia_mae_mfe.csv")
    comp = {k: CP.comparar(ref[k], cerradas[k], cfg["muestras_minimas_para_comparar"][k], mm[mm.estrategia == k], k)
            for k in ("NOISE_ZONE", "RSI2")}
    ruta_b = FT / "config" / "bandas_deriva_v1.json"
    b = json.loads(ruta_b.read_text(encoding="utf-8"))
    oficial = {k: v["umbral_oficial"] for k, v in cfg["deriva"].items() if k in ("NOISE_ZONE", "RSI2")}
    bp = json.loads((FT / "config" / "bandas_deriva_v1_pct.json").read_text(encoding="utf-8"))
    der = pd.concat([DV.evaluar(cerradas, b, oficial, "neto_$"), DV.evaluar(cerradas, bp, {}, "neto_%")], ignore_index=True)
    malas = der[der.estado.str.contains("WARNING|ALERT", regex=True)]
    if len(malas):
        malas.assign(fecha=str(fecha.date()), registrado_utc=datetime.now(timezone.utc).isoformat(timespec="seconds")) \
             .to_csv(ALERTAS / "alertas.csv", mode="a", header=not (ALERTAS / "alertas.csv").exists(), index=False)
    # (9) informes
    texto = IN.diario(fecha, estado, cerradas, abiertas, ea, emp, der, comp, cfg_hash, t["senal_rsi2_pendiente"])
    (DAILY / f"{fecha.date()}.md").write_text(texto, encoding="utf-8")
    pd.DataFrame([{"fecha": str(fecha.date()), "estado": estado["estado"], "motivos": " | ".join(estado["motivos"]),
                   "config_sha256": cfg_hash, "commit": commit, "ejecutado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}]) \
        .to_csv(LOGS / "estado_dias.csv", mode="a", header=not (LOGS / "estado_dias.csv").exists(), index=False)
    ventanas = {k: v["ventanas"] for k, v in cfg["deriva"].items() if k in ("NOISE_ZONE", "RSI2")}
    if a.semanal or fecha.weekday() == 4:
        semana = fecha.strftime("%G-W%V")
        (WEEKLY / f"{semana}.md").write_text(IN.semanal(semana, cerradas, ea, der, comp, ventanas), encoding="utf-8")
    resumen = ["# BACKTEST vs FORWARD (última ejecución)", "", f"Fecha: {fecha.date()} · estado {estado['estado']}", ""]
    for k, c in comp.items():
        resumen += [f"## {k}", f"Rango: {c['rango']}", "", IN._tabla(c["tabla"])]
    (REPORTS / "backtest_vs_forward.md").write_text("\n".join(resumen), encoding="utf-8")
    log(f"fin | {fecha.date()} {estado['estado']} | {'; '.join(estado['motivos']) or 'sin incidencias'}")
    return estado


if __name__ == "__main__":
    main()
