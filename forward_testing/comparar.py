"""Forward (live/demo) frente a backtest (PRE-REGISTRO §8). Solo describe hasta tener ≥ 50 operaciones (zona de ruido)
o ≥ 15 (RSI(2)); con menos, las comparaciones no son concluyentes.

Fuentes:
  - forward_testing/survivors.csv (registro manual o convertido), columnas del PRE-REGISTRO.
  - El APEX_registro.csv del EA (MQL5/Files): `python -m forward_testing.comparar --ea ruta/APEX_registro.csv`
    lo convierte en operaciones (entrada COMPRAR/VENDER + CERRAR de la misma estrategia) y las añade a survivors.csv.
    El P&L del EA se calcula en puntos del CFD × 2 $ (equivalente a 1 MNQ; el EA opera 2 lotes de NAS100 = 2 $/punto).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
MINIMO = {"NOISE_ZONE": 50, "RSI2": 15}
NOMBRES_EA = {"Zona de ruido": "NOISE_ZONE", "RSI(2)": "RSI2", "RSI2": "RSI2"}


def desde_ea(ruta: Path, valor_punto: float = 2.0) -> pd.DataFrame:
    r = pd.read_csv(ruta)
    filas, abiertas = [], {}
    for _, x in r.iterrows():
        est = next((v for k, v in NOMBRES_EA.items() if k.lower() in str(x.estrategia).lower()), str(x.estrategia))
        if x.accion in ("COMPRAR", "VENDER"):
            abiertas[est] = x
        elif x.accion == "CERRAR" and est in abiertas:
            e = abiertas.pop(est)
            lado = 1 if e.accion == "COMPRAR" else -1
            bruto = (float(x.precio) - float(e.precio)) * lado * valor_punto
            filas.append({"date": str(e.hora_NY)[:10], "strategy": est, "signal_time": e.hora_NY, "side": "LONG" if lado == 1 else "SHORT",
                          "expected_entry": np.nan, "actual_entry": e.precio, "slippage": np.nan, "spread": np.nan,
                          "exit": x.precio, "gross_pnl": bruto, "net_pnl": bruto, "MAE": np.nan, "MFE": np.nan,
                          "reason": x.motivo, "notes": "importado de APEX_registro.csv (net = gross; el spread va en el precio)"})
    return pd.DataFrame(filas)


def comparar(forward: pd.DataFrame, referencia: dict) -> pd.DataFrame:
    """referencia: por estrategia, métricas del backtest (operaciones_mes, acierto_%, expectativa_$, hora_media...)."""
    filas = {}
    for est, ref in referencia.items():
        f = forward[forward.strategy == est]
        n = len(f)
        x = f.net_pnl.astype(float)
        meses = max((pd.to_datetime(f.date).max() - pd.to_datetime(f.date).min()).days / 30.4, 1) if n else np.nan
        filas[est] = {"operaciones_forward": n, "suficiente": n >= MINIMO[est],
                      "operaciones_mes_forward": round(n / meses, 1) if n else np.nan, "operaciones_mes_backtest": ref["operaciones_mes"],
                      "acierto_%_forward": round((x > 0).mean() * 100, 1) if n else np.nan, "acierto_%_backtest": ref["acierto_%"],
                      "expectativa_$_forward": round(x.mean(), 2) if n else np.nan, "expectativa_$_backtest": ref["expectativa_$"],
                      "deslizamiento_medio_forward": round(f.slippage.astype(float).mean(), 2) if n and f.slippage.notna().any() else np.nan,
                      "dd_forward_$": round(float((x.cumsum() - x.cumsum().cummax()).min()), 0) if n else np.nan,
                      "dd_p95_backtest_1_año_$": ref.get("dd_p95_1_año_$")}
    return pd.DataFrame(filas).T


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ea", type=Path, help="APEX_registro.csv del EA para importar")
    a = ap.parse_args()
    ruta = AQUI / "survivors.csv"
    f = pd.read_csv(ruta)
    if a.ea:
        nuevo = desde_ea(a.ea)
        f = pd.concat([f, nuevo], ignore_index=True).drop_duplicates(["strategy", "signal_time"])
        f.to_csv(ruta, index=False)
    ref = json.loads((AQUI / "referencia_backtest.json").read_text(encoding="utf-8"))
    print(comparar(f, ref).to_string())
    from forward_testing.deriva import evaluar
    print(evaluar(f).to_string())
