#!/usr/bin/env python3
"""Detect common AI slop patterns in blog post drafts.

Zero dependencies — stdlib only. Scans markdown files for word-level,
formatting, and structural patterns that signal AI-generated text.

Usage:
    python scripts/detect_slop.py draft.md
    python scripts/detect_slop.py draft.md --json    # machine-readable output
    python scripts/detect_slop.py draft.md --verbose  # include context lines
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

TIER1_WORDS = {
    "delve": "Use 'explore', 'dig into', or 'look at'",
    "dive deep": "Use 'examine' or 'look at'",
    "unpack": "Use 'explain', 'break down', or 'walk through'",
    "leverage": "Use 'use'",
    "utilize": "Use 'use'",
    "robust": "Use 'strong', 'reliable', or 'solid'",
    "seamless": "Use 'smooth' or 'easy'",
    "cutting-edge": "Use 'latest', 'newest', or 'advanced'",
    "game-changer": "Describe what specifically changed and why",
    "pivotal": "Use 'important', 'key', or 'critical'",
    "testament": "Use 'shows' or 'proves'",
    "paradigm": "Use 'model', 'approach', or 'framework'",
    "embark": "Use 'start' or 'begin'",
    "comprehensive": "Use 'thorough', 'complete', or 'full'",
    "underscores": "Use 'highlights' or 'shows'",
    "showcases": "Use 'shows' or 'demonstrates' (or cut)",
    "showcasing": "Use 'showing' or 'demonstrating' (or cut)",
    "in order to": "Use 'to'",
    "serves as": "Use 'is'",
}

TIER2_WORDS = {
    "harness": "Use 'use' or 'take advantage of'",
    "navigate": "Use 'work through', 'handle', or 'deal with'",
    "foster": "Use 'encourage', 'support', or 'build'",
    "elevate": "Use 'improve', 'raise', or 'strengthen'",
    "streamline": "Use 'simplify' or 'speed up'",
    "empower": "Use 'enable', 'let', or 'allow'",
    "facilitate": "Use 'enable', 'help', or 'allow'",
    "nuanced": "Use 'specific', 'subtle', or 'detailed'",
    "crucial": "Use 'important', 'key', or 'necessary'",
    "ecosystem": "Use 'system', 'community', or 'network'",
    "synergy": "Describe the actual combined effect",
    "synergies": "Describe the actual combined effect",
    "holistic": "Use 'complete', 'full', or 'whole'",
    "actionable": "Use 'practical', 'useful', or 'concrete'",
    "impactful": "Use 'effective' or 'significant' (or describe impact)",
}

REDUNDANT_QUALIFIERS = [
    (r"\bcompletely\s+finish\b", "Redundant: 'finish' implies completion"),
    (r"\babsolutely\s+essential\b", "Redundant: 'essential' is absolute"),
    (r"\btotally\s+unique\b", "Redundant: 'unique' is absolute"),
    (r"\bvery\s+unique\b", "Redundant: 'unique' is absolute"),
    (r"\bpast\s+history\b", "Redundant: 'history' is about the past"),
    (r"\bend\s+result\b", "Redundant: 'result' is the end"),
    (r"\bfinal\s+outcome\b", "Redundant: 'outcome' is final"),
    (r"\bfuture\s+plans\b", "Redundant: 'plans' are about the future"),
    (r"\breally\s+important\b", "Redundant qualifier — state why it matters"),
    (r"\bquite\s+significant\b", "Redundant qualifier — be specific"),
]

HEDGE_PATTERNS = [
    (r"\b(?:may|might)\s+(?:or\s+)?(?:may\s+)?not\b", "Double hedge — state uncertainty concretely or cut"),
    (r"\bcould\s+potentially\b", "Double hedge — 'could' and 'potentially' say the same thing"),
    (r"\bmight\s+possibly\b", "Double hedge — use one or neither"),
    (r"\bits?\s+appears?\s+that\b", "Hedge — state the claim directly"),
    (r"\bits?\s+seems?\s+that\b", "Hedge — state the claim directly"),
    (r"\bone\s+could\s+argue\b", "Hedge — name who argues or cut"),
    (r"\bsome\s+might\s+say\b", "Hedge — name who says or cut"),
    (r"\bto\s+a\s+certain\s+extent\b", "Hedge — be specific about the extent"),
    (r"\bgenerally\s+speaking\b", "Filler — cut or be specific"),
    (r"\bin\s+some\s+cases\b", "Filler — name the cases or cut"),
]

META_COMMENTARY = [
    (r"\bin\s+this\s+(?:article|post|guide|tutorial)\b", "Meta-commentary — just start the content"),
    (r"\bas\s+(?:we|I)\s+(?:explore|discuss|delve)\b", "Meta-commentary — just explore/discuss"),
    (r"\blet'?s\s+(?:take\s+a\s+)?(?:closer\s+)?look\b", "Meta-commentary — just look"),
    (r"\bnow\s+that\s+we'?ve\s+covered\b", "Meta-commentary — transition is visible without it"),
    (r"\bbefore\s+we\s+(?:proceed|continue)\b", "Meta-commentary — just proceed"),
    (r"\bits?[']?s?\s+(?:crucial|important|worth\s+noting)\s+(?:to\s+)?(?:note|understand|remember)\s+that\b",
     "Meta-commentary — state the thing directly"),
]

FORMULAIC_OPENERS = [
    (r"\bin\s+(?:today'?s?|the\s+(?:ever-)?evolving)\s+(?:world|landscape|digital\s+age)\b",
     "Formulaic opener — start with the insight, not the context"),
    (r"\bin\s+an\s+era\s+where\b",
     "Formulaic opener — state the specific condition"),
]

EMPTY_INTENSIFIERS = [
    (r"\bquite\s+literally\b", "Empty intensifier — just state the fact"),
    (r"\bactually\b", "Intensifier check — only use when contrasting a prior claim"),
]

TRANSITION_PADDING = [
    (r"^Moreover,?\s+", "Transition padding — use 'and' or restructure"),
    (r"^Furthermore,?\s+", "Transition padding — use 'and' or restructure"),
    (r"^Additionally,?\s+", "Transition padding — use 'and' or restructure"),
    (r"^That\s+said,?\s+", "Transition padding — use 'but' or 'however'"),
    (r"^In\s+conclusion,?\s+", "Transition padding — conclusion should be obvious"),
]

GENERIC_VARIABLE_NAMES = [
    (r"\b(?:const|let|var)\s+\b(data|result|temp|tmp|item|items)\b",
     "Generic variable name — use domain-meaningful name"),
    (r"\b(def|function)\s+\b(process|handle|manage)(?:Data|Items|Things)?\s*\(",
     "Generic function name — name what's being processed"),
]

TEMPLATE_PHRASES = [
    (r"(?:I\s+)?recently\s+had\s+the\s+pleasure\s+of", "Template phrase — just say what happened"),
    (r"Whether\s+you'?re\s+\w+\s+or\s+\w+", "False-breadth construction — pick the audience or cut"),
    (r"Imagine\s+a\s+(?:world|future|scenario)", "Speculative opener — state the real claim"),
    (r"Picture\s+a\s+future\s+where", "Speculative opener — state the real claim"),
    (r"At\s+the\s+end\s+of\s+the\s+day", "Filler — say something specific or nothing"),
]


# ---------------------------------------------------------------------------
# Scanning helpers
# ---------------------------------------------------------------------------

def scan_words(text, patterns, category, label_fn):
    """Scan for word-level patterns, return list of findings."""
    findings = []
    lower = text.lower()
    for word, suggestion in patterns.items():
        # Word boundary for multi-word vs single
        if " " in word:
            rx = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        else:
            rx = re.compile(rf"\b{re.escape(word)}\w*\b", re.IGNORECASE)
        for m in rx.finditer(lower):
            line_num = text[:m.start()].count("\n") + 1
            findings.append({
                "line": line_num,
                "match": text[m.start():m.end()].strip(),
                "pattern": word,
                "category": category,
                "suggestion": label_fn(word),
            })
    return findings


def scan_regex_list(text, patterns, category):
    """Scan for regex patterns (strings compiled on the fly)."""
    findings = []
    for raw_rx, msg in patterns:
        rx = re.compile(raw_rx, re.IGNORECASE | re.MULTILINE)
        for m in rx.finditer(text):
            line_num = text[:m.start()].count("\n") + 1
            findings.append({
                "line": line_num,
                "match": text[m.start():m.end()].strip(),
                "pattern": rx.pattern[:40],
                "category": category,
                "suggestion": msg,
            })
    return findings


def count_em_dashes(text):
    """Count em dashes (—) in non-code blocks."""
    lines = text.split("\n")
    in_code = False
    count = 0
    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            count += line.count("—")
    return count


def check_bold_density(text):
    """Flag excessive bold usage."""
    lines = text.split("\n")
    in_code = False
    bold_count = 0
    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            # Count **...** patterns
            bold_count += len(re.findall(r"\*\*.+?\*\*", line))
    # Heuristic: more than 5 bold phrases per 1000 words
    word_count = len(text.split())
    threshold = max(3, word_count // 200)
    return bold_count > threshold, bold_count


def check_paragraph_monotony(text):
    """Flag uniform paragraph length — possible AI monotony."""
    paragraphs = [p for p in text.split("\n\n") if len(p.strip()) > 50]
    if len(paragraphs) < 4:
        return False, 0, 0
    lengths = [len(p.split()) for p in paragraphs]
    avg = sum(lengths) / len(lengths)
    variance = sum((l - avg) ** 2 for l in lengths) / len(lengths)
    # Low variance = suspiciously uniform
    return variance < avg * 0.3, variance, avg


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(findings, em_dash_count, bold_excessive, bold_count,
                 var_monotony, var_score, var_avg, word_count, verbose):
    """Print human-readable report."""
    findings.sort(key=lambda f: f["line"])

    total = len(findings)

    print(f"\n{'='*60}")
    print(f"  Slop Detection Report")
    print(f"  Words scanned: {word_count}")
    print(f"{'='*60}\n")

    if total == 0 and not em_dash_count > 1 and not bold_excessive and not var_monotony:
        print("  ✅ No significant slop patterns detected.\n")
        return

    # Group by category
    categories = defaultdict(list)
    for f in findings:
        categories[f["category"]].append(f)

    sev_order = ["Tier-1 word", "Redundant qualifier", "Hedge", "Meta-commentary",
                 "Formulaic opener", "Template phrase", "Filler",
                 "Transition padding", "Empty intensifier", "Generic code",
                 "Tier-2 word"]

    severity_emoji = {
        "Tier-1 word": "🔴",
        "Redundant qualifier": "🟡",
        "Hedge": "🟡",
        "Meta-commentary": "🟡",
        "Formulaic opener": "🟡",
        "Template phrase": "🟡",
        "Filler": "🟡",
        "Transition padding": "🟢",
        "Empty intensifier": "🟢",
        "Generic code": "🟡",
        "Tier-2 word": "🟢",
    }

    for cat in sev_order:
        if cat not in categories:
            continue
        items = categories[cat]
        emoji = severity_emoji.get(cat, "🟡")
        print(f"  {emoji} {cat} ({len(items)} found)")
        for f in items:
            ctx = f"  — {f['suggestion']}"
            if verbose:
                print(f"     L{f['line']:>4}: {f['match'][:80]}{ctx}")
            else:
                print(f"     L{f['line']:>4}: {f['match'][:60]}")
                print(f"        {f['suggestion']}")
        print()

    # Unflagged categories
    for cat in ["Tier-2 word", "Empty intensifier", "Generic code", "Transition padding"]:
        if cat not in categories:
            print(f"  ✅ No {cat.lower()} issues\n")

    # Global metrics
    print(f"  {'—'*40}")
    print(f"  Formatting metrics:")
    if em_dash_count > 0:
        if em_dash_count > word_count / 1000:
            print(f"     🔴 Em dashes: {em_dash_count} (>1 per 1K words)")
        else:
            print(f"     ✅ Em dashes: {em_dash_count}")
    if bold_excessive:
        print(f"     🟡 Bold phrases: {bold_count} (may be excessive)")
    else:
        print(f"     ✅ Bold density: OK")

    if var_monotony:
        print(f"     🟡 Paragraph length variance: low (avg {var_avg:.0f} words)")
        print(f"         — vary paragraph length; include some 1-2 sentence paragraphs")
    else:
        print(f"     ✅ Paragraph rhythm: varied")

    print()


def print_json(findings, em_dash_count, bold_excessive, bold_count,
               var_monotony, var_score, var_avg, word_count):
    """Output machine-readable JSON."""
    import json
    categories = defaultdict(list)
    for f in findings:
        categories[f["category"]].append({
            "line": f["line"],
            "match": f["match"],
            "pattern": f["pattern"],
            "suggestion": f["suggestion"],
        })

    report = {
        "word_count": word_count,
        "total_findings": len(findings),
        "em_dashes": em_dash_count,
        "em_dashes_excessive": em_dash_count > max(1, word_count // 1000),
        "bold_excessive": bold_excessive,
        "bold_count": bold_count,
        "paragraph_variance_low": var_monotony,
        "paragraph_variance": round(var_score, 1),
        "paragraph_avg_words": round(var_avg, 1),
        "categories": dict(categories),
    }
    print(json.dumps(report, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Detect AI slop patterns in blog post drafts.")
    parser.add_argument("file", help="Markdown file to scan")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON for machine consumption")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show context line for each finding")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    word_count = len(text.split())

    findings = []

    # Word-level scans
    tier1_fn = lambda w: TIER1_WORDS.get(w, "Replace with plain alternative")
    findings += scan_words(text, TIER1_WORDS, "Tier-1 word", tier1_fn)
    tier2_fn = lambda w: TIER2_WORDS.get(w, "Replace or verify usage")
    findings += scan_words(text, TIER2_WORDS, "Tier-2 word", tier2_fn)

    # Regex-based scans
    findings += scan_regex_list(text, REDUNDANT_QUALIFIERS, "Redundant qualifier")
    findings += scan_regex_list(text, HEDGE_PATTERNS, "Hedge")
    findings += scan_regex_list(text, META_COMMENTARY, "Meta-commentary")
    findings += scan_regex_list(text, FORMULAIC_OPENERS, "Formulaic opener")
    findings += scan_regex_list(text, EMPTY_INTENSIFIERS, "Empty intensifier")
    findings += scan_regex_list(text, TRANSITION_PADDING, "Transition padding")
    findings += scan_regex_list(text, GENERIC_VARIABLE_NAMES, "Generic code")
    findings += scan_regex_list(text, TEMPLATE_PHRASES, "Template phrase")

    # Formatting metrics
    em_dash_count = count_em_dashes(text)
    bold_excessive, bold_count = check_bold_density(text)
    var_monotony, var_score, var_avg = check_paragraph_monotony(text)

    # Output
    if args.json:
        print_json(findings, em_dash_count, bold_excessive, bold_count,
                   var_monotony, var_score, var_avg, word_count)
    else:
        print_report(findings, em_dash_count, bold_excessive, bold_count,
                     var_monotony, var_score, var_avg, word_count, args.verbose)


if __name__ == "__main__":
    main()
