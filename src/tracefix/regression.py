import numpy as np


class LinearRegressionScratch:
    """Ordinary least squares solved with the normal equation."""

    def __init__(self):
        self.intercept_ = None
        self.coef_ = None

    def _prepare(self, X):
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        return X

    def fit(self, X, y):
        X = self._prepare(X)
        y = np.asarray(y, dtype=float)
        X_b = np.hstack([np.ones((X.shape[0], 1)), X])
        beta = np.linalg.solve(X_b.T @ X_b, X_b.T @ y)
        self.intercept_ = beta[0]
        self.coef_ = beta[1:]
        return self

    def predict(self, X):
        X = self._prepare(X)
        return self.intercept_ + X @ self.coef_

    def r2_score(self, X, y):
        y = np.asarray(y, dtype=float)
        residual = np.sum((y - self.predict(X)) ** 2)
        total = np.sum((y - y.mean()) ** 2)
        return 1 - residual / total
