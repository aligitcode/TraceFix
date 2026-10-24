import numpy as np
from sklearn.linear_model import LinearRegression

from tracefix.regression import LinearRegressionScratch

rng = np.random.default_rng(0)
n = 100
x1 = rng.normal(size=n)
y = 1 + 2 * x1 + rng.normal(scale=0.1, size=n)
x2 = x1 + 1e-9 * rng.normal(size=n)
X = np.column_stack([x1, x2])

models = {
    "normal equation": LinearRegressionScratch(),
    "lstsq (SVD)": LinearRegressionScratch(solver="lstsq"),
    "ridge alpha=1e-3": LinearRegressionScratch(alpha=1e-3),
    "sklearn": LinearRegression(),
}
reference = LinearRegression().fit(X, y).predict(X)
for name, model in models.items():
    model.fit(X, y)
    coef = np.round(model.coef_, 4)
    diff = np.max(np.abs(model.predict(X) - reference))
    print(f"{name:18} coef={coef}  max pred diff vs sklearn={diff:.2e}")
