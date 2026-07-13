---
name: writing
description: Write a blog post in the author's voice — conversational, question-driven, citation-grounded. Use when writing a new blog post or editing an existing one.
---

# Writing

## Inputs

- **Topic**: what the post is about (a technology, concept, or walkthrough)
- **Post type**: one of `tutorial`, `conceptual-overview`, or `deep-dive` (series installment)
- **Series context** (optional): previous posts in the same series, so the opener can reference them

## What this skill does

Generates a blog post in the established voice. The rhetorical backbone is a **Question Chain** — exposition driven by escalating self-answered questions in blockquotes, each answer prompting a deeper question. Every factual claim carries a citation. The tone is conversational, self-aware, and humble — framing the author and reader as on the same learning journey.

## Process

### 1. Determine post type and structure

The template varies by intent:

- **Hands-on tutorial** (DVC workshop): Prerequisites → Background theory → Hands On (sub-sections per step) → Thank you
- **Conceptual overview** (Raft overview): Why → Question Chain → TL;DR
- **Deep-dive / series** (Raft Leader Election): Recap context → Question Chain → TL;DR → Next Up

*Completion: one post type chosen, template known.*

### 2. Open with a hook

- **Why** question for conceptual posts — state the personal motivation that led you to the topic.
- **Problem** statement for tutorials — what gap does this fill?
- Epigraph-style pull-quote (`> Based on...`) before the first H1 for series follow-ups.

The first prose after the H1 title is the hook. Keep it to 2–4 sentences.

*Completion: opening block written that answers "why this post exists".*

### 3. Build the Question Chain

Expose the topic through an escalating chain of questions:

1. Each question in a blockquote: `> **How does X work?**` (bold or bold+italic for emphasis; plain text also used — the constant is the blockquote, not the formatting).
2. Answer concisely in the paragraph below.
3. The answer's last sentence naturally prompts the next question — pivot to a deeper or related angle.
4. Repeat until you've covered the necessary ground.

When the chain naturally forks (implementation detail vs. conceptual angle), handle one fork and save the other for "we'll discuss it in the next post".

Each question must genuinely advance understanding. If a question can be collapsed into the previous answer, delete it.

*Completion: the chain covers every section the post needs without gaps or redundant links.*

### 4. Layer in support

After each answer in the chain, add the kind of support it needs:

- **Citations** — every factual claim gets a footnote: text `<cite>[^N]</cite>` with `[^N]: [Source Type](url) - description` at the bottom.
- **Math** — `{{< katex >}}` once at first use, `$$...$$` for display equations, `\\(...\\)` for inline; follow with a `where:` list explaining each variable.
- **Code** — always fenced with a language annotation; explain what it does *before* showing it.
- **Images** — `![alt](./file.png)` after the paragraph that first references the concept.
- **Warnings / Notes** — `{{< alert "bell" >}}` for notes, `{{< alert >}}` for caveats.
- **Collapsible extras** — `<details><summary>**Label**</summary>...</details>` for secondary or reference material (playlists, full paper embeds).

*Completion: every answer block has at least one support element; no bare assertions.*

### 5. Close the post

- **Tutorials**: `## Thank you!` — thank the reader, acknowledge limitations ("scratch the surface", "oversimplification"), link contact info (email hi@ditwrd.dev, LinkedIn).
- **Conceptual**: `## TL;DR` — bullet-point recap of everything covered.
- **Series**: also add `### Next Up` naming the next post.
- **All posts**: end on a warm note — "Have a good day!" or equivalent.

*Completion: closing section written matching the post type.*

## Voice

Every sentence is written in this voice:

- **Conversational, not casual.** Explain to a smart friend, not a classroom. Contractions ("it's", "don't") are fine; slang is not. Sentence fragments for rhythm: "Yes. Kinda. Not really."
- **Self-aware.** Acknowledge oversimplification explicitly: "this is an oversimplification", "I'll save you from reading too much math". Frame yourself as on the same journey as the reader. Self-deprecation (a "skill issue") is on-brand.
- **Dry humor.** One subtle joke per 500 words max. In-jokes (e.g. Rust "blazingly fast") land because the audience shares the context. Never force it.
- **Direct address.** Speak to the reader: "I hope this'll bring you closer to your goal", "We'll get back to it later", "this is left as an exercise for the reader".
- **Enthusiasm for the subject.** Genuinely curious and excited about the underlying ideas — Raft's elegance, the magic of backpropagation. That energy carries the reader through complexity.
- **Humble.** Frame as a learning journey, not a lecture. Acknowledge what you don't cover. Never oversell completeness.
- **Punchy descriptions.** Define new terms in one sentence with `To put it simply,` or a direct apposition. If it takes more than two sentences, the concept needs breaking down further.

## Templates

### Hugo frontmatter

```yaml
---
title: "Post Title"
date: YYYY-MM-DD
draft: false
description: "One-line hook that sells the post"
tags: ["Category", "Subtopic"]
# optional for series:
series: ["Series Name"]
series_order: N
---
```

`description` is the second hardest thing to write (after the title): it should make someone want to click. Tease the question, not the answer.

### Closing ritual (tutorials)

```
## Thank you!

Thank you for reading this article, the topic that has been taught here
[X what this was: just scratches the surface | is a complete overview] of
[Y the subject] with a touch of imperfection and oversimplification here
and there, I hope this'll bring you closer to your goal, whatever it is

For any inquiry feel free to contact me via email hi@ditwrd.dev or through
my [Linkedin](https://www.linkedin.com/in/adityawardianto/) DMs

Have a good day!
```

### Footnoting

```markdown
The claim is stated here.<cite>[^1]</cite>

[^1]: [Source Type](url) - Brief description
```

Use raw bracket-footnotes, not Hugo ref shortcodes. The footnote body always follows the pattern: `[Source Type](url) - description`.

## Anti-patterns

- ~~Formal/academic register~~ — no "thus", "henceforth", "it is worth noting"
- ~~Over-explaining~~ — trust the reader to fill simple gaps
- ~~Boilerplate transitions~~ — no "In this article, we will explore..."
- ~~Clickbait~~ — no "You won't believe what happens next!"
- **Fabricated post types** — every template in this skill is extracted from an existing post. If a pattern isn't in the corpus, don't extrapolate it; call it speculative or omit it.
- **Blockquote formatting rigidity** — the posts use bold, bold+italic, and plain blockquote questions. Don't prescribe one; describe the range.
