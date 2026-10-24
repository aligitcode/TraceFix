import numpy as np
from sklearn.linear_model import LinearRegression

from tracefix.regression import LinearRegressionScratch

rng = np.random.default_rng(42)

n = 200
X = rng.normal(size=(n, 3))
true_beta = np.array([2.0, -1.0, 0.5])
y = 4.0 + X @ true_beta + rng.normal(scale=0.5, size=n)

scratch = LinearRegressionScratch().fit(X, y)
library = LinearRegression().fit(X, y)

print("True intercept: 4.0   True coefficients:", true_beta)
print()
print("Scratch intercept:  ", round(float(scratch.intercept_), 6))
print("sklearn intercept:  ", round(float(library.intercept_), 6))
print("Scratch coefficients:", np.round(scratch.coef_, 6))
print("sklearn coefficients:", np.round(library.coef_, 6))
print()
print("Max coefficient difference:", float(np.max(np.abs(scratch.coef_ - library.coef_))))
print("Max prediction difference: ", float(np.max(np.abs(scratch.predict(X) - library.predict(X)))))
print("Scratch R2:", round(float(scratch.r2_score(X, y)), 6))
print("sklearn R2:", round(float(library.score(X, y)), 6))
