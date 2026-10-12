"""Mismo setup (barrida de un lado del rango, pullback que entra en un FVG y lo respeta; lecturas GIRO y CONTINUACIÓN,
mismas variantes de stop y objetivo) con FVG de 1 min y 3 min, a petición del usuario. Rangos:
  Asia 2:00-6:00 Italia (hasta 11:00 Italia) · Londres 1.ª vela de 15 min 9:00-9:15 Italia (hasta 11:00 Italia) ·
  NY 1.ª vela de 15 min 9:30-9:45 ET (hasta 11:00 ET). Cierre forzoso: 15:25 Italia (Asia y Londres) / fin de NY.
Reglas idénticas a run_asia_sweep_fvg.py y run_or15_sweep_fvg.py; solo cambia el marco del FVG. Fijadas antes de ver
resultados. Regla de selección: esperanza > 0 en desarrollo Y validación con coste base y n_val >= 30.
"""
import itertools

import pandas as pd

from backtests.intraday import simulate
from data.loaders import sessions
from execution_costs.costs import mnq
from run_asia_sweep_fvg import signal, signal_cont
from run_crt_italia import N, rome_days
from run_or15_sweep_fvg import windows
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest


def win(date, cm, ses):
    if ses == "Asia":
        return dict(a0=120, a1=360, w0=360, kz=660, exit_k=925)
    return windows(date, cm, ses)


def main():
    S = sessions()
    D = rome_days(S)
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    variants = {}
    for ses, tf in itertools.product(("Asia", "Londres", "NY"), (1, 3)):
        for sm, tg in itertools.product(("barrida", "fvg"), ("asia", "2R")):
            variants[f"{ses} · GIRO · FVG {tf} min, stop {sm}, obj {'lado opuesto' if tg == 'asia' else tg}"] = (
                ses, signal, dict(tf=tf, stop_mode=sm, target=tg))
        for sm, tg in itertools.product(("fvg", "nivel_asia"), ("1R", "2R")):
            variants[f"{ses} · CONT · FVG {tf} min, stop {'nivel roto' if sm == 'nivel_asia' else sm}, obj {tg}"] = (
                ses, signal_cont, dict(tf=tf, stop_mode=sm, target=tg))
    ndays = {}
    exp = new_experiment("fvg_1m_3m")
    rows = []
    for name, (ses, fn, p) in variants.items():
        for scen in ("base", "alto"):
            c = mnq(scen)
            fills = []
            for date, m, cm in D:
                w = win(date, cm, ses)
                o = fn(m, **p, **w)
                if o is not None:
                    f = simulate(date, m, min(cm, w["exit_k"] + 1), o, c)
                    if f is not None:
                        fills.append(f)
            t = trades_frame(fills, c)
            if scen == "base":
                t.to_csv(exp / f"ops_{''.join(ch if ch.isalnum() else '_' for ch in name)}.csv.gz", index=False)
            for k, tp in split(t, per).items():
                rows.append(dict(variante=name, coste=scen, periodo=k, **summary(tp, cals[k], minutes_per_session=N)))
            r = t.reason.str.replace("stop_hueco", "stop").replace("cierre_sesion", "tiempo")
            o_ = t[t.date >= "2022-01-01"]
            lo, hi = block_bootstrap_mean(o_.pnl.to_numpy()) if len(o_) > 10 else (float("nan"), float("nan"))
            rows.append(dict(variante=name, coste=scen, periodo="TODO", n=len(t), dias_pct=len(t) / len(D),
                             objetivo=(r == "objetivo").mean(), stop=(r == "stop").mean(),
                             gana_neto=(t.pnl > 0).mean(), gan_media=t.pnl[t.pnl > 0].mean(),
                             perd_media=t.pnl[t.pnl < 0].mean(), esperanza=t.pnl.mean(),
                             R_bruto=(t.gross_pts * 2 / t.risk_usd).mean(), riesgo_mediano=t.risk_usd.median(),
                             ic90_FM_bajo=lo, ic90_FM_alto=hi))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    b = res[res.coste == "base"]
    piv = b[b.periodo != "TODO"].pivot_table(index="variante", columns="periodo", values="esperanza", sort=False)
    nv = b[b.periodo == "validacion"].set_index("variante").n.reindex(piv.index)
    sel = piv[(piv.desarrollo > 0) & (piv.validacion > 0) & (nv >= 30)].index.tolist()
    write_manifest(exp, experimento="barrida + FVG de 1 y 3 min (Asia, Londres 15 min, NY 15 min)", reglas=__doc__,
                   seleccionadas=sel, periodos={k: [str(a.date()), str(b_.date())] for k, (a, b_) in per.items()})
    pd.set_option("display.width", 300, "display.max_rows", 200, "display.max_colwidth", 70)
    tot = b[b.periodo == "TODO"].set_index("variante")
    out = piv[["desarrollo", "validacion", "prueba"]].round(1)
    for col in ("n", "dias_pct", "objetivo", "stop", "gana_neto", "gan_media", "perd_media", "R_bruto", "riesgo_mediano"):
        out[col] = tot[col].round(3 if col == "R_bruto" else 2)
    print(out.to_string())
    print("Seleccionadas (dev>0, val>0, n_val>=30):", sel)
    a = res[(res.coste == "alto") & (res.periodo != "TODO")].pivot_table(index="variante", columns="periodo",
                                                                         values="esperanza", sort=False)
    print(a.loc[sel].round(1).to_string() if sel else "")
    print("→", exp)


if __name__ == "__main__":
    main()
