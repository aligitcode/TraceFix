import numpy as np
from sklearn.datasets import load_diabetes
from sklearn.linear_model import LinearRegression

from tracefix.metrics import mae, r2, rmse
from tracefix.regression import LinearRegressionScratch

X, y = load_diabetes(return_X_y=True)

rng = np.random.default_rng(42)
order = rng.permutation(len(y))
n_train = int(0.6 * len(y))
n_val = int(0.2 * len(y))
train, val, test = np.split(order, [n_train, n_train + n_val])

X_train, y_train = X[train], y[train]
X_val, y_val = X[val], y[val]
X_test, y_test = X[test], y[test]
print(f"train={len(train)}  validation={len(val)}  test={len(test)}")
print()


def report(name, y_true, y_pred):
    print(f"{name:34} MAE={mae(y_true, y_pred):7.2f}  RMSE={rmse(y_true, y_pred):7.2f}  R2={r2(y_true, y_pred):6.3f}")


# Baseline: always predict the training mean.
baseline = np.full(len(y_test), y_train.mean())

# Choose the ridge penalty on the VALIDATION set only.
alphas = [0.001, 0.01, 0.1, 1.0, 10.0]
val_rmse = {}
for alpha in alphas:
    model = LinearRegressionScratch(alpha=alpha).fit(X_train, y_train)
    val_rmse[alpha] = rmse(y_val, model.predict(X_val))
best_alpha = min(val_rmse, key=val_rmse.get)
print("Validation RMSE by alpha:", {a: round(v, 2) for a, v in val_rmse.items()})
print("Chosen alpha:", best_alpha)
print()

scratch = LinearRegressionScratch().fit(X_train, y_train)
library = LinearRegression().fit(X_train, y_train)
ridge = LinearRegressionScratch(alpha=best_alpha).fit(X_train, y_train)

# The test set is used once, at the end.
print("TEST SET RESULTS")
report("baseline (training mean)", y_test, baseline)
report("scratch OLS", y_test, scratch.predict(X_test))
report("sklearn LinearRegression", y_test, library.predict(X_test))
report(f"scratch ridge (alpha={best_alpha})", y_test, ridge.predict(X_test))
