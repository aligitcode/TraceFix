import numpy as np

from tracefix.metrics import mae, r2, rmse


def test_perfect_predictions():
    y = [1.0, 2.0, 3.0]
    assert mae(y, y) == 0.0
    assert rmse(y, y) == 0.0
    assert r2(y, y) == 1.0


def test_predicting_the_mean_gives_zero_r2():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    assert np.isclose(r2(y, np.full(4, y.mean())), 0.0)


def test_known_errors():
    assert np.isclose(mae([0, 0], [1, 3]), 2.0)
    assert np.isclose(rmse([0, 0], [3, 4]), np.sqrt(12.5))
