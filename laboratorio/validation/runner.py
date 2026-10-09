"""Ejecución de experimentos con manifiesto reproducible y particiones cronológicas."""
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

LAB = Path(__file__).resolve().parents[1]
EXP = LAB / "experiments"
PROTO = yaml.safe_load((LAB / "config" / "PROTOCOLO.yaml").read_text())


def periods(kind="intradia", include_test=False):
    p = PROTO["particion"][kind]
    keys = ["desarrollo", "validacion"] + (["prueba"] if include_test else [])
    return {k: (pd.Timestamp(p[k][0]), pd.Timestamp(p[k][1])) for k in keys}


def git_rev():
    try:
        rev = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=LAB, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "."], cwd=LAB, text=True).strip())
        return rev + ("+cambios_sin_commit" if dirty else "")
    except Exception:
        return "desconocida"


def file_fingerprint(path: Path):
    st = path.stat()
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read(1 << 20))
    return dict(archivo=str(path.relative_to(LAB.parent)), bytes=st.st_size, md5_primer_mb=h.hexdigest())


def new_experiment(name: str) -> Path:
    d = EXP / f"{datetime.now():%Y%m%d_%H%M%S}_{name}"
    d.mkdir(parents=True, exist_ok=False)
    return d


def write_manifest(d: Path, **kw):
    m = dict(fecha=datetime.now().isoformat(timespec="seconds"), version_codigo=git_rev(), **kw)
    (d / "manifest.json").write_text(json.dumps(m, indent=2, ensure_ascii=False, default=_json_default))


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, (pd.Timestamp, datetime)):
        return str(o)
    return str(o)


def split(t: pd.DataFrame, per: dict):
    return {k: t[(t["date"] >= a) & (t["date"] <= b)] for k, (a, b) in per.items()}


def calendar_split(cal: pd.DatetimeIndex, per: dict):
    return {k: cal[(cal >= a) & (cal <= b)] for k, (a, b) in per.items()}
