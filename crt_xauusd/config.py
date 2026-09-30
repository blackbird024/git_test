"""Configuration loading and reproducibility helpers."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: str | Path = ROOT / "CONFIG.json") -> dict:
    with open(path) as f:
        return json.load(f)


def sha256_file(path: str | Path) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()


def git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        return out.stdout.strip() + ("-dirty" if dirty else "")
    except Exception:
        return None


def build_manifest(cfg: dict, data_path: str | Path | None) -> dict:
    import numpy
    import pandas

    from . import __version__

    critical = sorted((ROOT / "crt_xauusd").glob("*.py")) + [ROOT / "CONFIG.json"]
    return {
        "code_version": __version__,
        "git_commit": git_commit(),
        "config_sha256": config_hash(cfg),
        "dataset_path": str(data_path) if data_path else None,
        "dataset_sha256": sha256_file(data_path) if data_path else None,
        "critical_file_sha256": {str(p.relative_to(ROOT)): sha256_file(p) for p in critical},
        "python": platform.python_version(),
        "pandas": pandas.__version__,
        "numpy": numpy.__version__,
        "seed": cfg["seed"],
    }
