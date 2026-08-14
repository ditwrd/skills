---
name: distill-skill
description: Distills session learnings into durable memory, then improves a target skill. Use when the user asks to "distill", "capture session learnings", "distill and improve", or "learn from this session" — runs session distillation first, then applies the improvement checklist through the lens of what the session taught. A router or the "improve-skill" skill can reach this skill when a session's lessons should be preserved before improvement.
---

# Distill Skill

**Leading word**: *distill* — condensing a session to its essential lessons, then using them to sharpen a skill.

Two phases. First, extract what the session taught and register it durably. Then improve the target skill, using those learnings as a lens on the checklist.

---

## Inputs

- **Path**: the target skill's directory. If given a full/relative path, use it as-is. If given a bare name, resolve it directly instead of searching: try your harness's native skill-lookup mechanism first if it has one (an internal URI scheme, a `skills list`/`skills path` command, etc.); otherwise check well-known skill roots directly (`.claude/skills/<name>/`, `.omp/skills/<name>/`, `~/.agents/skills/<name>/`, `~/.claude/skills/<name>/`, or wherever your harness documents skills living). NEVER `find`/glob the whole filesystem for it — only fall back to a shallow search scoped to those roots if none of them hit.
- **Optional concern**: what the user is seeing wrong ("not triggering", "too long", "agent skips steps")

---

## Process

### Step 1: Distill session learnings

Before touching the target skill, capture what this session taught.

#### 1a. Gather session material

- Read `history://` for the current agent's transcript (if available)
- Use `recall` to surface prior learnings relevant to the session's work
- Note: what problem was being solved, what approach worked, what didn't

#### 1b. Identify learnings

Scan for patterns in what happened:

- **Mistake** — something that burned time; worth flagging in the target skill
- **Edge case** — a corner the target skill didn't cover
- **Effective technique** — something that worked; the skill should promote it
- **Gap in the skill** — something the target skill claims but didn't deliver
- **Repeating pattern** — a structure worth standardizing

#### 1c. Condense

Write 3–5 bullets. Each one:

- Cites a specific session event (a tool call that failed, a decision that paid off, an assumption that broke)
- States what the target skill should do differently (a missing step, a sharper criterion, a new example)

Skip session minutiae (one-off commands, transient errors), the obvious (repeated exact steps), and what's already recorded.

#### 1d. Register

- **Durable fact** — `retain` it
- **Repeatable procedure** — `learn` with a managed skill

Learnings applicable to the target skill carry forward to Step 3.

**Completion criterion**: every bullet cites a specific session event AND states what the target skill should do differently. If nothing worth keeping, note that and proceed.

### Step 2: Read the skill

Read the whole target, in order:

1. `SKILL.md` (frontmatter + body)
2. Every `references/*.md` (just to know they exist and what they cover)
3. Every `scripts/*` (just to know they exist)
4. If the user named a concern, focus on that area first

### Step 3: Run the review checklist

Score each item PASS / FAIL / N/A. Tag each FAIL with P0 (breaks functionality), P1 (reduces discoverability/usability), or P2 (polish).

**Session lens**: for each FAIL, ask whether a session learning explains *why* it failed. If so, the fix is already grounded in real evidence — prioritize it.

#### Description

- [ ] **Max 1024 chars** — strict. Cut identity already in the body.
- [ ] **Third person** — "Distills / Reviews / Builds / …" not "You can …".
- [ ] **Front-loads the leading word** — the description's first word anchors the skill's identity.
- [ ] **One trigger per branch** — distinct intents, not synonyms. "improve a skill", "fix a skill", "tune a skill" is fine; "improve a skill", "make a skill better" is duplication.
- [ ] **"Use when [triggers]" sentence** with specific phrasings a real user would type.

#### Structure

- [ ] **SKILL.md under 200 lines** (warn at 100–200, split at >200)
- [ ] **References one level deep** — no `references/foo/bar.md` chains
- [ ] **Consistent terminology** across all files
- [ ] **No time-sensitive info** ("current as of 2024", "v3 API")

#### Content

- [ ] **Concrete examples** for non-obvious behavior (one is enough)
- [ ] **Each section has a clear purpose** — no meta-discussion in the body
- [ ] **Completion criteria are checkable** — agent can tell done from not-done
- [ ] **No no-op lines** — sentences the model already obeys by default

#### Discoverability

- [ ] **Description triggers match real user phrasings** (not internal jargon)
- [ ] **Skill name is dash-case**, descriptive, doesn't collide
- [ ] **No nested directory** — flat `skills/<name>/` shape

### Step 4: Prioritize

P0 → P1 → P2. Session-grounded FAILs move to the front of their priority tier.

### Step 5: Apply

Edit the skill in place. One improvement per concern. Do not restructure unless a structure check failed.

For description fixes, see `references/description-rules.md`.
For structure fixes, see `references/structure-rules.md`.
For content fixes, see `references/pruning-rules.md`.

### Step 6: Verify

Re-run the checklist. Every P0 must now PASS. Every P1 you fixed must now PASS. If a fix introduced a new FAIL, revert just that change with `git checkout -p` or a targeted edit.

If you cannot make a P0 PASS without breaking two other checks, STOP and report.

---

## Anti-patterns

- **Vague distillation** — "the session was about X" without citing a concrete event or extracting what changes. A bullet without both a citation and an implication is a no-op.
- **Distilling off-target** — capturing learnings about the wrong thing. The distill is for the session, not the skill. Stay grounded in what happened, not what the skill says.
- **Rewriting from scratch** — the improve phase edits in place, not rewrites.
- **Adding reference files no one will read** — split only when SKILL.md >200 lines.
- **Keeping duplicates between SKILL.md and references** — reference the file, don't repeat the content.
- **Removing distinctive trigger phrases from the description** — each is a chance to match a real user phrasing.
- **Hedging completion criteria** — "as needed", "if applicable", "where relevant" become no-ops.
