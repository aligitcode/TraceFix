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

## Why the stationary point is a minimum (Hessian argument)

Setting the gradient to zero only finds a *stationary* point; it could be a minimum, a maximum or a
saddle. The second derivative decides. The Hessian of S(b) is H = 2 X^T X. For any vector v:

    v^T H v = 2 v^T X^T X v = 2 ||X v||^2  >= 0

so H is positive semi-definite and S is convex: a bowl with no hills, so any stationary point is a
**global** minimum. If X has full column rank, X v = 0 only when v = 0, so v^T H v > 0 for every
v != 0: H is positive definite, the bowl is strictly curved, and the minimum is **unique**.

A second proof needs no calculus. Let b_hat solve the normal equations, so X^T (y - X b_hat) = 0
(the residual is perpendicular to every column of X). For any other b write
y - X b = (y - X b_hat) + X (b_hat - b). Expanding the square, the cross term is
2 (y - X b_hat)^T X (b_hat - b) = 0, which leaves

    S(b) = S(b_hat) + ||X (b - b_hat)||^2  >=  S(b_hat)

Geometrically, X b_hat is the orthogonal projection of y onto the column space of X, and every
other point of that space is farther from y. (Checked numerically on the diabetes data: for random
b the two sides agree to rounding error, about 1e-10 against S = 1.26e6; the residual mean is
-6e-15 and max |X^T r| is 3e-12.)

## What breaks when an assumption is violated, and how to check

| Assumption | What it looks like when violated | How to check | Consequence |
|---|---|---|---|
| Linear in the coefficients | Residuals curve when plotted against fitted values | Residual vs fitted plot; does adding squared terms raise R2? | Systematic error; a straight line cannot follow the data |
| Errors have mean zero | An omitted variable that is correlated with a feature pushes the error's mean up or down with that feature | **Not visible in the residuals**: with an intercept, the normal equations force the residual mean to exactly 0. Needs reasoning about what was left out. | Biased coefficients (the prediction can still look fine) |
| Constant variance | Residual spread grows with the fitted value (a funnel shape) | Residual vs fitted plot; Breusch-Pagan test | Estimates stay unbiased but are no longer the best; the usual standard errors are wrong |
| Errors uncorrelated | Neighbouring residuals have the same sign, typical for time series | Plot residuals in time order; Durbin-Watson statistic | Standard errors too small, so results look more certain than they are |
| No perfect collinearity | Huge coefficients of opposite sign that nearly cancel | Condition number of X; variance inflation factors | Unstable coefficients (our +5621 / -5619 experiment); singular X^T X if exact |

Two points worth being able to say aloud. First, normally distributed errors are **not** needed for
OLS to be the best linear unbiased estimator (Gauss-Markov); they are only needed for exact t-tests
and confidence intervals in small samples. Second, these assumptions are about *interpreting
coefficients and their uncertainty*. Predicting well on held-out data does not require them, which is
why the test-set RMSE is the honest check for prediction.

## Why ridge fixes a singular X^T X

X^T X is symmetric positive semi-definite, so its eigenvalues are lambda_i >= 0, and a singular
matrix has some lambda_i = 0. The matrix X^T X + alpha I has eigenvalues lambda_i + alpha, all
greater than 0 when alpha > 0, so it is always invertible. The cost is bias: the coefficients are
pulled toward zero. The penalty depends on the scale of the features, so features should be on a
comparable scale before ridge is used. (sklearn's diabetes features are already scaled; with
features in different units, standardise first.) The intercept is not penalised, as in the code.

## Gradient descent and why feature scaling matters

Use the mean squared error L(b) = (1/n) ||X b - y||^2. Its gradient is

    grad L(b) = (2/n) X^T (X b - y)

and one step moves downhill: b <- b - lr * (2/n) X^T (X b - y). This is exactly the update in
`gradient_descent.py`.

L is a quadratic bowl with Hessian H = (2/n) X^T X. Let b* be the exact minimum and e = b - b* the
error. Because the gradient is H e, a step gives e_next = (I - lr H) e. Along each eigenvector of H
(eigenvalue lambda_i) the error is multiplied by (1 - lr * lambda_i) at every step. So:

- **It converges only if |1 - lr * lambda_i| < 1 for every i, i.e. 0 < lr < 2 / lambda_max.**
  A larger step overshoots further each time and the loss blows up.
- **Speed is set by the slowest direction**, the one with the smallest lambda_i. With the best
  lr = 2 / (lambda_max + lambda_min), each step multiplies the worst error by (k - 1) / (k + 1),
  where k = lambda_max / lambda_min is the condition number of H (equal to cond(X)^2 once the
  column of ones is included). Roughly (k / 2) ln(1 / eps) steps are needed to shrink the error by
  a factor eps. A large k means very many steps.

Feature scaling changes k. In `gradient_descent_experiment.py` one feature has standard deviation
about 1 and the other about 1000. Computed for that exact data:

| | lambda_max | lambda_min | k | stable lr must be below |
|---|---|---|---|---|
| raw features | 2.12e6 | 1.84 | 1.15e6 | 9.4e-7 |
| standardised features | 2.13 | 1.87 | 1.14 | 0.94 |

This explains all three saved results (`results/gd_experiment.txt`):

- raw, lr = 0.01: far above 9.4e-7, so it diverged (MSE became infinite after 37 iterations).
- raw, lr = 1e-7: stable, but the slow direction shrinks by a factor 1 - 1e-7 * 1.84 per step, which
  is almost no progress in 1000 steps: MSE 4.747 against the best possible 0.0099.
- standardised, lr = 0.1: below 0.94 and k is almost 1, so it reached MSE 0.009919 in 131 steps
  (stopped by the tolerance).

Standardising makes every column's variance 1, so the curvature is similar in every direction
(k near 1) and one learning rate suits all of them. The scaling must be learned on the training set
only and applied unchanged to validation and test data.

## What is verified and what is not

- The scratch normal-equation solution matches scikit-learn to about 2e-16 and the saved test-set
  metrics are identical to two decimals (`results/regression_eval.txt`).
- The Hessian, orthogonality and convergence-bound claims above were checked numerically on the
  diabetes data and on the gradient-descent experiment's data (this file's numbers).
- Not shown here: Gauss-Markov is stated, not proved; the (k - 1) / (k + 1) rate is quoted for the
  best fixed step on a quadratic, not derived line by line.
- The ridge penalty alpha = 0.001 was the best value on the validation set and sits at the edge of
  the grid that was tried (0.001 to 10), so a smaller value was never tested.
