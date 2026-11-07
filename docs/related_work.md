# Related work

TraceFix is a small teaching pipeline, not a new idea. Tools that read an error, look at code and ask a
language model for a cause or a fix already exist, from commercial products to research systems. This page
says what they do, using only what their own pages and abstracts state (retrieved 2026-11-07), and where
TraceFix sits next to them. Claims about what a system does *not* do are limited to "the page I read does not
mention it"; I did not run these tools.

| System | What it is | What it works from | What it produces | Evaluated on |
|---|---|---|---|---|
| **Sentry Seer** (product) | "Sentry's AI debugging agent" built into Sentry. | Error messages, stack traces and event metadata; distributed traces and spans; structured logs (beta); relevant code from linked GitHub or GitLab repositories. | A first guess at the problem on the issue page, remediation recommendations, and (Autofix) a code fix or pull request. | Not stated on the page I read. The page does not mention a confidence score. |
| **SWE-agent** (Yang et al., 2024) | An agent whose custom "agent-computer interface" lets a language model edit files, navigate a repository and run tests. | A GitHub issue and a whole repository, explored interactively. | A patch. | SWE-bench (12.5% pass@1) and HumanEvalFix (87.7%), as reported in the abstract. |
| **AutoCodeRover** (Zhang et al., 2024) | LLM plus code search over classes and methods of the program's syntax tree; uses spectrum-based fault localization when tests exist. | A GitHub issue and the repository. | A patch. | SWE-bench-lite: 19% resolved at about $0.43 per issue (abstract). |
| **Agentless** (Xia et al., 2024) | Argues a complex agent is not needed: a fixed three-step process of localization, repair and patch validation. | A GitHub issue and the repository. | A patch. | SWE-bench Lite: 32.00% (96 fixes) at about $0.70; also builds a cleaned subset after finding problematic issues in the benchmark. |
| **OpenHands** (Wang et al., 2024) | An open platform for building agents that write code, use a command line and browse the web, with sandboxed execution. | Whatever task the agent is given. | Whatever the agent does. | 15 tasks, including SWE-bench and WebArena. |
| **debug-gym** (Yuan et al., 2025) | A text environment in which an agent can explore a codebase interactively, with tools such as the Python debugger. | A buggy program and the debugger. | Debugging actions and a fix. | The abstract reports no headline number. |

## How TraceFix differs, and how much that is worth

- **Different task.** The systems above (except Sentry) are scored on issue-to-patch benchmarks. TraceFix
  starts from a crash and asks only for the *cause*, with the lines that support it. It is not comparable to
  their numbers and no such comparison is made.
- **No exploration.** SWE-agent, AutoCodeRover, OpenHands and debug-gym let the model look around.
  TraceFix collects a fixed set of evidence by rules (code at the failing line, bodies of called functions,
  code at the other traceback frames, imported constants) and asks once. That is simpler, cheaper and
  predictable, and it misses anything the rules do not reach (bugs 15 and 20 are built to show this).
- **The one measurable idea: check the answer against the evidence.** Every cited line must exist in the
  evidence that was sent, and a case counts as correct only if the cited lines include the real cause, or,
  when the cause was never in the evidence, the model said it was not sure. This tests whether the model
  is *calibrated*, not only whether it is right. Whether that adds anything beyond what the products above
  already do internally is **not known**: Sentry's page does not mention a confidence score, which does not
  mean it has none.
- **Scale.** 14 + 6 tiny bugs, one model, one author. The result is evidence about this pipeline on these
  bugs, not about debugging assistants in general.

## What would be needed to claim more

A fair comparison with any of these needs the same bugs, the same model and a defined input for each tool.
The only baseline built here is the plain chatbot (`python evaluate.py --baseline`: traceback plus the failing
file). Comparing against Sentry Seer or an open-source agent is future work.

## Sources

- Sentry Seer: <https://docs.sentry.io/product/ai-in-sentry/seer/>
- SWE-agent: Yang et al., *SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering*, arXiv:2405.15793
- AutoCodeRover: Zhang et al., *AutoCodeRover: Autonomous Program Improvement*, arXiv:2404.05427
- Agentless: Xia et al., *Agentless: Demystifying LLM-based Software Engineering Agents*, arXiv:2407.01489
- OpenHands: Wang et al., *OpenHands: An Open Platform for AI Software Developers as Generalist Agents*, arXiv:2407.16741
- debug-gym: Yuan et al., *debug-gym: A Text-Based Environment for Interactive Debugging*, arXiv:2503.21557
