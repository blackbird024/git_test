"""Ejecuta el laboratorio VWAP + EMA.

    python -m vwap_lab.run_all --config vwap_lab/config/vwap_lab.yaml --step select   # desarrollo + validación → congela
    python -m vwap_lab.run_all --config vwap_lab/config/vwap_lab.yaml --step oos      # OOS (una vez), estrés, robustez, WF
    python -m vwap_lab.run_all --config vwap_lab/config/vwap_lab.yaml --step report   # informe final
`--step all` ejecuta los tres en orden (la congelación se escribe en disco ANTES de calcular el OOS).

Regla de selección (fijada antes de ver resultados): para cada estrategia, entre umbral ∈ {sin filtro, 0,05 … 0,20} y
objetivo ∈ {1R, 1,5R, 2R}, se elige la configuración con mayor esperanza en R en VALIDACIÓN entre las que tienen
esperanza > 0 en DESARROLLO, esperanza > 0 en VALIDACIÓN y al menos `min_trades_validation` operaciones en validación.
(La condición "> 0 en validación" se añadió el 10-oct-2026 ANTES de calcular el OOS del oro, para cumplir el criterio
14 del usuario; no altera MNQ, que no tenía configuraciones positivas en desarrollo.) Si ninguna cumple → sin
candidato. El "mejor candidato" de cada instrumento-sesión es el de mayor min(esperanza desarrollo, validación).
Se informa siempre además la configuración de partida (umbral 0,10, objetivo 2R).
"""
import argparse
import itertools
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .src.backtest.engine import run_session, to_df
from .src.data import loader
from .src.indicators import core
from .src.metrics.stats import day_block_bootstrap, summary
from .src.strategies import signals as _sig
from .src.strategies.signals import signals

SESSION_MIN = {"london": 180, "newyork": 385}
STRATEGIES = _sig.STRATEGIES


# ───────────────────────── preparación ─────────────────────────
def prepare(cfg, sym, sname):
    ic = cfg["instruments"][sym]
    path = Path(ic["data_file"])
    if not path.exists():
        return None, f"no existe {path}"
    df, v, q = loader.load(path, ic["tick_size"], cfg.get("bar_minutes", 5))
    if not v.ok:
        return None, "datos inválidos: " + "; ".join(v.fatal)
    o, h, l, c, vol = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
    p = cfg["strategy"]
    g = dict(o=o, h=h, l=l, c=c, ema9=core.ema(c, 9), ema20=core.ema(c, 20), ema21=core.ema(c, 21),
             ema50=core.ema(c, 50), atr=core.atr(h, l, c, p["atr_period"]), rsi=core.rsi(c, 14))
    k = p["ema50_slope_bars"]
    d50 = np.full(len(c), np.nan)
    d50[k:] = g["ema50"][k:] - g["ema50"][:-k]
    scfg = dict(cfg["sessions"][sname], name=sname)
    sess = loader.sessions(df, scfg, cfg["data_quality"], cfg.get("bar_minutes", 5))
    items = []
    for s in sess:
        if s.invalid:
            continue
        ix = s.idx
        a = {key: g[key][ix] for key in g}
        a["ema50_delta"] = d50[ix]
        a["vwap"] = core.session_vwap(h[ix], l[ix], c[ix], vol[ix])
        a["slope"] = core.vwap_slope(a["vwap"], a["atr"], p["slope_bars"])
        items.append((s, a))
    info = dict(validacion=v.__dict__, calidad=q, sesiones=len(sess), sesiones_validas=len(items),
                invalidas=pd.Series([s.invalid for s in sess if s.invalid]).value_counts().to_dict())
    return dict(sym=sym, sname=sname, inst=dict(ic, symbol=sym), items=items, info=info), None


def periods(prep, split):
    dates = [str(s.date.date()) for s, _ in prep["items"]]
    n = len(dates)
    a, b = int(round(n * split[0])), int(round(n * (split[0] + split[1])))
    return {"desarrollo": (dates[0], dates[a - 1]), "validacion": (dates[a], dates[b - 1]), "oos": (dates[b], dates[-1])}


def run_config(prep, cfg, strat, thr, target, costs_name="base", stop_mode="bar", max_trades=None, daily_loss_R=None,
               until=None):
    p, risk = cfg["strategy"], cfg["risk"]
    costs = dict(cfg["costs"][costs_name], limit_fill_ticks_through=cfg["costs"]["limit_fill_ticks_through"])
    eq = risk["initial_capital"]
    out, raw = [], 0
    skipped = dict(hueco=0, stop_pequeno=0, riesgo=0)
    tick = prep["inst"]["tick_size"]
    for s, a in prep["items"]:
        if until and str(s.date.date()) > until:
            break
        side, ref = signals(a, strat, thr, p, tick)
        raw += int((side != 0).sum())
        tr, eq = run_session(s, a, side, ref, prep["inst"], costs, p, risk, eq, strat, thr, target, stop_mode,
                             max_trades or p["max_trades_per_session"], daily_loss_R, skipped, cfg.get("bar_minutes", 5))
        out += tr
    t = to_df(out)
    return t, raw, skipped


def psum(t, prep, per, key):
    a, b = per[key]
    tp = t[(t.date >= a) & (t.date <= b)] if len(t) else t
    days = [str(s.date.date()) for s, _ in prep["items"] if a <= str(s.date.date()) <= b]
    cap0 = float(tp["equity_before"].iloc[0]) if len(tp) else 50000.0
    s = summary(tp, len(days), cap0, SESSION_MIN[prep["sname"]])
    lo, hi = day_block_bootstrap(tp, days) if len(tp) else (np.nan, np.nan)
    s.update(ic90_R_bajo=lo, ic90_R_alto=hi)
    return s


# ───────────────────────── paso 1: selección (sin OOS) ─────────────────────────
def step_select(cfg, out_dir, only=None):
    fpath = out_dir / "reglas_congeladas.yaml"
    frozen = yaml.safe_load(fpath.read_text()) if (only and fpath.exists()) else {}
    p = cfg["strategy"]
    for sym, ic in cfg["instruments"].items():
        for sname in ic["sessions"]:
            key = f"{sym}_{sname}"
            if only and sym not in only:
                continue
            prep, err = prepare(cfg, sym, sname)
            d = out_dir / key
            d.mkdir(parents=True, exist_ok=True)
            if err:
                frozen[key] = {"estado": "BLOQUEADO", "motivo": err}
                print(key, "BLOQUEADO:", err)
                continue
            per = periods(prep, cfg["split"])
            (d / "datos.json").write_text(json.dumps(dict(prep["info"], periodos=per), indent=2, ensure_ascii=False, default=str))
            rows = []
            for strat, thr, tg in itertools.product(STRATEGIES, p["thresholds"], p["targets_R"]):
                t, raw, sk = run_config(prep, cfg, strat, thr, tg, until=per["validacion"][1])
                r = dict(estrategia=strat, umbral="sin filtro" if thr is None else thr, objetivo_R=tg,
                         senales_brutas_dev_val=raw, **{f"desc_{k}": v for k, v in sk.items()})
                for k in ("desarrollo", "validacion"):
                    s = psum(t, prep, per, k)
                    r.update({f"{k}_{m}": s.get(m, np.nan) for m in ("n", "esperanza_R", "esperanza_usd", "pf", "dd_usd",
                                                                     "neto", "costes", "acierto", "ic90_R_bajo")})
                rows.append(r)
            grid = pd.DataFrame(rows)
            grid.to_csv(d / "rejilla_desarrollo_validacion.csv", index=False)
            sel = cfg["selection"]
            cands = {}
            for strat, g in grid.groupby("estrategia"):
                ok = g[(g.validacion_n >= sel["min_trades_validation"]) & (g.validacion_esperanza_R > 0) &
                       ((g.desarrollo_esperanza_R > 0) if sel["require_positive_development"] else True)]
                if len(ok):
                    b = ok.sort_values("validacion_esperanza_R", ascending=False).iloc[0]
                    cands[strat] = dict(umbral=None if b.umbral == "sin filtro" else float(b.umbral), objetivo_R=float(b.objetivo_R),
                                        esperanza_R_desarrollo=float(b.desarrollo_esperanza_R),
                                        esperanza_R_validacion=float(b.validacion_esperanza_R),
                                        n_validacion=int(b.validacion_n), configs_probadas=int(len(g)))
            best = max(cands, key=lambda k: min(cands[k]["esperanza_R_desarrollo"], cands[k]["esperanza_R_validacion"])) if cands else None
            frozen[key] = dict(estado="OK", periodos=per, candidatos=cands, mejor_candidato=best,
                               partida=dict(umbral=p["base_threshold"], objetivo_R=p["base_target_R"]))
            print(key, "candidatos:", {k: (v["umbral"], v["objetivo_R"], round(v["esperanza_R_validacion"], 3)) for k, v in cands.items()},
                  "mejor:", best, flush=True)
    (out_dir / "reglas_congeladas.yaml").write_text(
        "# Escrito por --step select ANTES de calcular el OOS. No modificar después de ver el OOS.\n" +
        yaml.safe_dump(frozen, allow_unicode=True, sort_keys=False))
    return frozen


# ───────────────────────── paso 2: OOS, estrés, robustez, walk-forward ─────────────────────────
def step_oos(cfg, out_dir, only=None):
    frozen = yaml.safe_load((out_dir / "reglas_congeladas.yaml").read_text())
    p = cfg["strategy"]
    for key, fz in frozen.items():
        if fz.get("estado") != "OK":
            continue
        sym, sname = key.split("_", 1)
        if only and sym not in only:
            continue
        prep, _ = prepare(cfg, sym, sname)
        per = fz["periodos"]
        d = out_dir / key
        res, trades_all = [], []
        configs = {f"{k} (candidato)": (k, v["umbral"], v["objetivo_R"]) for k, v in fz["candidatos"].items()}
        configs.update({f"{k} (partida 0,10 / 2R)": (k, p["base_threshold"], p["base_target_R"]) for k in STRATEGIES})
        for label, (strat, thr, tg) in configs.items():
            for cn in ("base", "stress", "severe"):
                t, raw, sk = run_config(prep, cfg, strat, thr, tg, costs_name=cn)
                if cn == "base":
                    trades_all.append(t.assign(config=label))
                for k in ("desarrollo", "validacion", "oos"):
                    s = psum(t, prep, per, k)
                    res.append(dict(config=label, estrategia=strat, umbral=thr, objetivo_R=tg, escenario_costes=cn, periodo=k, **s))
        R = pd.DataFrame(res)
        R.to_csv(d / "resultados_dev_val_oos.csv", index=False)
        T = pd.concat(trades_all) if trades_all else pd.DataFrame()
        T.to_csv(d / "operaciones.csv", index=False)
        # ── robustez de cada candidato (y de la configuración de partida del mejor)
        rob = []
        for strat, v in fz["candidatos"].items():
            thr, tg = v["umbral"], v["objetivo_R"]
            base_t = T[T.config == f"{strat} (candidato)"]
            oos_t = base_t[base_t.date >= per["oos"][0]]
            fm = base_t[base_t.date >= per["validacion"][0]]
            for lab, sub in (("validacion+oos", fm), ("oos", oos_t)):
                if len(sub) == 0:
                    continue
                dsum = sub.groupby("date").R.sum().sort_values()
                wk = sub.groupby(pd.to_datetime(sub.date).dt.to_period("W")).R.sum().sort_values()
                rob.append(dict(estrategia=strat, prueba="sin el mejor día", muestra=lab, esperanza_R=(sub.R.sum() - dsum.iloc[-1]) / max(len(sub) - 1, 1)))
                rob.append(dict(estrategia=strat, prueba="sin la mejor semana", muestra=lab, esperanza_R=(sub.R.sum() - wk.iloc[-1]) / max(len(sub) - 1, 1)))
                rob.append(dict(estrategia=strat, prueba="solo largos", muestra=lab, esperanza_R=sub[sub.side == 1].R.mean(), n=int((sub.side == 1).sum())))
                rob.append(dict(estrategia=strat, prueba="solo cortos", muestra=lab, esperanza_R=sub[sub.side == -1].R.mean(), n=int((sub.side == -1).sum())))
                rob.append(dict(estrategia=strat, prueba="mejor día / neto", muestra=lab, valor=float(dsum.iloc[-1] / sub.R.sum()) if sub.R.sum() > 0 else np.nan))
            thrs = [x for x in p["thresholds"] if x is not None]
            neigh_thr = [x for x in thrs if thr is not None and abs(x - thr) <= 0.051 and x != thr] or ([0.05] if thr is None else [])
            neigh_tg = [x for x in p["targets_R"] if abs(x - tg) <= 0.51 and x != tg]
            for nt, ntg in [(x, tg) for x in neigh_thr] + [(thr, x) for x in neigh_tg]:
                t2, _, _ = run_config(prep, cfg, strat, nt, ntg)
                for k in ("validacion", "oos"):
                    rob.append(dict(estrategia=strat, prueba=f"vecino umbral={nt} objetivo={ntg}R", muestra=k,
                                    esperanza_R=psum(t2, prep, per, k).get("esperanza_R", np.nan)))
            for lab, kw in (("stop por ATR", dict(stop_mode="atr")), ("máx. 1 operación/sesión", dict(max_trades=1)),
                            ("stop diario 2R", dict(daily_loss_R=2.0))):
                t2, _, _ = run_config(prep, cfg, strat, thr, tg, **kw)
                for k in ("validacion", "oos"):
                    rob.append(dict(estrategia=strat, prueba=lab, muestra=k, esperanza_R=psum(t2, prep, per, k).get("esperanza_R", np.nan)))
            # volatilidad y hora (validación + OOS)
            if len(fm):
                atrp = {str(s.date.date()): float(np.nanmean(a["atr"][:6]) / a["c"][0]) for s, a in prep["items"]}
                ser = pd.Series(atrp)
                q = ser.rolling(250, min_periods=60).quantile(1 / 3).shift(1), ser.rolling(250, min_periods=60).quantile(2 / 3).shift(1)
                reg = pd.Series("sin_historial", index=ser.index)
                reg[ser <= q[0]] = "baja"; reg[(ser > q[0]) & (ser <= q[1])] = "media"; reg[ser > q[1]] = "alta"
                f2 = fm.assign(regimen=fm.date.map(reg))
                for rg, g2 in f2.groupby("regimen"):
                    rob.append(dict(estrategia=strat, prueba=f"volatilidad {rg}", muestra="validacion+oos", esperanza_R=g2.R.mean(), n=len(g2)))
                for hr, g2 in fm.groupby("hour"):
                    rob.append(dict(estrategia=strat, prueba=f"hora de señal {hr:02d}", muestra="validacion+oos", esperanza_R=g2.R.mean(), n=len(g2)))
        pd.DataFrame(rob).to_csv(d / "robustez.csv", index=False)
        # ── ablación del filtro (objetivo 2R)
        abl = []
        for strat in STRATEGIES:
            off, raw_off, _ = run_config(prep, cfg, strat, None, p["base_target_R"])
            off_sig = set(off.signal_time)
            for thr in p["thresholds"]:
                t, raw, _ = run_config(prep, cfg, strat, thr, p["base_target_R"])
                rem = off[~off.signal_time.isin(set(t.signal_time))]
                dv = t[t.date <= per["validacion"][1]]
                sdv = summary(dv, 1, cfg["risk"]["initial_capital"])
                abl.append(dict(estrategia=strat, umbral="sin filtro" if thr is None else thr, senales_originales=raw_off,
                                senales_filtradas=raw_off - raw, operaciones=len(t),
                                ganadoras_eliminadas=int((rem.net_usd > 0).sum()), perdedoras_eliminadas=int((rem.net_usd < 0).sum()),
                                esperanza_R_dev_val=sdv.get("esperanza_R"), pf_dev_val=sdv.get("pf"), dd_usd_dev_val=sdv.get("dd_usd"),
                                costes_dev_val=sdv.get("costes"),
                                esperanza_R_validacion=psum(t, prep, per, "validacion").get("esperanza_R"),
                                esperanza_R_oos=psum(t, prep, per, "oos").get("esperanza_R")))
        pd.DataFrame(abl).to_csv(d / "ablacion_filtro_vwap.csv", index=False)
        # ── walk-forward anual: la configuración de cada año se elige solo con datos anteriores
        wf = []
        grid_trades = {}
        for strat, thr, tg in itertools.product(STRATEGIES, p["thresholds"], p["targets_R"]):
            grid_trades[(strat, thr, tg)], _, _ = run_config(prep, cfg, strat, thr, tg)
        years = sorted({int(s.date.year) for s, _ in prep["items"]})
        for strat in STRATEGIES:
            for y in years[2:]:
                best, bv = None, -np.inf
                for (s_, thr, tg), t in grid_trades.items():
                    if s_ != strat or len(t) == 0:
                        continue
                    past = t[t.date < f"{y}-01-01"]
                    if len(past) >= cfg["selection"]["min_trades_validation"] and past.R.mean() > 0 and past.R.mean() > bv:
                        best, bv = (thr, tg), past.R.mean()
                if best is None:
                    wf.append(dict(estrategia=strat, año=y, config="sin candidato", n=0, esperanza_R=np.nan, neto_usd=0.0))
                    continue
                cur = grid_trades[(strat,) + best]
                cur = cur[(cur.date >= f"{y}-01-01") & (cur.date <= f"{y}-12-31")]
                wf.append(dict(estrategia=strat, año=y, config=f"umbral={best[0]} objetivo={best[1]}R", n=len(cur),
                               esperanza_R=cur.R.mean() if len(cur) else np.nan, neto_usd=float(cur.net_usd.sum())))
        pd.DataFrame(wf).to_csv(d / "walk_forward.csv", index=False)
        # ── descriptivo: pendiente del VWAP frente al resultado (sin filtro, objetivo 2R, desarrollo + validación)
        allt = pd.concat([grid_trades[(s_, None, 2.0)] for s_ in STRATEGIES if (s_, None, 2.0) in grid_trades])
        allt = allt[allt.date <= per["validacion"][1]]
        if len(allt):
            allt["pend_a_favor"] = allt.slope * allt.side
            allt["tramo"] = pd.qcut(allt.pend_a_favor, 10, duplicates="drop")
            allt.groupby("tramo", observed=True).R.agg(["count", "mean"]).to_csv(d / "pendiente_vs_resultado.csv")
        print(key, "OOS y robustez ok", flush=True)


# ───────────────────────── paso 3: informe ─────────────────────────
def step_report(cfg, out_dir):
    from .report import write
    write(cfg, out_dir)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="vwap_lab/config/vwap_lab.yaml")
    ap.add_argument("--step", default="all", choices=["select", "oos", "report", "all"])
    ap.add_argument("--only", nargs="*", help="limitar a estos instrumentos (fusiona con las reglas ya congeladas)")
    a = ap.parse_args(argv)
    cfg = yaml.safe_load(Path(a.config).read_text())
    global STRATEGIES
    STRATEGIES = tuple(cfg.get("strategies", _sig.STRATEGIES))
    np.random.seed(cfg["seed"])
    out = Path(cfg["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "entorno.json").write_text(json.dumps(dict(python=sys.version, plataforma=platform.platform(),
                                                      pandas=pd.__version__, numpy=np.__version__, config=cfg), indent=2,
                                                 ensure_ascii=False, default=str))
    if a.step in ("select", "all"):
        step_select(cfg, out, a.only)
    if a.step in ("oos", "all"):
        step_oos(cfg, out, a.only)
    if a.step in ("report", "all"):
        step_report(cfg, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
