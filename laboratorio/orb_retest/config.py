"""Configuración versionada de MNQ_ORB_RETEST. Todos los parámetros viven aquí y en backtest_config.json.

Convenciones de tiempo: minuto de sesión k = 0 es la vela de 1 min que empieza a las 9:30:00 ET (Databento ohlcv-1m
marca cada vela con su hora de INICIO). La vela de 5 min número b cubre los minutos [5b, 5b+5) y su cierre se conoce al
empezar el minuto 5b+5.
"""
import hashlib
import json
from dataclasses import asdict, dataclass, field, replace

VERSION = "MNQ_ORB_RETEST_v1.0"


@dataclass(frozen=True)
class Strategy:
    version: str = VERSION
    or_minutes: int = 15             # rango 9:30:00-9:44:59 ET
    bar_minutes: int = 5             # ruptura, retesteo y confirmación en velas de 5 min
    tol_ticks: int = 2               # tolerancia del retesteo (2 ticks = 0,50 pts)
    retest_bars: int = 3             # velas de 5 min completas tras la ruptura para encontrar el retesteo
    tp_r: float = 2.0                # objetivo en R desde la entrada EJECUTADA
    last_entry_k: int = 120          # no abrir después de las 11:30 ET (minuto 120)
    flat_k: int = 385                # cierre obligatorio 15:55 ET (o 5 min antes de una media jornada)
    stop_offset_ticks: int = 1       # SL = extremo de la vela de retesteo ∓ 1 tick
    min_or_minutes_with_data: int = 14   # si faltan más de 1 min del rango, no se opera
    max_trades_per_session: int = 1


@dataclass(frozen=True)
class Costs:
    name: str = "base"
    point_value: float = 2.0         # MNQ: 2 USD por punto
    tick: float = 0.25               # 0,50 USD por tick
    commission_per_side: float = 1.00    # USD por contrato y lado (comisión + tasas)
    slip_ticks_entry: float = 1.0    # entrada a mercado
    slip_ticks_stop: float = 1.0     # stop-loss (orden stop → mercado)
    slip_ticks_time: float = 1.0     # salida por tiempo a mercado
    tp_cross_ticks: int = 1          # el objetivo (límite) solo se llena si el precio lo cruza 1 tick


COST_SCENARIOS = {
    "sin_costes": Costs("sin_costes", commission_per_side=0.0, slip_ticks_entry=0, slip_ticks_stop=0,
                        slip_ticks_time=0, tp_cross_ticks=0),
    "base": Costs("base"),                                                       # 1 USD/lado + 1 tick
    "base_2t": Costs("base_2t", slip_ticks_entry=2, slip_ticks_stop=2, slip_ticks_time=2),   # 1 USD/lado + 2 ticks
    "proyecto_previo": Costs("proyecto_previo", commission_per_side=0.75, slip_ticks_entry=2, slip_ticks_stop=2,
                             slip_ticks_time=2),                                 # CONFIG_COSTES.yaml escenario base
    "estres": Costs("estres", commission_per_side=1.50, slip_ticks_entry=3, slip_ticks_stop=4, slip_ticks_time=3),
}


@dataclass(frozen=True)
class Risk:
    initial_capital: float = 50_000.0
    risk_usd: float = 50.0           # presupuesto por operación (escenarios 25 / 50 / 100)
    risk_pct: float = 0.0            # si > 0, se usa en lugar de risk_usd (% del saldo)
    max_contracts: int = 50
    daily_loss_limit: float = 0.0    # 0 = sin límite diario
    max_drawdown: float = 0.0        # 0 = sin límite; si se alcanza, no se abren más operaciones
    drawdown_type: str = "estatico"  # "estatico" (desde el capital inicial) o "trailing_cierre" (desde el máximo de cierre)


@dataclass(frozen=True)
class Partition:
    desarrollo: tuple = ("2018-01-01", "2021-12-31")
    validacion: tuple = ("2022-01-01", "2024-12-31")
    prueba: tuple = ("2025-01-01", "2026-10-02")


@dataclass(frozen=True)
class Config:
    strategy: Strategy = field(default_factory=Strategy)
    costs: Costs = field(default_factory=lambda: COST_SCENARIOS["base"])
    risk: Risk = field(default_factory=Risk)
    partition: Partition = field(default_factory=Partition)

    def to_dict(self):
        return asdict(self)

    def with_(self, **kw):
        s = replace(self.strategy, **{k: v for k, v in kw.items() if k in Strategy.__dataclass_fields__})
        return replace(self, strategy=s)

    def strategy_hash(self):
        """Huella de las REGLAS (estrategia + partición), sin costes ni riesgo: es lo que se congela."""
        d = dict(strategy=asdict(self.strategy), partition=asdict(self.partition))
        return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]


BASELINE = Config()
