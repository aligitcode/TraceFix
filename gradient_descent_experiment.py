import numpy as np

from tracefix.gradient_descent import LinearRegressionGD, standardize
from tracefix.regression import LinearRegressionScratch

rng = np.random.default_rng(0)
n = 200
x1 = rng.normal(size=n)
x2 = 1000 * rng.normal(size=n)
X = np.column_stack([x1, x2])
y = 1 + 2 * x1 + 0.003 * x2 + rng.normal(scale=0.1, size=n)

optimal = LinearRegressionScratch().fit(X, y)
optimal_mse = float(np.mean((y - optimal.predict(X)) ** 2))
print(f"Normal equation MSE (the best possible): {optimal_mse:.4f}")
print()

X_scaled, _, _ = standardize(X)
runs = [
    ("scaled features, lr=0.1", X_scaled, 0.1),
    ("raw features, lr=0.01", X, 0.01),
    ("raw features, lr=1e-7", X, 1e-7),
]
for label, features, lr in runs:
    model = LinearRegressionGD(lr=lr, n_iter=1000).fit(features, y)
    print(f"{label:26} iterations={model.n_iter_:5d}  final MSE={model.loss_history_[-1]:.4g}")
