"""Datos del forward: descarga diaria de NQ 1 min (Databento), guardada APPEND-ONLY en forward_testing/raw/nq/ con su
SHA-256 en raw/MANIFIESTO.csv, y comprobaciones de calidad.

- Antes de descargar se estima el coste (metadata.get_cost). Si supera 0,50 $ NO se descarga (regla del proyecto).
- Los archivos descargados no se modifican nunca; si un rango se vuelve a pedir, se guarda como archivo nuevo.
- El conjunto de trabajo = data/processed/NQ_1M.parquet (historia) + raw/nq/*.parquet, con la misma limpieza del
  proyecto (src.data.calidad.limpiar: duplicados y velas imposibles).
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.calidad import limpiar
from src.data.datos import velas_1m

RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "forward_testing" / "raw" / "nq"
MANIFIESTO = RAIZ / "forward_testing" / "raw" / "MANIFIESTO.csv"
LIMITE_COSTE = 0.50
COLS = ["open", "high", "low", "close", "volume", "instrument_id"]


def conjunto() -> pd.DataFrame:
    base = velas_1m("NQ")
    partes = [base] + [pd.read_parquet(f)[COLS] for f in sorted(RAW.glob("*.parquet"))]
    df = pd.concat(partes).sort_index()
    df.index = df.index.tz_convert("UTC")
    df.index.name = "tiempo_utc"
    return limpiar(df)


def descargar(hasta: pd.Timestamp | None = None, log=print) -> dict:
    import databento as db
    clave = os.environ.get("DATABENTO_API_KEY")
    if not clave:
        return {"estado": "sin clave", "detalle": "DATABENTO_API_KEY no definida: no se descarga"}
    c = db.Historical(clave)
    desde = conjunto().index.max() + pd.Timedelta(minutes=1)
    fin_disp = pd.Timestamp(c.metadata.get_dataset_range(dataset="GLBX.MDP3")["end"])
    hasta = min(pd.Timestamp(hasta, tz="UTC") if hasta is not None else fin_disp, fin_disp)
    if hasta <= desde:
        return {"estado": "al día", "detalle": f"sin datos nuevos (último {desde - pd.Timedelta(minutes=1)})"}
    kw = dict(dataset="GLBX.MDP3", symbols=["NQ.v.0"], schema="ohlcv-1m", stype_in="continuous", start=desde, end=hasta)
    coste = float(c.metadata.get_cost(**kw))
    if coste > LIMITE_COSTE:
        return {"estado": "NO DESCARGADO", "detalle": f"coste estimado {coste:.4f} $ > {LIMITE_COSTE} $", "coste": coste}
    df = c.timeseries.get_range(**kw).to_df()
    if df.empty:
        return {"estado": "vacío", "detalle": "Databento no devolvió velas", "coste": coste}
    df = df[COLS]
    RAW.mkdir(parents=True, exist_ok=True)
    nombre = f"NQ_1m_{desde:%Y%m%dT%H%M}_{hasta:%Y%m%dT%H%M}.parquet"
    ruta = RAW / nombre
    df.to_parquet(ruta)
    h = hashlib.sha256(ruta.read_bytes()).hexdigest()
    fila = pd.DataFrame([{"archivo": nombre, "desde_utc": desde, "hasta_utc": hasta, "velas": len(df), "coste_$": round(coste, 4),
                          "sha256": h, "descargado_utc": datetime.now(timezone.utc).isoformat()}])
    fila.to_csv(MANIFIESTO, mode="a", header=not MANIFIESTO.exists(), index=False)
    log(f"descargadas {len(df)} velas {desde} -> {hasta} ({coste:.4f} $)")
    return {"estado": "descargado", "detalle": nombre, "velas": len(df), "coste": coste}


def verificar_raw() -> list[str]:
    """Los archivos descargados no se han modificado (SHA-256 del manifiesto)."""
    if not MANIFIESTO.exists():
        return []
    m = pd.read_csv(MANIFIESTO)
    problemas = []
    for _, f in m.iterrows():
        ruta = RAW / f.archivo
        if not ruta.exists():
            problemas.append(f"falta el archivo descargado {f.archivo}")
        elif hashlib.sha256(ruta.read_bytes()).hexdigest() != f.sha256:
            problemas.append(f"{f.archivo} ha cambiado después de descargarse")
    return problemas


def calidad_dia(m1: pd.DataFrame, fecha) -> list[tuple[str, str]]:
    """Problemas de datos de la sesión RTH del día NY `fecha`: lista de (gravedad, texto), gravedad GRAVE o AVISO.
    GRAVE invalida el día; AVISO solo se informa (p. ej. media sesión por festivo)."""
    out = []
    if m1.index.tz is None or str(m1.index.tz) != "UTC":
        out.append(("GRAVE", "índice de tiempo sin zona UTC"))
    if m1.index.duplicated().any():
        out.append(("GRAVE", "velas duplicadas"))
    if not m1.index.is_monotonic_increasing:
        out.append(("GRAVE", "velas desordenadas"))
    ny = m1.index.tz_convert("America/New_York")
    minuto = ny.hour * 60 + ny.minute
    dia = m1[(ny.normalize().tz_localize(None) == pd.Timestamp(fecha)) & (minuto >= 570) & (minuto < 960)]
    if len(dia) == 0:
        return out + [("AVISO", "sin datos RTH (festivo o datos aún no disponibles)")]
    ult = dia.index[-1].tz_convert("America/New_York")
    ult_min = ult.hour * 60 + ult.minute
    malas = int(((dia.high < dia.low) | (dia.open > dia.high) | (dia.open < dia.low) | (dia.close > dia.high) |
                 (dia.close < dia.low)).sum())
    if malas:
        out.append(("GRAVE", f"{malas} velas imposibles"))
    hueco = np.diff(dia.index.asi8) / 60e9
    if len(hueco) and hueco.max() > 5:
        out.append(("GRAVE", f"hueco de {hueco.max():.0f} min dentro de la sesión RTH"))
    if ult_min < 955:
        esperado = ult_min - 570 + 1
        tipo = "AVISO" if ult_min <= 800 else "GRAVE"          # cierre anticipado (≈ 13:15 NY) frente a datos cortados
        out.append((tipo, f"la sesión termina a las {ult:%H:%M} NY ({len(dia)} minutos)"
                          + (" — posible media sesión" if tipo == "AVISO" else " — datos incompletos")))
        return out
    if len(dia) < 0.95 * 390:
        out.append(("GRAVE", f"sesión RTH incompleta: {len(dia)} de 390 minutos"))
    return out
