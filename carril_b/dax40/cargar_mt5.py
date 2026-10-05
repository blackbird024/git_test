"""Carga el CSV de velas M1 exportado desde MT5 (Símbolos → Barras → Exportar) y lo deja en UTC y hora de Berlín.

    python -m carril_b.dax40.cargar_mt5 /ruta/GER40_M1.csv

Escribe carril_b/dax40/datos/GER40_M1.parquet (no se versiona) y su SHA-256 en datos/MANIFIESTO.csv, y muestra el
informe de integridad. El servidor de Pepperstone va a NY+7 (PREREGISTRO.md §1); el desfase se comprueba con los datos.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
DATOS = AQUI / "datos"
NY, BERLIN = "America/New_York", "Europe/Berlin"
SERVIDOR_MENOS_NY_H = 7


def _leer_texto(ruta: Path) -> str:
    b = ruta.read_bytes()
    for bom, cod in ((b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be"), (b"\xef\xbb\xbf", "utf-8-sig")):
        if b.startswith(bom):
            return b[len(bom):].decode(cod)
    if len(b) > 1 and b[1:2] == b"\x00":                      # UTF-16 LE sin BOM
        return b.decode("utf-16-le")
    return b.decode("utf-8")


def leer_csv_mt5(ruta: str | Path) -> pd.DataFrame:
    """Devuelve velas indexadas en UTC con open, high, low, close, tickvol, spread_pts (puede faltar)."""
    import io
    txt = _leer_texto(Path(ruta))
    primera = txt.split("\n", 1)[0]
    sep = "\t" if "\t" in primera else ("," if primera.count(",") >= 4 else ";")
    df = pd.read_csv(io.StringIO(txt), sep=sep)
    df.columns = [c.strip().strip("<>").lower() for c in df.columns]
    if "time" in df and "date" in df:
        ts = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str), format="%Y.%m.%d %H:%M:%S", errors="coerce")
        if ts.isna().mean() > 0.5:
            ts = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str), errors="coerce")
    else:
        ts = pd.to_datetime(df[df.columns[0]].astype(str), errors="coerce")
    out = pd.DataFrame({"open": df["open"].astype(float), "high": df["high"].astype(float), "low": df["low"].astype(float),
                        "close": df["close"].astype(float)})
    out["tickvol"] = df["tickvol"].astype(float) if "tickvol" in df else np.nan
    out["spread_pts"] = df["spread"].astype(float) if "spread" in df else np.nan
    out["t_servidor"] = ts.to_numpy()
    out = out.dropna(subset=["t_servidor"])
    return _a_utc(out)


def _a_utc(df: pd.DataFrame) -> pd.DataFrame:
    """Hora del servidor (NY+7, sin DST propio) → hora de NY → UTC. La hora ambigua del cambio de horario de otoño se
    resuelve por orden; la inexistente de primavera no tiene velas (el mercado está cerrado a esa hora)."""
    ny_local = pd.DatetimeIndex(df.t_servidor) - pd.Timedelta(hours=SERVIDOR_MENOS_NY_H)
    ny = ny_local.tz_localize(NY, ambiguous="infer" if ny_local.is_monotonic_increasing else "NaT",
                              nonexistent="NaT") if len(ny_local) else ny_local.tz_localize(NY)
    df = df.assign(t=ny).dropna(subset=["t"])
    df = df.set_index(pd.DatetimeIndex(df.pop("t")).tz_convert("UTC")).drop(columns="t_servidor")
    df.index.name = "t_utc"
    return df


def integridad(df: pd.DataFrame) -> dict:
    """Comprobaciones de PREREGISTRO §1. Devuelve el informe y la lista de sesiones válidas (fecha de Berlín)."""
    b = df.tz_convert(BERLIN)
    dup = int(b.index.duplicated().sum())
    b = b[~b.index.duplicated()].sort_index()
    imposibles = int(((b.high < b[["open", "close"]].max(axis=1)) | (b.low > b[["open", "close"]].min(axis=1))).sum())
    m = b.index.hour * 60 + b.index.minute
    xetra = b[(m >= 540) & (m < 1050)]
    fechas = xetra.index.date
    validas, motivos = [], {}
    for f, g in xetra.groupby(fechas):
        mins = g.index.hour * 60 + g.index.minute
        huecos = np.diff(np.r_[540, mins, 1050]) - 1
        hueco_tot = int(huecos[huecos > 5].sum())
        if len(g) < 300:
            motivos[f] = f"{len(g)} velas en 09:00-17:30"
        elif hueco_tot > 30:
            motivos[f] = f"huecos > 5 min suman {hueco_tot} min"
        else:
            validas.append(f)
    return {"velas": len(df), "duplicadas": dup, "imposibles": imposibles, "desde": str(b.index.min()), "hasta": str(b.index.max()),
            "sesiones_xetra": len(validas) + len(motivos), "sesiones_validas": validas, "excluidas": motivos,
            "spread_disponible": bool(df.spread_pts.notna().any())}


def comprobar_desfase(df: pd.DataFrame) -> dict:
    """El minuto de mayor recorrido medio (sobre las sesiones de lunes a viernes) debe ser 09:00 o 15:30 de Berlín."""
    b = df.tz_convert(BERLIN)
    rango = (b.high - b.low) / b.close
    por_min = rango.groupby(b.index.hour * 60 + b.index.minute).mean()
    top = por_min.sort_values(ascending=False).index[:3]
    hhmm = [f"{x // 60:02d}:{x % 60:02d}" for x in top]
    return {"top3_minutos_berlin": hhmm, "ok": hhmm[0] in ("09:00", "15:30")}


def huella(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def main(ruta_csv: str):
    ruta = Path(ruta_csv)
    df = leer_csv_mt5(ruta)
    rep, des = integridad(df), comprobar_desfase(df)
    DATOS.mkdir(exist_ok=True)
    salida = DATOS / "GER40_M1.parquet"
    df.to_parquet(salida)
    man = DATOS / "MANIFIESTO.csv"
    nuevo = not man.exists()
    with man.open("a", encoding="utf-8") as fh:
        if nuevo:
            fh.write("registrado_utc,archivo_origen,sha256_origen,sha256_parquet,velas,desde,hasta\n")
        fh.write(f"{pd.Timestamp.now('UTC'):%Y-%m-%dT%H:%M:%SZ},{ruta.name},{huella(ruta)},{huella(salida)},{rep['velas']},"
                 f"{rep['desde']},{rep['hasta']}\n")
    print(f"velas {rep['velas']} | {rep['desde']} → {rep['hasta']} (Berlín)")
    print(f"duplicadas {rep['duplicadas']} | imposibles {rep['imposibles']} | spread en el CSV: {'sí' if rep['spread_disponible'] else 'NO'}")
    print(f"sesiones Xetra {rep['sesiones_xetra']} | válidas {len(rep['sesiones_validas'])} | excluidas {len(rep['excluidas'])}")
    print(f"desfase: minutos de mayor recorrido {des['top3_minutos_berlin']} → {'OK' if des['ok'] else 'REVISAR (no seguir)'}")


if __name__ == "__main__":
    main(sys.argv[1])
