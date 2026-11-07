# TraceFix

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

## Install (Windows PowerShell)

```powershell
cd TraceFix
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install pytest google-genai python-dotenv numpy scikit-learn
$env:PYTHONPATH = "src"        # needed in every new terminal, or you get "No module named tracefix"
```

Put your key in a file named `.env` (it is git-ignored; never paste it into a chat or commit it):

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

Measured on `gemini-3.8-flash`; saved files are in `results/`.

| Run | Code | Correct behaviour | False confidence |
|---|---|---|---|
| `before_definitions.json` (bugs 1-10) | 12fca21, before called-function retrieval | 9 / 10 | 1 (bug 10) |
| `baseline_bugs11_14.json` (bugs 1-14) | 3193912, before frame and constant evidence (file committed in 280f1aa) | 11 / 14 | 3 (bugs 11, 12, 13) |
| After frame and constant evidence (current code) | 939f647 | **not complete yet**: 6 of 14 bugs answered, all 6 correct | pending |
| Plain-chatbot baseline | `--baseline` | pending | pending |
| Fresh bugs 15-20 | `--cases examples/expected_heldout.json` | pending | pending |

"Pending" means the Gemini runs are not finished, not that they failed. Do not read the 6 / 6
as a result: it is 6 easy bugs out of 14, and bugs 10 and 11 are the ones that matter.

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
results/        saved results (generated files are git-ignored)
```

## Security

Running a failing script **executes it**. Only run benchmark cases you trust. Free-tier prompts may
be used by Google, so only send practice bugs and public code to Gemini.
