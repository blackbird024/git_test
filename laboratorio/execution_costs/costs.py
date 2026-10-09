"""Modelo de costes. Lee config/CONFIG_COSTES.yaml; ningún valor está escrito en el código."""
from dataclasses import dataclass
from pathlib import Path

import yaml

CFG = Path(__file__).resolve().parents[1] / "config" / "CONFIG_COSTES.yaml"


@dataclass(frozen=True)
class FutCost:
    point_value: float
    tick: float
    fixed_per_side: float        # comisión + tasas por contrato y lado (USD)
    slip_ticks: float            # deslizamiento por lado en órdenes a mercado/stop
    limit_cross_ticks: int = 1

    @property
    def slip(self) -> float:
        return self.slip_ticks * self.tick

    def round_trip_usd(self) -> float:
        """Coste total esperado ida y vuelta por contrato si ambas órdenes son a mercado/stop."""
        return 2 * self.fixed_per_side + 2 * self.slip * self.point_value


def load_yaml():
    return yaml.safe_load(CFG.read_text())


def mnq(scenario="base", fixed_mult=1.0, extra_slip_ticks=0.0) -> FutCost:
    c = load_yaml()["MNQ"]
    e = c["especificacion"]
    return FutCost(point_value=e["multiplicador_usd_por_punto"], tick=e["tick"],
                   fixed_per_side=(c["comision_por_lado_usd"] + c["tasas_por_lado_usd"]) * fixed_mult,
                   slip_ticks=c["slippage_ticks_por_lado"][scenario] + extra_slip_ticks,
                   limit_cross_ticks=c["limite_requiere_cruce_ticks"])
