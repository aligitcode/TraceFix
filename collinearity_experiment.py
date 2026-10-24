import numpy as np
from sklearn.linear_model import LinearRegression

from tracefix.regression import LinearRegressionScratch

rng = np.random.default_rng(0)
n = 100
x1 = rng.normal(size=n)
y = 1 + 2 * x1 + rng.normal(scale=0.1, size=n)

cases = [
    ("exact duplicate feature", 0.0),
    ("nearly duplicate (noise 1e-9)", 1e-9),
    ("mildly different (noise 1e-1)", 1e-1),
]

for label, noise in cases:
    x2 = x1 + noise * rng.normal(size=n)
    X = np.column_stack([x1, x2])
    X_b = np.hstack([np.ones((n, 1)), X])

    print("=" * 60)
    print(label)
    print("Condition number of X'X:", f"{np.linalg.cond(X_b.T @ X_b):.3e}")

    library = LinearRegression().fit(X, y)
    print("sklearn coefficients:", np.round(library.coef_, 4))
    print("sklearn R2:", round(float(library.score(X, y)), 6))

    try:
        scratch = LinearRegressionScratch().fit(X, y)
        print("scratch coefficients:", np.round(scratch.coef_, 4))
        print("scratch R2:", round(float(scratch.r2_score(X, y)), 6))
        diff = np.max(np.abs(scratch.predict(X) - library.predict(X)))
        print("Max prediction difference:", f"{diff:.3e}")
    except np.linalg.LinAlgError as error:
        print("scratch FAILED:", error)
