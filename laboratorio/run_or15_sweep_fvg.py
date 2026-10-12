"""Mismo setup que run_asia_sweep_fvg.py (barrida de un lado del rango, pullback que entra en un FVG de 5/15 min y lo
respeta; lecturas GIRO y CONTINUACIÓN, mismas variantes de stop y objetivo), pero el rango es la PRIMERA VELA DE 15 MIN
de la sesión. Pregunta del usuario: "¿cuántas veces ocurre lo mismo en el rango de la primera vela de 15 min?".
Reglas fijadas antes de ver resultados:
  Londres: rango 9:00-9:15 Italia (apertura de Londres); barrida, FVG y señal hasta las 11:00 Italia; cierre 15:25.
  Nueva York: rango 9:30-9:45 ET (normalmente 15:30-15:45 Italia); barrida, FVG y señal hasta las 11:00 ET
  (killzone de NY); cierre 5 min antes del cierre de NY.
"""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import simulate
from data.loaders import sessions
from execution_costs.costs import mnq
from run_asia_sweep_fvg import signal, signal_cont
from run_crt_italia import N, rome_days
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest


def windows(date, cm, ses):
    if ses == "Londres":
        return dict(a0=540, a1=555, w0=555, kz=660, exit_k=925)
    d = date.date()
    t0 = pd.Timestamp(f"{d} 00:00", tz="Europe/Rome")
    k = int((pd.Timestamp(f"{d} 09:30", tz="America/New_York") - t0).total_seconds() // 60)
    return dict(a0=k, a1=k + 15, w0=k + 15, kz=k + 90, exit_k=cm)


def main():
    S = sessions()
    D = rome_days(S)
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    variants = {}
    for ses in ("Londres", "NY"):
        for tf, sm, tg in itertools.product((5, 15), ("barrida", "fvg"), ("asia", "2R")):
            variants[f"{ses} · GIRO · FVG {tf} min, stop {sm}, objetivo {'lado opuesto' if tg == 'asia' else tg}"] = (
                ses, signal, dict(tf=tf, stop_mode=sm, target=tg))
        for tf, sm, tg in itertools.product((5, 15), ("fvg", "nivel_asia"), ("1R", "2R")):
            variants[f"{ses} · CONTINUACIÓN · FVG {tf} min, stop {'nivel roto' if sm == 'nivel_asia' else sm}, objetivo {tg}"] = (
                ses, signal_cont, dict(tf=tf, stop_mode=sm, target=tg))
    exp = new_experiment("or15_barrida_fvg")
    rows, freq = [], []
    for ses in ("Londres", "NY"):
        nd = sw = 0
        for date, m, cm in D:
            w = windows(date, cm, ses)
            H, L = m[:, 1], m[:, 2]
            if np.isnan(H[w["a0"]:w["a1"]]).sum() > 7:
                continue
            nd += 1
            hi, lo = np.nanmax(H[w["a0"]:w["a1"]]), np.nanmin(L[w["a0"]:w["a1"]])
            sw += (np.nanmax(H[w["w0"]:w["kz"]]) > hi) or (np.nanmin(L[w["w0"]:w["kz"]]) < lo)
        freq.append(dict(sesion=ses, dias=nd, barre_un_lado=sw / nd))
        print(f"{ses}: {nd} días · barre un lado del rango de 15 min antes de las 11:00: {sw / nd * 100:.1f} %", flush=True)
    for name, (ses, fn, p) in variants.items():
        for scen in ("base", "alto"):
            c = mnq(scen)
            fills = []
            for date, m, cm in D:
                w = windows(date, cm, ses)
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
            rows.append(dict(variante=name, coste=scen, periodo="TODO", n=len(t), dias_pct=len(t) / freq[0 if ses == "Londres" else 1]["dias"],
                             objetivo=(r == "objetivo").mean(), stop=(r == "stop").mean(), tiempo=(r == "tiempo").mean(),
                             gana_neto=(t.pnl > 0).mean(), gan_media=t.pnl[t.pnl > 0].mean(),
                             perd_media=t.pnl[t.pnl < 0].mean(), esperanza=t.pnl.mean(),
                             R_bruto=(t.gross_pts * 2 / t.risk_usd).mean()))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    pd.DataFrame(freq).to_csv(exp / "frecuencias.csv", index=False)
    b = res[res.coste == "base"]
    piv = b[b.periodo != "TODO"].pivot_table(index="variante", columns="periodo", values="esperanza", sort=False)
    sel = piv[(piv.desarrollo > 0) & (piv.validacion > 0)].index.tolist()
    write_manifest(exp, experimento="barrida del rango de la 1.ª vela de 15 min + FVG", reglas=__doc__,
                   seleccionadas=sel, periodos={k: [str(a.date()), str(b_.date())] for k, (a, b_) in per.items()})
    pd.set_option("display.width", 280, "display.max_rows", 200, "display.max_colwidth", 80)
    tot = b[b.periodo == "TODO"].set_index("variante")
    out = piv[["desarrollo", "validacion", "prueba"]].round(1)
    for col in ("n", "dias_pct", "objetivo", "stop", "gana_neto", "gan_media", "perd_media", "R_bruto"):
        out[col] = tot[col].round(3 if col == "R_bruto" else 2)
    print(out.to_string())
    print("Coste alto, desarrollo/validación/prueba:")
    print(res[(res.coste == "alto") & (res.periodo != "TODO")].pivot_table(index="variante", columns="periodo",
                                                                          values="esperanza", sort=False).round(1).to_string())
    print("Seleccionadas (dev>0 y val>0):", sel)
    print("→", exp)


if __name__ == "__main__":
    main()
