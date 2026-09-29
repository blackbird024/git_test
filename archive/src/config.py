"""Carga de la configuración desde los archivos YAML de la carpeta config/.

La idea: las reglas viven en archivos de texto y el código solo las lee.
Así, si Apex cambia una regla, se edita el YAML y no hace falta tocar Python.
"""
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@dataclass(frozen=True)
class Instrument:
    symbol: str
    tick: float
    point_value: float          # dólares por punto de precio y contrato
    commission_rt: float        # comisión ida y vuelta por contrato
    slippage_ticks: int         # ticks de deslizamiento por lado (entrada, stop, cierre forzado)
    group: str                  # grupo de correlación

    @property
    def slippage(self) -> float:
        """Deslizamiento por lado expresado en puntos de precio."""
        return self.slippage_ticks * self.tick


@dataclass(frozen=True)
class FirmAccount:
    start_balance: float
    profit_target: float
    max_drawdown: float
    daily_loss_limit: float
    max_micros: int
    access_days: int
    threshold_cap: float | None  # nivel en el que el umbral deja de subir (None = nunca para)
    dll_fails_account: bool      # True = tocar el límite diario hace perder la cuenta


@dataclass(frozen=True)
class SystemRules:
    risk_per_trade: float
    daily_budget: float         # pérdida máxima que el sistema se permite en un día
    max_trades_per_day: int
    min_reward_risk: float
    session_start: str
    force_close: str
    entry_delay_bars: int


def _load(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_instruments() -> dict[str, Instrument]:
    raw = _load("instruments.yaml")
    return {
        sym: Instrument(
            symbol=sym,
            tick=v["tick"],
            point_value=v["valor_punto_usd"],
            commission_rt=v["comision_ida_vuelta_usd"],
            slippage_ticks=v["slippage_ticks_por_lado"],
            group=v["grupo_correlacion"],
        )
        for sym, v in raw.items()
    }


def load_firm_account(firm: str, size: str) -> FirmAccount:
    raw = _load(f"firms/{firm}.yaml")
    acc = raw["cuentas"][size]
    assumptions = raw.get("supuestos", {})
    cap_offset = assumptions.get("umbral_deja_de_subir_en")
    return FirmAccount(
        start_balance=acc["saldo_inicial"],
        profit_target=acc["objetivo_beneficio"],
        max_drawdown=acc["drawdown_max_eod"],
        daily_loss_limit=acc["limite_perdida_diaria"],
        max_micros=acc["contratos_max"] * assumptions.get("micros_por_mini", 10),
        access_days=raw["dias_acceso"],
        threshold_cap=None if cap_offset is None else acc["saldo_inicial"] + cap_offset,
        dll_fails_account=not assumptions.get("limite_diario_suspende_solo_el_dia", True),
    )


def load_system() -> tuple[SystemRules, FirmAccount]:
    """Devuelve las reglas del sistema y la cuenta de la firma que indica system.yaml."""
    raw = _load("system.yaml")
    account = load_firm_account(raw["firma"], raw["cuenta"])
    r = raw["riesgo"]
    rules = SystemRules(
        risk_per_trade=r["riesgo_por_operacion_usd"],
        daily_budget=r["limite_diario_sistema_pct"] * account.daily_loss_limit,
        max_trades_per_day=r["max_operaciones_por_dia"],
        min_reward_risk=r["ratio_min_objetivo_stop"],
        session_start=raw["horario_et"]["inicio_sesion"],
        force_close=raw["horario_et"]["cierre_forzado"],
        entry_delay_bars=raw["ejecucion_manual"]["retraso_entrada_barras"],
    )
    return rules, account
