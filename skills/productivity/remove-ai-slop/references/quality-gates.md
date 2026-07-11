# Quality Gates

A pass is complete only when all applicable gates are green. Skip gates that are genuinely N/A for the project (e.g., no security scanner configured), and report `N/A` explicitly — do not silently skip.

| Gate | Tool | Pass condition |
|---|---|---|
| Regression tests | project's test runner | all green |
| Lint | project's linter | zero errors (warnings OK if pre-existing) |
| Typecheck | project type-checker + diagnostics on changed files | zero new errors |
| Unit/integration tests | project's test runner | all green (pre-existing failures noted, not introduced) |
| Static/security scan | project's scanner | zero new findings, or `N/A` if not configured |

---

## Tool Persistence

- When a tool call fails, retry with adjusted parameters.
- Never silently skip a failed tool call.
- Never claim a gate passed without running it and reading the output.
- If correctness depends on further inspection, keep using diagnostics, the test runner, and direct file reads until the result is grounded.

---

## Quality Assurance

- NEVER remove code that serves a functional purpose.
- ALWAYS verify changes compile/parse and pass type-check.
- ALWAYS preserve test coverage; add tests rather than remove them.
- If uncertain about a change, err on the side of keeping the original code.
- The default action when in doubt is SKIP, not GUESS.
