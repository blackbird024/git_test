from src.risk_manager import RiskManager


def _rm(**k):
    base = dict(sizing="risk_pct", risk_pct=0.5, fixed_contracts=1, max_contracts=20, min_contracts=1, point_value=2.0,
                daily_loss_limit_pct=2.0, max_trades_per_session=3, pause_after_losses=2)
    base.update(k)
    return RiskManager(**base)


def test_tamano_por_riesgo():
    rm = _rm()
    # 0,5 % de 50.000 = 250 $; stop a 20 puntos x 2 $ = 40 $/contrato -> 6 contratos
    assert rm.size(50_000, 20) == 6


def test_tamano_menor_que_un_contrato_no_opera():
    assert _rm().size(50_000, 200) == 0          # 400 $/contrato > 250 $


def test_tamano_maximo_y_fijo():
    assert _rm(max_contracts=3).size(50_000, 1) == 3
    assert _rm(sizing="fixed", fixed_contracts=2).size(50_000, 999) == 2


def test_limites_de_sesion():
    rm = _rm()
    rm.new_session(50_000)
    rm.on_open(); rm.on_close(-100)
    rm.on_open(); rm.on_close(-100)
    ok, porque = rm.can_open()
    assert not ok and porque == "pausa_por_perdidas"
    rm.new_session(50_000)
    rm.on_open(); rm.on_close(-1_000)            # 2 % de 50.000
    assert rm.can_open() == (False, "limite_perdida_diaria")
    rm.new_session(50_000)
    for _ in range(3):
        rm.on_open(); rm.on_close(10)
    assert rm.can_open() == (False, "max_operaciones_sesion")
