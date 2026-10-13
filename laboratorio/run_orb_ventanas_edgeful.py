"""Newsletter de edgeful (oct. 2026): "doble ruptura" de ORB de 15 min en NQ para las 37 ventanas de 3:00 a 12:00 ET.
(1) Reproducir sus porcentajes con nuestros datos (últimos 12 meses) y ver su estabilidad por año 2018-2026.
(2) Probar lo que sugieren ("cuando rompe un lado, el otro lado es el objetivo") como estrategia, con reglas fijadas antes:
    en la primera ruptura (1 tick fuera del rango, minuto a minuto), entrada a mercado en el minuto siguiente EN CONTRA
    de la ruptura; objetivo = el otro lado del rango; stop = entrada ± 1 × rango (1:1 aprox.) o ± 0,5 × rango.
    Si ambos lados se rompen en el mismo minuto, no se opera. Ventanas probadas: 5:45 (cierre 9:25 ET), 9:30 y 11:15
    (cierre 15:55 ET). Coste base del laboratorio.
"Doble ruptura en X h" = el máximo y el mínimo del rango se superan (1 tick) dentro de las X horas tras cerrar el rango.
"""
import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from data.loaders import TICK, nq_1m, sessions
from execution_costs.costs import mnq
from validation.metrics import summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest

NE = 960                                              # 0:00 → 16:00 ET


def et_days(S):
    df = nq_1m()
    arr = df[["open", "high", "low", "close", "volume"]].to_numpy()
    out = []
    for s in S:
        if s.close_min < 390:
            continue
        t0 = pd.Timestamp(f"{s.date.date()} 00:00", tz="America/New_York")
        lo, hi = df.index.searchsorted(t0), df.index.searchsorted(t0 + pd.Timedelta(minutes=NE))
        m = np.full((NE, 5), np.nan)
        mm = ((df.index[lo:hi] - t0).total_seconds() // 60).astype(int)
        m[mm] = arr[lo:hi]
        out.append((s.date, m))
    return out


def first_breaks(m, a):
    H, L = m[:, 1], m[:, 2]
    if np.isnan(H[a:a + 15]).sum() > 7:
        return None
    hi, lo = np.nanmax(H[a:a + 15]), np.nanmin(L[a:a + 15])
    up = np.nonzero(H[a + 15:] >= hi + TICK)[0]
    dn = np.nonzero(L[a + 15:] <= lo - TICK)[0]
    return hi, lo, (up[0] + a + 15 if len(up) else None), (dn[0] + a + 15 if len(dn) else None)


def main():
    S = sessions()
    D = et_days(S)
    exp = new_experiment("orb_ventanas_edgeful")
    starts = list(range(180, 721, 15))               # 3:00 … 12:00 ET (37 ventanas)
    rows = []
    for date, m in D:
        for a in starts:
            r = first_breaks(m, a)
            if r is None:
                continue
            hi, lo, ku, kd = r
            end = a + 15
            both = None if ku is None or kd is None else max(ku, kd)
            rows.append(dict(date=date, ventana=f"{a // 60}:{a % 60:02d}",
                             h15=both is not None and both < end + 90, h25=both is not None and both < end + 150,
                             h35=both is not None and both < end + 210, cierre=both is not None,
                             antes_930=both is not None and both < 570))
    f = pd.DataFrame(rows)
    f.to_csv(exp / "dobles_rupturas.csv.gz", index=False)
    last = f[f.date > f.date.max() - pd.Timedelta(days=365)]
    t12 = (last.groupby("ventana", sort=False)[["h15", "h25", "h35", "cierre"]].mean() * 100).round(1)
    print(f"Últimos 12 meses ({last.date.min().date()} a {last.date.max().date()}), % de sesiones con doble ruptura:")
    print(t12.loc[["5:45", "9:30", "11:15"]].to_string())
    print("5:45 antes de las 9:30 ET:", round(last[last.ventana == "5:45"].antes_930.mean() * 100, 1), "%")
    print("\nRanking últimos 12 meses (por 'cierre', ventanas desde 9:45):")
    print(t12.loc[[v for v in t12.index if int(v.split(':')[0]) * 60 + int(v.split(':')[1]) >= 585]]
          .sort_values("cierre", ascending=False).head(5).to_string())
    print("\nEstabilidad por año (doble ruptura en 3,5 h):")
    y = (f.groupby([f.date.dt.year, "ventana"], sort=False).h35.mean() * 100).unstack().round(1)
    print(y[["5:45", "9:30", "11:15"]].to_string())
    best = (f.groupby([f.date.dt.year, "ventana"], sort=False).h35.mean().unstack()).idxmax(axis=1)
    print("Ventana con más doble ruptura en 3,5 h cada año:", best.to_dict())
    rng = f.merge(pd.DataFrame(), how="cross") if False else None

    # (2) estrategia "el otro lado es el objetivo"
    per = periods("intradia", include_test=True)
    cal = pd.DatetimeIndex([d for d, _ in D])
    cals = calendar_split(cal, per)
    res = []
    c = mnq("base")
    for win, a, ex in (("5:45", 345, 565), ("9:30", 570, 955), ("11:15", 675, 955)):
        for sm in (1.0, 0.5):
            fills = []
            for date, m in D:
                r = first_breaks(m, a)
                if r is None:
                    continue
                hi, lo, ku, kd = r
                R = hi - lo
                if R <= 0:
                    continue
                cand = [(k, s) for k, s in ((ku, -1), (kd, 1)) if k is not None and k < ex]
                if not cand or (ku is not None and kd is not None and ku == kd):
                    continue
                k, side = min(cand)
                entry_ref = hi if side == -1 else lo
                o = Order(side, "market", k + 1, entry_ref - side * sm * R, lo if side == -1 else hi, ex, tag=win)
                fl = simulate(date, m, ex + 1, o, c)
                if fl is not None:
                    fills.append(fl)
            t = trades_frame(fills, c)
            t.to_csv(exp / f"ops_{win.replace(':', '')}_stop{sm}.csv.gz", index=False)
            for kk, tp in split(t, per).items():
                res.append(dict(ventana=win, stop=f"{sm} × rango", periodo=kk, **summary(tp, cals[kk], minutes_per_session=NE)))
            res.append(dict(ventana=win, stop=f"{sm} × rango", periodo="TODO", n=len(t), esperanza=t.pnl.mean(),
                            acierto=(t.pnl > 0).mean(), llega_otro_lado=(t.reason == "objetivo").mean(),
                            R_bruto=(t.gross_pts * 2 / t.risk_usd).mean(), riesgo_mediano=t.risk_usd.median()))
    res = pd.DataFrame(res)
    res.to_csv(exp / "resultados.csv", index=False)
    pd.set_option("display.width", 250)
    print("\nEstrategia 'el otro lado es el objetivo' (coste base, 1 MNQ):")
    print(res.pivot_table(index=["ventana", "stop"], columns="periodo", values="esperanza", sort=False).round(1).to_string())
    print(res[res.periodo == "TODO"][["ventana", "stop", "n", "acierto", "llega_otro_lado", "R_bruto", "riesgo_mediano"]]
          .round(3).to_string(index=False))
    write_manifest(exp, experimento="ventanas ORB 15 min (newsletter edgeful)", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
