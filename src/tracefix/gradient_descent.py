import numpy as np


def standardize(X):
    """Return (X scaled to mean 0 and std 1, column means, column stds)."""
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std = np.where(std == 0, 1.0, std)
    return (X - mean) / std, mean, std


class LinearRegressionGD:
    """Linear regression fitted by batch gradient descent on the mean squared error.

    Update: beta <- beta - lr * (2/n) * X'(X beta - y)
    Stops after n_iter steps, when the step becomes smaller than tol, or as
    soon as the loss stops being finite (divergence). The loss after each
    step is stored in loss_history_.
    """

    def __init__(self, lr=0.1, n_iter=1000, tol=1e-12):
        if lr <= 0:
            raise ValueError("lr must be > 0")
        if n_iter < 1:
            raise ValueError("n_iter must be >= 1")
        self.lr = lr
        self.n_iter = n_iter
        self.tol = tol
        self.intercept_ = None
        self.coef_ = None
        self.loss_history_ = []
        self.n_iter_ = 0

    def _prepare(self, X):
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        return X

    def fit(self, X, y):
        X = self._prepare(X)
        y = np.asarray(y, dtype=float)
        X_b = np.hstack([np.ones((X.shape[0], 1)), X])
        n = X_b.shape[0]
        beta = np.zeros(X_b.shape[1])
        self.loss_history_ = []

        with np.errstate(over="ignore", invalid="ignore"):
            for _ in range(self.n_iter):
                residual = X_b @ beta - y
                loss = float(np.mean(residual ** 2))
                self.loss_history_.append(loss)
                if not np.isfinite(loss):
                    break
                step = self.lr * (2 / n) * (X_b.T @ residual)
                beta = beta - step
                if np.max(np.abs(step)) < self.tol:
                    break

        self.n_iter_ = len(self.loss_history_)
        self.intercept_ = beta[0]
        self.coef_ = beta[1:]
        return self

    def predict(self, X):
        X = self._prepare(X)
        return self.intercept_ + X @ self.coef_
