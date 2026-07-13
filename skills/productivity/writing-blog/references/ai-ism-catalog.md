# AI-ism catalog

Full reference catalog of AI writing patterns to detect and remove. The core replacements belong in the main SKILL.md — this file holds the extended tables, severity tiers, voice profiles, and context-sensitive rules for deeper audits.

---

## Word replacement tables

Words organized into three tiers based on how reliably they signal AI-generated text. Adapted from [conorbronsdon/avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing) (MIT).

- **Tier 1** — Always flag. Replace on sight.
- **Tier 2** — Flag in clusters. Two or more in the same paragraph is a strong AI signal.
- **Tier 3** — Flag by density. Only flag when they make up ~3%+ of total words.

Tier 1 replacements are duplicated in the main SKILL.md since they're the most critical to apply during generation; the full table lives here.

### Tier 1 — Always replace

| Replace | With |
|---|---|
| delve / delve into | explore, dig into, look at |
| landscape (metaphor) | field, space, industry, world |
| tapestry | (describe the actual complexity) |
| realm | area, field, domain |
| paradigm | model, approach, framework |
| embark | start, begin |
| beacon | (rewrite entirely) |
| testament to | shows, proves, demonstrates |
| robust | strong, reliable, solid |
| comprehensive | thorough, complete, full |
| cutting-edge | latest, newest, advanced |
| leverage (verb) | use |
| pivotal | important, key, critical |
| underscores | highlights, shows |
| meticulous / meticulously | careful, detailed, precise |
| seamless / seamlessly | smooth, easy, without friction |
| game-changer / game-changing | describe what specifically changed and why it matters |
| hit differently / hits different | (say what specifically changed, or cut) |
| utilize | use |
| watershed moment | turning point, shift (or describe what changed) |
| marking a pivotal moment | (state what happened) |
| the future looks bright | (cut — say something specific or nothing) |
| only time will tell | (cut — say something specific or nothing) |
| nestled | is located, sits, is in |
| vibrant | (describe what makes it active, or cut) |
| thriving | growing, active (or cite a number) |
| despite challenges… continues to thrive | (name the challenge and the response, or cut) |
| showcasing | showing, demonstrating (or cut the clause) |
| deep dive / dive into | look at, examine, explore |
| unpack / unpacking | explain, break down, walk through |
| bustling | busy, active (or cite what makes it busy) |
| intricate / intricacies | complex, detailed (or name the specific complexity) |
| complexities | (name the actual complexities, or use "problems" / "details") |
| ever-evolving | changing, growing (or describe how) |
| enduring | lasting, long-running (or cite how long) |
| daunting | hard, difficult, challenging |
| holistic / holistically | complete, full, whole (or describe what's included) |
| actionable | practical, useful, concrete |
| impactful | effective, significant (or describe the impact) |
| learnings | lessons, findings, takeaways |
| thought leader / thought leadership | expert, authority (or describe their actual contribution) |
| best practices | what works, proven methods, standard approach |
| at its core | (cut — just state the thing) |
| synergy / synergies | (describe the actual combined effect) |
| interplay | relationship, connection, interaction |
| in order to | to |
| due to the fact that | because |
| serves as | is |
| features (verb) | has, includes |
| boasts | has |
| presents (inflated) | is, shows, gives |
| commence | start, begin |
| ascertain | find out, determine, learn |
| endeavor | effort, attempt, try |
| keen (as intensifier) | interested, eager, enthusiastic (or cut — just state the interest) |
| genuinely / genuine (as intensifier) | (cut — just state the fact) |
| symphony (metaphor) | (describe the actual coordination or combination) |
| embrace (metaphor) | adopt, accept, use, switch to |

### Tier 2 — Flag when 2+ appear in the same paragraph

| Replace | With |
|---|---|
| harness | use, take advantage of |
| navigate / navigating | work through, handle, deal with |
| foster | encourage, support, build |
| elevate | improve, raise, strengthen |
| unleash | release, enable, unlock |
| streamline | simplify, speed up |
| empower | enable, let, allow |
| bolster | support, strengthen, back up |
| spearhead | lead, drive, run |
| resonate / resonates with | connect with, appeal to, matter to |
| revolutionize | change, transform, reshape (or describe what changed) |
| facilitate / facilitates | enable, help, allow, run |
| underpin | support, form the basis of |
| nuanced | specific, subtle, detailed (or name the actual nuance) |
| crucial | important, key, necessary |
| multifaceted | (describe the actual facets, or cut) |
| ecosystem (metaphor) | system, community, network, market |
| myriad | many, numerous (or give a number) |
| plethora | many, a lot of (or give a number) |
| encompass | include, cover, span |
| catalyze | start, trigger, accelerate |
| reimagine | rethink, redesign, rebuild |
| galvanize | motivate, rally, push |
| augment | add to, expand, supplement |
| cultivate | build, develop, grow |
| illuminate | clarify, explain, show |
| elucidate | explain, clarify, spell out |
| juxtapose | compare, contrast, set side by side |
| paradigm-shifting | (describe what actually shifted) |
| transformative / transformation | (describe what changed and how) |
| cornerstone | foundation, basis, key part |
| paramount | most important, top priority |
| poised (to) | ready, set, about to |
| burgeoning | growing, emerging (or cite a number) |
| nascent | new, early-stage, emerging |
| quintessential | typical, classic, defining |
| overarching | main, central, broad |
| quietly | cut, or name the concrete contrast |
| deeply *(significance collocations only)* | cut, or name what specifically runs deep |
| underpinning / underpinnings | basis, foundation, what supports |

### Tier 3 — Flag only at high density

| Word | What to do |
|---|---|
| significant / significantly | Replace some with specifics: numbers, comparisons, examples |
| innovative / innovation | Describe what's actually new |
| effective / effectively | Say how or cite a metric |
| dynamic / dynamics | Name the actual forces or changes |
| scalable / scalability | Describe what scales and to what |
| compelling | Say why it compels |
| unprecedented | Name the precedent it breaks (or cut) |
| exceptional / exceptionally | Cite what makes it an exception |
| remarkable / remarkably | Say what's worth remarking on |
| sophisticated | Describe the sophistication |
| instrumental | Say what role it played |
| world-class / state-of-the-art / best-in-class | Cite a benchmark or comparison |

### Tier 3 phrases — Flag at density or in clusters

Flag at 2+ uses of the same phrase, plus a cluster rule: three or more distinct phrases from this table in one piece is a strong signal.

| Phrase | What to do |
|---|---|
| emerging sector / emerging space / emerging category | Name the actual sector or what's emerging |
| the integration of (X with Y) | Describe what's being integrated and what changes for the user |
| the intersection of (X and Y) | Pick the specific overlap that matters or cut |
| community-driven | Name what the community does |
| long-term sustainability | Cite the time horizon and the constraint |
| user engagement | Name the action |
| decentralized compute | Specify the architecture or cut |
| (sustainable) reward emissions | Cite the emission schedule and the sink |
| tokenized incentive structures | Describe the actual mechanism |
| designed for long-term [X] | Cut "designed for" — either it is or it isn't |

---

## Formatting rules

### Em dashes (— and --)

Replace with commas, periods, parentheses, or rewrite as two sentences. **Target: zero. Hard max: one per 1,000 words.** Applies to headings and section titles too, not just body prose. Catch both Unicode em dash (—) and double-hyphen (--).

### Bold overuse

Strip bold from most phrases. One bolded phrase per major section at most. If something's important enough to bold, restructure the sentence to lead with it instead.

### Emoji in headers

Remove entirely. No `## 🚀 What This Means`. Exception: social posts may use one or two emoji sparingly — at the end of a line, never mid-sentence.

### Excessive bullet lists

Convert bullet-heavy sections into prose paragraphs. Bullets only for genuinely list-like content (feature comparisons, step-by-step instructions, API parameters).

### Curly quotation marks

Curly quotes (“ ” ‘ ’) are a *weak* paste-from-chat signal — meaningful mainly in plain-text contexts (code comments, commit messages, plaintext drafts). Word, Google Docs, macOS, and iOS curl quotes by default, so most human prose contains them. Don't flag curly apostrophes (U+2019) on their own. Replace with straight quotes in plain-text/code; leave in finished publications.

### Title case headings

Use sentence case for subheadings. Title case only for the piece's main title, if at all.

### Hyphenated-pair overuse

AI stacks compound modifiers: "a high-quality, well-architected, future-proof solution." Two problems: density (cut to the modifier that matters), and attributive/predicate error (hyphenated before noun, not after linking verb: "the report is high quality" — no hyphen).

---

## Sentence structure patterns

### "It's not X — it's Y" / "This isn't about X, it's about Y"

Rewrite as a direct positive statement. Max one per piece. Includes the split-sentence form where negation and correction fall in separate sentences: "The headline isn't the speed. The real story is Y." Also catches multi-negation countdowns ("It's not the price. It's not the features. It's the trust.").

### Hollow intensifiers

Cut `genuine` / `genuinely`, `real` (as in "a real improvement"), `truly`, `quite frankly`, `to be honest`, `let's be clear`, `it's worth noting that`. Just state the fact.

### Vague endorsement

Cut or replace `worth reading`, `worth paying attention to`, `worth a look`, `worth exploring`, `worth your time`. Say *why* something matters instead.

### Hedging

Cut `perhaps`, `could potentially`, `it's important to note that`, `to be clear`. Make the point directly.

### Missing bridge sentences

Each paragraph should connect to the last. If paragraphs could be rearranged without the reader noticing, add connective tissue.

### Compulsive rule of three

Vary groupings. Use two items, four items, or a full sentence instead of triads. Max one "adjective, adjective, and adjective" pattern per piece.

### Copula avoidance

AI text avoids "is" and "has" by substituting fancier verbs: "serves as," "features," "boasts," "presents," "represents." Default to "is" or "has" unless a more specific verb genuinely adds meaning.

### Synonym cycling

AI rotates synonyms to avoid repeating a word: "developers… engineers… practitioners… builders." Human writers repeat the clearest word. If the same word is right three times, use it three times.

### Vague attributions

"Experts believe," "Studies show," "Research suggests" — without naming the expert, study, or leader. Either cite a specific source or drop the attribution.

---

## Template phrases to avoid

These slot-fill constructions signal that a sentence was generated, not written.

- "a [adjective] step towards [adjective] AI infrastructure" → describe the specific capability
- "a [adjective] step forward for [noun]" → say what actually changed
- "Whether you're [X] or [Y]" → false-breadth construction. Pick the audience or cut.
- "I recently had the pleasure of [verb]-ing" → just say what happened

## Transition phrases to remove or rewrite

- "Moreover" / "Furthermore" / "Additionally" → restructure, or use "and," "also"
- "In today's [X]" / "In an era where" → cut or state specific context
- "It's worth noting that" / "Notably" → just state the fact
- "Here's what's interesting" / "Here's what caught my eye" → let the content signal its own importance
- "In conclusion" / "In summary" → your conclusion should be obvious
- "When it comes to" → talk about the thing directly
- "At the end of the day" → cut
- "That said" / "That being said" → use "but," "yet," or "however"

---

## Structural issues

- **Uniform paragraph length**: Vary deliberately. Include some 1-2 sentence paragraphs and some longer ones.
- **Formulaic openings**: If the piece opens with broad context ("In the rapidly evolving world of…"), rewrite to lead with the insight.
- **Suspiciously clean grammar**: Don't sand away all personality. Deliberate fragments, sentences starting with "And" or "But," comma splices for effect — if the voice uses them, keep them.
- **Generic conclusions**: "The future looks bright," "Only time will tell," "One thing is certain" — cut. If the piece needs a closing thought, make it specific.
- **Chatbot artifacts**: "I hope this helps!", "Certainly!", "Great question!" — remove entirely. Also: "In this article, we will explore…" or "Let's dive in!" — cut.
- **"Let's" constructions**: "Let's explore," "Let's take a look" — AI uses "let's" as a false-collaborative opener. Just start with the point.
- **Speculative scenario openers**: "Imagine a world where…", "Picture a future in which…" — cut the hypothetical and state the real claim.
- **False ranges**: "from the Big Bang to dark matter" — list the actual topics or pick the one that matters.
- **Notability name-dropping**: "cited in The New York Times, BBC, Financial Times, and The Hindu" — one specific reference with context beats four name-drops.
- **Promotional language**: "nestled within the breathtaking foothills," "a vibrant hub of innovation" — replace with plain description.
- **Significance inflation**: "marking a pivotal moment in the evolution of…" — state what happened and let the reader judge.
- **Future-narrative closers**: "may become one of the most important narratives" — pattern: modal + "become" + "one of the most" + adjective + narrative noun. Pick the falsifiable version or cut.
- **Hedge-stacked predictions**: "could potentially create," "may eventually unlock" — pick one hedge, not both.
- **Emotional flatline**: "What surprised me most," "I was fascinated to discover" — if the thing is genuinely surprising, the reader should feel it from the content, not from you announcing it.
- **Numbered list inflation**: "Three key takeaways" / "Five things to know" — only use when the content genuinely has that many discrete items.

---

## Significance inflation

Phrases like "marking a pivotal moment in the evolution of…" or "a watershed moment for the industry" inflate routine events into history-making ones. State what happened and let the reader judge significance. If the sentence still works after you delete the inflation clause, delete it.

---

## Severity tiers

When triaging a large document, prioritize:

- **P0 — Credibility killers (fix immediately)**: Cutoff disclaimers ("As of my last update"), chatbot artifacts, vague attributions without sources, significance inflation on routine events.
- **P1 — Obvious AI smell (fix before publishing)**: Word-list violations (Tier 1), template phrases, "let's" openers, synonym cycling, formulaic openings, bold overuse, em dash frequency, generic future-narrative closers, hedge-stacked predictions.
- **P2 — Stylistic polish (fix when time allows)**: Generic conclusions, compulsive rule of three, uniform paragraph length, copula avoidance, transition padding.

Use P0+P1 for quick passes. Full audit covers all tiers.

---

## Tone calibration principles

1. **Vary sentence length** — mix short with long. Fragments are fine.
2. **Be concrete** — replace vague claims with numbers, names, dates, or examples.
3. **Have a voice** — use first person, state preferences, show reactions where appropriate.
4. **Cut the neutrality** — humans have opinions. If the piece is supposed to take a position, take it.
5. **Earn your emphasis** — don't tell the reader something is interesting. Make it interesting.
