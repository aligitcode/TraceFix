# TraceFix: evidence-checked root-cause suggestions for Python crashes, and linear regression from scratch

*Draft. Every number below comes from a saved result file or a terminal output quoted in the text.
Anything not measured says NOT RUN. The Gemini runs listed in section 4.4 are optional for the release:
if they are completed, add them to the tables; if not, the claims below already say what is not supported.*

## Abstract

TraceFix investigates a failing Python program: it parses the traceback, collects code evidence, asks a
language model (Gemini) for the likely cause with the source lines it relied on, checks that those lines
exist in the evidence, and scores the answer against a known cause. A separate module implements linear
regression from scratch with NumPy and compares it with scikit-learn. On a benchmark of 14 small bugs,
retrieving called function bodies removed the false confidence on bug 10 (saved result), and adding
other-frame code and imported constants gave 14 / 14 correct behaviour with no false confidence in a
complete saved run (`after_evidence.json`). That run is repair evidence: the fixes were designed after
seeing those bugs fail, six of its answers came from earlier cached runs, and the scorer checks cited
lines, not the explanation. The plain-chatbot baseline (2 of 14 answered) and the six fresh bugs could not
be run because Gemini's free tier returned overload errors, so no comparison with a plain chatbot is
claimed. The benchmark is tiny, so the results are evidence about this pipeline on these bugs and nothing
more.

## 1. Scope

The course requires linear regression from scratch with NumPy, compared against scikit-learn, with a
derivation, experiments, honest limitations, a report and a clean repository. TraceFix is the applied
project. The two are separate: the regression module does not locate bug causes, and no claim connects them.

## 2. Related work

Sentry Seer, SWE-agent, AutoCodeRover, Agentless, OpenHands and debug-gym already read errors or issues
and propose causes or fixes (`related_work.md`). TraceFix is not new as a tool. Its narrow, testable idea is
to check the answer against the evidence and to score whether the model is calibrated when the evidence does
not contain the cause. The only baseline built is a plain chatbot; no comparison with the products above is claimed.

## 3. Method

**Pipeline.** (1) Run the script and parse the traceback. (2) Evidence: code around the failing line;
bodies of functions called there, found by AST in the failing file's folder; code around every other
traceback frame; top-level constants the failing file imports from local modules. (3) Prompt Gemini for JSON:
likely cause, cited lines, confidence, fix. (4) Verify each cited line exists in the evidence (`supported`,
`weak` or `inconclusive`). (5) Score.

**Scoring.** If the cause line is in the evidence, the answer is correct only if the cited lines include it.
If it is not, the correct behaviour is low or inconclusive confidence. *False confidence* means the verifier
said "supported" but the behaviour was wrong. The scorer is lenient (a long list passes if it includes the
cause line) and does not judge the written explanation, so each cause is read by a person.

**Root-cause rule.** The cause is where the wrong value is created, not where the program crashes (for
example bug 10: `find_user` silently returns `None`; the crash is later).

**Answer keys.** `evidence_sufficient` is defined as "the cause line is inside the evidence TraceFix collects",
and a test checks every case against the real retrieval, so a mislabelled key fails the test suite.

**Baseline.** `--baseline` gives the same model, JSON format and scoring only what a developer would paste
into a chatbot: the traceback and the whole failing file. Sufficiency is computed from that input, not copied.

**Runner.** Free-tier Gemini allows about 20 requests a day per model. The runner reuses saved answers,
paces requests, waits out per-minute limits, backs off on 503/504, stops after 3 failures in a row, and never
saves an incomplete result (`gemini_quota_notes.md`). It is tested against a fake Gemini server (135 tests)
and has run against the real API on the author's machine (the 14-bug run in 4.3), but a daily-quota stop has not been seen live.

## 4. Experiments

### 4.1 Linear regression (`results/regression_eval.txt`)

Data: scikit-learn diabetes, 442 rows split 265 / 88 / 89 (train / validation / test, seed 42). Ridge alpha was
chosen on validation; the test set was used once.

| Model (test set) | MAE | RMSE | R2 |
|---|---|---|---|
| Baseline (training mean) | 66.17 | 80.04 | -0.006 |
| Scratch OLS (normal equation) | 42.05 | 51.18 | 0.589 |
| scikit-learn LinearRegression | 42.05 | 51.18 | 0.589 |
| Scratch ridge, alpha = 0.001 | 42.05 | 51.20 | 0.588 |

Validation RMSE by alpha: 0.001: 50.24, 0.01: 50.54, 0.1: 51.39, 1: 58.84, 10: 72.62. The best value is at the
edge of the grid, and ridge brings no gain here because the features are not badly collinear.

Other findings (from earlier experiments, derivations in `derivation.md`):

- Scratch coefficients match scikit-learn to about 2e-16.
- Exact duplicate features make X^T X singular. Near-duplicates (difference 1e-9) gave coefficients
  of about +5621 and -5619 with the normal equation (condition number about 1.8e15).
- `lstsq` with numpy's default cutoff was worse (about +/-2.7 million); `rcond=1e-8` gave 1.0028 and 1.0028,
  matching scikit-learn. The right `rcond` depends on the data.
- Gradient descent (`results/gd_experiment.txt`): on standardised features lr = 0.1 reached MSE 0.009919 in
  131 steps (best possible 0.0099); on raw features lr = 0.01 diverged and lr = 1e-7 ended at 4.747 after 1000
  steps. The stability bounds computed for that data are lr < 0.94 (scaled) and lr < 9.4e-7 (raw), which explain
  all three runs.

### 4.2 TraceFix on the 14 original bugs: saved results

`python compare_runs.py results/before_definitions.json results/baseline_bugs11_14.json`:

| Run | Code | Answered | Correct behaviour | False confidence |
|---|---|---|---|---|
| before_definitions | 12fca21 (before called-function retrieval) | 10 / 10 | 9 / 10 | 1 (bug 10) |
| baseline_bugs11_14 | 3193912 (before frame and constant evidence) | 14 / 14 | 11 / 14 | 3 (bugs 11, 12, 13) |

Bug 10 was fixed by retrieving called function bodies, bugs 11-13 by adding other-frame code and imported
constants. **Both fixes were designed after seeing those bugs fail**, so this is repair evidence, not a test.

### 4.3 Current evidence: complete run (`results/after_evidence.json`)

| Run | Code | Answered | Correct behaviour | False confidence |
|---|---|---|---|---|
| after_evidence | run before the final commit f001548 (file records 881897f, uncommitted changes) | 14 / 14 | 14 / 14 | 0 |

The run took 13 requests (8 answered, 5 failed with 503/504 and were retried by the runner); the other 6
answers were reused from earlier cached runs. The prompt text is locked byte-for-byte by a test, so those
cached answers are valid for this code, but the 14 answers were not produced by one clean invocation.
Bug 12's cause was given as `DEFAULT_TAX` being the string "0.2", and bug 13's as the key typo `'nam'`,
the two baseline false-confidence cases that need other files.

This is **repair evidence, not a test**: bugs 10-13 and their fixes were developed on the same cases.
The written causes were read from one-line summaries only. Two things still need a human check: bug 10's
explanation names the symptom more than the silent-`None` design flaw, and bug 4's answer contains doubled
quotes (`'"5"'`), to be compared with `examples/buggy_shop/run_bug4.py`.

Offline check without any API call (`python evaluate.py --no-llm`): 14 / 14 tracebacks parsed and 14 / 14
cases have the known cause line inside the collected evidence. This tests parsing and retrieval, not
Gemini's diagnosis.

### 4.4 Runs not completed

| Run | Command | Result |
|---|---|---|
| Complete run, current evidence | `python evaluate.py --save-as results/after_evidence.json` | done, see 4.3 |
| Plain-chatbot baseline | `python evaluate.py --baseline --save-as results/plain_baseline.json` | PARTIAL: 2 of 14 answered (bugs 1 and 2, both correct); Gemini overload (503/504) blocked the rest; not a result |
| Fresh bugs 15-20 | `python evaluate.py --cases examples/expected_heldout.json --save-as results/heldout.json` | NOT RUN |
| Fresh bugs, plain baseline | `python evaluate.py --baseline --cases examples/expected_heldout.json --save-as results/heldout_plain.json` | NOT RUN |

Why they are not done: the free tier allows about 20 requests a day per model, and over several days most
requests were answered with 503/504 overload errors (inferred: failed requests appear to count against the
daily limit; not confirmed by Google). The runner stops instead of wasting requests and never saves an
incomplete result.

If they are completed later, `python compare_runs.py results/baseline_bugs11_14.json
results/after_evidence.json results/plain_baseline.json` gives the comparison table. Read every
`likely_cause` before writing any sentence about accuracy.

The fresh bugs: 16-19 have their cause inside the collected evidence; 15 (a mutable default argument) and
20 (a function that lets a string through) do not, so the correct answer for those two is low confidence.
They were written with the code frozen but by the author who knew the pipeline, so they are not blind.
Bug 19's error message differs between Python versions, which is part of the test.

## 5. Engineering lessons

1. The verifier checks that cited lines exist, not that the cause is correct. "Supported" is not "correct".
2. A plausible Gemini fix is not a correct fix; several fixes only hid the bug (return 0 / a default).
3. The normal equation squares the condition number and fails on near-collinear features; `lstsq` alone does not
   fix near-duplicates, `rcond` matters.
4. Passing tests prove only what they exercise. Unit tests, integration tests, benchmark runs and live API calls
   are different things. Here the runner has unit and fake-server tests and one complete real-API run, but a daily-quota stop has not been seen live.
5. Changing the evidence changes every prompt and invalidates the cache, so each change costs a full re-run.
6. A milestone needs an implementation, a run and a commit. A partial paste was once misread as a pass.
7. The fix for bug 10 was not "read every frame": `find_user` is never a traceback frame because it returned.
8. Reliability code needs a failing example first: the Nov 2 run showed a per-minute 429 being treated as the
   daily limit, and the test for that case failed before the fix and passes after (checked by reintroducing
   the bug).

## 6. Limitations and threats to validity

- 14 + 6 tiny bugs, one model, one author, one run per condition. No confidence intervals. Gemini's answers can
  vary between runs, and each answer is cached, so a repeat does not re-sample.
- Bugs 10-13 and their fixes were developed against the same cases, so those cases cannot test the fixes. Bugs 15-20 are not blind.
- Lenient scoring; the explanation is not judged automatically; the verifier checks lines, not truth.
- Evidence rules reach only part of a program: they miss star imports, data files and state set far from the
  crash. Bug 15 and 20 show this on purpose.
- Failed free-tier requests appear to count against the daily limit (inferred from two days that each added up
  to exactly 20, not confirmed by Google).
- Similar products exist and were not run; no market or usability claim is made.

## 7. Security and ethics

Running a failing script executes it, so only trusted benchmark cases are run. Free-tier prompts may be used by
Google, so only practice bugs and public code are sent. API keys live in a git-ignored `.env`.

## 8. Conclusion

What the evidence supports: called-function retrieval fixed bug 10 and the other-frame and constant
evidence fixed bugs 11-13 (saved results, repair evidence); a complete saved run scored 14 / 14 with no
false confidence by the line-citation measure; the offline pipeline parses all 14 tracebacks and retrieves
the cause line for all 14; and the regression module reproduces scikit-learn.

What it does not support: that TraceFix beats a plain chatbot (the baseline was not completed), that it
generalises (the fresh bugs were not run and are not blind), or that its written explanations are correct
beyond the cited lines (the scorer does not judge them). The tool also has no runtime values, no sandbox and
no fix verification (see section 6).

## Appendix A. Reproduce

```
python -m pytest -q
python evaluate.py --no-llm
python evaluate.py --save-as results/after_evidence.json
python evaluate.py --baseline --save-as results/plain_baseline.json
python compare_runs.py results/baseline_bugs11_14.json results/after_evidence.json results/plain_baseline.json
python evaluate_regression.py
python gradient_descent_experiment.py
```
