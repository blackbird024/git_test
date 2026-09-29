"""Interfaz de terminal.

  python -m src.run_backtest validate
  python -m src.run_backtest baseline   [--periodo train|validation|dev]
  python -m src.run_backtest variant    --set strategy.exits.tp_r=2 --set strategy.filters.ema.enabled=true
  python -m src.run_backtest optimize   [--periodo train]
  python -m src.run_backtest walkforward
  python -m src.run_backtest export     [--periodo ...] [--set ...] --salida reports/operaciones.csv
  python -m src.run_backtest report     # investigación completa + test final (una sola vez) + informe

El periodo de test solo se usa con `report` (etapa final) o con --incluir-test explícito.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .backtester import run
from .data_loader import DataQualityError
from .metrics import resumen
from .optimizer import elegir, rejilla
from .pipeline import RAIZ, barras_con_indicadores, load_config, preparar
from .walk_forward import walk_forward


def periodo(cfg: dict, nombre: str, incluir_test: bool = False) -> tuple[str, str]:
    sp = cfg["splits"]
    if nombre == "dev":
        return sp["train"][0], sp["validation"][1]
    if nombre == "test" and not incluir_test:
        raise SystemExit("El test final no se usa fuera de la etapa final (añade --incluir-test si es a propósito).")
    return tuple(sp[nombre])


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Investigación VWAP direccional MNQ 15 min")
    ap.add_argument("comando", choices=["validate", "baseline", "variant", "optimize", "walkforward", "export", "report"])
    ap.add_argument("--config", default=str(RAIZ / "config" / "settings.yaml"))
    ap.add_argument("--set", action="append", default=[], help="clave.anidada=valor (YAML)")
    ap.add_argument("--periodo", default="train", choices=["train", "validation", "dev", "test"])
    ap.add_argument("--incluir-test", action="store_true")
    ap.add_argument("--adverso", action="store_true", help="deslizamiento adverso")
    ap.add_argument("--salida", default=None)
    a = ap.parse_args(argv)
    cfg = load_config(a.config, a.set)
    try:
        ses, inf = preparar(cfg)
    except DataQualityError as e:
        raise SystemExit(f"DATOS NO VÁLIDOS: {e}")
    if a.comando == "validate":
        print(json.dumps(inf, indent=2, ensure_ascii=False, default=str))
        return
    if a.comando == "report":
        from .research import investigacion_completa
        investigacion_completa(cfg, ses, inf)
        return
    b = barras_con_indicadores(ses, cfg)
    desde, hasta = periodo(cfg, a.periodo, a.incluir_test)
    if a.comando in ("baseline", "variant", "export"):
        r = run(b, ses.sub, cfg, desde, hasta, adverso=a.adverso)
        print(json.dumps(resumen(r.trades, r.daily, r.capital_inicial), indent=2, ensure_ascii=False, default=str))
        print("contadores:", r.contadores)
        if a.comando == "export" or a.salida:
            salida = Path(a.salida or RAIZ / cfg["reports_dir"] / f"operaciones_{a.periodo}.csv")
            salida.parent.mkdir(parents=True, exist_ok=True)
            r.trades.to_csv(salida, index=False)
            print("operaciones exportadas a", salida)
    elif a.comando == "optimize":
        t = rejilla(b, ses.sub, cfg, desde, hasta)
        print(t.to_string(index=False))
        print("elección:", elegir(t, cfg["optimization"]["min_trades"]).to_dict())
    elif a.comando == "walkforward":
        t, _ = walk_forward(b, ses.sub, cfg)
        print(t.to_string(index=False))


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    main()
