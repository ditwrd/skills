---
name: remove-ai-slop
description: Remove AI-generated code smells (slop) from changed files while preserving behavior. Locks behavior with regression tests first, then runs a categorized cleanup, then verifies with quality gates. Use when the user asks to "deslop", "clean up AI-generated code", "remove AI slop", or "remove slop" from recent changes.
---

# Remove AI Slop Skill

## Inputs

- **Default scope**: branch diff vs `merge-base main` (no arguments needed)
- **Optional scope**: explicit file list passed by the caller

## What this skill does

Cleans AI-generated slop from a bounded set of changed files while strictly preserving behavior. The safety invariant: **behavior is locked by green tests before a single line is removed**. A checklist alone is not safety; a passing regression test is.

---

## Process

### Step 0: Plan with TodoWrite

Create todos for the 5 steps below. Mark `in_progress` one at a time.

### Step 1: Lock behavior with regression tests (non-negotiable)

This is the safety mechanism. Skip it and every later step is a behavior-change time bomb.

For each in-scope source file:

1. Identify the public/observable behavior (exported functions, HTTP handlers, CLI commands, classes used elsewhere).
2. Check whether existing tests cover that behavior. Use `git grep` / project test conventions to find related test files.
3. **If behavior is uncovered or weakly covered, write the narrowest regression test that pins current behavior BEFORE editing the file.** Tests should pin observable outputs, not implementation details.
4. Run the test suite (or at minimum the relevant tests). They must be **green** before any cleanup begins.

If you cannot establish a green baseline (e.g., test runner is broken), STOP and report. Do not proceed with cleanup on unverified ground.

### Step 2: Determine scope and plan cleanup

If file paths were passed as arguments, that is the scope. Otherwise:

```bash
git diff $(git merge-base main HEAD)..HEAD --name-only
```

**Edge case — on main with no branch**: `git merge-base main HEAD` is empty when HEAD = main. Use one of:
- `git diff HEAD~N --name-only` for the last N commits
- `git diff --cached --name-only` for staged changes
- An explicit file list from the user

Filter out: deleted files, binary files, generated/vendored files (`node_modules/`, `dist/`, `target/`, lockfiles).

Then produce an explicit cleanup plan:

```
File: src/foo.py
  Categories: dead code, excessive complexity, performance
  Order: dead code → complexity → performance
  Risk: medium (touches caching layer)
```

Order rule (safest → riskiest): comments → dead code → defensive → duplication → complexity → abstraction/boundary → performance → tests → oversized-modules. This minimizes blast radius of any one change.

### Step 3: Parallel slop removal in batches of 5

Files are processed in parallel via background tasks, **batched 5 at a time**. More than 5 creates result-merging noise and context contention; fewer wastes parallelism.

**Batching protocol** (strict):

1. Slice the in-scope file list into chunks of up to 5 files.
2. For each chunk, launch all background tasks **in a single message**, every one with `background: true`.
3. End your turn. Wait for completion notifications as each task finishes.
4. Once all 5 in the batch complete, collect each result.
5. Launch the next batch of 5. Repeat until every file is processed.
6. If total files ≤ 5, launch all in one batch.

**Never** launch all files at once when there are more than 5; **never** launch them serially when more than one remains in the current batch.

The per-file prompt template is in `references/cleanup-prompt-template.md` — read it once, reuse it for every file in the batch. The template lists the 10 categories (full rules in `references/categories.md`), the order rule, hard constraints, and the required output format.

**Batch failure handling**: a timeout on a background task only means no new update arrived, not that the worker failed. Treat a running task as alive. Mark a file for retry only when the task is completed without the deliverable, ack-only after followup, explicitly reports blocked, or no longer running. Do NOT block the remaining 4 in that batch; collect successful results and retry the failed file once later. If retry also fails, escalate that file under "Issues Found & Fixed" in the final report.

### Step 4: Verify with quality gates and critical review

Run the five quality gates listed in `references/quality-gates.md`. Then walk the critical review checklist:

**Safety**:
- [ ] No functional logic accidentally removed
- [ ] All error handling preserved (especially around I/O, network, external APIs)
- [ ] Type hints intact and correct
- [ ] Imports still valid
- [ ] No breaking changes to public APIs

**Behavior**:
- [ ] Return values unchanged (verified by Step 1 regression tests)
- [ ] Side effects unchanged
- [ ] Exception behavior unchanged
- [ ] Edge case handling preserved

**Quality**:
- [ ] Removed changes are genuinely slop, not intentional patterns
- [ ] Remaining code follows project conventions
- [ ] No orphaned code or dead references
- [ ] Performance changes are obviously equivalent (no subtle algorithm shifts)
- [ ] No new abstractions introduced

### Step 5: Fix issues and produce report

If any gate fails or any checklist item flips:

1. Identify the specific change that caused the failure.
2. `git checkout` the affected file (or use `git diff` + targeted edit to revert just the problematic hunk).
3. If genuine slop remains after revert, edit the file directly — applying only the changes you can prove are safe.
4. Re-run the failing gate and re-walk the checklist for the affected file.
5. Repeat until all gates green AND checklist clean.

If you fail three times on the same file, STOP and escalate to the user with: the file, what you tried, what failed, your hypothesis. Do not keep editing.

Then produce the report using the template in `references/output-template.md`.

---

## When NOT to use this skill

- Fixing actual bugs (that's a regular fix, not cleanup)
- Refactoring for a real architectural goal (that's its own PR, not slop removal)
- Touching files the user didn't put in scope (the skill is explicitly bounded)

---

## Anti-Patterns (do not do these)

- **Skipping Step 1.** The regression test IS the safety mechanism; the checklist is its complement, not its replacement.
- **Bundling unrelated refactors.** A single "cleanup" commit with dead code deletion + abstraction removal + performance change is impossible to review and impossible to bisect. Stay scoped to slop.
- **Algorithm changes disguised as performance optimization.** If equivalence requires a proof, it is not a slop fix — it is a refactor and belongs in a separate change.
- **Silent skips.** If a quality gate is N/A, say `N/A` and why. If a check failed and you could not fix it, say so. Never claim PASS without evidence.
- **Removing comments that explain WHY.** "It is obvious from the code" is rarely true for the next reader. Only remove comments that restate WHAT.
- **Touching files outside scope.** If a file was not in the branch diff or explicit list, do not edit it, even if you notice slop in passing. Report it under "Remaining Risks".

---

## Reference Files

- `references/categories.md` — the 10 slop categories with KEEP rules and REFACTOR guidance, plus one worked example
- `references/cleanup-prompt-template.md` — per-file prompt template for batched background tasks
- `references/oversized-modules.md` — full procedure for category 10 (modular refactoring of files >250 pure LOC)
- `references/quality-gates.md` — gate definitions, tool persistence, quality assurance rules
- `references/output-template.md` — final report template
