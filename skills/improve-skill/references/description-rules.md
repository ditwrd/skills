# Description Rules

The description is the only thing the agent sees when deciding which skill to load. Every word costs **context load** (always in the window). The body has more room; the description earns harder pruning.

## What makes a description trigger well

### 1. Two jobs, one slot

A model-invoked description does two jobs:

- **State what the skill is** (one short clause)
- **List the branches** that should trigger it (the "Use when" sentence)

Cut identity that's already in the body. The body can say "this skill does X"; the description says "when the user says X, fire this skill".

### 2. Front-load the leading word

The leading word is the compact concept the agent thinks with while running the skill (e.g., *slop*, *slop*, *regression*). The description's first word should be the same word the agent uses to think about the problem.

If the leading word is buried in the second clause, the agent has to read two sentences to know whether to fire the skill. Front-loading wins.

**Bad**: "Create skills for AI agents. Use when the user wants to write a skill..."
**Good**: "Skill. Use when the user wants to write, create, or build a new agent skill..."

### 3. One trigger per branch

Different user phrasings for the same intent are **one branch**, not multiple. "improve a skill", "fix a skill", "tune a skill" are one branch (intent: make an existing skill better). "improve a skill", "make a skill better", "fix up a skill" are duplication.

Distinct branches look like:

- Create vs improve (different intents)
- Description only vs structure too (different fixes)
- Won't trigger vs triggers too often (different problems)

### 4. Triggers must be real user phrasings

Don't invent internal jargon. A description trigger should be a phrase a real user would type. If you wouldn't say it, don't list it.

## Hard limits

- **Max 1024 chars** — the loader truncates beyond this. The whole description is silently cut.
- **Third person** — "Creates / Reviews / Builds / Extracts" not "You can / I help / We provide". The agent reads descriptions about skills, not about itself.
- **No time-sensitive info** — "current API as of 2024" ages. State capability, not version.

## Optional: model-invoked vs user-invoked

If the skill only ever fires by hand (the user types its name), make it user-invoked:

```yaml
---
name: skill-name
description: One-line human-facing summary.
disable-model-invocation: true
---
```

This drops the description from the agent's reach — zero context load — but shifts the cost to **cognitive load** (you must remember it exists). Use it for skills that don't need to trigger autonomously.

When user-invoked skills multiply past what you can remember, build one router skill that names the others.

## What to fix in an existing description

When reviewing, check in order:

1. Is it over 1024 chars? Cut body-duplicated identity first.
2. Does it have one trigger per branch? Collapse synonyms.
3. Is the leading word front-loaded? Move it to the first phrase.
4. Are the triggers real user phrasings? Replace internal jargon.
5. Is it in third person? Rewrite "you can" → "Creates".
