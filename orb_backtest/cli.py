"""Interfaz de línea de comandos.

    python -m orb_backtest --config CONFIG [run]   ejecuta el backtest y genera el informe (por defecto)
    python -m orb_backtest --config CONFIG validate valida los datos sin ejecutar el backtest
    python -m orb_backtest test                    ejecuta las pruebas automatizadas
    python -m orb_backtest synthetic --out FILE    genera el dataset SINTÉTICO de demostración

Códigos de salida: 0 correcto · 1 error de configuración · 2 datos inválidos · 3 error de ejecución · 4 pruebas fallidas
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="orb_backtest", description="ORB 1h + estructura 1h + entrada 5m")
    ap.add_argument("command", nargs="?", default="run", choices=["run", "validate", "test", "synthetic", "report"])
    ap.add_argument("--config")
    ap.add_argument("--out", default="orb_backtest/data/SINTETICO_MNQ_5m.csv")
    a = ap.parse_args(argv)
    if a.command == "test":
        return 0 if subprocess.call([sys.executable, "-m", "pytest", "-q", str(Path(__file__).parent / "tests")]) == 0 else 4
    if a.command == "synthetic":
        from .synthetic import write_demo
        p = write_demo(a.out)
        print(f"dataset SINTÉTICO escrito en {p}")
        return 0
    from .config import ConfigError, load
    from .data_io import DataError
    if not a.config:
        print("error: falta --config", file=sys.stderr)
        return 1
    try:
        cfg = load(a.config)
    except ConfigError as e:
        print(f"error de configuración: {e}", file=sys.stderr)
        return 1
    from .pipeline import RunError, backtest, load_and_validate
    try:
        if a.command == "validate":
            _, v = load_and_validate(cfg)
            from dataclasses import asdict
            print(json.dumps(asdict(v), indent=2, ensure_ascii=False))
            print("DATOS VÁLIDOS" if v.ok else "DATOS INVÁLIDOS")
            return 0 if v.ok else 2
        out = backtest(cfg)
    except DataError as e:
        print(f"datos inválidos: {e}", file=sys.stderr)
        return 2
    except RunError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2 if "datos inválidos" in str(e) else 3
    s = out["summary"]
    cols = ["version", "periodo", "operaciones", "expectativa_R", "profit_factor", "resultado_neto", "dd_max_usd"]
    print(s[s.version.isin(["completa", "sin_filtro_1h"])][cols].to_string(index=False))
    print(f"\ninforme: {out['dir']}/INFORME.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
