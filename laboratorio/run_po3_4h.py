"""Petición (vídeo ICT avanzado nº 7): Power of 3 de la vela de 4 h que abre a las 10:00 ET (16:00 Italia). MNQ
(precios NQ 1 min) 2018-2026. Reglas fijadas ANTES de ver resultados:
  Nivel a barrer entre 10:00 y 10:59 ET (manipulación):
    RANGO_930  mínimo / máximo de 9:30-9:59 ET;
    DIA_ANT    mínimo / máximo de la sesión regular del día anterior (mismo contrato).
  Compra (espejo para venta): el precio cae por debajo del nivel (barrido). Pierna de manipulación = desde el máximo
    más alto entre las 10:00 y el mínimo de la pierna hasta ese mínimo (se actualiza mientras siga cayendo).
  Confirmación (hasta las 11:30 ET; la primera señal del día manda):
    RECUPERA_5  vela de 5 min que cierra de nuevo por encima del nivel barrido;
    IFG_5 / IFG_1  vela de 5 / 1 min que cierra por encima del techo del FVG bajista más reciente de la pierna
      (velas a, b, c con máximo de c < mínimo de a), por encima del 50 % de la pierna y por debajo de su máximo.
  Entrada a mercado en la apertura siguiente; SL = mínimo de la pierna − 1 tick; objetivo 1R o 2R; cierre 15:55 ET;
    una operación al día. Ejecución y costes: motor de orb_retest (coste base).
  Descriptivo: P(la vela de 4 h 10:00-13:59 cierra alcista) en todos los días frente a los días en que entre las 10:00
    y las 10:59 se barre primero el mínimo (o el máximo) de 9:30-9:59.
Selección (protocolo): esperanza neta > 0 en desarrollo Y validación, n_val >= 30."""
import itertools
from dataclasses import replace

import numpy as np
import pandas as pd

from data.loaders import sessions
from orb_retest.config import BASELINE, COST_SCENARIOS
from orb_retest.execution import simulate
from orb_retest.pipeline import label
from orb_retest.signals import Signal
from validation.metrics import block_bootstrap_mean
from validation.runner import new_experiment, write_manifest

K10, K11, K1130, K14 = 30, 90, 120, 270


def velas(m, tf, k0, k1):
    """[(k_cierre, o, h, l, c)] velas de tf min entre k0 y k1 (alineadas a k0)."""
    out = []
    for a in range(k0, k1, tf):
        x = m[a:a + tf]
        ok = ~np.isnan(x[:, 0])
        if ok.any():
            out.append((a + tf, x[ok][0, 0], x[ok, 1].max(), x[ok, 2].min(), x[ok][-1, 3]))
    return out


def señal(m, lvl_lo, lvl_hi, conf):
    """Primera señal del día: (k, lado, extremo, cierre) o None. Velas: (k_cierre, o, h, l, c)."""
    tf = 1 if conf == "IFG_1" else 5
    B = velas(m, tf, K10, K1130)
    best = None
    for s, lvl in ((1, lvl_lo), (-1, lvl_hi)):
        swept, ext, top, itop = False, None, None, 0
        for i, (k, o, h, l, c) in enumerate(B):
            fav_ext = l if s == 1 else h
            if not swept:
                if k <= K11 and s * (lvl - fav_ext) > 0:
                    swept = True
                else:
                    continue
            if ext is None or s * (ext - fav_ext) > 0:          # la pierna sigue: nuevo extremo
                ext = fav_ext
                hs = [x[2] if s == 1 else -x[3] for x in B[:i + 1]]
                itop = int(np.argmax(hs))
                top = B[itop][2] if s == 1 else B[itop][3]
            if conf == "RECUPERA_5":
                ok = s * (c - lvl) > 0
            else:
                gaps = [B[j - 2][3] if s == 1 else B[j - 2][2] for j in range(itop + 2, i)
                        if (B[j][2] < B[j - 2][3] if s == 1 else B[j][3] > B[j - 2][2])]
                mid = (top + ext) / 2
                ok = bool(gaps) and s * (c - gaps[-1]) > 0 and s * (c - mid) >= 0 and s * (top - c) > 0
            if ok:
                if best is None or k < best[0]:
                    best = (k, s, ext, c)
                break
    return best


def run(S, nivel, conf, tp_r, cost="base"):
    cfg = replace(BASELINE.with_(last_entry_k=K1130 + 1, tp_r=tp_r), costs=COST_SCENARIOS[cost])
    rows = []
    prev = None
    for s in S:
        m = s.m
        if s.close_min < 390 or np.isnan(m[:K10, 0]).all():
            prev = s
            continue
        if nivel == "RANGO_930":
            lo, hi = np.nanmin(m[:K10, 2]), np.nanmax(m[:K10, 1])
        else:
            if prev is None or prev.instrument_id != s.instrument_id:
                prev = s
                continue
            lo, hi = np.nanmin(prev.m[:prev.close_min, 2]), np.nanmax(prev.m[:prev.close_min, 1])
            o10 = m[K10, 0] if not np.isnan(m[K10, 0]) else np.nan
            if not (lo < o10 < hi):                             # el nivel ya se rompió antes de las 10:00
                prev = s
                continue
        prev = s
        sg = señal(m, lo, hi, conf)
        if sg is None:
            continue
        k, side, ext, c = sg
        sig = Signal(side, np.nan, np.nan, -1, -1, k, ext if side == -1 else np.nan, ext if side == 1 else np.nan, c)
        tr, _ = simulate(sig, m, s.close_min, cfg.strategy, cfg.costs)
        if tr is None:
            continue
        net = tr.gross_pts * 2 - 2 * cfg.costs.commission_per_side
        rows.append(dict(date=s.date, **tr.as_dict(), R=net / (tr.r_pts * 2), net_usd_1c=net))
    t = pd.DataFrame(rows)
    if len(t):
        t["particion"] = label(t.date, BASELINE)
    return t


def descriptivo(S):
    rows = []
    for s in S:
        m = s.m
        if s.close_min < 390 or np.isnan(m[K10, 0]) or np.isnan(m[:K10, 0]).all():
            continue
        lo, hi = np.nanmin(m[:K10, 2]), np.nanmax(m[:K10, 1])
        c14 = m[K14 - 1, 3] if not np.isnan(m[K14 - 1, 3]) else np.nan
        first = None
        for k in range(K10, K11):
            if np.isnan(m[k, 0]):
                continue
            dl, dh = m[k, 2] < lo, m[k, 1] > hi
            if dl or dh:
                first = "ambos" if dl and dh else ("minimo" if dl else "maximo")
                break
        rows.append(dict(date=s.date, alcista=c14 > m[K10, 0], primero=first or "ninguno"))
    d = pd.DataFrame(rows)
    d["particion"] = label(d.date, BASELINE)
    return d


def main():
    S = sessions()
    exp = new_experiment("po3_4h_10am")
    d = descriptivo(S)
    d.to_csv(exp / "descriptivo.csv.gz", index=False)
    desc = d.groupby(["primero", "particion"]).alcista.agg(["mean", "size"]).unstack().round(3)
    print("P(vela 4 h 10:00 cierra alcista) según qué lado del rango 9:30-9:59 se barre primero (10:00-10:59):")
    print(desc.to_string())
    print("todos los días:", d.groupby("particion").alcista.mean().round(3).to_dict(), flush=True)
    rows = []
    for nivel, conf, tp_r in itertools.product(("RANGO_930", "DIA_ANT"), ("RECUPERA_5", "IFG_5", "IFG_1"), (1.0, 2.0)):
        t = run(S, nivel, conf, tp_r)
        name = f"{nivel} · {conf} · {tp_r:g}R"
        t.to_csv(exp / f"ops_{nivel}_{conf}_{tp_r:g}R.csv.gz", index=False)
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
    desc.to_csv(exp / "descriptivo_resumen.csv")
    write_manifest(exp, experimento="PO3 vela de 4 h 10:00 ET", reglas=__doc__)
    pd.set_option("display.width", 300, "display.max_colwidth", 60)
    print(res.round(3).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
