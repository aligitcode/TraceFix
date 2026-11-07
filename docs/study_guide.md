# Study guide for the oral exam

Short answers you should be able to give without notes. If you cannot say an answer in your own words,
read the matching part of `derivation.md` or the code until you can. Numbers are from this repository's
saved results.

## Linear regression

**1. What problem does linear regression solve?**
Given features X (n rows, p columns) and a target y (n values), find weights b so that X b predicts y.
We pick the b that makes the sum of squared errors smallest.

**2. Shapes?**
X is n x p, with a column of ones added (n x (p+1)) so the first weight is the intercept. b is (p+1) x 1.
y is n x 1. The prediction X b is n x 1.

**3. Why square the errors?**
Squaring makes every error positive (so they cannot cancel), punishes big errors more, and gives a
smooth bowl-shaped function whose minimum can be found by setting the derivative to zero. Absolute
errors also work but have no simple closed form.

**4. Derive the normal equation.**
S(b) = (y - Xb)^T (y - Xb) = y^T y - 2 b^T X^T y + b^T X^T X b. The gradient is -2 X^T y + 2 X^T X b.
Set it to zero: X^T X b = X^T y. If X^T X is invertible, b = (X^T X)^(-1) X^T y.

**5. How do you know it is a minimum, not a maximum?**
The Hessian is 2 X^T X, and v^T (2 X^T X) v = 2 ||X v||^2 is never negative, so the function is a bowl
(convex) and any stationary point is the global minimum. With full column rank it is strictly positive,
so the minimum is unique. Second proof: S(b) = S(b_hat) + ||X(b - b_hat)||^2.

**6. What does "the residual is perpendicular to the columns of X" mean?**
The normal equations say X^T (y - X b) = 0. The prediction is the projection of y onto the space
spanned by the columns of X, and what is left over points straight out of that space. With an intercept
this also makes the residuals average to exactly zero.

**7. Why does the code use `solve` and not an explicit inverse?**
Solving X^T X b = X^T y directly is faster and more accurate than forming the inverse.

**8. Gauss-Markov assumptions and the conclusion?**
Linear in the coefficients, errors with mean zero, constant variance, uncorrelated errors, no perfect
collinearity. Then OLS is the best linear unbiased estimator. Normality is not required for that; it is
only needed for exact t-tests in small samples.

**9. Which assumption can you not see in the residuals?**
Mean-zero errors. With an intercept the residual mean is forced to zero, so an omitted variable that
biases the coefficients is invisible there.

**10. What goes wrong with collinear features?**
Exact duplicates make X^T X singular, so there is no unique solution. Near-duplicates make it nearly
singular. Forming X^T X squares the condition number (cond(X^T X) = cond(X)^2); ours reached about 1.8e15,
near the limit of double precision, and the coefficients came out +5621 and -5619 while their sum
stayed right.

**11. How do `lstsq`, `rcond` and ridge help?**
`lstsq` uses an SVD of X and never forms X^T X. Singular values below rcond times the largest are treated
as zero. With numpy's default cutoff a 1e-9 difference was still kept (about -2.7e6 and +2.7e6);
rcond=1e-8 dropped that direction (1.0028 and 1.0028, like scikit-learn). Ridge adds alpha I, so every
eigenvalue becomes lambda + alpha > 0 and the matrix is always invertible, at the price of some bias.

**12. How does gradient descent work, and when does it converge?**
b <- b - lr * (2/n) X^T (X b - y). On this quadratic it converges only if lr < 2 / lambda_max of
(2/n) X^T X, and its speed depends on the condition number lambda_max / lambda_min.

**13. Why scale the features for gradient descent?**
Different scales make lambda_max huge, which forces a tiny learning rate, while lambda_min stays small,
so progress along the slow direction is almost zero. In our experiment raw features need lr < 9.4e-7
(lr = 0.01 diverged, lr = 1e-7 left MSE at 4.747 against 0.0099 after 1000 steps); standardised features
allow lr < 0.94 and lr = 0.1 converged in 131 steps.

## Metrics and experimental method

**14. MAE, RMSE, R2?**
MAE is the average absolute error. RMSE is the square root of the average squared error, so it punishes
large errors more and is in the units of y. R2 = 1 - (sum of squared residuals) / (sum of squares around
the mean): the fraction of variance explained compared with always predicting the mean.

**15. What does R2 near 0 or negative mean?**
The model is no better than predicting the training mean. Our baseline scored R2 = -0.006 on the test set;
OLS scored 0.589.

**16. Why a train / validation / test split?**
Train to fit, validation to choose settings (we chose ridge alpha there), test once at the end for an
honest estimate. Choosing alpha on the test set would leak the answer into the score. Sizes: 265 / 88 / 89.

**17. What did the comparison with scikit-learn show?**
Scratch OLS and `LinearRegression` gave identical test MAE 42.05, RMSE 51.18, R2 0.589. Ridge with
alpha = 0.001 gave RMSE 51.20: no gain, because the diabetes features are not badly collinear.

**18. What is a limitation of that experiment?**
One dataset, one random split, no confidence intervals, and the best alpha (0.001) is at the edge of the
grid so smaller values were never tried.

## TraceFix

**19. What does TraceFix do, in one breath?**
It runs a failing script, parses the traceback, collects evidence (code at the failing line, bodies of
called functions, code at the other frames, imported constants), asks Gemini for a likely cause as JSON
with the lines it relied on and a confidence, verifies that those lines exist in the evidence, and scores
the answer against a known cause.

**20. Does the regression module find the bugs?**
No. It is a separate project requirement and has nothing to do with locating causes.

**21. What does the verifier check, and what does it not?**
It checks that the lines Gemini cites exist in the evidence that was sent. It does not check that the
explanation is correct. "Supported" is not "correct", so every written cause must be read by a person.

**22. What is false confidence?**
The model says "high" and the verifier says "supported" while the behaviour was wrong, for example the
cause line was never in the evidence. Before the extra evidence, bugs 11, 12 and 13 were like this.

**23. How is an answer scored?**
If the cause line is in the evidence, the answer must cite it. If it is not, the right behaviour is to say
low or inconclusive. The scoring is lenient (a long list of cited lines passes if it includes the cause)
and does not judge the wording of the explanation.

**24. Why compare against a plain chatbot?**
A claim that the extra evidence helps needs a baseline with the same model and scoring. `--baseline` gives
the model only the traceback and the failing file, which is what a developer would paste. Only for bug 13
is that enough, because Python prints the bad line in the traceback.

**25. Why is the benchmark weak, and what did you do about it?**
The bugs are tiny, and the fixes for bugs 10-13 were designed after seeing them fail, so they cannot test
themselves. Bugs 15-20 were written afterwards, with the code frozen, but by the author who knew the
pipeline, so they are not blind. Two of them (15, 20) are designed so the cause is not in the evidence.

**26. What did you learn from the quota problems?**
Free tier means about 20 requests a day per model, and failed 503/504 calls seem to count. A per-minute
429 was misread as the daily limit and threw away a run; a 20-second timeout made every call fail. The
runner now waits out per-minute limits, backs off on overload, stops after 3 failures in a row, always
reuses saved answers, and never saves an incomplete result. Evidence: `docs/gemini_quota_notes.md`.

**27. What are the main limitations to admit?**
Tiny benchmark, one model, lenient scoring, evidence rules that cannot reach everything (star imports,
data files, state set far away), similar tools already exist, and no validation that anyone would use or
pay for it.

**28. Security?**
Running a failing script executes it, so only trusted benchmark cases are run. Free-tier prompts may be
used by Google, so only practice bugs and public code are sent.
