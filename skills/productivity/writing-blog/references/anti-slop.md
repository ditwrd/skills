# Anti-slop reference for blog writing

Detection and removal strategies for AI-generated patterns in blog posts. Use during Step 6 (Review) — when the editing checklist flags something, this reference tells you how to fix it.

---

## Detection workflow

When reviewing a draft, run these scans in order:

1. **Word scan** — grep for Tier-1 replacement words (see the word replacements table in SKILL.md)
2. **Format scan** — check em dash count, bold density, bullet overuse, rule of three
3. **Structure scan** — check paragraph length variance, opening formulation, closing substance
4. **Rhetoric scan** — check for parallelism tics, unearned profundity, awkward analogies
5. **Substance scan** — check each paragraph for what it actually adds; if removing it changes nothing, cut it

---

## Rhetorical slop (not covered by word lists)

These patterns make text sound AI-generated even when every individual word is fine. They're harder to catch with grep — they require reading the draft as a human would.

### Parallelism tics

AI overuses specific rhetorical structures:

| Pattern | Example | Fix |
|---------|---------|-----|
| "It's not X — it's Y" | "It's not about speed — it's about trust." | State the claim directly. "Trust matters more than speed." |
| Snappy triads | "Fast, reliable, and secure." | Vary groupings. Use two items or rephrase as a sentence. |
| Unearned profundity | "Something shifted." / "Everything changed." | Cut unless the shift is specific and earned. |
| Mid-sentence questions | "The solution? It's simpler than you think." | Just state the solution. |
| Vapid transitions | "But here's the thing." / "Here's what's interesting." | Let the content carry itself. Cut. |

**Rule**: If the rhetorical device draws attention to itself, cut it. Human writers use these devices sparingly and with specific intent.

### Awkward or generic analogies

AI analogies are plausible but not specific. They gesture toward meaning without quite achieving it.

- **AI**: "Learning the ukulele is like teaching your fingers to dance again after years of sitting still."
- **AI**: "Every chord is a puzzle piece that finally clicks into a song."
- **Human**: specific, personal, or culturally grounded. Draws from actual experience.

**Fix**: Replace with a concrete personal observation. If you can't think of a specific analogy from your own experience, cut it — the explanation works without it.

### Surface polish, no substance

The biggest red flag: text that reads well sentence-by-sentence but leaves the reader thinking "what did I just read?" after a paragraph.

**Fix**: After each paragraph, ask: "What did this paragraph actually say?" If the answer is vague or the paragraph restates something already said, cut it. AI generates text that sounds correct but carries no information — the cure is specific, grounded claims.

---

## Rewrite patterns

When you find slop, use these patterns to rewrite it:

### Wordy → Concise

| Slop | Clean |
|------|-------|
| It's important to note that X is essential for... | X matters because... |
| In order to leverage the full potential of... | To use... |
| This serves as a testament to the fact that... | This shows... |
| The integration of X and Y creates synergy in... | X and Y work together to... |

### Hedge-heavy → Direct

| Slop | Clean |
|------|-------|
| This could potentially lead to improved performance. | This improves performance. |
| It appears that the system may have some limitations. | The system has these limitations: ... |
| One could argue that this approach is somewhat more effective. | This approach is more effective because... |
| Generally speaking, the results seem to suggest... | The results show... |

### Meta-commentary → Straight to content

| Slop | Clean |
|------|-------|
| In this post, I'll explore the key differences between... | Here's what's different between... |
| Let's take a closer look at how... | X works by... |
| Now that we've covered the basics, let's dive into... | (Cut entirely — just start the new section.) |
| Before we proceed, it's crucial to understand... | (State the crucial thing directly.) |

### Generic praise → Specific observation

| Slop | Clean |
|------|-------|
| X is a game-changer in the world of cloud computing. | X cuts deployment time from hours to minutes by... |
| This innovative approach revolutionizes how we think about... | This approach solves the specific problem of... |
| A robust, comprehensive solution for modern teams. | It handles three things: ... |

---

## The Stanislavski test

If you're unsure whether a sentence is slop, apply the Stanislavski test — a method acting exercise adapted for writing: **read the sentence aloud and ask "what is my character doing?"**

- Am I explaining? → fine
- Am I showing enthusiasm? → fine
- Am I filling space with sound? → slop. Cut it.
- Am I gesturing at meaning without delivering content? → slop. Rewrite with specifics.
- Am I performing "being a writer" instead of communicating? → slop. The performance is detectable.

---

## External resources

- **[The Field Guide to AI Slop](https://www.ignorance.ai/p/the-field-guide-to-ai-slop)** (Charlie Guo, 2025) — Practical guide to stylistic tics: em dashes, parallelism, random formatting, monotony, awkward analogies, filler. Covers both detection and the authenticity crisis AI creates for human writers.
- **[Measuring AI "Slop" in Text](https://arxiv.org/abs/2509.19163)** (Shaib et al., 2025) — Academic taxonomy of slop dimensions: coherence, relevance, information density. Useful for understanding WHY slop reads as slop.
- **[detect_slop.py](scripts/detect_slop.py)** (local) — Zero-dependency Python script that scans markdown files for Tier-1/2 words, redundant qualifiers, hedging, meta-commentary, formatting issues (em dashes, bold density, paragraph monotony), generic code names, and template phrases. Run: `python scripts/detect_slop.py draft.md [--json] [--verbose]`.
- **[Anti-slop skill (cc-polymath)](https://github.com/rand/cc-polymath/blob/main/skills/anti-slop/)** — Contains `detect_slop.py` (scoring 0–100) and `clean_slop.py` (automated removal with backup).
- **[Avoid AI Writing](https://github.com/conorbronsdon/avoid-ai-writing)** — Claude Code skill with Tier 1–3 word tables (the source of the extended catalog in `references/ai-ism-catalog.md`). Has a comprehensive `patterns.js` that can be adapted for automated scanning.
- **[lmscan](https://github.com/brandon-frylinck/lmscan)** — Zero-dependency Python alternative to GPTZero. Lightweight ML-free approach, right complexity level for blog post checking.
- **[is-it-slop](https://github.com/beardypig/is-it-slop)** — Python slop detector with regex and ML-based approaches.
