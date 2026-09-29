"""Paso 1 de la investigación (sin optimizar y SIN tocar el test):

  1. inspecciona y valida los datos de cada instrumento (informa de los que faltan)
  2. baseline VWAP (modelo A) -> +EMA200 (B) -> +EMA50/200 (C) -> +EMA20 (D), mismo resto de reglas
  3. tipos de entrada (state / breakout / pullback) para cada modelo
  4. filtros de tendencia, uno a uno
  5. franjas horarias (desglose y ventana única)

Uso: python run_backtest.py            -> results/backtest.pkl, backtest/*.csv
"""
from __future__ import annotations

import json
import pickle

import pandas as pd

from src.common import ROOT, labs_disponibles, load_config, params


def fila(nombre, periodo, m):
    return {"variante": nombre, "periodo": periodo, **m}


def main() -> None:
    cfg = load_config()
    labs, faltan = labs_disponibles(cfg)
    out = {"datos": {n: l.info for n, l in labs.items()}, "faltan": faltan,
           "particiones": {n: {k: [str(a.date()), str(b.date())] for k, (a, b) in l.splits.items()} for n, l in labs.items()},
           "instrumentos": {}}
    print("DATOS:", json.dumps({n: {k: v for k, v in i.items() if k in ("desde", "hasta", "sesiones_validas", "invalidas_eliminadas")}
                               for n, i in out["datos"].items()}, indent=1, default=str))
    for n, e in faltan.items():
        print(f"SIN DATOS para {n}: {e}")
    (ROOT / "backtest").mkdir(exist_ok=True)
    for nombre, lab in labs.items():
        print(f"\n=== {nombre} ===")
        res = {"secuencia_modelos": [], "entradas": [], "filtros": [], "franjas": [], "ventanas": [], "muestra": None}
        # 2) Secuencia de modelos (baseline = A)
        for m in cfg["search"]["models"]:
            p = params(cfg, model=m)
            for per in ("train", "validation"):
                r, s = lab.run(p, per)
                res["secuencia_modelos"].append(fila(f"modelo {m}", per, s))
                if m == "A" and per == "train":
                    res["muestra"] = r.trades.head(20)
                    res["contadores_baseline"] = r.counters
                    print("baseline A train:", {k: s.get(k) for k in ("trades", "expectancy_R", "t_R", "profit_factor", "net_pnl")})
        # 3) Entradas por modelo
        for m in cfg["search"]["models"]:
            for et in cfg["search"]["entry_types"]:
                p = params(cfg, model=m, entry_type=et)
                for per in ("train", "validation"):
                    res["entradas"].append(fila(f"modelo {m} / {et}", per, lab.run(p, per)[1]))
        # 4) Filtros de tendencia uno a uno (sobre el baseline). EMA200 y EMA50/200 = modelos B y C
        for f in [None] + cfg["search"]["trend_filters"]:
            p = params(cfg, trend_filters=[] if f is None else [f])
            for per in ("train", "validation"):
                res["filtros"].append(fila("sin filtro" if f is None else f, per, lab.run(p, per)[1]))
        # 5) Franjas: desglose del baseline por franja y variante que solo opera en cada ventana
        from src.metrics import breakdowns
        for per in ("train", "validation"):
            r, _ = lab.run(params(cfg), per)
            if len(r.trades):
                t = breakdowns(r.trades, lab.inst)["franja"].reset_index().rename(columns={"index": "franja", "entry_min": "franja"})
                t.insert(0, "periodo", per)
                res["franjas"].append(t)
            for franja, w in lab.inst["hour_buckets"].items():
                res["ventanas"].append(fila(f"solo {franja}", per, lab.run(params(cfg, window=w), per)[1]))
        for k in ("secuencia_modelos", "entradas", "filtros", "ventanas"):
            res[k] = pd.DataFrame(res[k])
            res[k].to_csv(ROOT / "backtest" / f"{nombre}_{k}.csv", index=False)
        res["franjas"] = pd.concat(res["franjas"]) if res["franjas"] else pd.DataFrame()
        out["instrumentos"][nombre] = res
        cols = ["variante", "periodo", "trades", "expectancy_R", "expectancy_R_gross", "t_R", "profit_factor", "net_pnl", "max_dd_%"]
        print(res["secuencia_modelos"][cols].to_string(index=False))
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "backtest.pkl").write_bytes(pickle.dumps(out))
    print("\nGuardado en results/backtest.pkl y backtest/*.csv")


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    main()
