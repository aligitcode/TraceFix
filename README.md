# TraceFix

By [aligitcode](https://github.com/aligitcode) · MIT license

TraceFix investigates a failing Python program. It parses the traceback, finds the failing
file, line and function, collects code evidence around the failure, asks Gemini for the likely
cause, then **checks the answer against the evidence** and scores it against a known cause.

It is a university project. It also contains a second, separate module: linear regression
written from scratch with NumPy and compared with scikit-learn. The regression module does
**not** find bug causes, and nothing here claims it does.

## Honest status

- The benchmark is tiny (14 original bugs plus 6 fresh ones) and the bugs are small.
- Fixes for bugs 10-13 were designed after seeing those bugs fail, so they cannot test themselves.
  The fresh bugs 15-20 were written afterwards, but by the same author who knew the pipeline, so
  they are **not blind**.
- The verifier checks that the lines Gemini cites exist in the evidence. It does not check that
  the explanation is right, so every `likely_cause` must be read by a person.
- Similar tools already exist (see `docs/related_work.md`). Nothing here is claimed to be new.
- No claim of business value is made.
- TraceFix reads the traceback and the source code only. It has no runtime values (variable contents),
  no sandbox, and it never runs or verifies a suggested fix.

## Install (Windows PowerShell)

Requires Python 3.10 or newer.

```powershell
cd TraceFix
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Copy the example settings file, then put your key in the new `.env` (it is git-ignored; never
paste it into a chat or commit it):

```powershell
Copy-Item .env.example .env
```

```
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.8-flash
```

## Everyday commands

| What | Command |
|---|---|
| Unit and fake-server tests (no key, no quota) | `python -m pytest -q` |
| Offline checks: traceback parsing and retrieval, no request | `python evaluate.py --no-llm` |
| Ask Gemini for every bug that has no saved answer | `python evaluate.py` |
| Same, then keep a copy once every bug is answered | `python evaluate.py --save-as results/after_evidence.json` |
| Rebuild a result from saved answers only | `python evaluate.py --cache-only` |
| Plain-chatbot baseline (traceback + failing file only) | `python evaluate.py --baseline` |
| The fresh bugs 15-20 | `python evaluate.py --cases examples/expected_heldout.json` |
| Just some bugs | `python evaluate.py --only 11,12,13` |
| Read what Gemini wrote | `python show_causes.py` |
| Compare saved results side by side (Markdown table) | `python compare_runs.py results/baseline_bugs11_14.json results/after_evidence.json` |

`evaluate.py` is the main entry point. `investigate.py` is an older single-script entry point
that sends only the code around the failing line; it does not collect the extra evidence.

Every answer is saved in `results/cache/` keyed by model and prompt, so **nothing is ever asked
twice**. If a run stops (daily limit, Google overloaded, Ctrl+C) run the same command later; it
only asks for what is missing. The free tier allows about 20 requests a day per model, and the
runner paces, backs off and stops early to protect that allowance. Details and the evidence for
every choice: `docs/gemini_quota_notes.md`.

Result files never overwrite each other: `latest.json`, `latest_baseline.json`,
`latest_heldout.json`, `latest_no_llm.json`. They are git-ignored; `--save-as` is how a result
becomes a committed file, and it refuses to save an incomplete run.

## How a bug is investigated

1. Run the failing script and read its traceback (`main.py`).
2. Collect evidence: code around the failing line, the body of functions called there, code around
   every other traceback frame, and top-level constants the failing file imports.
3. Build a prompt and ask Gemini for JSON: cause, cited lines, confidence, fix (`investigator.py`).
4. Verify that every cited line exists in the evidence (`verifier.py`).
5. Score against `examples/expected.json`: correct only if the cited lines include the line where
   the defect is, or, when that line was not in the evidence, if confidence was low or inconclusive
   (`scoring.py`).

The baseline (`baseline.py`) gives the same model only what a developer would paste into a chatbot,
so the extra evidence can be measured instead of assumed.

## Results so far

Measured on `gemini-3.8-flash`; saved files are in `results/`. Every number below comes from a
saved file or a quoted terminal output.

| Run | Code | Answered | Correct behaviour | False confidence |
|---|---|---|---|---|
| `before_definitions.json` (bugs 1-10) | 12fca21, before called-function retrieval | 10 / 10 | 9 / 10 | 1 (bug 10) |
| `baseline_bugs11_14.json` (bugs 1-14) | 3193912, before frame and constant evidence | 14 / 14 | 11 / 14 | 3 (bugs 11, 12, 13) |
| `after_evidence.json` (bugs 1-14) | run just before the final commit f001548 (the file records 881897f with uncommitted changes); the prompt is locked by a test | 14 / 14 | 14 / 14 | 0 |
| Plain-chatbot baseline (`--baseline`) | f001548 | 3 / 14 (bugs 1, 2 and 10) | not a result | not a result |
| Fresh bugs 15-20 | f001548 | not run | not run | not run |

How to read this table:

- `after_evidence.json` is **repair evidence, not a test**. Bugs 10-13 and their fixes were developed
  on the same cases. Six of its 14 answers came from earlier cached runs (13 requests were sent: 8
  answered, 5 failed with 503/504), so it was not produced by one clean invocation.
- "Correct behaviour" means the cited lines include the known cause line. The scorer is lenient and
  does not judge the written explanation, so read each `likely_cause` yourself
  (`python show_causes.py`).
- The plain-chatbot baseline could not be completed: over several days Gemini answered most requests
  with 503/504 overload errors (3 of 14 answered). **No claim is made about TraceFix versus a plain
  chatbot.** The fresh bugs have not been run either.
- Offline check, no API: `python evaluate.py --no-llm` parses 14 / 14 tracebacks and finds the known
  cause line in the collected evidence for 14 / 14 bugs. That tests parsing and retrieval only, not
  Gemini's diagnosis.

Regression module (`results/regression_eval.txt`, diabetes dataset, 265 / 88 / 89 split):
scratch OLS and scikit-learn agree (MAE 42.05, RMSE 51.18, R2 0.589), the training-mean baseline
has R2 -0.006. Experiments on collinearity, `lstsq` and `rcond`, ridge and gradient descent are
in `docs/derivation.md`.

## Layout

```
src/tracefix/   main.py, investigator.py, baseline.py, verifier.py, scoring.py,
                resilience.py, runner.py, compare.py  (TraceFix)
                regression.py, gradient_descent.py, metrics.py  (regression)
examples/       buggy_shop/ (bugs 1-14), heldout/ (bugs 15-20), expected*.json (answer keys)
tests/          unit tests, fake Gemini server tests, answer-key checks
docs/           derivation.md, gemini_quota_notes.md, related_work.md, report.md, study_guide.md
scripts/        small helpers: show_prompt.py, show_extra.py, try_summary.py
experiments/    regression/ one-off experiments behind docs/derivation.md
results/        saved results (generated files are git-ignored)
```

## Security

Running a failing script **executes it**. Only run benchmark cases you trust. Free-tier prompts may
be used by Google, so only send practice bugs and public code to Gemini. The failing script also runs with
your environment variables, which include `GEMINI_API_KEY`, so a malicious script could read the key.
Use a key you can revoke, and only run code you trust.