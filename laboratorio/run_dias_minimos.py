"""Vídeo "modelo de días mínimos" (ganar 150 $ y arriesgar 500 $ con 2 órdenes límite en zonas de reacción), versión
MECÁNICA en MNQ 2018-2026. Las zonas del vídeo son a ojo; aquí se fijan ANTES de ver resultados:
  Vela de referencia de 15 min: NY 9:30-9:45 ET (15:30-15:45 Italia, la "vela asesina") y LONDRES 3:00-3:15 ET
  (9:00-9:15 Italia). Dirección (variantes): COLOR de esa vela (verde → compras) o TENDENCIA del día (cierre de la vela
  vs precio a las 0:00 ET).
  Zonas (variantes), para compras (ventas en espejo):
    Z50   orden 1 al 50 % de la vela, orden 2 en su mínimo; stop = mínimo − 25 % del tamaño de la vela.
    ZLIQ  orden 1 en el mínimo de la vela, orden 2 = mínimo − 50 % de la vela ("debajo del low"); stop = mínimo − 100 %.
  Contratos: cada orden arriesga 250 $ hasta el stop (MNQ 2 $/pt, redondeo hacia abajo, máx. 50 MNQ en total); si una
  orden no llega a 1 MNQ, no se opera.
  Objetivo: +150 $ BRUTOS sobre la posición llena (se recalcula si entra la 2.ª); al tocarlo se cierra todo y se cancela
  la otra orden. Las límite exigen 1 tick de cruce. Dentro de cada minuto, orden pesimista: primero el lado contrario
  (llenado de la 2.ª y stop) y luego el objetivo.
  Ventana: órdenes activas 3 h desde el cierre de la vela; salida a mercado al final. Una operación por sesión.
  Coste base por contrato (comisión por lado y deslizamiento en el stop y en la salida por tiempo).
Para no perder dinero hace falta acertar > 500/650 ≈ 77 % de las veces. Selección: neto > 0 en dev Y val, n_val >= 30."""
import itertools

import numpy as np
import pandas as pd

from execution_costs.costs import fut
from rangos_lib import load_days
from validation.runner import new_experiment, periods, write_manifest

SES = {"NY 15:30": 570, "LONDRES 9:00": 180}
PV, RISK_LEG, TGT, MAXC = 2.0, 250.0, 150.0, 50


def dia(m, a, direccion, zonas, c):
    tk = c.tick
    O, H, L, C = m[:, 0], m[:, 1], m[:, 2], m[:, 3]
    if np.isnan(H[a:a + 15]).sum() > 7:
        return None
    hi, lo = np.nanmax(H[a:a + 15]), np.nanmin(L[a:a + 15])
    o15 = O[a:a + 15][~np.isnan(O[a:a + 15])][0]
    c15 = C[a:a + 15][~np.isnan(C[a:a + 15])][-1]
    R = hi - lo
    if R <= 0:
        return None
    if direccion == "color":
        side = 1 if c15 > o15 else -1 if c15 < o15 else 0
    else:
        p0 = O[:60][~np.isnan(O[:60])]
        if not len(p0):
            return None
        side = 1 if c15 > p0[0] else -1 if c15 < p0[0] else 0
    if side == 0:
        return None
    rnd = lambda x: round(x / tk) * tk
    base = lo if side == 1 else hi                      # extremo "a favor del retroceso"
    mid = (hi + lo) / 2
    if zonas == "Z50":
        e1, e2, st = mid, base, base - side * 0.25 * R
    else:
        e1, e2, st = base, base - side * 0.5 * R, base - side * R
    e1, e2, st = rnd(e1), rnd(e2), rnd(st)
    n1 = int(RISK_LEG // (abs(e1 - st) * PV))
    n2 = int(RISK_LEG // (abs(e2 - st) * PV))
    if n1 < 1 or n2 < 1:
        return None
    if n1 + n2 > MAXC:
        n2 = max(1, MAXC - n1)
    k0, ex = a + 15, a + 15 + 180
    cross = c.limit_cross_ticks * tk
    legs = []                                           # (precio, contratos)
    for k in range(k0, ex):
        if np.isnan(O[k]):
            continue
        adv = L[k] if side == 1 else H[k]               # extremo en contra
        fav = H[k] if side == 1 else L[k]
        # 1) llenados de órdenes (lado contrario primero)
        for p, n in ((e1, n1), (e2, n2)):
            if (p, n) in legs:
                continue
            if side * (p - adv) >= cross:               # el precio cruza el nivel
                fill = min(p, O[k]) if side == 1 else max(p, O[k])
                legs.append((p, n))
                legs[-1] = (fill, n)
        # 2) stop
        if legs and side * (st - adv) >= 0:
            xp = st - side * c.slip
            if side * (O[k] - st) <= 0:
                xp = O[k] - side * c.slip
            return cerrar(legs, side, xp, "stop", c)
        # 3) objetivo
        if legs:
            n = sum(q for _, q in legs)
            avg = sum(p * q for p, q in legs) / n
            tp = avg + side * TGT / (n * PV)
            if side * (fav - tp) >= cross:
                return cerrar(legs, side, tp, "objetivo", c)
    if not legs:
        return dict(resultado="sin_entrada", bruto=0.0, neto=0.0, contratos=0)
    j = ex
    while j < 960 and np.isnan(O[j]):
        j += 1
    return cerrar(legs, side, (O[j] if j < 960 else C[ex - 1]) - side * c.slip, "tiempo", c)


def cerrar(legs, side, xp, why, c):
    n = sum(q for _, q in legs)
    bruto = sum(side * (xp - p) * q * PV for p, q in legs)
    return dict(resultado=why, bruto=bruto, neto=bruto - n * 2 * c.fixed_per_side, contratos=n)


def main():
    D, _ = load_days("MNQ")
    per = periods("intradia", include_test=True)
    c = fut("MNQ", "base")
    exp = new_experiment("dias_minimos")
    rows, allops = [], []
    for (ses, a), di, zo in itertools.product(SES.items(), ("color", "tendencia"), ("Z50", "ZLIQ")):
        ops = []
        for d, m in D:
            r = dia(m, a, di, zo, c)
            if r is not None and r["resultado"] != "sin_entrada":
                ops.append(dict(date=d, **r))
        t = pd.DataFrame(ops)
        t["variante"] = f"{ses} · dirección {di} · zonas {zo}"
        allops.append(t)
        res = {}
        for k, (p0, p1) in per.items():
            x = t[(t.date >= p0) & (t.date <= p1)]
            res[k] = x.neto.mean()
            res["n_" + k] = len(x)
        eq = t.neto.cumsum()
        rows.append(dict(variante=t.variante.iloc[0], ops_año=len(t) / 8.75, gana=(t.bruto > 0).mean(),
                         objetivo=(t.resultado == "objetivo").mean(), stop=(t.resultado == "stop").mean(),
                         gana_usd=t.neto[t.neto > 0].mean(), pierde_usd=t.neto[t.neto < 0].mean(),
                         neto_año=t.neto.sum() / 8.75, dd=(eq - eq.cummax()).min(),
                         años_pos=int((t.groupby(t.date.dt.year).neto.sum() > 0).sum()),
                         dev=res["desarrollo"], val=res["validacion"], prueba=res["prueba"],
                         n_val=res["n_validacion"]))
    r = pd.DataFrame(rows)
    r["pasa"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    r.to_csv(exp / "resultados.csv", index=False)
    pd.concat(allops).to_csv(exp / "ops.csv.gz", index=False)
    write_manifest(exp, experimento="modelo de días mínimos (150 $ / 500 $, 2 límites)", reglas=__doc__)
    pd.set_option("display.width", 280, "display.max_colwidth", 50)
    print(r[["variante", "ops_año", "gana", "objetivo", "stop", "gana_usd", "pierde_usd", "dev", "val", "prueba",
             "neto_año", "años_pos", "dd", "pasa"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
