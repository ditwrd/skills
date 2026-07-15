# Editing checklist

Pre-publication review. Run this against the draft after the closing section is written.

---

## 1. Hook check

- [ ] The first 2-4 sentences after the H1 grab attention — does it pass the "so what?" test?
- [ ] Matches the post type's hook pattern (why question / problem statement / epigraph / misconception)
- [ ] If a question-driven post: is the hook a question or does it immediately provoke one?

## 2. Question Chain check

- [ ] Every question is in a blockquote
- [ ] No two consecutive questions without an answer between them
- [ ] No question gives away its answer (no named resources in the question)
- [ ] Each answer bridges to the next question (read the last sentence of each answer and confirm it prompts the next question)
- [ ] The emotional arc tracks: skepticism → curiosity → how-to → challenged assumption → scaling → rewired understanding
- [ ] No question can be collapsed into the previous answer (deletion test: if removing a question doesn't break the chain, it's redundant)
- [ ] Forks handled: one fork explained, the other deferred with "we'll discuss in the next post"

## 3. Support check

- [ ] Every factual claim has a citation (`<cite>[^N]</cite>`)
- [ ] Every footnote body follows the pattern: `[Source Type](url) - description`
- [ ] Every code block has a language annotation
- [ ] Code blocks are explained *before* they appear
- [ ] Every image has alt text
- [ ] Every Mermaid diagram has a matching type (flowchart / sequence / state / class / ER) from `references/mermaid-diagrams.md`
- [ ] Math blocks followed by a `where:` list
- [ ] No bare assertions — every answer block has at least one support element

## 4. Voice check

- [ ] Reads like explaining to a smart friend (not lecturing a classroom)
- [ ] At least one self-aware nod ("this is an oversimplification", "I'm skipping...")
- [ ] No more than one joke/500 words
- [ ] The reader is addressed directly at least once ("you", "we")
- [ ] At least one sentence fragment for rhythm
- [ ] No formal register — scan for "thus", "henceforth", "it is worth noting"

## 5. AI pattern scan (text)

- [ ] No Tier-1 replacement words (delve, leverage, utilize, robust, seamless, cutting-edge, game-changer, pivotal, paradigm, embark, comprehensive, underscores, serves as, showcases, unpack, dive into)
- [ ] No clusters of Tier-2 words (harness, navigate, foster, elevate, streamline, empower, facilitate, nuanced, crucial, ecosystem) — if 2+ in one paragraph, rewrite
- [ ] No redundant qualifiers (completely finish, absolutely essential, totally unique, past history, end result, future plans)
- [ ] No empty boosters (very, really, extremely, incredibly, actually, quite literally)
- [ ] No hedging clusters ("might possibly perhaps", "could potentially")
- [ ] Em dashes: ≤1 per 1,000 words
- [ ] Bold: ≤1 per major section
- [ ] Rule of three: ≤1 triad per piece
- [ ] No formulaic opener ("In the rapidly evolving world of...", "In today's...")
- [ ] No generic conclusion ("The future looks bright", "Only time will tell")
- [ ] No synonym cycling (don't swap words to avoid repetition)
- [ ] No "Moreover", "Furthermore", "Additionally" used as paragraph starters

If you have access to the anti-slop detection scripts, also run: `python scripts/detect_slop.py <draft> --verbose`

## 6. Structure check

- [ ] Paragraphs vary in length (include some 1-2 sentence paragraphs)
- [ ] Walls of text (>3 consecutive paragraphs of pure description) broken up with a Mermaid diagram or image
- [ ] For Veritasium-style posts: A‑Plot and B‑Plot alternate at least twice, no more than two consecutive B‑Plot segments without a return to narrative

## 7. Closing check

- [ ] Tutorials end with `## Thank you!` + limitations + contact info
- [ ] Conceptual posts end with `## TL;DR` bullet recap
- [ ] Series posts also have `### Next Up`
- [ ] All posts end on a warm note

## 8. Metadata check

- [ ] Title passes the "would I click this?" test (see `references/headlines.md`)
- [ ] Description: one-line hook that teases the question without giving away the answer
- [ ] Tags match the category/subtopic pattern
- [ ] Series name matches previous posts in the series
- [ ] date is today (not a placeholder)
- [ ] draft is false (or deliberately true)

---

A full pass takes 15-20 minutes on a 2,000-word post. The AI pattern scan is the most mechanical — batch that first, then focus on the chain and voice checks.
