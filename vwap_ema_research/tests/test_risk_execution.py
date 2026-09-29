import pytest

from src.execution import Costs, check_subbar
from src.risk import Risk


def test_tamano_nunca_supera_el_riesgo():
    r = Risk("risk", 0.5, 1, 50, 2.0, 2.0, 3, 6)
    assert r.size(50_000, 20) == 6                 # 250 $ / 40 $ = 6,25 -> 6 (6 x 40 = 240 <= 250)
    assert r.size(50_000, 200) == 0
    assert Risk("fixed", 0.5, 1, 50, 20.0, 2, 3, 6).size(50_000, 200) == 1


def test_limites_diarios():
    r = Risk("risk", 0.5, 1, 50, 2.0, 2.0, 2, 3)
    r.new_day(50_000)
    r.opened(); r.closed(-10); r.opened(); r.closed(-10)
    assert r.can_open() == "max_consecutive_losses"
    r.new_day(50_000); r.opened(); r.closed(-1000)
    assert r.can_open() == "daily_loss_limit"


def test_costes_con_spread():
    c = Costs(0.01, 100, 3.5, 5, 20)
    assert c.market(2000, 1, True) == pytest.approx(2000 + 0.15)
    assert c.commission(2) == 14


def test_stop_primero_si_ambos():
    assert check_subbar(100, 110, 90, 1, 95, 105, 0.25)[0] == "stop"
    assert check_subbar(100, 105.0, 99, 1, None, 105, 0.25) is None            # tocar no basta
    assert check_subbar(106, 107, 105.5, 1, None, 105, 0.25) == ("target", 106)  # abre por encima: se llena en la apertura
