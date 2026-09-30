"""Motor de ejecución del laboratorio (numba). Mismas reglas conservadoras que src/engine/ejecucion.py:

  - Orden A MERCADO (tipo 0): la señal se calcula al cierre del minuto `i_sig`; se entra en la APERTURA de i_sig + 1
    con deslizamiento en contra.
  - Orden STOP OCO (tipo 1): niveles de compra (`nivel_l`) y/o venta (`nivel_c`) activos desde i_sig + 1 hasta
    `i_exp` (excluido). Se llena al tocar el nivel, al nivel o a la apertura si abre más allá (hueco), con
    deslizamiento. Si en el mismo minuto se tocan los dos niveles, se toma el más cercano a la apertura. En el
    minuto del llenado solo puede saltar el stop.
  - Stop: si el minuto abre más allá del stop se sale en la apertura; si no, en el stop; siempre con deslizamiento.
  - Objetivo: orden límite exacta, sin deslizamiento. Objetivo dinámico (VWAP): el VWAP conocido en la apertura del
    minuto; si el minuto abre ya más allá, se llena en la apertura.
  - Stop y objetivo en el mismo minuto: cuenta el STOP.
  - Trailing (chandelier): al cierre de cada minuto, stop = max(stop, máximo cierre desde la entrada - distancia)
    (largos; simétrico en cortos). Se aplica desde el minuto siguiente.
  - Salida por tiempo: en la apertura del minuto `i_fin`, con deslizamiento.
  - Una posición a la vez: una orden se ignora si su señal llega antes del minuto de salida de la anterior.
  - `max_ses`: máximo de operaciones por sesión (0 = sin límite).

Todo en precio real. Costes: comisión por lado x mult y deslizamiento en ticks (1 o 2 según la hora) x mult.
"""
from __future__ import annotations

import numba as nb
import numpy as np
import pandas as pd

MOTIVOS = np.array(["stop", "objetivo", "tiempo", "trailing", "fin_datos"])


@nb.njit(cache=True)
def _simular(O, H, L, C, desl, ses, vwap_prev,
             i_sig, tipo, dirc, stop_abs, stop_dist, nivel_l, stop_l, nivel_c, stop_c, i_exp,
             r_obj, obj_abs, obj_vwap, trail, i_fin,
             tick, mult, max_ses):
    n = len(O)
    m = len(i_sig)
    out_ie = np.full(m, -1, np.int64)
    out_ix = np.full(m, -1, np.int64)
    out_d = np.zeros(m, np.int64)
    out_pe = np.zeros(m)
    out_px = np.zeros(m)
    out_st = np.zeros(m)
    out_mot = np.zeros(m, np.int64)
    out_mae = np.zeros(m)
    out_mfe = np.zeros(m)
    out_ord = np.zeros(m, np.int64)
    nses = ses.max() + 1 if n > 0 else 1
    cuenta = np.zeros(nses, np.int64)
    libre = -1
    k_out = 0
    for j in range(m):
        s = i_sig[j]
        if s < libre or s + 1 >= n:
            continue
        if max_ses > 0 and cuenta[ses[s]] >= max_ses:
            continue
        fin = i_fin[j]
        d = 0
        ent = 0.0
        stp = 0.0
        k0 = -1
        solo_stop_en_k0 = False
        if tipo[j] == 0:
            i = s + 1
            if i >= fin:
                continue
            d = dirc[j]
            ent = O[i] + d * desl[i] * mult * tick
            if not np.isnan(stop_dist[j]):
                stp = ent - d * stop_dist[j]
            else:
                stp = stop_abs[j]
            k0 = i
        else:
            lim = min(i_exp[j], fin)
            enc = False
            for k in range(s + 1, lim):
                tl = (not np.isnan(nivel_l[j])) and H[k] >= nivel_l[j]
                tc = (not np.isnan(nivel_c[j])) and L[k] <= nivel_c[j]
                if tl and tc:
                    if abs(O[k] - nivel_l[j]) <= abs(O[k] - nivel_c[j]):
                        tc = False
                    else:
                        tl = False
                if tl:
                    d = 1
                    ent = max(nivel_l[j], O[k]) + desl[k] * mult * tick
                    stp = ent - stop_dist[j] if not np.isnan(stop_dist[j]) else stop_l[j]
                elif tc:
                    d = -1
                    ent = min(nivel_c[j], O[k]) - desl[k] * mult * tick
                    stp = ent + stop_dist[j] if not np.isnan(stop_dist[j]) else stop_c[j]
                if tl or tc:
                    k0 = k
                    enc = True
                    solo_stop_en_k0 = True
                    break
            if not enc:
                continue
        if (ent - stp) * d <= 0:
            continue
        riesgo = abs(ent - stp)
        obj = np.nan
        if not np.isnan(r_obj[j]):
            obj = ent + d * r_obj[j] * riesgo
        elif not np.isnan(obj_abs[j]):
            obj = obj_abs[j]
            if (obj - ent) * d <= 0:
                continue
        dinam = obj_vwap[j]
        tr = trail[j]
        mejor_c = ent
        mae = 0.0
        mfe = 0.0
        stop_movido = False
        salida = np.nan
        mot = 4
        kx = n - 1
        for k in range(k0, n):
            if k >= fin and not (solo_stop_en_k0 and k == k0):
                salida = O[k] - d * desl[k] * mult * tick
                mot = 2
                kx = k
                break
            peor = L[k] if d == 1 else H[k]
            mejor = H[k] if d == 1 else L[k]
            exc_mala = (ent - peor) * d
            if exc_mala > mae:
                mae = exc_mala
            if (peor - stp) * d <= 0:
                base = min(stp, O[k]) if d == 1 else max(stp, O[k])
                salida = base - d * desl[k] * mult * tick
                mot = 3 if stop_movido else 0
                kx = k
                exc_buena = (mejor - ent) * d
                if exc_buena > mfe:
                    mfe = exc_buena
                break
            exc_buena = (mejor - ent) * d
            if exc_buena > mfe:
                mfe = exc_buena
            if not (solo_stop_en_k0 and k == k0):
                if not np.isnan(obj) and (mejor - obj) * d >= 0:
                    salida = obj
                    mot = 1
                    kx = k
                    break
                if dinam:
                    lv = vwap_prev[k]
                    if not np.isnan(lv) and (mejor - lv) * d >= 0:
                        salida = max(lv, O[k]) if d == 1 else min(lv, O[k])
                        mot = 1
                        kx = k
                        break
            if not np.isnan(tr):
                if (C[k] - mejor_c) * d > 0:
                    mejor_c = C[k]
                nuevo = mejor_c - d * tr
                if (nuevo - stp) * d > 0:
                    stp = nuevo
                    stop_movido = True
        if np.isnan(salida):
            salida = C[n - 1] - d * desl[n - 1] * mult * tick
            kx = n - 1
            mot = 4
        out_ie[k_out] = k0
        out_ix[k_out] = kx
        out_d[k_out] = d
        out_pe[k_out] = ent
        out_px[k_out] = salida
        out_st[k_out] = riesgo
        out_mot[k_out] = mot
        out_mae[k_out] = mae
        out_mfe[k_out] = mfe
        out_ord[k_out] = j
        k_out += 1
        cuenta[ses[k0]] += 1
        libre = kx
    return (out_ie[:k_out], out_ix[:k_out], out_d[:k_out], out_pe[:k_out], out_px[:k_out], out_st[:k_out],
            out_mot[:k_out], out_mae[:k_out], out_mfe[:k_out], out_ord[:k_out])


COLUMNAS = {"i_sig": np.int64, "tipo": np.int64, "dir": np.int64, "stop": float, "stop_dist": float,
            "nivel_l": float, "stop_l": float, "nivel_c": float, "stop_c": float, "i_exp": np.int64,
            "r_obj": float, "obj": float, "obj_vwap": np.bool_, "trail": float, "i_fin": np.int64}
DEFECTOS = {"tipo": 0, "dir": 0, "stop": np.nan, "stop_dist": np.nan, "nivel_l": np.nan, "stop_l": np.nan,
            "nivel_c": np.nan, "stop_c": np.nan, "i_exp": -1, "r_obj": np.nan, "obj": np.nan, "obj_vwap": False,
            "trail": np.nan}


def normalizar(ordenes: pd.DataFrame) -> pd.DataFrame:
    o = ordenes.copy()
    for c, v in DEFECTOS.items():
        if c not in o:
            o[c] = v
    o["i_exp"] = np.where(o.i_exp < 0, o.i_fin, o.i_exp)
    o = o.sort_values("i_sig", kind="stable").reset_index(drop=True)
    return o.astype(COLUMNAS)[list(COLUMNAS)]


def simular(ctx, ordenes: pd.DataFrame, mult: float = 1.0, max_ses: int = 0, vwap: str = "rth",
            tick: float = 0.25, valor_punto: float = 2.0, comision_lado: float = 1.0) -> pd.DataFrame:
    """Simula las órdenes sobre el 1 min del contexto. Devuelve una fila por operación."""
    cols = ["t_entrada", "t_salida", "direccion", "entrada", "salida", "motivo", "riesgo_pts", "mae_pts", "mfe_pts",
            "bruto", "comision", "neto", "r", "i_entrada", "i_salida", "orden"]
    if ordenes is None or len(ordenes) == 0:
        return pd.DataFrame(columns=cols)
    o = normalizar(ordenes)
    vp = ctx.vwap_previo(vwap) if o.obj_vwap.any() else np.full(len(ctx.C), np.nan)
    r = _simular(ctx.O, ctx.H, ctx.L, ctx.C, ctx.ticks_desl, ctx.ses, vp,
                 *(o[c].to_numpy() for c in COLUMNAS), tick, mult, max_ses)
    ie, ix, d, pe, px, st, mot, mae, mfe, jo = r
    bruto = (px - pe) * d * valor_punto
    com = 2 * comision_lado * mult
    neto = bruto - com
    return pd.DataFrame({
        "t_entrada": ctx.t[ie], "t_salida": ctx.t[ix], "direccion": d, "entrada": pe, "salida": px,
        "motivo": MOTIVOS[mot], "riesgo_pts": st, "mae_pts": mae, "mfe_pts": mfe, "bruto": bruto, "comision": com,
        "neto": neto, "r": neto / (st * valor_punto + com), "i_entrada": ie, "i_salida": ix, "orden": jo})
