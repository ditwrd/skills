# Structure Rules

A skill is built from two content types — **steps** and **reference** — that mix freely. The core decision is which to use, and where each sits on the **information hierarchy**: how immediately the agent needs the material.

## The hierarchy

From top (most-immediate) to bottom (on-demand):

1. **In-skill step** — an ordered action in `SKILL.md`, the primary tier. What the agent does, in order. Each step ends on a **completion criterion**: checkable ("can the agent tell done from not-done?") and, where it matters, exhaustive.
2. **In-skill reference** — a definition, rule, or fact in `SKILL.md`, consulted on demand. A flat peer-set (every rule of a review on one rung) is fine.
3. **External reference** — material pushed out of `SKILL.md` into a sibling file, reached by a **context pointer** (a one-line link), loaded only when the pointer fires.

Push too little down and the top bloats; push too much and you hide material the agent needs. That tension is the whole decision.

## Progressive disclosure

The move down the hierarchy — out of `SKILL.md` into a linked `.md` file in the same skill folder. Name the file for what it holds, not for the type (`pruning-rules.md`, not `reference.md`).

The context pointer's **wording** decides when and how reliably the agent reaches the material. "See REFERENCE.md" is weak. "See `pruning-rules.md` for the no-op test and leading-word principles" is strong — the agent can decide whether it needs that material.

**Co-location**: keep a concept's definition, rules, and caveats under one heading. Reading one part should bring its neighbours with it.

## When to split

Each cut spends one of two budgets — **context load** (always-loaded description) or **cognitive load** (you remembering the skill exists). Split only when the cut earns it.

Two cuts:

- **By invocation** — split off a model-invoked skill when you have a distinct **leading word** that should trigger it on its own, or another skill must reach it. You pay context load for the new always-loaded description.
- **By sequence** — split a run of steps when the steps still ahead tempt the agent to rush the one in front (**premature completion**). Keeping them out of view encourages more legwork on the current step.

## When to inline

Inline what every **branch** of the skill needs. Push behind a pointer what only some branches reach. If the skill is used in more than one way, and each way is a distinct branch, inline the shared material and disclose the rest.

## Hard limits

- **SKILL.md under 200 lines** — warn at 100–200, split at >200. After 200 lines, the agent's working memory is full of skill text, not the work.
- **References one level deep** — no `references/foo/bar.md` chains. The agent has to remember a path; chains cost recall.
- **Flat skill directory** — `skills/<name>/` shape. No nesting.

## What to fix in an existing structure

When reviewing, check in order:

1. Is SKILL.md over 200 lines? Disclose reference into siblings; inline what's left.
2. Are references one level deep? Flatten chains.
3. Is the skill nested? Move to flat `skills/<name>/`.
4. Do the context pointers actually guide the agent? Rewrite weak "see REFERENCE.md" to descriptive pointers.
5. Is in-skill material actually a step? Steps belong in `SKILL.md`. Reference material belongs in `references/`. The two are not interchangeable.
