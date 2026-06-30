# Pruning Rules

The default fate of any skill without a pruning discipline is **sediment** — stale layers that settle because adding feels safe and removing feels risky. Pruning is the discipline.

## The root virtue: predictability

A skill exists to wrangle determinism out of a stochastic system. **Predictability** — the agent taking the same _process_ every run, not producing the same output — is the root virtue. Every lever below serves it.

If a change reduces tokens but makes behavior less predictable, it's a loss. If a change makes behavior more predictable but costs tokens, it's a win.

## Single source of truth

Each meaning lives in exactly one place. Changing the behavior is a one-place edit. Duplication inflates a meaning's prominence on the hierarchy past its real rank, and creates drift when one place is updated and the other isn't.

**Test**: find the same idea in two places. Either one is a duplicate (delete it) or one is a paraphrase (collapse it to a single token — a leading word).

## The no-op test

For every line in the skill, run the deletion test: does removing the line change the agent's behavior versus the default? If no, the line is a **no-op** — it costs tokens and context attention to say nothing.

Most prose that fails this test should go, not be rewritten. Rewriting a no-op is wasted work; the line itself is the problem.

Weak leading words are no-ops: "be thorough" when the agent is already thorough-ish. The fix isn't to find a different technique — it's a stronger leading word. *Thorough* becomes *relentless*; *careful* becomes *surgical*; *clear* becomes *unambiguous*.

## Leading words

A **leading word** is a compact concept already living in the model's pretraining that the agent thinks with while running the skill. Recurring through the text, it accumulates a distributed definition and anchors a region of behavior in few tokens, by recruiting priors the model already holds.

It serves predictability twice:

- **In the body**, it anchors execution: the agent reaches for the same behavior every time the word appears.
- **In the description**, it anchors invocation: when the same word lives in your prompts, docs, and code, the agent links that shared language to the skill and fires it more reliably.

Hunt for opportunities to refactor skills to use leading words. A triad spelled out at three sites (duplication), a description spending a sentence to gesture at one idea (duplication) — each is a passage begging to **collapse** into a single token.

**Common collapses**:

- "fast, deterministic, low-overhead" → *tight*
- "a loop you believe in" → *red* (the loop goes red on a bug, or it doesn't — binary observable)
- "the safety invariant" → *lock* (or whatever word survives scrutiny)
- "behavior preserved" → *equivalent*

You win twice over: fewer tokens, and a sharper hook for the agent to hang its thinking on. Assume every skill is carrying restatements that leading words retire — go find them.

## Failure modes

Diagnose issues with a skill using these categories:

### Premature completion

Ending a step before it's genuinely done, attention slipping to *being done*.

Defence, in order:

1. Sharpen the completion criterion first (cheap, local). "Produce a change list" is vague. "Every modified file accounted for" is exhaustive. A vague criterion invites premature completion.
2. Only if the criterion is irreducibly fuzzy _and_ you observe the rush, hide the post-completion steps by splitting (the sequence cut).

### Duplication

The same meaning in more than one place. Costs maintenance, tokens, and inflates a meaning's prominence past its real rank. Find and collapse.

### Sediment

Stale layers that settle because adding feels safe and removing feels risky. The default fate of any skill without a pruning discipline. The cure is a periodic review pass — re-read the skill, run the no-op test, cut.

### Sprawl

A skill too long even when every line is live and unique. Hurts readability, maintainability, and wastes tokens. The cure is the hierarchy: disclose reference behind pointers, and split by branch or sequence so each path carries only what it needs.

### No-op

A line the model already obeys by default. The test is deletion. A weak leading word is a no-op; the fix is a stronger word, not a different technique.

## What to fix in existing content

When reviewing, check in order:

1. Run the no-op test. Cut lines that pass.
2. Find duplication. Collapse to a single token or a single source.
3. Find sediment. Cut anything no longer bearing on what the skill does.
4. Check leading words. Any triad restated in three places collapses to one.
5. Check completion criteria. Each one is checkable AND exhaustive.
