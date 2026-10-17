"""Petición: marcar los puntos importantes del perfil de volumen (vista de 4 h), esperar a que el precio llegue y
entrar con confirmación en 5 min (y, para comparar, en 1 min). MNQ (precios NQ 1 min) 2018-2026, reglas fijadas
ANTES de ver resultados:
  Perfiles (volumen de cada vela de 1 min asignado a su precio típico redondeado a 1 pt, sesión completa de 24 h):
    COMPUESTO_5D  los 5 días anteriores · DIA_ANTERIOR  el día anterior. Niveles: POC, VAH, VAL (área de valor 70 %).
  Ventana: toques entre 9:30 y 12:00 ET (15:30-18:00 Italia); cada nivel cuenta una vez al día (primer toque).
  Toque y confirmación (vela de 5 min, o de 1 min en la variante): la vela toca el nivel (mínimo <= nivel <= máximo)
    viniendo de un lado (apertura de la vela por encima → compra; por debajo → venta), CIERRA de nuevo de ese lado y en
    su mitad favorable (rechazo). Entrada a mercado en la apertura siguiente; SL = extremo de la vela ∓ 1 tick;
    objetivo 1R o 2R; cierre forzoso 15:55 ET; una posición a la vez, máximo 2 operaciones al día.
  Filtro opcional VWAP de la sesión regular: compras solo con el cierre por encima del VWAP, ventas por debajo.
  Ejecución y costes: motor de orb_retest (coste base 1 USD/lado + 1 tick; TP con cruce de 1 tick; SL primero).
Selección (protocolo): esperanza neta > 0 en desarrollo Y validación, n_val >= 30."""
import itertools
from dataclasses import replace

import numpy as np
import pandas as pd

from data.loaders import nq_1m, sessions
from orb_retest.config import BASELINE, COST_SCENARIOS
from orb_retest.execution import simulate
from orb_retest.pipeline import label
from orb_retest.signals import Signal
from orb_retest.metrics import part_metrics
from validation.metrics import block_bootstrap_mean
from validation.runner import new_experiment, write_manifest

TICK = 0.25


def perfiles():
    """{fecha_de_sesion: Serie volumen por precio} con el día de trading = fecha a las 18:00 ET + 6 h."""
    df = nq_1m()
    tp = ((df.high + df.low + df.close) / 3).round()
    tday = (df.index + pd.Timedelta(hours=6)).date
    g = pd.DataFrame(dict(p=tp.to_numpy(), v=df.volume.to_numpy(), d=tday)).groupby(["d", "p"]).v.sum()
    return {d: s.droplevel(0) for d, s in g.groupby(level=0)}


def niveles(vp: pd.Series):
    vp = vp.sort_index()
    poc = vp.idxmax()
    tot, acc = vp.sum(), vp[poc]
    prices = vp.index.to_numpy()
    i = j = int(np.nonzero(prices == poc)[0][0])
    while acc < 0.7 * tot and (i > 0 or j < len(prices) - 1):
        up = vp.iloc[j + 1] if j < len(prices) - 1 else -1
        dn = vp.iloc[i - 1] if i > 0 else -1
        if up >= dn:
            j += 1
            acc += up
        else:
            i -= 1
            acc += dn
    return dict(POC=float(poc), VAH=float(prices[j]), VAL=float(prices[i]))


def señales(m, close_min, lv: dict, tf: int, vwap_f: bool, vwap):
    O, H, L, C = m[:, 0], m[:, 1], m[:, 2], m[:, 3]
    out, usados = [], set()
    for b in range(0, 150 // tf):                    # velas que cierran como muy tarde a las 12:00
        k0, k1 = b * tf, b * tf + tf
        x = m[k0:k1]
        ok = ~np.isnan(x[:, 0])
        if not ok.any():
            continue
        o, h, l, c = x[ok][0, 0], x[:, 1][ok].max(), x[:, 2][ok].min(), x[ok][-1, 3]
        for name, p in lv.items():
            if name in usados or not (l <= p <= h):
                continue
            usados.add(name)
            if o > p and c > p and c >= (h + l) / 2:
                side, ext = 1, l
            elif o < p and c < p and c <= (h + l) / 2:
                side, ext = -1, h
            else:
                continue
            if vwap_f and not (side * (c - vwap[k1 - 1]) > 0):
                continue
            out.append((k1, side, ext, c))
    return sorted(out)


def run(S, P, fechas, perfil, tf, tp_r, vwap_f, cost="base"):
    cfg = replace(BASELINE.with_(last_entry_k=150, tp_r=tp_r), costs=COST_SCENARIOS[cost])
    rows = []
    for s in S:
        d = s.date.date()
        if d not in fechas:
            continue
        i = fechas[d]
        prev = [P[x] for x in list(P)[max(0, i - (5 if perfil == "COMPUESTO_5D" else 1)):i]]
        if len(prev) < (5 if perfil == "COMPUESTO_5D" else 1):
            continue
        vp = pd.concat(prev).groupby(level=0).sum()
        lv = niveles(vp)
        m = s.m
        tpz = (m[:, 1] + m[:, 2] + m[:, 3]) / 3
        v = np.nan_to_num(m[:, 4])
        vwap = np.cumsum(np.nan_to_num(tpz) * v) / np.maximum(np.cumsum(v), 1)
        free, n = -1, 0
        for k, side, ext, c in señales(m, s.close_min, lv, tf, vwap_f, vwap):
            if n >= 2 or k <= free:
                continue
            sig = Signal(side, np.nan, np.nan, -1, -1, k, ext if side == -1 else np.nan, ext if side == 1 else np.nan, c)
            tr, _ = simulate(sig, m, s.close_min, cfg.strategy, cfg.costs)
            if tr is None:
                continue
            n += 1
            free = tr.exit_k
            net = tr.gross_pts * 2 - 2 * cfg.costs.commission_per_side
            rows.append(dict(date=s.date, **tr.as_dict(), R=net / (tr.r_pts * 2), net_usd_1c=net,
                             risk_usd_1c=tr.r_pts * 2, R_gross=tr.gross_pts / tr.r_pts,
                             minutes_in_trade=tr.exit_k - tr.entry_k))
    t = pd.DataFrame(rows)
    if len(t):
        t["particion"] = label(t.date, BASELINE)
    return t


def main():
    S = sessions()
    P = perfiles()
    keys = list(P)
    fechas = {d: i for i, d in enumerate(keys)}
    exp = new_experiment("perfil_niveles_confirmacion")
    rows = []
    days = pd.DataFrame(dict(date=[s.date for s in S]))
    days["particion"] = label(days.date, BASELINE)
    for perfil, tf, tp_r, vf in itertools.product(("COMPUESTO_5D", "DIA_ANTERIOR"), (5, 1), (1.0, 2.0), (False, True)):
        t = run(S, P, fechas, perfil, tf, tp_r, vf)
        name = f"{perfil} · confirmación {tf} min · objetivo {tp_r:g}R · {'con' if vf else 'sin'} VWAP"
        t.to_csv(exp / f"ops_{perfil}_{tf}m_{tp_r:g}R_{int(vf)}.csv.gz", index=False)
        r = dict(variante=name, perfil=perfil, tf=tf, tp_r=tp_r, vwap=vf, ops=len(t))
        for p in ("desarrollo", "validacion", "prueba"):
            x = t[t.particion == p] if len(t) else t
            r[p + "_ops"] = len(x)
            r[p + "_ER"] = x.R.mean() if len(x) else np.nan
            r[p + "_acierto"] = (x.net_usd_1c > 0).mean() if len(x) else np.nan
        r["stop_mediano_pts"] = t.r_pts.median() if len(t) else np.nan
        r["R_total"] = t.R.sum() if len(t) else np.nan
        oos = t[t.particion != "desarrollo"] if len(t) else t
        r["ic90_fuera"] = block_bootstrap_mean(oos.R.to_numpy()) if len(oos) > 30 else (np.nan, np.nan)
        rows.append(r)
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res["pasa"] = (res.desarrollo_ER > 0) & (res.validacion_ER > 0) & (res.validacion_ops >= 30)
    res.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="niveles del perfil de volumen + confirmación 5/1 min", reglas=__doc__)
    pd.set_option("display.width", 300, "display.max_colwidth", 80)
    print(res.drop(columns=["perfil", "tf", "tp_r", "vwap", "ops"]).round(3).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
