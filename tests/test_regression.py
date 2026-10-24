import numpy as np

from tracefix.regression import LinearRegressionScratch


def test_recovers_a_perfect_line():
    X = [1, 2, 3, 4, 5]
    y = [3, 5, 7, 9, 11]
    model = LinearRegressionScratch().fit(X, y)
    assert np.isclose(model.intercept_, 1.0)
    assert np.isclose(model.coef_[0], 2.0)
    assert np.isclose(model.r2_score(X, y), 1.0)


def test_two_features():
    X = [[1, 2], [2, 1], [3, 5], [4, 3], [5, 8]]
    y = [1 + 2 * a + 3 * b for a, b in X]
    model = LinearRegressionScratch().fit(X, y)
    assert np.isclose(model.intercept_, 1.0)
    assert np.allclose(model.coef_, [2.0, 3.0])


def test_predict():
    model = LinearRegressionScratch().fit([1, 2, 3], [2, 4, 6])
    assert np.isclose(model.predict([10])[0], 20.0)
