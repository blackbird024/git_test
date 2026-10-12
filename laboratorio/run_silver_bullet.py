"""ICT Silver Bullet, mecanizada para NQ/MNQ. Reglas fijadas ANTES de ver resultados (hora de Nueva York, ET):

Ventanas de una hora: 3:00-4:00 (Londres), 10:00-11:00 (NY AM), 14:00-15:00 (NY PM).
1. Liquidez: máximo y mínimo de la hora ANTERIOR a la ventana (p. ej. 9:00-10:00 para la de las 10:00).
2. Barrida: dentro de la ventana, la primera vela (del marco del FVG) que supera ese máximo → cortos (o perfora el
   mínimo → largos). Si la misma vela barre los dos lados, no se opera.
3. Desplazamiento: FVG en contra de la barrida (cortos: máximo de la vela i+1 < mínimo de la vela i−1) formado después
   de la barrida y dentro de la ventana; se usa el más reciente.
4. Entrada: el precio vuelve al FVG y lo respeta (cierra por debajo del borde superior en cortos) → entrada a mercado
   en la apertura siguiente, como muy tarde al final de la ventana. Se anula si antes supera el extremo de la barrida
   o ya ha tocado el objetivo.
5. Stop (variantes): extremo de la barrida + 1 tick, o borde del FVG + 1 tick.
6. Objetivo (variantes): la liquidez opuesta (mínimo de la hora anterior en cortos) o 2R.
7. Marco del FVG (variantes): 1, 3 y 5 min. Cierre forzoso: 9:25 ET para la ventana de las 3:00; 15:55 ET para las otras.
Una operación por ventana y día. Regla de selección: esperanza > 0 en desarrollo Y validación (coste base), n_val >= 30.
"""
import itertools

import pandas as pd

from backtests.intraday import simulate
from data.loaders import sessions
from execution_costs.costs import mnq
from run_asia_sweep_fvg import signal
from run_crt_italia import N, rome_days
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest

WINDOWS = {"3:00 ET (Londres)": 3, "10:00 ET (NY AM)": 10, "14:00 ET (NY PM)": 14}


def kwin(date, cm, hour):
    d = date.date()
    t0 = pd.Timestamp(f"{d} 00:00", tz="Europe/Rome")
    k = int((pd.Timestamp(f"{d} {hour:02d}:00", tz="America/New_York") - t0).total_seconds() // 60)
    if hour == 3:
        ex = int((pd.Timestamp(f"{d} 09:25", tz="America/New_York") - t0).total_seconds() // 60)
    else:
        ex = cm
    return dict(a0=k - 60, a1=k, w0=k, kz=k + 60, exit_k=min(ex, cm))


def main():
    S = sessions()
    D = rome_days(S)
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    variants = {f"SB {wn} · FVG {tf} min, stop {sm}, objetivo {'liquidez opuesta' if tg == 'asia' else tg}":
                (h, dict(tf=tf, stop_mode=sm, target=tg))
                for (wn, h), tf, sm, tg in itertools.product(WINDOWS.items(), (1, 3, 5), ("barrida", "fvg"), ("asia", "2R"))}
    exp = new_experiment("silver_bullet")
    rows = []
    for name, (h, p) in variants.items():
        for scen in ("base", "alto"):
            c = mnq(scen)
            fills = []
            for date, m, cm in D:
                w = kwin(date, cm, h)
                if w["kz"] > cm:
                    continue
                o = signal(m, **p, **w)
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
            lo, hi = block_bootstrap_mean(o_.pnl.to_numpy())
            srt = o_.pnl.sort_values(ascending=False)
            rows.append(dict(variante=name, coste=scen, periodo="TODO", n=len(t), dias_pct=len(t) / len(D),
                             objetivo=(r == "objetivo").mean(), stop=(r == "stop").mean(),
                             gana_neto=(t.pnl > 0).mean(), gan_media=t.pnl[t.pnl > 0].mean(),
                             perd_media=t.pnl[t.pnl < 0].mean(), esperanza=t.pnl.mean(),
                             R_bruto=(t.gross_pts * 2 / t.risk_usd).mean(), riesgo_mediano=t.risk_usd.median(),
                             ic90_FM_bajo=lo, ic90_FM_alto=hi,
                             top10_FM=100 * srt[:10].sum() / o_.pnl.sum() if o_.pnl.sum() > 0 else float("nan")))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    b = res[res.coste == "base"]
    piv = b[b.periodo != "TODO"].pivot_table(index="variante", columns="periodo", values="esperanza", sort=False)
    nv = b[b.periodo == "validacion"].set_index("variante").n.reindex(piv.index)
    sel = piv[(piv.desarrollo > 0) & (piv.validacion > 0) & (nv >= 30)].index.tolist()
    write_manifest(exp, experimento="ICT Silver Bullet", reglas=__doc__, seleccionadas=sel,
                   periodos={k: [str(a.date()), str(b_.date())] for k, (a, b_) in per.items()})
    pd.set_option("display.width", 300, "display.max_rows", 200, "display.max_colwidth", 80)
    tot = b[b.periodo == "TODO"].set_index("variante")
    out = piv[["desarrollo", "validacion", "prueba"]].round(1)
    for col in ("n", "dias_pct", "objetivo", "stop", "gana_neto", "gan_media", "perd_media", "R_bruto", "riesgo_mediano",
                "ic90_FM_bajo", "ic90_FM_alto", "top10_FM"):
        out[col] = tot[col].round(3 if col == "R_bruto" else 1 if "ic90" in col or "top" in col else 2)
    print(out.to_string())
    print("Seleccionadas (dev>0, val>0, n_val>=30):", sel)
    a = res[(res.coste == "alto") & (res.periodo != "TODO")].pivot_table(index="variante", columns="periodo",
                                                                         values="esperanza", sort=False)
    if sel:
        print("Coste alto de las seleccionadas:")
        print(a.loc[sel].round(1).to_string())
    print("→", exp)


if __name__ == "__main__":
    main()
