import numpy as np
from sklearn.linear_model import LinearRegression

rng = np.random.default_rng(0)
n = 100
x1 = rng.normal(size=n)
y = 1 + 2 * x1 + rng.normal(scale=0.1, size=n)
x2 = x1 + 1e-9 * rng.normal(size=n)
X = np.column_stack([x1, x2])
X_b = np.hstack([np.ones((n, 1)), X])

s = np.linalg.svd(X_b, compute_uv=False)
print("singular values:", s)
print("smallest / largest:", s[-1] / s[0])
print("numpy default cutoff:", np.finfo(float).eps * max(X_b.shape))
print()
for rcond in [None, 1e-12, 1e-10, 1e-8, 1e-6]:
    beta, *_ = np.linalg.lstsq(X_b, y, rcond=rcond)
    print(f"rcond={rcond}: coef={np.round(beta[1:], 4)}")
print("sklearn:", np.round(LinearRegression().fit(X, y).coef_, 4))
