import numpy as np


class LinearRegressionScratch:
    """Linear regression with two solvers and an optional ridge penalty.

    solver="normal": normal equation (X'X) beta = X'y. Fast, but fails or
        becomes unstable when features are collinear.
    solver="lstsq": SVD-based least squares. Handles collinear features and
        returns the minimum-norm solution.
    alpha > 0: ridge penalty (the intercept is not penalised). This uses the
        normal equation with (X'X + alpha*I) and takes precedence over solver.
    """

    def __init__(self, solver="normal", alpha=0.0):
        if solver not in ("normal", "lstsq"):
            raise ValueError("solver must be 'normal' or 'lstsq'")
        if alpha < 0:
            raise ValueError("alpha must be >= 0")
        self.solver = solver
        self.alpha = alpha
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

        if self.alpha > 0:
            penalty = self.alpha * np.eye(X_b.shape[1])
            penalty[0, 0] = 0.0
            beta = np.linalg.solve(X_b.T @ X_b + penalty, X_b.T @ y)
        elif self.solver == "lstsq":
            beta, *_ = np.linalg.lstsq(X_b, y, rcond=None)
        else:
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
