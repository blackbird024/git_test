"""Descarga velas de 1 minuto de NQ y GC (contrato continuo) desde Databento.

Uso:
    python scripts/download_databento.py                 # solo muestra lo que COSTARÍA
    python scripts/download_databento.py --confirmar     # descarga de verdad

Necesita la variable de entorno DATABENTO_API_KEY. Nunca escribas la clave en el código.

Detalles que conviene entender:
- Dataset GLBX.MDP3 = datos oficiales de CME Globex.
- "NQ.v.0" = contrato continuo que siempre sigue al vencimiento con más volumen.
  Los precios NO están ajustados en los cambios de contrato (rolls). Para intradía no importa,
  porque cerramos todo cada día, pero los indicadores de varios días se calcularán con cuidado.
- Se guarda un archivo por instrumento y año en data/raw/ (formato parquet: compacto y rápido).
"""
import argparse
import os
import sys
from pathlib import Path

import databento as db
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DATASET = "GLBX.MDP3"
SYMBOLS = {"NQ": "NQ.v.0", "GC": "GC.v.0"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--desde", default="2015-01-01")
    parser.add_argument("--hasta", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    parser.add_argument("--confirmar", action="store_true", help="descargar (consume crédito)")
    args = parser.parse_args()

    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        sys.exit("Falta la variable de entorno DATABENTO_API_KEY.")
    client = db.Historical(key)

    total = 0.0
    for root, sym in SYMBOLS.items():
        cost = client.metadata.get_cost(dataset=DATASET, symbols=[sym], schema="ohlcv-1m",
                                        stype_in="continuous", start=args.desde, end=args.hasta)
        total += cost
        print(f"{root}: {args.desde} -> {args.hasta}  coste estimado ${cost:,.2f}")
    print(f"TOTAL estimado: ${total:,.2f}  (el crédito gratuito es de $125)")
    if not args.confirmar:
        print("No se ha descargado nada. Repite con --confirmar para descargar.")
        return

    RAW.mkdir(parents=True, exist_ok=True)
    # Año a año: si una descarga larga se corta, solo se repite ese año.
    first, last = pd.Timestamp(args.desde).year, pd.Timestamp(args.hasta).year
    for root, sym in SYMBOLS.items():
        for year in range(first, last + 1):
            out = RAW / f"{root}_1m_{year}.parquet"
            if out.exists():
                print(f"  {out.name}: ya existe, se omite")
                continue
            start = max(pd.Timestamp(args.desde), pd.Timestamp(f"{year}-01-01"))
            end = min(pd.Timestamp(args.hasta), pd.Timestamp(f"{year + 1}-01-01"))
            for attempt in range(1, 4):
                try:
                    data = client.timeseries.get_range(dataset=DATASET, symbols=[sym], schema="ohlcv-1m",
                                                       stype_in="continuous", start=start, end=end)
                    break
                except db.BentoError as exc:
                    print(f"  {root} {year}: intento {attempt} fallido ({exc})")
                    if attempt == 3:
                        raise
            df = data.to_df()  # índice ts_event en UTC = inicio de la vela
            df[["open", "high", "low", "close", "volume", "instrument_id"]].to_parquet(out)
            print(f"  {out.name}: {len(df):,} velas", flush=True)

if __name__ == "__main__":
    main()
