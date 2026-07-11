# Oversized Modules (category 10) — full procedure

Any source file exceeding **250 pure LOC** (non-blank, non-comment lines) is an architectural defect, not a style preference. Measure:

```bash
awk '!/^[[:space:]]*$/ && !/^[[:space:]]*(#|\/\/)/' <file> | wc -l
```

**When found, do NOT just flag it. Execute a full modular refactoring:**

1. Identify all oversized files in the scope.
2. For each, identify distinct responsibilities (single-responsibility principle).
3. Plan the split: name each new file after the concept it owns (never `utils.py`, `helpers.py`, `common.py`, `part_1.py`).
4. Present the split plan to the user before executing.
5. Extract into clean modules with explicit re-exports where appropriate (re-exports ONLY, no logic in `__init__.py`).
6. Verify: every file must be ≤250 pure LOC. Run tests, typecheck, lint.

## Forbidden escapes

- Counting blanks/comments toward budget.
- Splitting by token count (`foo_1.py`, `foo_2.py`) — split by what each file DOES.
- Catch-all dump files (`utils.py`, `helpers.py`, `service.py`).
- "It's generated" — only valid if the file lives in a build output directory.
- "230 LOC, close enough" — a 230-LOC file about to grow is already over. Split now.

## KEEP

Genuinely self-contained single-responsibility scripts (e.g., a standalone CLI checker) may exceed the limit. Opt out with an explicit comment in the first 5 lines explaining why.
