from risk.topstep import Rules, attempt

R = Rules(start=50000, target=3000, mll=2000, mll_lock=50000, dll=1000, consistency=0.55, personal_daily_stop=10**9)


def test_pass_needs_consistency():
    # un día de +3000: mejor día 100 % del beneficio → no aprueba; tras más días sí
    days = [[(3000, 0)], [(1000, 0)], [(1000, 0)], [(500, 0)]]
    res, n = attempt(days, R)
    assert res == "aprobado" and n == 4          # beneficio 5500, mejor día 3000 ≤ 0,55 × 5500 = 3025


def test_trailing_mll_uses_close_and_floating():
    r = Rules(50000, 3000, 2000, 50000, 10**9, 0.55, 10**9)
    days = [[(1500, 0)], [(0, -1999)], [(0, -2000)]]
    res, n = attempt(days, r)
    assert res == "suspendido" and n == 3        # umbral 49.500 (máximo de cierre 51.500): 51.500 − 2.000 lo toca


def test_mll_stops_trailing_at_start():
    R2 = Rules(50000, 3000, 2000, 50000, 10**9, 0.55, 10**9)
    days = [[(1500, 0)], [(1400, 0)], [(-900, -900)], [(0, -1500)]]
    # máximo de cierre 52.900 → umbral min(50.900, 50.000) = 50.000; flotante 52.000 − 1.500 = 50.500 → sigue viva
    # (sin el bloqueo, el umbral sería 50.900 y quedaría suspendida)
    res, n = attempt(days, R2, max_days=4)
    assert res == "sin_resolver"


def test_dll_caps_day():
    days = [[(-1500, -1500)], [(0, 0)]]
    res, n = attempt(days, R, max_days=2)
    assert res == "sin_resolver"                 # el DLL corta en −1000 y el MLL (−2000) no se toca
