"""Orquestación: datos → validación → sesiones → estructura 1 h → backtests → métricas → informe."""
import hashlib
import json
import subprocess
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import bars, data_io, engine, stats, structure
from .config import Config, to_dict


class RunError(RuntimeError):
    pass


def load_and_validate(cfg: Config):
    df = data_io.read_csv(cfg.data_file, cfg.timezone)
    if cfg.start_date:
        df = df[df.index >= pd.Timestamp(cfg.start_date, tz=cfg.timezone)]
    if cfg.end_date:
        df = df[df.index < pd.Timestamp(cfg.end_date, tz=cfg.timezone) + pd.Timedelta(days=1)]
    s = cfg.strategy
    v = data_io.validate(df, cfg.instrument.tick_size, cfg.bar_minutes, s.session_start.strftime("%H:%M"),
                         s.session_end.strftime("%H:%M"))
    return df, v


def vol_regime(sess):
    """Terciles del rango medio (máx − mín)/cierre de las 20 sesiones ANTERIORES (sin usar la sesión actual)."""
    rows = [(str(s.date.date()), (s.h.max() - s.l.min()) / s.c[-1] if len(s.c) else np.nan) for s in sess]
    r = pd.Series([x[1] for x in rows], index=[x[0] for x in rows])
    prior = r.rolling(20, min_periods=20).mean().shift(1)
    q = prior.expanding(min_periods=60).quantile(1 / 3).shift(1), prior.expanding(min_periods=60).quantile(2 / 3).shift(1)
    lab = pd.Series("sin_historial", index=r.index)
    ok = prior.notna() & q[0].notna()
    lab[ok & (prior <= q[0])] = "baja"
    lab[ok & (prior > q[0]) & (prior <= q[1])] = "media"
    lab[ok & (prior > q[1])] = "alta"
    return lab.to_dict()


def _sha(path: Path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True,
                                       cwd=Path(__file__).parent).strip()
    except Exception:  # noqa: BLE001
        return "desconocida"


def backtest(cfg: Config, write=True):
    df, v = load_and_validate(cfg)
    if not v.ok:
        raise RunError("datos inválidos: " + "; ".join(v.fatal))
    sess, cal_warn = bars.sessions(df, cfg.strategy, cfg.bar_minutes)
    hb = bars.hourly_bars(df, cfg.strategy.hourly_min_bars)
    piv = structure.find_pivots(hb, cfg.strategy.pivot_left, cfg.strategy.pivot_right)
    regime = vol_regime([s for s in sess if not s.invalid_reason])
    sm = int((cfg.strategy.session_end.hour * 60 + cfg.strategy.session_end.minute)
             - (cfg.strategy.session_start.hour * 60 + cfg.strategy.session_start.minute))
    dates = [str(s.date.date()) for s in sess]
    periods = stats.split_dates(dates, cfg.split)

    def one(use_filter, costs=None, risk=None):
        tr, lg, eq = engine.run(sess, piv, cfg, use_filter=use_filter, costs=costs, risk=risk)
        t, l = engine.trades_df(tr), engine.logs_df(lg)
        if len(t):
            t["vol_regime"] = t["session"].map(regime).fillna("sin_historial")
            t["periodo"] = t["session"].map(lambda d: next(k for k, (a, b) in periods.items() if a <= d <= b))
        l["periodo"] = l["session"].map(lambda d: next(k for k, (a, b) in periods.items() if a <= d <= b))
        return t, l

    res = {}
    variants = {"completa": dict(use_filter=True), "sin_filtro_1h": dict(use_filter=False)}
    for name, kw in variants.items():
        res[name] = one(**kw)
    stress = {}
    for sname, sc in cfg.stress_costs.items():
        c2 = replace(cfg.costs, **sc)
        stress[sname] = {name: one(costs=c2, **kw) for name, kw in variants.items()}
    sens = {}
    for rp in cfg.raw.get("sensitivity_risk_pct", []):
        sens[f"riesgo {rp:.2%}"] = one(True, risk=replace(cfg.risk, risk_pct=rp))
    sens["tamaño fijo 1 contrato"] = one(True, risk=replace(cfg.risk, sizing_mode="fixed", fixed_contracts=1))

    def summ(t, l, eq0):
        return stats.summary(t, l, eq0, cfg.bar_minutes, sm)

    table = []
    for name, (t, l) in res.items():
        eq0 = cfg.risk.initial_capital
        table.append(dict(version=name, periodo="total", **summ(t, l, eq0)))
        for p in periods:
            tp = t[t.periodo == p] if len(t) else t
            lp = l[l.periodo == p]
            eqp = float(tp["equity_before"].iloc[0]) if len(tp) else eq0
            table.append(dict(version=name, periodo=p, **summ(tp, lp, eqp)))
    for sname, d in stress.items():
        for name, (t, l) in d.items():
            table.append(dict(version=f"{name} · costes {sname}", periodo="total", **summ(t, l, cfg.risk.initial_capital)))
            for p in periods:
                tp = t[t.periodo == p] if len(t) else t
                eqp = float(tp["equity_before"].iloc[0]) if len(tp) else cfg.risk.initial_capital
                table.append(dict(version=f"{name} · costes {sname}", periodo=p, **summ(tp, l[l.periodo == p], eqp)))
    for sname, (t, l) in sens.items():
        table.append(dict(version=f"sensibilidad: {sname}", periodo="total", **summ(t, l, cfg.risk.initial_capital)))
    summary = pd.DataFrame(table)
    boot = {name: {"iid": stats.bootstrap(t["net_R"].to_numpy(), cfg.bootstrap_samples, cfg.seed, 1) if len(t) else {},
                   "bloques_5": stats.bootstrap(t["net_R"].to_numpy(), cfg.bootstrap_samples, cfg.seed, 5) if len(t) else {}}
            for name, (t, l) in res.items()}
    manifest = dict(fecha=datetime.now().isoformat(timespec="seconds"), version_codigo=_git(),
                    datos=dict(archivo=str(cfg.data_file), sha256=_sha(cfg.data_file), etiqueta=cfg.data_label,
                               filas=v.rows, primera=v.first, ultima=v.last),
                    validacion=asdict(v), aviso_calendario=cal_warn, velas_1h=len(hb.h),
                    velas_1h_descartadas_incompletas=hb.dropped, pivotes=dict(highs=len(piv.hi_val), lows=len(piv.lo_val)),
                    periodos={k: list(v_) for k, v_ in periods.items()}, configuracion=to_dict(cfg))
    out = dict(results=res, stress=stress, sens=sens, summary=summary, bootstrap=boot, manifest=manifest,
               periods=periods)
    if write:
        from .report import write_report
        out["dir"] = write_report(cfg, out)
    return out
