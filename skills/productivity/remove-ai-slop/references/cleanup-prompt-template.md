# Cleanup Prompt Template (per-file)

Use this exact prompt shape for every file in a batch. Read it once, substitute `{file_path}`, launch the background task.

```
Remove AI slop from: {file_path}

Apply changes in this order (safest → riskiest): comments → dead code → defensive → duplication → complexity → abstraction/boundary → performance → oversized-modules.

Read references/categories.md for the full list of 10 slop categories and KEEP rules. Read references/oversized-modules.md if the file is over 250 pure LOC.

Hard constraints:
- Behavior MUST be preserved. When equivalence is not obvious, SKIP.
- Do NOT change public API signatures.
- Do NOT remove type hints.
- Do NOT introduce new abstractions or dependencies.
- Diff stays minimal and scoped to slop removal.

Report changes grouped by category. For each change, give before/after, why-slop, why-safe.
For each skipped issue, give reason.
```
