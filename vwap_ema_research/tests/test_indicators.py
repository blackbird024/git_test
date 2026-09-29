import numpy as np

from src import indicators as ind


def test_vwap_a_mano_y_reinicio():
    h, l, c = np.array([11, 21, 31, 11.0]), np.array([9, 19, 29, 9.0]), np.array([10, 20, 30, 10.0])
    v = np.array([1, 1, 2, 1.0])
    np.testing.assert_allclose(ind.vwap(h, l, c, v, [0, 0, 0, 1]), [10, 15, 22.5, 10])


def test_ema_y_atr_se_reinician_por_grupo():
    x = np.arange(10, dtype=float)
    e = ind.ema(x, 3, [0] * 5 + [1] * 5)
    assert np.isnan(e[5]) and np.isnan(e[6]) and np.isfinite(e[7])
    a = ind.atr(x + 1, x - 1, x, 2, [0] * 10)
    assert np.isnan(a[0]) and a[2] == 2.0          # TR = max(h-l=2, |h-c_prev|=2, |l-c_prev|=0) = 2


def test_pendiente():
    np.testing.assert_allclose(ind.slope([1, 2, 4, 7.0], 2, [0, 0, 0, 0])[2:], [3, 5])
