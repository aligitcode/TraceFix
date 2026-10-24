import numpy as np
import pytest

from tracefix.gradient_descent import LinearRegressionGD, standardize
from tracefix.regression import LinearRegressionScratch


def mixed_scale_data():
    rng = np.random.default_rng(0)
    n = 200
    x1 = rng.normal(size=n)
    x2 = 1000 * rng.normal(size=n)
    X = np.column_stack([x1, x2])
    y = 1 + 2 * x1 + 0.003 * x2 + rng.normal(scale=0.1, size=n)
    return X, y


def test_scaled_gd_matches_normal_equation():
    X, y = mixed_scale_data()
    X_scaled, _, _ = standardize(X)
    gd = LinearRegressionGD(lr=0.1, n_iter=5000).fit(X_scaled, y)
    exact = LinearRegressionScratch().fit(X_scaled, y)
    assert np.allclose(gd.predict(X_scaled), exact.predict(X_scaled), atol=1e-6)


def test_loss_decreases_on_scaled_features():
    X, y = mixed_scale_data()
    X_scaled, _, _ = standardize(X)
    gd = LinearRegressionGD(lr=0.1, n_iter=200).fit(X_scaled, y)
    assert gd.loss_history_[-1] < gd.loss_history_[0]


def test_unscaled_features_diverge_with_the_same_kind_of_step():
    X, y = mixed_scale_data()
    gd = LinearRegressionGD(lr=0.01, n_iter=1000).fit(X, y)
    final = gd.loss_history_[-1]
    assert (not np.isfinite(final)) or final > gd.loss_history_[0]


def test_invalid_lr_raises():
    with pytest.raises(ValueError):
        LinearRegressionGD(lr=0)
