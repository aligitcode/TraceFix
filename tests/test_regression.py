import numpy as np
import pytest
from sklearn.linear_model import LinearRegression, Ridge

from tracefix.regression import LinearRegressionScratch


def duplicate_data():
    rng = np.random.default_rng(0)
    x = rng.normal(size=100)
    y = 1 + 2 * x + rng.normal(scale=0.1, size=100)
    return np.column_stack([x, x]), y


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


def test_normal_equation_fails_on_duplicate_features():
    X, y = duplicate_data()
    with pytest.raises(np.linalg.LinAlgError):
        LinearRegressionScratch().fit(X, y)


def test_lstsq_handles_duplicate_features():
    X, y = duplicate_data()
    model = LinearRegressionScratch(solver="lstsq").fit(X, y)
    library = LinearRegression().fit(X, y)
    assert np.allclose(model.coef_, library.coef_, atol=1e-6)
    assert np.allclose(model.predict(X), library.predict(X), atol=1e-8)


def test_ridge_matches_sklearn():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(60, 3))
    y = 2 + X @ np.array([1.0, -2.0, 0.5]) + rng.normal(scale=0.3, size=60)
    mine = LinearRegressionScratch(alpha=5.0).fit(X, y)
    theirs = Ridge(alpha=5.0).fit(X, y)
    assert np.allclose(mine.coef_, theirs.coef_, atol=1e-6)
    assert np.isclose(mine.intercept_, theirs.intercept_, atol=1e-6)


def test_ridge_stabilises_duplicate_features():
    X, y = duplicate_data()
    model = LinearRegressionScratch(alpha=1e-3).fit(X, y)
    assert abs(model.coef_[0] - model.coef_[1]) < 1e-6
    assert abs(model.coef_.sum() - 2.0) < 0.1


def test_invalid_solver_raises():
    with pytest.raises(ValueError):
        LinearRegressionScratch(solver="magic")
