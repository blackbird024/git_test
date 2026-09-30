"""Forward de EJECUCIÓN: el EA APEX_Multiestrategia en la demo (CFD NAS100 de Pepperstone).

Lee el registro del EA (MQL5/Files/APEX_registro_v2.csv; también el v1 antiguo, sin bid/ask), empareja cada entrada
(COMPRAR/VENDER) con su CERRAR de la misma estrategia y calcula:
  - deslizamiento = precio de ejecución − precio de referencia (ask para comprar / bid para vender, tomado justo antes
    de enviar la orden), en puntos, positivo = en contra;
  - spread en el momento de la orden;
  - P&L en $ = puntos × lotes × 1 $/punto/lote (NAS100 de Pepperstone). Sin comisión (CFD: el coste va en el spread).
    El swap NO está en el registro (exportar el historial de MT5 si se quiere).
El CFD NO es el futuro: estas cifras miden la EJECUCIÓN, no la estrategia pura (ver PROTOCOLO).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

NOMBRES = {"zona de ruido": "NOISE_ZONE", "rsi(2)": "RSI2", "rsi2": "RSI2"}
VALOR_PUNTO_LOTE = 1.0


def leer(ruta) -> pd.DataFrame:
    r = pd.read_csv(ruta, dtype=str)
    for c in ("precio", "bid_previo", "ask_previo", "spread_previo", "lotes"):
        if c in r:
            r[c] = pd.to_numeric(r[c], errors="coerce")
    r["t_ny"] = pd.to_datetime(r.hora_NY, format="%Y.%m.%d %H:%M:%S", errors="coerce")
    r["estrategia_id"] = r.estrategia.str.lower().map(lambda x: next((v for k, v in NOMBRES.items() if k in x), x))
    return r.sort_values("t_ny", kind="stable").reset_index(drop=True)


def operaciones(reg: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    filas, abiertas, problemas = [], {}, []
    for _, x in reg.iterrows():
        est = x.estrategia_id
        if x.accion in ("COMPRAR", "VENDER"):
            if est in abiertas:
                problemas.append(f"{est}: nueva entrada {x.hora_NY} con otra posición abierta sin CERRAR registrado")
            abiertas[est] = x
        elif x.accion == "CERRAR":
            if est not in abiertas:
                problemas.append(f"{est}: CERRAR {x.hora_NY} sin entrada registrada")
                continue
            e = abiertas.pop(est)
            d = 1 if e.accion == "COMPRAR" else -1
            lotes = e.get("lotes", np.nan)
            lotes = 2.0 if pd.isna(lotes) else float(lotes)
            ref_e = e.get("ask_previo") if d == 1 else e.get("bid_previo")
            ref_x = x.get("bid_previo") if d == 1 else x.get("ask_previo")
            ref_e = np.nan if ref_e is None or ref_e == 0 else ref_e
            ref_x = np.nan if ref_x is None or ref_x == 0 else ref_x
            pts = d * (x.precio - e.precio)
            filas.append({
                "id_ea": f"{est}|{e.t_ny:%Y-%m-%dT%H:%M}NY", "estrategia": est, "direccion": "LARGO" if d == 1 else "CORTO",
                "t_entrada_ny": e.t_ny, "t_salida_ny": x.t_ny, "duracion_min": (x.t_ny - e.t_ny).total_seconds() / 60,
                "contrato": "CFD NAS100 (Pepperstone)", "lotes": lotes,
                "precio_referencia_entrada": ref_e, "precio_real_entrada": e.precio,
                "precio_referencia_salida": ref_x, "precio_real_salida": x.precio,
                "slippage_entrada_pts": d * (e.precio - ref_e) if pd.notna(ref_e) else np.nan,
                "slippage_salida_pts": -d * (x.precio - ref_x) if pd.notna(ref_x) else np.nan,
                "spread_entrada_pts": e.get("spread_previo", np.nan), "spread_salida_pts": x.get("spread_previo", np.nan),
                "comision_$": 0.0, "neto_$": pts * lotes * VALOR_PUNTO_LOTE, "puntos": pts,
                "motivo_entrada": e.motivo, "motivo_salida": x.motivo, "estado": "CERRADA"})
    for est, e in abiertas.items():
        filas.append({"id_ea": f"{est}|{e.t_ny:%Y-%m-%dT%H:%M}NY", "estrategia": est,
                      "direccion": "LARGO" if e.accion == "COMPRAR" else "CORTO", "t_entrada_ny": e.t_ny,
                      "precio_real_entrada": e.precio, "estado": "ABIERTA"})
    o = pd.DataFrame(filas)
    if len(o):
        o["slippage_total_pts"] = o[["slippage_entrada_pts", "slippage_salida_pts"]].sum(axis=1, min_count=1)
    return o, problemas


def emparejar(teorico: pd.DataFrame, ea: pd.DataFrame, tolerancia_min: dict | None = None) -> pd.DataFrame:
    """Empareja operaciones teóricas (futuro) con las del EA (CFD): misma estrategia y dirección, entrada a menos de la
    tolerancia (ZR 3 min; RSI2 180 min, porque el CFD tiene otro horario de sesión). Sin emparejar = discrepancia."""
    tol = tolerancia_min or {"NOISE_ZONE": 3, "RSI2": 180}
    filas = []
    usados = set()
    for _, t in teorico.iterrows():
        te = pd.Timestamp(t.t_entrada_ny)
        cand = ea[(ea.estrategia == t.estrategia) & (ea.direccion == t.direccion)] if len(ea) else ea
        mejor = None
        for j, e in cand.iterrows():
            if j in usados:
                continue
            dif = abs((pd.Timestamp(e.t_entrada_ny) - te).total_seconds()) / 60
            if dif <= tol[t.estrategia] and (mejor is None or dif < mejor[1]):
                mejor = (j, dif)
        if mejor:
            usados.add(mejor[0])
            e = ea.loc[mejor[0]]
            filas.append({"id": t.id, "id_ea": e.id_ea, "estado": "emparejada", "diferencia_min": round(mejor[1], 1),
                          "neto_teorico_$": t["neto_$"], "neto_ea_$": e.get("neto_$", np.nan)})
        else:
            filas.append({"id": t.id, "id_ea": None, "estado": "solo en el teórico (el EA no la hizo)"})
    for j, e in ea.iterrows() if len(ea) else []:
        if j not in usados:
            filas.append({"id": None, "id_ea": e.id_ea, "estado": "solo en el EA (el teórico no la tiene)"})
    return pd.DataFrame(filas)
