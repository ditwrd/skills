# Headline patterns

Reference for writing blog post titles. The core principle: a headline should make the reader ask "why?" or "how?" — the same curiosity gap the post itself uses.

## Question headlines (primary pattern)

The strongest pattern for this blog's voice. A question headline promises an answer, and the Question Chain delivers it.

| Pattern | Formula | Example |
|---------|---------|---------|
| Direct how-question | `How does X work?` | How does Crossplane work? |
| Direct what-question | `What happens when X?` | What happens when your consensus protocol has a leader failure? |
| Direct why-question | `Why does X matter?` | Why does Raft use randomized election timeouts? |
| Implied knowledge gap | `What I learned about X` | What I learned about Raft leader election |
| Stacked question | `X? And Y?` | Raft? Leader election? What actually happens? |

Rules:
- Lead with the core concept, not a preamble (`How does X work?` not `A comprehensive guide to...`)
- Default to concrete nouns over abstract ones (`Crossplane` vs `cloud infrastructure`)
- No colon-hack titles (`How X Works: A Deep Dive` — just ask the question)

## Curiosity gap headlines

Tease the gap between what the reader knows and what they're about to learn.

| Pattern | Example |
|---------|---------|
| `The X you (probably) don't know` | The database trick you probably don't know |
| `What X actually does` | What `Docker run` actually does |
| `The X that changed how I Y` | The Raft paper that changed how I think about distributed systems |
| `Why X (and not Y)` | Why Raft (and not Paxos)? |
| `Everything I know about X` | Everything I know about Crossplane compositions |

Use sparingly — one per several posts. Question headlines are the default; curiosity gap is the spice.

## How-to headlines

For tutorial posts. Still question-shaped when possible.

| Pattern | Example |
|---------|---------|
| `How to X with Y` | How to set up Crossplane with AWS |
| `How to X` | How to build a custom Crossplane function |
| `X from scratch` | A Kubernetes operator from scratch |

Tutorial titles name both the goal AND the tool/platform. "How to set up Crossplane with AWS" is better than "How to set up Crossplane" — specificity helps the right reader find it.

## What to avoid

- **Clickbait**: "You won't believe what happens when..." — erodes trust
- **Colon-hack**: "How X Works: A Deep Dive" — empty calories
- **Meta**: "A Guide to X" / "An Introduction to X" — the post is the introduction
- **Stacked modifiers**: "Building Scalable, Cloud-Native, Enterprise-Grade Infrastructure" — each modifier bleeds specificity
- **Promotional**: "Why X Is the Best" — let the reader decide

## Brainstorming ritual (Veritasium-style)

When stuck on a title:

1. **Write three versions** — one question, one curiosity gap, one how-to
2. **Read each aloud** — which makes you want to click?
3. **Test against the hook** — does the headline match the opening block? If the headline promises a question and the hook starts with a problem statement, rewrite one or the other
4. **Cut to the core** — remove every word you can while keeping the question intact
5. **Ask: would someone who doesn't know me click this?** — if it requires context only regular readers would have, add a concrete noun

The best headlines come from the **question chain itself** — look at the first question in your chain. That's often your headline.
