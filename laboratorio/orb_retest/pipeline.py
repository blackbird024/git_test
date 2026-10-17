"""Orquestación: carga, ejecución por escenario de costes, tamaño, desgloses y congelación de reglas."""
import json
import subprocess
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from data.loaders import daily_from_sessions, sessions
from .config import BASELINE, COST_SCENARIOS, VERSION, Config, Risk
from .engine import run, size_and_account
from .metrics import by_group, part_metrics

LAB = Path(__file__).resolve().parents[1]
OUT = LAB / "reports" / "MNQ_ORB_RETEST_v1"
FREEZE = OUT / "FREEZE.json"
PARTS = ("desarrollo", "validacion", "prueba")


def git_rev():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=LAB, text=True).strip()
    except Exception:
        return "desconocida"


def label(dates: pd.Series, cfg: Config) -> pd.Series:
    p = asdict(cfg.partition)
    lab = pd.Series("fuera", index=dates.index)
    for k in PARTS:
        a, b = pd.Timestamp(p[k][0]), pd.Timestamp(p[k][1])
        lab[(dates >= a) & (dates <= b)] = k
    return lab


def check_freeze(cfg: Config):
    if not FREEZE.exists():
        raise SystemExit("La partición de PRUEBA está cerrada: primero congela las reglas con --congelar.")
    f = json.loads(FREEZE.read_text())
    if f["strategy_hash"] != cfg.strategy_hash():
        raise SystemExit(f"Las reglas actuales ({cfg.strategy_hash()}) no son las congeladas ({f['strategy_hash']}). "
                         "Una prueba con reglas cambiadas ya no es independiente.")
    return f


def freeze(cfg: Config):
    OUT.mkdir(parents=True, exist_ok=True)
    d = dict(version=VERSION, strategy_hash=cfg.strategy_hash(), git=git_rev(),
             fecha=pd.Timestamp.now().isoformat(timespec="seconds"), reglas=asdict(cfg.strategy),
             particion=asdict(cfg.partition),
             nota="Reglas congeladas tras ver SOLO desarrollo y validación. La prueba se abre una vez con estas reglas.")
    FREEZE.write_text(json.dumps(d, indent=2, ensure_ascii=False))
    return d


def context(S):
    """Variables conocidas ANTES de cada sesión: rango medio de las 20 sesiones previas (volatilidad)."""
    d = daily_from_sessions(S)
    rng = (d.high - d.low).rolling(20).mean().shift(1)
    return pd.DataFrame(dict(vol20_prev=rng))


def run_all(cfg: Config = BASELINE, include_test=False, scenarios=None, S=None):
    S = S if S is not None else sessions()
    scenarios = scenarios or list(COST_SCENARIOS)
    res = {}
    for sc in scenarios:
        c = replace(cfg, costs=COST_SCENARIOS[sc])
        t, days = run(S, c)
        for x in (t, days):
            if len(x):
                x["particion"] = label(x["date"], c)
        if not include_test:
            t = t[t.particion != "prueba"] if len(t) else t
            days = days[days.particion != "prueba"]
        res[sc] = (t.reset_index(drop=True), days.reset_index(drop=True))
    return res


def add_context(t: pd.DataFrame, S, thresholds=None):
    ctx = context(S)
    t = t.join(ctx, on="date")
    if thresholds is None:
        dev = t[t.particion == "desarrollo"]
        thresholds = dict(or_width=list(np.nanquantile(dev.or_width, [1 / 3, 2 / 3])),
                          vol20_prev=list(np.nanquantile(dev.vol20_prev.dropna(), [1 / 3, 2 / 3])))
    for k in ("or_width", "vol20_prev"):
        a, b = thresholds[k]
        t[k + "_tercil"] = np.where(t[k] <= a, "bajo", np.where(t[k] <= b, "medio", "alto"))
        t.loc[t[k].isna(), k + "_tercil"] = "sin_dato"
    return t, thresholds


def metrics_table(t, days, cfg: Config, sized=None):
    out = {}
    for p in PARTS + ("total_fuera_de_muestra",):
        if p == "total_fuera_de_muestra":
            tp_, dp_ = t[t.particion.isin(["validacion", "prueba"])], days[days.particion.isin(["validacion", "prueba"])]
        else:
            tp_, dp_ = t[t.particion == p], days[days.particion == p]
        if len(dp_) == 0:
            continue
        sz = sized[sized.particion == p] if sized is not None and p in PARTS else None
        out[p] = part_metrics(tp_, dp_, sz)
    return out


def breakdowns(t: pd.DataFrame):
    t = t.copy()
    t["año"] = t.date.dt.year
    t["lado"] = np.where(t.side == 1, "largo", "corto")
    return {k: by_group(t, ["particion", k]).reset_index() for k in
            ("año", "lado", "or_width_tercil", "vol20_prev_tercil", "roll_week", "reason")}


def sized_runs(t: pd.DataFrame, budgets=(25, 50, 100), base=BASELINE):
    out = {}
    for b in budgets:
        cfg = replace(base, risk=Risk(risk_usd=b))
        z = []
        for p in PARTS:                                   # cada partición empieza con el capital inicial
            x = t[t.particion == p]
            if len(x):
                z.append(size_and_account(x, cfg))
        out[b] = pd.concat(z) if z else pd.DataFrame()
    return out
