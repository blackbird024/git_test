"""Mismo trabajo completo que en el NQ, ahora en ORO (GC.v.0 1 min de Databento, operado como MGC: 10 $/punto, tick 0,1).
Reglas idénticas a run_rangos_multi_tf.py, run_rangos15_objetivos.py y run_rangos_objetivo_parcial.py, fijadas antes:
FASE 1 · ¿gira o continúa? Tras la 1.ª ruptura (1 tick) del rango de cada vela (5 min cada 5 min y 15/30 min de 0:00 a
         14:00 ET; 1 h cada hora de 0:00 a 13:00 ET; 4 h a las 2:00, 6:00 y 10:00 ET), carrera hasta el plazo
         máx(3,5 h, 2 × vela), máx. 15:55 ET: continuación = nivel roto + 1 rango, giro = otro lado del rango.
FASE 2 · Candidatas: continuación (o giro) gana en >= 8 de 9 años y diferencia >= 5 puntos. Estrategia: a favor (orden
         stop OCO, stop = otro lado, objetivo +1 rango) o en contra para las de giro (entrada en la ruptura, objetivo
         el otro lado, stop a 1 rango del nivel roto). Costes base, alto, alto + 4 ticks.
FASE 3 · Las velas de 15 min y las candidatas que pasen la fase 2 con objetivo 0,5 / 0,75 / 1 rango (base y alto).
Regla de selección: esperanza > 0 en desarrollo (2018-21) Y validación (2022-24), n_val >= 30; luego se mira la prueba.
Calidad de datos: se excluyen días con < 80 % de minutos entre 8:20 y 13:30 ET, días con cambio de contrato dentro del
día y el primer día tras un cambio de contrato (GC.v.0 rueda por volumen)."""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from execution_costs.costs import mgc
from validation.metrics import block_bootstrap_mean, trades_frame
from validation.runner import new_experiment, periods, split, write_manifest

SRC = "/home/user/git_test/vwap_lab/data/cache/GC_v0_1m.pkl"
NE, GT = 960, 0.1
TFS = {5: list(range(0, 841, 5)), 15: list(range(0, 841, 15)), 30: list(range(0, 841, 30)),
       60: list(range(0, 781, 60)), 240: [120, 360, 600]}


def gold_days():
    df = pd.read_pickle(SRC)
    df.index = df.index.tz_convert("America/New_York")
    arr = df[["open", "high", "low", "close", "volume"]].to_numpy()
    ins = df["instrument_id"].to_numpy()
    t = df.index
    dates = pd.Index(t.date)
    mins = (t.hour * 60 + t.minute).to_numpy()
    out, prev_ins, excl = [], None, dict(cobertura=0, cambio_contrato=0, primer_dia_tras_cambio=0)
    for d, idx in pd.Series(np.arange(len(df)), index=dates).groupby(level=0):
        d = pd.Timestamp(d)
        if d.weekday() >= 5:
            continue
        ii = idx.to_numpy()
        ii = ii[mins[ii] < NE]
        if len(ii) == 0:
            continue
        m = np.full((NE, 5), np.nan)
        m[mins[ii]] = arr[ii]
        cov = (~np.isnan(m[500:810, 0])).mean()
        di = np.unique(ins[ii])
        if cov < 0.8:
            excl["cobertura"] += 1
            prev_ins = di[-1]
            continue
        if len(di) > 1:
            excl["cambio_contrato"] += 1
            prev_ins = di[-1]
            continue
        if prev_ins is not None and di[0] != prev_ins:
            excl["primer_dia_tras_cambio"] += 1
            prev_ins = di[0]
            continue
        prev_ins = di[0]
        out.append((d, m))
    return out, excl


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
    up = np.nonzero(H[s0:ex] >= hi + GT - 1e-9)[0]
    dn = np.nonzero(L[s0:ex] <= lo - GT + 1e-9)[0]
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
    c, r = (H >= hi + R, L <= lo) if side == 1 else (L <= lo - R, H >= hi)
    ic = np.argmax(c) if c.any() else 10 ** 6
    ir = np.argmax(r) if r.any() else 10 ** 6
    if ic == ir == 10 ** 6:
        return "nada"
    if ic == ir:
        return "ambos"
    return "continua" if ic < ir else "gira"


def rnd(x):
    return round(x / GT) * GT


def run_strategy(D, dur, a, mode, frac, c):
    fills = []
    for date, m in D:
        st = setup(m, a, dur)
        if st is None or st == "mismo":
            continue
        hi, lo, R, side, k, ex = st
        if mode == "favor":
            tgt = hi + frac * R if side == 1 else lo - frac * R
            o = Order(side, "stop", k, rnd(lo - GT) if side == 1 else rnd(hi + GT), rnd(tgt), ex,
                      level=rnd(hi + GT) if side == 1 else rnd(lo - GT), k_last=k + 1)
        else:
            s = -side
            edge = hi if side == 1 else lo
            o = Order(s, "market", k + 1, rnd(edge + side * R), lo if side == 1 else hi, ex)
        f = simulate(date, m, ex + 1, o, c)
        if f is not None:
            fills.append(f)
    return trades_frame(fills, c)


def stats(t, per, c):
    sp = split(t, per)
    fm = t[t.date >= "2022-01-01"]
    lo_, hi_ = block_bootstrap_mean(fm.pnl.to_numpy()) if len(fm) > 20 else (np.nan, np.nan)
    srt = fm.pnl.sort_values(ascending=False)
    return dict(n=len(t), dev=sp["desarrollo"].pnl.mean(), val=sp["validacion"].pnl.mean(),
                prueba=sp["prueba"].pnl.mean(), n_val=len(sp["validacion"]), ic90_FM=f"[{lo_:.1f}; {hi_:.1f}]",
                top10=100 * srt[:10].sum() / fm.pnl.sum() if len(fm) and fm.pnl.sum() > 0 else np.nan,
                neto_año=t.pnl.sum() / 8.75, acierto=(t.pnl > 0).mean(), riesgo_med=t.risk_usd.median(),
                R_bruto=(t.gross_pts * c.point_value / t.risk_usd).mean(),
                años_pos=int((t.groupby(t.date.dt.year).pnl.sum() > 0).sum()))


def lab(dur, a):
    return f"{dur} min {a // 60}:{a % 60:02d} ET ({(a // 60 + 6) % 24}:{a % 60:02d} Italia)"


def main():
    D, excl = gold_days()
    per = periods("intradia", include_test=True)
    exp = new_experiment("oro_rangos")
    print(f"Días de oro: {len(D)} ({D[0][0].date()} a {D[-1][0].date()}) · excluidos: {excl}", flush=True)
    pd.set_option("display.width", 280, "display.max_rows", 400, "display.max_colwidth", 60)

    # FASE 1
    rows = []
    for dur, starts in TFS.items():
        for a in starts:
            for date, m in D:
                st = setup(m, a, dur)
                if st is None or st == "mismo":
                    continue
                rows.append(dict(tf=dur, a=a, date=date, res=race(m, st)))
    df = pd.DataFrame(rows)
    df.to_csv(exp / "fase1_carreras.csv.gz", index=False)
    out = []
    for (dur, a), g in df.groupby(["tf", "a"]):
        y = g.groupby(g.date.dt.year).res.agg(lambda s: (s == "continua").mean() - (s == "gira").mean())
        out.append(dict(tf=dur, a=a, ventana=lab(dur, a), dias=len(g), continua=(g.res == "continua").mean() * 100,
                        gira=(g.res == "gira").mean() * 100,
                        dif=((g.res == "continua").mean() - (g.res == "gira").mean()) * 100,
                        años_c=int((y > 0).sum()), años_g=int((y < 0).sum())))
    o = pd.DataFrame(out)
    o.to_csv(exp / "fase1_resumen.csv", index=False)
    print("\n=== FASE 1 · resumen por tamaño de vela ===")
    print(o.groupby("tf").agg(ventanas=("a", "size"), dif_media=("dif", "mean"), dif_max=("dif", "max"),
                              dif_min=("dif", "min")).round(1).to_string())
    print("\nTop 15 continuación:")
    print(o.sort_values("dif", ascending=False).head(15).drop(columns=["tf", "a"]).round(1).to_string(index=False))
    print("\nTop 10 giro:")
    print(o.sort_values("dif").head(10).drop(columns=["tf", "a"]).round(1).to_string(index=False))
    print("\nVelas de 30 min, 1 h y 4 h:")
    print(o[o.tf >= 30].drop(columns=["tf", "a"]).round(1).to_string(index=False))

    # FASE 2
    cc = o[(o.años_c >= 8) & (o.dif >= 5)].assign(modo="favor")
    cg = o[(o.años_g >= 8) & (o.dif <= -5)].assign(modo="contra")
    cand = pd.concat([cc, cg])
    print(f"\n=== FASE 2 · candidatas: {len(cc)} de continuación, {len(cg)} de giro ===", flush=True)
    costs = {"base": mgc("base"), "alto": mgc("alto"), "alto+4": mgc("alto", extra_slip_ticks=4)}
    r2 = []
    for _, cr in cand.iterrows():
        for cn, c in costs.items():
            t = run_strategy(D, cr.tf, cr.a, cr.modo, 1.0, c)
            r2.append(dict(ventana=cr.ventana, tf=cr.tf, a=cr.a, modo=cr.modo, coste=cn, **stats(t, per, c)))
    r2 = pd.DataFrame(r2)
    if len(r2):
        r2["pasa"] = (r2.dev > 0) & (r2.val > 0) & (r2.n_val >= 30)
        r2.to_csv(exp / "fase2_estrategias.csv", index=False)
        print(r2[r2.coste == "base"].drop(columns=["tf", "a", "coste"]).round(2).to_string(index=False))
        ok = r2[(r2.coste == "base") & r2.pasa]
        print("\nPasan la regla (base):", ok.ventana.tolist())
        if len(ok):
            print(r2[r2.ventana.isin(ok.ventana)].drop(columns=["tf", "a"]).round(2).to_string(index=False))
    else:
        ok = pd.DataFrame(columns=["tf", "a", "ventana", "modo"])

    # FASE 3
    print("\n=== FASE 3 · objetivos 0,5 / 0,75 / 1 rango ===", flush=True)
    sel = [(15, a) for a in TFS[15]] + [(int(x.tf), int(x.a)) for _, x in ok.iterrows() if x.modo == "favor" and x.tf != 15]
    r3 = []
    for (dur, a), frac in itertools.product(sel, (0.5, 0.75, 1.0)):
        for cn in ("base", "alto"):
            c = costs[cn]
            t = run_strategy(D, dur, a, "favor", frac, c)
            r3.append(dict(ventana=lab(dur, a), objetivo=frac, coste=cn, **stats(t, per, c)))
    r3 = pd.DataFrame(r3)
    r3["pasa"] = (r3.dev > 0) & (r3.val > 0) & (r3.n_val >= 30)
    r3.to_csv(exp / "fase3_objetivos.csv", index=False)
    b3 = r3[r3.coste == "base"]
    print("Pasan la regla (base):")
    print(b3[b3.pasa].drop(columns=["coste"]).round(2).to_string(index=False))
    pv = b3[b3.pasa].set_index(["ventana", "objetivo"]).index
    a3 = r3[r3.coste == "alto"].set_index(["ventana", "objetivo"])
    if len(pv):
        print("\nLas mismas con coste alto:")
        print(a3.loc[pv].drop(columns=["coste"]).round(2).to_string())
    print("\nVelas de 15 min: nº de ventanas con neto > 0 y con los 3 periodos > 0, por objetivo (base):")
    q = b3[b3.ventana.str.startswith("15 min")]
    print(q.groupby("objetivo").agg(neto_pos=("neto_año", lambda s: int((s > 0).sum())),
                                    tres_pos=("pasa", lambda s: int((s & (q.loc[s.index, "prueba"] > 0)).sum())),
                                    neto_medio_año=("neto_año", "mean")).round(0).to_string())
    write_manifest(exp, experimento="oro: gira o continúa + estrategias de rango (5/15/30/60/240 min)", reglas=__doc__,
                   datos=SRC, exclusiones=excl, periodos={k: [str(x.date()), str(y_.date())] for k, (x, y_) in per.items()})
    print("→", exp)


if __name__ == "__main__":
    main()
