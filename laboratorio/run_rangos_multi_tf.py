"""Gira o continúa tras la 1.ª ruptura del rango de una vela, para velas de 5, 30, 60 y 240 min (NQ 2018-2026, ET).
Distancias iguales: continuación = nivel roto + 1 × rango; reversión = otro lado del rango.
Plazo = máx(3,5 h, 2 × duración de la vela) tras cerrar el rango, como muy tarde 15:55 ET.
Ventanas: 5 min cada 5 min y 30 min cada 30 min de 0:00 a 14:00 ET; 1 h en cada hora de 0:00 a 13:00 ET;
4 h alineadas con las velas de CME (2:00, 6:00, 10:00 ET).
FASE 2 (regla fijada antes de ver la fase 1): son candidatas las ventanas con continuación > reversión en >= 8 de 9 años
y diferencia total >= 5 puntos; se prueban como estrategia: orden stop OCO 1 tick fuera del rango, stop = otro lado,
objetivo = +1 rango, salida al plazo; costes base, alto y alto + 4 ticks. Regla de selección: dev>0 y val>0 (base).
"""
import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from data.loaders import TICK, sessions
from execution_costs.costs import mnq
from run_orb_ventanas_edgeful import NE, et_days
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest

TFS = {5: list(range(0, 841, 5)), 30: list(range(0, 841, 30)), 60: list(range(0, 781, 60)), 240: [120, 360, 600]}


def setup(m, a, dur):
    H, L = m[:, 1], m[:, 2]
    if np.isnan(H[a:a + dur]).sum() > dur / 2:
        return None
    hi, lo = np.nanmax(H[a:a + dur]), np.nanmin(L[a:a + dur])
    R = hi - lo
    if R <= 0:
        return None
    s0 = a + dur
    ex = min(s0 + max(210, 2 * dur), 955)
    if s0 >= ex:
        return None
    up = np.nonzero(H[s0:ex] >= hi + TICK)[0]
    dn = np.nonzero(L[s0:ex] <= lo - TICK)[0]
    ku = up[0] + s0 if len(up) else None
    kd = dn[0] + s0 if len(dn) else None
    if ku is None and kd is None:
        return None
    if ku is not None and ku == kd:
        return "mismo"
    side, k = (1, ku) if kd is None or (ku is not None and ku < kd) else (-1, kd)
    return hi, lo, R, side, k, ex


def race(m, st):
    hi, lo, R, side, k, ex = st
    H, L = m[k:ex, 1], m[k:ex, 2]
    if side == 1:
        c, r = H >= hi + R, L <= lo
    else:
        c, r = L <= lo - R, H >= hi
    ic = np.argmax(c) if c.any() else 10 ** 6
    ir = np.argmax(r) if r.any() else 10 ** 6
    if ic == ir == 10 ** 6:
        return "nada"
    if ic == ir:
        return "ambos"
    return "continua" if ic < ir else "gira"


def main():
    D = et_days(sessions())
    exp = new_experiment("rangos_multi_tf")
    rows = []
    for dur, starts in TFS.items():
        for a in starts:
            for date, m in D:
                st = setup(m, a, dur)
                if st is None or st == "mismo":
                    continue
                rows.append(dict(tf=dur, a=a, date=date, res=race(m, st)))
        print("tf", dur, "ok", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(exp / "carreras.csv.gz", index=False)
    out = []
    for (dur, a), g in df.groupby(["tf", "a"]):
        y = g.groupby(g.date.dt.year).res.agg(lambda s: (s == "continua").mean() - (s == "gira").mean())
        out.append(dict(tf=dur, ny=f"{a // 60}:{a % 60:02d}", italia=f"{(a // 60 + 6) % 24}:{a % 60:02d}", a=a,
                        dias=len(g), continua=(g.res == "continua").mean() * 100, gira=(g.res == "gira").mean() * 100,
                        dif=((g.res == "continua").mean() - (g.res == "gira").mean()) * 100,
                        años_c=int((y > 0).sum()), años_g=int((y < 0).sum())))
    o = pd.DataFrame(out)
    o.to_csv(exp / "resumen.csv", index=False)
    pd.set_option("display.width", 220, "display.max_rows", 400)
    for dur in TFS:
        x = o[o.tf == dur].drop(columns=["a"])
        print(f"\n=== velas de {dur} min · {len(x)} ventanas ===")
        if dur == 5:
            print("Top 12 continuación y top 8 giro:")
            print(x.sort_values("dif", ascending=False).head(12).round(1).to_string(index=False))
            print(x.sort_values("dif").head(8).round(1).to_string(index=False))
        else:
            print(x.round(1).to_string(index=False))
    cand = o[(o.años_c >= 8) & (o.dif >= 5)]
    print(f"\nCandidatas (>= 8/9 años y dif >= 5): {len(cand)}")
    print(cand.drop(columns=["a"]).round(1).to_string(index=False))

    per = periods("intradia", include_test=True)
    cals = calendar_split(pd.DatetimeIndex([d for d, _ in D]), per)
    costs = {"base": mnq("base"), "alto": mnq("alto"), "alto+4": mnq("alto", extra_slip_ticks=4)}
    res = []
    for _, cr in cand.iterrows():
        name = f"{cr.tf} min {cr.ny} ET ({cr.italia} Italia)"
        for cn, c in costs.items():
            fills = []
            for date, m in D:
                st = setup(m, cr.a, cr.tf)
                if st is None or st == "mismo":
                    continue
                hi, lo, R, side, k, ex = st
                o_ = Order(side, "stop", k, lo - TICK if side == 1 else hi + TICK, hi + R if side == 1 else lo - R, ex,
                           level=hi + TICK if side == 1 else lo - TICK, k_last=k + 1, tag=name)
                f = simulate(date, m, ex + 1, o_, c)
                if f is not None:
                    fills.append(f)
            t = trades_frame(fills, c)
            sp = split(t, per)
            fm = t[t.date >= "2022-01-01"]
            lo_, hi_ = block_bootstrap_mean(fm.pnl.to_numpy())
            srt = fm.pnl.sort_values(ascending=False)
            res.append(dict(variante=name, coste=cn, n=len(t), dev=sp["desarrollo"].pnl.mean(),
                            val=sp["validacion"].pnl.mean(), prueba=sp["prueba"].pnl.mean(),
                            n_val=len(sp["validacion"]), ic90_FM=f"[{lo_:.1f}; {hi_:.1f}]",
                            top10=100 * srt[:10].sum() / fm.pnl.sum() if fm.pnl.sum() > 0 else np.nan,
                            neto_año=t.pnl.sum() / 8.75, acierto=(t.pnl > 0).mean(),
                            riesgo_med=t.risk_usd.median(), años_pos=int((t.groupby(t.date.dt.year).pnl.sum() > 0).sum())))
            if cn == "base":
                t.to_csv(exp / f"ops_{cr.tf}_{cr.a}.csv.gz", index=False)
    r = pd.DataFrame(res)
    r.to_csv(exp / "estrategias.csv", index=False)
    r["selec"] = (r.dev > 0) & (r.val > 0) & (r.n_val >= 30)
    for cn in costs:
        print(f"\n== estrategia, coste {cn} ==")
        print(r[r.coste == cn].drop(columns=["coste"]).round(2).to_string(index=False))
    write_manifest(exp, experimento="gira o continúa + estrategia, velas de 5/30/60/240 min", reglas=__doc__)
    print("→", exp)


if __name__ == "__main__":
    main()
