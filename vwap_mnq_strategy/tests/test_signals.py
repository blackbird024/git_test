import numpy as np
import pandas as pd

from src.signals import lado, señales


def _bars(closes, vwaps, sesiones=None):
    n = len(closes)
    return pd.DataFrame({"close": closes, "v": vwaps, "session": sesiones or ["d1"] * n})


def test_lado():
    np.testing.assert_array_equal(lado([1, 2, 3, np.nan], [2, 2, 2, 2]), [-1, 0, 1, 0])


def test_cruce_basico_y_primera_vela_sin_senal():
    b = _bars([11, 9, 9, 12, 13], [10] * 5)
    np.testing.assert_array_equal(señales(b, "v", "cross"), [0, -1, 0, 1, 0])


def test_cierre_igual_al_vwap_no_genera_senal_ni_rompe_el_cruce():
    # abajo, igual, arriba -> el cruce se detecta en la tercera (el 0 se ignora)
    b = _bars([9, 10, 11], [10] * 3)
    np.testing.assert_array_equal(señales(b, "v", "cross"), [0, 0, 1])


def test_no_hay_cruce_entre_sesiones():
    b = _bars([9, 11], [10, 10], ["d1", "d2"])
    np.testing.assert_array_equal(señales(b, "v", "cross"), [0, 0])


def test_confirmacion():
    # cruce al alza en la vela 1, confirmación en la 2; nuevo cruce a la baja en la 3 sin confirmar
    b = _bars([9, 11, 12, 8, 11], [10] * 5)
    np.testing.assert_array_equal(señales(b, "v", "confirm"), [0, 0, 1, 0, 0])
