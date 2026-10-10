"""Configuración del backtest (YAML → dataclasses validadas). Nada de parámetros fijos en el código."""
from dataclasses import dataclass, field, asdict
from datetime import time
from pathlib import Path
from typing import Optional

import yaml

PKG = Path(__file__).resolve().parent


class ConfigError(ValueError):
    pass


def _t(s: str) -> time:
    try:
        h, m = str(s).split(":")
        return time(int(h), int(m))
    except Exception as e:  # noqa: BLE001
        raise ConfigError(f"hora no válida: {s!r} (formato HH:MM)") from e


@dataclass
class Instrument:
    symbol: str
    tick_size: float
    tick_value: float
    point_value: float

    def __post_init__(self):
        if self.tick_size <= 0 or self.tick_value <= 0:
            raise ConfigError(f"{self.symbol}: tick_size y tick_value deben ser > 0")
        if abs(self.tick_value / self.tick_size - self.point_value) > 1e-9:
            raise ConfigError(f"{self.symbol}: tick_value / tick_size ({self.tick_value / self.tick_size}) "
                              f"no coincide con point_value ({self.point_value})")


@dataclass
class Costs:
    commission_per_side: float        # USD por contrato y lado
    slippage_ticks_per_side: float    # ticks adversos por lado en órdenes a mercado y stop
    extra_cost_per_side: float = 0.0  # spread u otros costes por contrato y lado
    limit_fill_ticks_through: int = 1  # el objetivo (límite) solo se llena si el precio lo supera en N ticks
    nota: str = ""


@dataclass
class Strategy:
    or_start: time = time(9, 30)
    or_end: time = time(10, 30)
    entry_cutoff: time = time(15, 0)
    flat_time: time = time(15, 55)
    session_start: time = time(9, 30)
    session_end: time = time(16, 0)
    retest_window_bars: int = 3
    retest_tolerance_ticks: int = 2
    stop_offset_ticks: int = 2
    reward_risk: float = 2.0
    use_structure_filter: bool = True
    pivot_left: int = 2
    pivot_right: int = 2
    invalidate_on_close_inside: bool = True
    hourly_min_bars: int = 6           # una vela de 1 h necesita al menos N velas de 5 min (de 12)


@dataclass
class Risk:
    initial_capital: float = 50_000.0
    risk_pct: float = 0.0025
    sizing_mode: str = "percent"       # "percent" o "fixed"
    fixed_contracts: int = 1
    compounding: bool = True           # percent: riesgo sobre el capital vigente (True) o el inicial (False)
    max_contracts: Optional[int] = None


@dataclass
class Config:
    instrument: Instrument
    data_file: Path
    timestamp_is: str                  # "start" (la marca es la apertura de la vela)
    timezone: str
    bar_minutes: int
    costs: Costs
    stress_costs: dict
    strategy: Strategy
    risk: Risk
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    split: tuple = (0.6, 0.2, 0.2)
    output_dir: Path = Path("orb_backtest/output")
    bootstrap_samples: int = 5000
    seed: int = 12345
    data_label: str = ""
    raw: dict = field(default_factory=dict)


def load(path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"no existe el archivo de configuración {path}")
    c = yaml.safe_load(path.read_text())
    try:
        specs = yaml.safe_load((PKG / "configs" / "instruments.yaml").read_text())
        sym = c["instrument"]
        spec = {**specs.get(sym, {}), **c.get("instrument_overrides", {})}
        inst = Instrument(sym, float(spec["tick_size"]), float(spec["tick_value"]), float(spec["point_value"]))
        st = c.get("strategy", {})
        times = {k: _t(st[k]) for k in ("or_start", "or_end", "entry_cutoff", "flat_time", "session_start",
                                        "session_end") if k in st}
        strat = Strategy(**{**{k: v for k, v in st.items() if k not in times}, **times})
        if not (strat.or_start < strat.or_end <= strat.entry_cutoff <= strat.flat_time <= strat.session_end):
            raise ConfigError("orden de horas inválido: or_start < or_end <= entry_cutoff <= flat_time <= session_end")
        risk = Risk(**c.get("risk", {}))
        if risk.sizing_mode not in ("percent", "fixed"):
            raise ConfigError("risk.sizing_mode debe ser 'percent' o 'fixed'")
        if not (0 < risk.risk_pct < 0.05):
            raise ConfigError("risk.risk_pct fuera de rango (0, 5 %)")
        costs = Costs(**c["costs"])
        split = tuple(c.get("split", (0.6, 0.2, 0.2)))
        if abs(sum(split) - 1) > 1e-9:
            raise ConfigError("split debe sumar 1")
        if c.get("timestamp_is", "start") != "start":
            raise ConfigError("solo se admite timestamp_is: start (marca = apertura de la vela)")
        data_file = Path(c["data_file"])
        if not data_file.is_absolute():
            data_file = (path.parent / data_file).resolve() if not data_file.exists() else data_file.resolve()
        out = Path(c.get("output_dir", "orb_backtest/output"))
        return Config(instrument=inst, data_file=data_file, timestamp_is="start", timezone=c.get("timezone", "America/New_York"),
                      bar_minutes=int(c.get("bar_minutes", 5)), costs=costs, stress_costs=c.get("stress_costs", {}),
                      strategy=strat, risk=risk, start_date=c.get("start_date"), end_date=c.get("end_date"),
                      split=split, output_dir=out, bootstrap_samples=int(c.get("bootstrap_samples", 5000)),
                      seed=int(c.get("seed", 12345)), data_label=c.get("data_label", ""), raw=c)
    except KeyError as e:
        raise ConfigError(f"falta la clave obligatoria {e} en {path}") from e
    except TypeError as e:
        raise ConfigError(f"parámetro desconocido o inválido en {path}: {e}") from e


def to_dict(cfg: Config) -> dict:
    d = asdict(cfg)
    d.pop("raw", None)
    return d
