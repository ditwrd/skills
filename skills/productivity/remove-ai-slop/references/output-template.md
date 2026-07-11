# Output Report Template

Produce this report at the end of every run. Replace bracketed values; do not omit sections even if a section is empty (use `[None]`).

```text
AI SLOP REMOVAL REPORT
======================

Scope: [branch diff vs merge-base main / explicit file list / staged changes / last N commits]
Files: [N files]
  - path/to/file1.ts
  - path/to/file2.py

Behavior Lock:
  - Existing coverage: [N files already covered]
  - Tests added: [M new regression tests at path/to/test_X.py]
  - Baseline status: GREEN

Cleanup Plan:
  - path/to/file1.ts: [dead code → complexity → performance]
  - path/to/file2.py: [comments → defensive]

Per-File Results:
  path/to/file1.ts
    - Dead code: 3 removed (lines X-Y, A-B, C)
    - Excessive complexity: 1 simplified (nested ternary at L42 → if/else)
    - Performance: 1 (line N: list scan → set lookup, O(n²)→O(n), behavior identical)
    - Skipped (preserved): 2 (defensive null check at boundary; commented WHY at L88)

  path/to/file2.py
    - Obvious comments: 5 removed
    - Over-defensive: 1 simplified (redundant isinstance on typed param)

Quality Gates:
  - Regression tests: PASS (12 tests, 0 failed)
  - Lint: PASS
  - Typecheck: PASS (0 new errors on changed files)
  - Unit/integration tests: PASS (45 tests, 0 failed)
  - Static/security scan: N/A (not configured)

Critical Review:
  - Safety: PASS
  - Behavior: PASS
  - Quality: PASS

Issues Found & Fixed:
  - [None] OR [Issue description → Fix applied]

Remaining Risks / Deferred:
  - [None] OR [e.g., "boundary violation in module X flagged but not refactored — needs human judgment"]

Final Status: CLEAN | ISSUES FIXED | REQUIRES ATTENTION
```
