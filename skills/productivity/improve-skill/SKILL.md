---
name: improve-skill
description: Improve an existing agent skill's description, structure, and references using a checklist-driven review. Use when the user asks to "improve a skill", "fix a skill", "tune a skill", or "review a skill" — or when a skill's description stops triggering, the SKILL.md gets too long, or the agent starts skipping steps.
---

# Improve Skill

## Inputs

- **Path**: path to the skill directory (e.g., `skills/my-skill/`)
- **Optional concern**: what the user is seeing wrong ("not triggering", "too long", "agent skips steps")

## What this skill does

Reviews an existing skill against the same principles used to write good skills, then applies targeted improvements. The root virtue is **predictability** — the agent running the skill the same way every time. Improvements should make the skill more predictable, not just more polished.

The improvements are scoped and minimal. A description fix is a one-line edit. A structure split is a new file + a pointer. Never rewrite a working skill from scratch.

---

## Process

### Step 1: Read the skill

Read the whole skill, in this order:

1. `SKILL.md` (frontmatter + body)
2. Every `references/*.md` (just to know they exist and what they cover)
3. Every `scripts/*` (just to know they exist)
4. If the user named a concern, focus on that area first

### Step 2: Run the review checklist

Score each item PASS / FAIL / N/A, and tag each FAIL with P0 (breaks functionality), P1 (reduces discoverability/usability), or P2 (polish).

**Description** (the only thing the agent sees):

- [ ] **Max 1024 chars** — strict. Cut identity already in the body.
- [ ] **Third person** — "Creates / Reviews / Builds / …" not "You can …".
- [ ] **Front-loads the leading word** — the description's first word should be the word the agent uses to think with while running the skill.
- [ ] **One trigger per branch** — list distinct branches the user might mean, not synonyms. "improve a skill", "fix a skill", "tune a skill" is fine; "improve a skill", "make a skill better", "fix up a skill" is duplication — collapse.
- [ ] **"Use when [triggers]" sentence** with specific phrasings a real user would type.

**Structure**:

- [ ] **SKILL.md under 200 lines** (warn at 100–200, split at >200)
- [ ] **References one level deep** — no `references/foo/bar.md` chains
- [ ] **Consistent terminology** across all files
- [ ] **No time-sensitive info** ("current as of 2024", "v3 API")

**Content**:

- [ ] **Concrete examples** for non-obvious behavior (one is enough; "the only useful number")
- [ ] **Each section has a clear purpose** — no meta-discussion of the skill itself in the body
- [ ] **Completion criteria are checkable** — agent can tell done from not-done; "produce a change list" is vague, "every modified file accounted for" is exhaustive
- [ ] **No no-op lines** — sentences the model already obeys by default. Test by deletion: does removing the line change behavior?

**Discoverability**:

- [ ] **Description triggers match real user phrasings** (not internal jargon)
- [ ] **Skill name is dash-case**, descriptive, doesn't collide with existing skills
- [ ] **No nested directory** — flat `skills/<name>/` shape

### Step 3: Prioritize

Work in this order. Stop when you've done enough.

1. **P0** — anything that breaks the skill (description over 1024 chars gets truncated, missing completion criterion causes premature completion, broken references)
2. **P1** — discoverability (description doesn't trigger, structure too long, references unreachable)
3. **P2** — polish (terminology consistency, no-op lines, leading-word collapse)

### Step 4: Apply

Edit the skill in place. Keep changes minimal — one improvement per concern. Do not restructure unless the structure check failed.

For description fixes, see `references/description-rules.md`.
For structure fixes (when to split, when to inline), see `references/structure-rules.md`.
For content fixes (no-op test, leading words, pruning), see `references/pruning-rules.md`.

### Step 5: Verify

Re-run the review checklist. Every P0 must now PASS. Every P1 you fixed must now PASS. If a fix introduced a new FAIL, revert just that change with `git checkout -p` or a targeted edit.

If you cannot make a P0 PASS without breaking two other checks, STOP and report. Do not over-rotate.

---

## Anti-patterns

- **Rewriting from scratch** when only the description needs fixing. Diff stays small.
- **Adding reference files** that no one will read. Split when SKILL.md >200, not before.
- **Keeping duplicates** between SKILL.md and references — reference the file, don't repeat the content.
- **Removing distinctive trigger phrases** from the description. Each one is a chance to match a real user phrasing.
- **Hedging completion criteria** with "as needed", "if applicable", "where relevant". These become no-ops the model obeys by default.

---

## Reference files

- `references/description-rules.md` — description principles: triggers, leading word, branches
- `references/structure-rules.md` — when to split, when to inline, information hierarchy
- `references/pruning-rules.md` — no-op test, single source of truth, leading words, failure modes
