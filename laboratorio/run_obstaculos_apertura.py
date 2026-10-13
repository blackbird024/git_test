"""Pregunta del usuario: "hoy en la apertura de NY el precio rompió abajo pero estaba el Low de Asia".
¿La ruptura a favor de la vela de 5 min que termina en la apertura (9:25-9:30 ET) y en el dato (8:25-8:30 ET) funciona
peor cuando hay un nivel importante EN EL CAMINO (entre el nivel roto y el objetivo)? Hora de Italia para los niveles.
Niveles: Asia = máx/mín de 2:00-6:00 Italia (definición del usuario); Londres = máx/mín de 9:00 Italia hasta el inicio
de la vela; día anterior = máx/mín de la sesión regular de ayer (PDH/PDL).
Estrategia: la de run_rangos_objetivo_parcial.py (orden stop OCO, stop = otro lado, objetivo 0,75 rango, plazo 3,5 h).
"En el camino": el nivel está más allá del lado roto y a menos de 0,75 rango (antes del objetivo). Para Asia y Londres
se exige además que el nivel siga intacto (no superado antes de la vela). Coste base. Es un análisis, no una regla nueva."""
import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from data.loaders import TICK, daily_from_sessions, sessions
from execution_costs.costs import mnq
from run_crt_italia import rome_days
from strategies.features import daily_context
from validation.metrics import trades_frame
from validation.runner import new_experiment, periods, split, write_manifest

FRAC = 0.75


def main():
    S = sessions()
    ctx = daily_context(daily_from_sessions(S))
    D = rome_days(S)
    per = periods("intradia", include_test=True)
    exp = new_experiment("obstaculos_apertura")
    c = mnq("base")
    rows = []
    for et_hm, lab in (("09:25", "apertura NY (5 min 9:25 ET)"), ("08:25", "dato 8:30 (5 min 8:25 ET)")):
        for date, m, cm in D:
            d = date.date()
            t0 = pd.Timestamp(f"{d} 00:00", tz="Europe/Rome")
            a = int((pd.Timestamp(f"{d} {et_hm}", tz="America/New_York") - t0).total_seconds() // 60)
            H, L = m[:, 1], m[:, 2]
            if np.isnan(H[a:a + 5]).sum() > 2 or np.isnan(H[120:360]).sum() > 120:
                continue
            hi, lo = np.nanmax(H[a:a + 5]), np.nanmin(L[a:a + 5])
            R = hi - lo
            if R <= 0:
                continue
            s0, ex = a + 5, min(a + 5 + 210, cm)
            up = np.nonzero(H[s0:ex] >= hi + TICK)[0]
            dn = np.nonzero(L[s0:ex] <= lo - TICK)[0]
            ku = up[0] + s0 if len(up) else None
            kd = dn[0] + s0 if len(dn) else None
            if (ku is None and kd is None) or (ku is not None and ku == kd):
                continue
            side, k = (1, ku) if kd is None or (ku is not None and ku < kd) else (-1, kd)
            edge = hi if side == 1 else lo
            tgt = edge + side * FRAC * R
            o = Order(side, "stop", k, lo - TICK if side == 1 else hi + TICK, round(tgt / TICK) * TICK, ex,
                      level=edge + side * TICK, k_last=k + 1)
            f = simulate(date, m, ex + 1, o, c)
            if f is None:
                continue
            ah, al = np.nanmax(H[120:360]), np.nanmin(L[120:360])
            lh, ll = np.nanmax(H[540:a]), np.nanmin(L[540:a])
            mh, ml = np.nanmax(H[360:a]), np.nanmin(L[360:a])          # máx/mín desde el fin de Asia hasta la vela
            cd = ctx.get(date, {})
            ph, pl = cd.get("prev_high", np.nan), cd.get("prev_low", np.nan)

            def en_camino(lvl, intacto=True):
                if np.isnan(lvl):
                    return False
                dist = side * (lvl - edge)
                return 0 < dist < FRAC * R

            asia = (al if side == -1 else ah)
            asia_ok = (ml > al) if side == -1 else (mh < ah)          # Asia intacta antes de la vela
            lond = (ll if side == -1 else lh)
            prev = (pl if side == -1 else ph)
            rows.append(dict(ventana=lab, date=date, pnl=f.gross_pts * 2 - c.round_trip_usd() if False else None, fill=f,
                             asia=en_camino(asia) and asia_ok, londres=en_camino(lond),
                             dia_anterior=en_camino(prev)))
    t = trades_frame([r["fill"] for r in rows], c)
    flags = pd.DataFrame([{k: v for k, v in r.items() if k not in ("fill", "pnl")} for r in rows])
    t = pd.concat([t.reset_index(drop=True), flags.drop(columns=["date"])], axis=1)
    t["cualquiera"] = t.asia | t.londres | t.dia_anterior
    t.to_csv(exp / "ops.csv.gz", index=False)
    out = []
    for lab, g in t.groupby("ventana"):
        for col in ("asia", "londres", "dia_anterior", "cualquiera"):
            for val, gg in g.groupby(col):
                sp = split(gg, per)
                out.append(dict(ventana=lab, nivel=col, en_camino=val, n=len(gg), pct=len(gg) / len(g) * 100,
                                acierto=(gg.pnl > 0).mean() * 100, llega_obj=(gg.reason == "objetivo").mean() * 100,
                                esperanza=gg.pnl.mean(), dev=sp["desarrollo"].pnl.mean(),
                                val=sp["validacion"].pnl.mean(), prueba=sp["prueba"].pnl.mean()))
    o = pd.DataFrame(out)
    o.to_csv(exp / "resumen.csv", index=False)
    pd.set_option("display.width", 220)
    print(o.round(1).to_string(index=False))
    write_manifest(exp, experimento="niveles en el camino de la ruptura de apertura/dato", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
