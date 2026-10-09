"""FASE 1 · Auditoría de los datos disponibles para el estudio ORB 5 min en MNQ.

Solo LEE los archivos (no modifica nada). Escribe reports/auditoria_datos.md y reports/auditoria_datos.json.

Uso:
    python data_audit.py
"""

import json
import pickle
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).resolve().parent.parent / "alpaca" / ".lab_cache"
OUT = Path(__file__).resolve().parent / "reports"
FILES = ["databento_nq_1m_2018_2024.pkl", "databento_glbx_1m.pkl", "dbn_NQ_5m.pkl"]
NY = "America/New_York"


def load(name):
    return pickle.loads((CACHE / name).read_bytes())


def audit(name):
    df = load(name)
    info = {"archivo": str(CACHE / name), "tamaño_MB": round((CACHE / name).stat().st_size / 1e6, 1),
            "tipo": type(df).__name__, "columnas": list(map(str, df.columns)), "filas_total": int(len(df))}
    if "symbol" in df.columns:
        info["símbolos"] = {str(k): int(v) for k, v in df.symbol.value_counts().items()}
        df = df[df.symbol == "NQ.c.0"]
    info["filas_NQ"] = int(len(df))
    idx = df.index
    info["zona_horaria_índice"] = str(idx.tz)
    info["primer_timestamp_UTC"] = str(idx.min().tz_convert("UTC"))
    info["último_timestamp_UTC"] = str(idx.max().tz_convert("UTC"))
    info["índice_ordenado"] = bool(idx.is_monotonic_increasing)
    info["timestamps_duplicados"] = int(idx.duplicated().sum())
    step = pd.Series(idx).diff().dropna()
    info["granularidad_modal"] = str(step.mode().iloc[0])
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    info["NaN_en_OHLC"] = int(np.isnan(np.c_[o, h, l, c]).sum())
    info["velas_incoherentes (high<max(o,c) o low>min(o,c))"] = int(((h < np.maximum(o, c) - 1e-9) | (l > np.minimum(o, c) + 1e-9)).sum())
    info["precios_fuera_de_tick_0.25"] = int((np.abs(np.round(c / 0.25) * 0.25 - c) > 1e-6).sum())
    if "volume" in df.columns:
        info["velas_volumen_0"] = int((df.volume == 0).sum())
    if "instrument_id" in df.columns:
        iid = df.instrument_id.to_numpy()
        ch = np.flatnonzero(iid[1:] != iid[:-1]) + 1
        info["contratos_distintos (instrument_id)"] = int(len(np.unique(iid)))
        info["cambios_de_contrato (rollovers)"] = [str(idx[k].tz_convert(NY)) for k in ch][:60]
    # sesiones regulares (9:30-16:00 NY)
    ny = idx.tz_convert(NY)
    mins = ny.hour * 60 + ny.minute
    rth = (mins >= 570) & (mins < 960)
    per_day = pd.Series(1, index=ny[rth]).groupby(ny[rth].normalize()).count()
    bar_min = int(step.mode().iloc[0].total_seconds() // 60)
    full = 390 // bar_min
    info["sesiones_con_datos_RTH"] = int(len(per_day))
    info["sesiones_RTH_completas"] = int((per_day == full).sum())
    info["sesiones_RTH_incompletas"] = {str(d.date()): int(n) for d, n in per_day[per_day != full].items()}
    first_bar = pd.Series(mins[rth], index=ny[rth]).groupby(ny[rth].normalize()).min()
    info["sesiones_sin_vela_09:30"] = [str(d.date()) for d, m in first_bar.items() if m != 570]
    return info, per_day


def main():
    OUT.mkdir(exist_ok=True)
    res, days = {}, {}
    for f in FILES:
        res[f], days[f] = audit(f)
        print(f, "auditado", flush=True)
    # solapamiento entre los dos archivos de 1 min
    a = load(FILES[0])
    b = load(FILES[1])
    b = b[b.symbol == "NQ.c.0"]
    common = a.index.intersection(b.index)
    ov = {"velas_comunes": int(len(common))}
    if len(common):
        diff = (a.loc[common, "close"] - b.loc[common, "close"]).abs()
        ov.update({"desde": str(common.min()), "hasta": str(common.max()), "diferencia_media_cierre_pts": round(float(diff.mean()), 4),
                   "velas_con_diferencia": int((diff > 1e-9).sum())})
    res["solapamiento_1m"] = ov
    res["fecha_auditoría_UTC"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (OUT / "auditoria_datos.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: {kk: (vv if not isinstance(vv, (list, dict)) or len(vv) < 12 else f"{len(vv)} elementos") for kk, vv in v.items()}
                      if isinstance(v, dict) else v for k, v in res.items()}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
