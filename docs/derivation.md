# Linear regression: derivation

## Model
y = X b + e, where X is n x p (with a column of ones for the intercept),
b is the vector of coefficients, and e is the error.

## Objective (least squares)
Choose b to minimise the sum of squared residuals:

S(b) = (y - Xb)^T (y - Xb)

## Normal equation
Expand: S(b) = y^T y - 2 b^T X^T y + b^T X^T X b

Gradient: dS/db = -2 X^T y + 2 X^T X b

Set it to zero: X^T X b = X^T y

If X^T X is invertible: b = (X^T X)^(-1) X^T y

The Hessian is 2 X^T X, which is positive semi-definite, so this stationary
point is a minimum. It is unique when X has full column rank.

## Assumptions (Gauss-Markov)
1. The model is linear in the coefficients.
2. The errors have mean zero.
3. The errors have constant variance (homoscedasticity).
4. The errors are uncorrelated.
5. The features are not perfectly collinear (X has full column rank).
Under 1-5, OLS is the best linear unbiased estimator. Normal errors are only
needed for the usual t-tests and confidence intervals.

## Why the normal equation breaks with collinear features
If two columns are identical, X^T X is singular and cannot be inverted.
If they are nearly identical, X^T X is nearly singular. Forming X^T X squares
the condition number: cond(X^T X) = cond(X)^2. Our experiment reached about
1.8e15, close to the limit of double precision, so the coefficients exploded
(+5621 and -5619) while their sum stayed correct.

## Fixes implemented
- lstsq: solves least squares with an SVD of X, never forming X^T X.
- Ridge: minimise S(b) + alpha * ||b||^2 (intercept not penalised), giving
  b = (X^T X + alpha I)^(-1) X^T y. The added alpha I makes the matrix invertible.

## Experimental finding: lstsq and near-duplicate features
With features that differ by about 1e-9, the smallest singular value of X was
about 5.8e-10 times the largest. numpy's default cutoff (about 2.2e-14) keeps
it, so lstsq returned coefficients of about -2.7e6 and +2.7e6. Setting
rcond=1e-8 dropped that direction and gave 1.0028 and 1.0028, matching
scikit-learn on this dataset. The right rcond depends on the data, so it is a
tolerance to choose, not a universal setting.

## Still to write in my own words
- Why the Hessian argument proves the point is a minimum.
- What each assumption would look like if violated, and how to check it.
- The gradient descent update b <- b - lr * (2/n) X^T (X b - y) and why
  feature scaling affects convergence.
