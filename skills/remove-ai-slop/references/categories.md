# Categories (what counts as slop)

The agent looks for these ten categories. The first three are stylistic, the next three are boundaries and dead code, the next two are about hidden cost, the ninth is about behavior coverage, and the tenth is sizing. The last one has its own procedure — see `references/oversized-modules.md`.

## Stylistic

### 1. Obvious comments
Comments restating code, trivial docstrings, section dividers, commented-out code, vague TODOs/Notes.

- **KEEP**: comments explaining WHY (business logic, edge cases, workarounds), ticket links, regex/algorithm explanations.
- **KEEP**: BDD markers (`# given`, `# when`, `# then`, `# when/then`).

### 2. Over-defensive code
Null checks for guaranteed values, try/except around code that cannot raise, isinstance checks for statically typed params, default values for required params, backward-compat shims, redundant validation duplicated at multiple layers, **broad exception catching** (`except Exception`/`except BaseException` in Python, empty `catch {}` or `catch (e) { console.error(e) }` without narrowing in TypeScript/JavaScript).

- **KEEP**: validation at system boundaries (user input, external APIs), I/O error handling, nullable DB fields. Top-level boundary catch-all (CLI `main()`, HTTP handler) with explicit logging + re-raise is acceptable.
- **REFACTOR**: `except Exception` → catch the specific exception you expect. Empty `catch {}` → add `instanceof` narrowing or re-throw. `catch (e) { log(e) }` → narrow with `instanceof`, handle known cases, re-throw unknown.

### 3. Excessive complexity
Deep nesting (>3 levels), nested ternaries, complex boolean expressions (combine 4+ predicates), long parameter lists (>5 args without a struct/dataclass/object), god functions (>50 lines doing many things), overly clever one-liners that sacrifice readability, `if/elif/else` chains for type/enum/literal discrimination (must be `match/case` + `assert_never`), `object` used as a type annotation (must be `Protocol`, `TypeVar`, or explicit union).

- **KEEP**: established complexity patterns in this codebase, performance-critical hot paths that intentionally use a complex idiom. `if/else` for boolean conditions and range checks (not variant discrimination).
- **REFACTOR**: nested if-chains → guard clauses / early returns. Complex ternaries → explicit if/else. isinstance/enum if/elif chains → `match/case` with `assert_never` on the wildcard. `object` annotations → `Protocol` (structural), `TypeVar` (generic), or union (known variants).

## Boundaries and dead code

### 4. Needless abstraction
Pass-through wrappers, single-use helpers, speculative indirection ("we might need this later"), interfaces with one implementer where the interface adds no testability win, factory functions that just call a constructor.

- **KEEP**: abstractions that provide a real seam (testability, multiple implementers, framework-required boundaries).

### 5. Boundary violations
Wrong-layer imports (UI importing DB driver), leaky responsibilities (handler doing business logic that belongs in a service), hidden coupling (module A reads module B's private state), side effects in pure-named functions.

- **KEEP**: pragmatic short-circuits already established as a pattern in this codebase. Flag for human judgment if unsure.

### 6. Dead code
Unused imports, unused private functions/methods, unreachable branches, stale feature flags, debug leftovers (`console.log`, `print(...)`, `dbg!`), removed-but-still-referenced code.

- **KEEP**: code referenced via reflection, dynamic dispatch, or string lookup. Code intentionally kept as a feature flag rollback path (verify with the user).

## Hidden cost

### 7. Duplication
Copy-pasted branches with trivial differences, redundant helpers that do the same thing in two places, repeated literal/magic-number sequences.

- **KEEP**: incidental duplication (two pieces of code that look similar but serve different intents that could diverge). Prefer leaving them separate over forcing a premature shared abstraction.

### 8. Performance equivalences (behavior-preserving optimizations)
Changes that are provably equivalent in semantics but cheaper in time/space:

- O(n²) → O(n) when correctness preserved (e.g., set lookup vs list scan)
- Repeated computation inside a loop → hoist outside
- Unnecessary intermediate collections (eager `list(...)` when only iterated once → generator)
- String concatenation in loop → `join`
- Redundant DB/API calls in a loop → batch
- Redundant deep copies / clones
- `.length` / `len()` recomputed inside loop → cache

**Hard rule**: only apply when behavior equivalence is obvious. Do NOT change algorithms with subtle correctness implications. Do NOT micro-optimize hot paths without a benchmark. If in doubt, SKIP.

## Behavior coverage

### 9. Missing tests
Behavior present in changed files that is not locked by any regression test. The fix is not to remove code but to ADD the narrowest test that pins the behavior.

## Sizing

### 10. Oversized modules
Any source file exceeding **250 pure LOC** (non-blank, non-comment lines). This is an architectural defect, not a style preference.

**This is a procedure, not a category.** Full refactoring protocol in `references/oversized-modules.md`.

---

## Worked example: Performance equivalences (category 8)

**Before** (in a hot path called per request):

```python
def get_user_emails(user_ids: list[int]) -> list[str]:
    emails = []
    for uid in user_ids:
        user = None
        for u in users:                    # O(n) scan per uid
            if u.id == uid:
                user = u
                break
        if user is not None:
            emails.append(user.email)
    return emails
```

**After**:

```python
def get_user_emails(user_ids: list[int]) -> list[str]:
    user_by_id = {u.id: u for u in users}    # O(n) build once, hoist out of loop
    return [user_by_id[uid].email for uid in user_ids if uid in user_by_id]
```

- **Why slop**: O(n) scan per lookup, in a loop → O(n²) total. The lookup table is computed inside the loop on every call.
- **Why safe**: same set of return values for any input — no user is returned that wasn't returned before, no user is missing that was returned before. Order preserved (dict iteration order is insertion order, which mirrors the original `users` list). The `if uid in user_by_id` guards against missing IDs the same way the original `if user is not None` did.
- **What was NOT changed**: error handling for missing users (silent skip, as before), input type expectations, return type.
