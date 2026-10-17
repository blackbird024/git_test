"""Petición (versión del usuario): marcar en el perfil de volumen POC, VAH, VAL y los PICOS (nodos de mucho volumen),
esperar a que el precio llegue y entrar con confirmación de VELA ENVOLVENTE o de DESPLAZAMIENTO CON FVG, en 5 min
(y en 1 min para comparar). MNQ (precios NQ 1 min) 2018-2026. Reglas fijadas ANTES de ver resultados:
  Perfiles (como run_perfil_niveles.py): volumen de cada vela de 1 min a su precio típico redondeado a 1 pt, día de
    24 h. COMPUESTO_5D (5 días anteriores) o DIA_ANTERIOR. Niveles: POC, VAH, VAL (área de valor 70 %) y PICOS:
    perfil suavizado con media móvil centrada de h pts (h = 0,2 % del precio, ~13 pts en 2018, ~50 en 2026); pico =
    máximo local en ±h con volumen >= 25 % del máximo, a más de h del POC; como mucho los 4 mayores.
  Toque: primera vela (de tf min) entre 9:30 y 12:00 ET cuyo rango contiene el nivel; una vez por nivel y día.
    Apertura de la vela por encima del nivel → se busca COMPRA (soporte); por debajo → VENTA (resistencia).
  Confirmación en las 3 velas siguientes al toque (incluida la del toque), siempre cerrando del lado correcto del nivel:
    ENVOLVENTE: vela previa en contra (bajista para compra) y vela actual a favor cuyo cuerpo envuelve el de la previa
      (cierre >= apertura previa y apertura <= cierre previo).
    FVG: tres velas a, b, c con b a favor (cuerpo >= 60 % de su rango, empezando en o después del toque) y hueco
      (compra: mínimo de c > máximo de a). Entrada:
        FVG_MERCADO  a mercado en la apertura siguiente al cierre de c;
        FVG_LIMITE   orden límite en la mitad del hueco, válida 30 min; se llena solo si el precio la cruza 1 tick.
  SL = extremo desde el toque hasta la vela de confirmación ∓ 1 tick; objetivo 1R o 2R; cierre forzoso 15:55 ET;
    una posición a la vez; máximo 2 operaciones al día; ninguna entrada después de las 12:30 ET.
  Ejecución y costes: motor de orb_retest (coste base 1 USD/lado + 1 tick; TP con cruce de 1 tick; SL primero). En la
    variante límite: sin deslizamiento de entrada y, en el minuto del llenado, el TP no cuenta (no se sabe el orden).
Selección (protocolo): esperanza neta > 0 en desarrollo Y validación, n_val >= 30."""
import itertools
from dataclasses import replace

import numpy as np
import pandas as pd

from data.loaders import sessions
from orb_retest.config import BASELINE, COST_SCENARIOS
from orb_retest.execution import Trade, round_tp, simulate
from orb_retest.pipeline import label
from orb_retest.signals import Signal
from run_perfil_niveles import niveles, perfiles
from validation.metrics import block_bootstrap_mean
from validation.runner import new_experiment, write_manifest

TICK = 0.25
LAST_TOUCH_K = 150        # velas de toque que cierran como muy tarde a las 12:00
LAST_ENTRY_K = 180        # ninguna entrada después de las 12:30
VENTANA = 3               # velas de confirmación tras el toque (incluida la del toque)
LIMITE_MIN = 30           # validez de la orden límite del FVG


def picos(vp: pd.Series, poc: float):
    idx = np.arange(vp.index.min(), vp.index.max() + 1)
    v = vp.reindex(idx, fill_value=0.0)
    h = max(5, int(round(0.002 * poc)))
    sm = v.rolling(h, center=True, min_periods=1).mean()
    a = sm.to_numpy()
    out = []
    for i in range(len(a)):
        lo, hi = max(0, i - h), min(len(a), i + h + 1)
        if a[i] > 0 and a[i] == a[lo:hi].max() and a[i] >= 0.25 * a.max() and abs(idx[i] - poc) > h:
            out.append((a[i], float(idx[i])))
    out = sorted(out, reverse=True)[:4]
    return {f"PICO{j + 1}": p for j, (_, p) in enumerate(out)}


def velas(m, tf, close_min):
    rows = []
    for k0 in range(0, close_min - tf + 1, tf):
        x = m[k0:k0 + tf]
        ok = ~np.isnan(x[:, 0])
        if not ok.any():
            rows.append((np.nan,) * 4)
            continue
        rows.append((x[ok][0, 0], x[ok, 1].max(), x[ok, 2].min(), x[ok][-1, 3]))
    return np.array(rows)


def señales(B, tf, lv, setup):
    """[(k_señal, lado, extremo_para_SL, cierre, limite_o_nan)]"""
    O, H, L, C = B.T
    out, usados = [], set()
    for t in range(min(LAST_TOUCH_K // tf, len(B))):
        if np.isnan(O[t]):
            continue
        for name, p in lv.items():
            if name in usados or not (L[t] <= p <= H[t]):
                continue
            usados.add(name)
            if O[t] == p:
                continue
            s = 1 if O[t] > p else -1
            for b in range(t, min(t + VENTANA, len(B))):
                if np.isnan(O[b]) or s * (C[b] - p) <= 0:
                    continue
                ext = L[t:b + 1].min() if s == 1 else H[t:b + 1].max()
                if setup == "ENVOLVENTE":
                    a = b - 1
                    if a < 0 or np.isnan(O[a]):
                        continue
                    if s * (C[a] - O[a]) < 0 and s * (C[b] - O[b]) > 0 and s * (C[b] - O[a]) >= 0 \
                            and s * (O[b] - C[a]) <= 0:
                        ext = min(ext, L[a]) if s == 1 else max(ext, H[a])
                        out.append(((b + 1) * tf, s, ext, C[b], np.nan))
                        break
                else:
                    a, mid = b - 2, b - 1
                    if mid < t or a < 0 or np.isnan(O[a]) or np.isnan(O[mid]):
                        continue
                    rng = H[mid] - L[mid]
                    disp = rng > 0 and s * (C[mid] - O[mid]) >= 0.6 * rng
                    gap = (L[b] > H[a]) if s == 1 else (H[b] < L[a])
                    if disp and gap:
                        lim = np.round(((H[a] + L[b]) / 2 if s == 1 else (L[a] + H[b]) / 2) / TICK) * TICK
                        out.append(((b + 1) * tf, s, ext, C[b], lim if setup == "FVG_LIMITE" else np.nan))
                        break
    return sorted(out, key=lambda x: x[0])


def simulate_limit(s, k0, lim, ext, m, close_min, st, c):
    """Orden límite en lim desde el minuto k0 durante LIMITE_MIN min; luego gestión igual que simulate()."""
    O, H, L, C = m[:, 0], m[:, 1], m[:, 2], m[:, 3]
    tick = c.tick
    flat_k = min(st.flat_k, close_min - 5)
    sl = round((ext - st.stop_offset_ticks * tick) / tick) * tick if s == 1 else \
        round((ext + st.stop_offset_ticks * tick) / tick) * tick
    r_pts = s * (lim - sl)
    if r_pts <= 1e-9:
        return None
    k = None
    for j in range(k0, min(k0 + LIMITE_MIN, st.last_entry_k + 1, flat_k)):
        if np.isnan(O[j]):
            continue
        if s * (O[j] - sl) <= 0:            # el precio ya está más allá del stop: se anula
            return None
        if (L[j] <= lim - tick) if s == 1 else (H[j] >= lim + tick):
            k = j
            break
    if k is None:
        return None
    entry = lim
    tp = round_tp(entry + s * st.tp_r * r_pts, s, tick)
    cross = c.tp_cross_ticks * tick
    sslip, tslip = c.slip_ticks_stop * tick, c.slip_ticks_time * tick

    def out(j, px, why, amb=False):
        return Trade(s, k, entry, sl, tp, r_pts, j, px, why, amb, s * (px - entry))

    for j in range(k, flat_k):
        if np.isnan(O[j]):
            continue
        first = j == k
        if not first and s * (O[j] - sl) <= 0:
            return out(j, O[j] - s * sslip, "sl_hueco")
        if (L[j] <= sl) if s == 1 else (H[j] >= sl):
            return out(j, sl - s * sslip, "sl")
        if first:
            continue
        if s * (O[j] - tp) >= 0:
            return out(j, tp, "tp")
        if (H[j] >= tp + cross) if s == 1 else (L[j] <= tp - cross):
            return out(j, tp, "tp")
    j = flat_k
    while j < close_min and np.isnan(O[j]):
        j += 1
    if j < close_min:
        return out(j, O[j] - s * tslip, "tiempo")
    j = close_min - 1
    while np.isnan(C[j]):
        j -= 1
    return out(j, C[j] - s * tslip, "tiempo")


def run(S, LV, perfil, tf, setup, tp_r, cost="base"):
    cfg = replace(BASELINE.with_(last_entry_k=LAST_ENTRY_K, tp_r=tp_r), costs=COST_SCENARIOS[cost])
    rows = []
    for s in S:
        lv = LV[perfil].get(s.date.date())
        if lv is None:
            continue
        m = s.m
        B = velas(m, tf, s.close_min)
        free, n = -1, 0
        for k, side, ext, c, lim in señales(B, tf, lv, setup):
            if n >= 2 or k <= free:
                continue
            if setup == "FVG_LIMITE":
                tr = simulate_limit(side, k, lim, ext, m, s.close_min, cfg.strategy, cfg.costs)
            else:
                sig = Signal(side, np.nan, np.nan, -1, -1, k, ext if side == -1 else np.nan,
                             ext if side == 1 else np.nan, c)
                tr, _ = simulate(sig, m, s.close_min, cfg.strategy, cfg.costs)
            if tr is None:
                continue
            n += 1
            free = tr.exit_k
            net = tr.gross_pts * 2 - 2 * cfg.costs.commission_per_side
            rows.append(dict(date=s.date, **tr.as_dict(), R=net / (tr.r_pts * 2), net_usd_1c=net,
                             risk_usd_1c=tr.r_pts * 2))
    t = pd.DataFrame(rows)
    if len(t):
        t["particion"] = label(t.date, BASELINE)
    return t


def main():
    S = sessions()
    P = perfiles()
    keys = list(P)
    pos = {d: i for i, d in enumerate(keys)}
    LV = {"COMPUESTO_5D": {}, "DIA_ANTERIOR": {}}
    for s in S:
        d = s.date.date()
        if d not in pos:
            continue
        i = pos[d]
        for perfil, n in (("COMPUESTO_5D", 5), ("DIA_ANTERIOR", 1)):
            if i < n:
                continue
            vp = pd.concat([P[x] for x in keys[i - n:i]]).groupby(level=0).sum().sort_index()
            lv = niveles(vp)
            lv.update(picos(vp, lv["POC"]))
            LV[perfil][d] = lv
    exp = new_experiment("perfil_envolvente_fvg")
    npk = pd.Series([sum(k.startswith("PICO") for k in v) for v in LV["COMPUESTO_5D"].values()])
    print("picos por día (5D): media", round(npk.mean(), 2), flush=True)
    rows = []
    for perfil, tf, setup, tp_r in itertools.product(("COMPUESTO_5D", "DIA_ANTERIOR"), (5, 1),
                                                     ("ENVOLVENTE", "FVG_MERCADO", "FVG_LIMITE"), (1.0, 2.0)):
        t = run(S, LV, perfil, tf, setup, tp_r)
        name = f"{perfil} · {tf} min · {setup} · {tp_r:g}R"
        t.to_csv(exp / f"ops_{perfil}_{tf}m_{setup}_{tp_r:g}R.csv.gz", index=False)
        r = dict(variante=name, ops=len(t))
        for p in ("desarrollo", "validacion", "prueba"):
            x = t[t.particion == p] if len(t) else t
            r[p + "_ops"] = len(x)
            r[p + "_ER"] = x.R.mean() if len(x) else np.nan
            r[p + "_acierto"] = (x.net_usd_1c > 0).mean() if len(x) else np.nan
        r["stop_mediano_pts"] = t.r_pts.median() if len(t) else np.nan
        oos = t[t.particion != "desarrollo"] if len(t) else t
        r["ic90_fuera"] = block_bootstrap_mean(oos.R.to_numpy()) if len(oos) > 30 else (np.nan, np.nan)
        rows.append(r)
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res["pasa"] = (res.desarrollo_ER > 0) & (res.validacion_ER > 0) & (res.validacion_ops >= 30)
    res.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="perfil (POC/VAH/VAL/picos) + envolvente o desplazamiento con FVG", reglas=__doc__)
    pd.set_option("display.width", 300, "display.max_colwidth", 60)
    print(res.round(3).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
