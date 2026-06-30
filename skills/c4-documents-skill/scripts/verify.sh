#!/usr/bin/env bash
# Post-run verifier for c4-documents-skill output.
# Usage: verify.sh [output_dir]
#   output_dir defaults to ./c4.docs (relative to cwd)
#
# Exits 0 if all checks pass, 1 if any fail.
# Uses selkie (https://github.com/btucker/selkie) for real Mermaid parsing
# when available; falls back to regex checks otherwise.

set -uo pipefail

DST_DIR="${1:-./c4.docs}"

pass=0
fail=0

ok()   { printf '  PASS  %s\n' "$1"; pass=$((pass+1)); }
bad()  { printf '  FAIL  %s\n' "$1"; fail=$((fail+1)); }
note() { printf '  NOTE  %s\n' "$1"; }

if [[ ! -d $DST_DIR ]]; then
  echo "error: output dir not found: $DST_DIR" >&2
  exit 1
fi

echo "==> File presence in $DST_DIR"
for f in 1.Overview.md 2.Architecture.md 3.Workflow.md 5.Boundary-Interfaces.md; do
  if [[ -f $DST_DIR/$f ]]; then ok "exists: $f"; else bad "exists: $f"; fi
done

if [[ -d $DST_DIR/4.Deep-Exploration ]]; then
  ok "exists: 4.Deep-Exploration/"
  mod_count=$(find "$DST_DIR/4.Deep-Exploration" -maxdepth 1 -name '*.md' | wc -l)
  if [[ $mod_count -ge 1 ]]; then
    ok "4.Deep-Exploration/ has >=1 module doc ($mod_count found)"
  else
    bad "4.Deep-Exploration/ has >=1 module doc (0 found)"
  fi
else
  bad "exists: 4.Deep-Exploration/"
fi

if [[ -f $DST_DIR/6.Database-Overview.md ]]; then
  ok "exists: 6.Database-Overview.md"
else
  note "6.Database-Overview.md not present (ok if no database detected)"
fi

echo
echo "==> Mermaid validation"

mermaid_total=0
mermaid_bad=0

# Extract every ```mermaid block, prefixed with the source file path.
# Format per record: "FILE\tSTART_LINE\t<mermaid content lines>"
mermaid_buf=$(mktemp)
trap 'rm -f "$mermaid_buf"' EXIT

while IFS= read -r -d '' f; do
  awk -v file="$f" '
    /^```mermaid$/ { printf "FILE=%s\n", file; flag=1; next }
    /^```$/        { if (flag) { print "---"; flag=0 }; next }
    flag           { print }
  ' "$f" >> "$mermaid_buf"
done < <(find "$DST_DIR" -name '*.md' -print0 2>/dev/null)

mermaid_total=$(grep -c '^FILE=' "$mermaid_buf" 2>/dev/null || echo 0)

if [[ $mermaid_total -eq 0 ]]; then
  note "no Mermaid blocks found"
elif command -v selkie >/dev/null 2>&1; then
  ok "Mermaid blocks found ($mermaid_total), validating with selkie"
  tmpd=$(mktemp -d)
  trap 'rm -f "$mermaid_buf"; rm -rf "$tmpd"' EXIT
  block_no=0
  current_file=""
  block_content=""
  while IFS= read -r line; do
    case "$line" in
      FILE=*) current_file="${line#FILE=}"; block_content=""; block_no=$((block_no+1)) ;;
      ---)     # block boundary — render and report
        if [[ -n $block_content ]]; then
          tmpf="$tmpd/block.mmd"
          printf '%s\n' "$block_content" > "$tmpf"
          if selkie render -q -i "$tmpf" -o /dev/null 2>"$tmpd/err" >/dev/null; then
            :
          else
            mermaid_bad=$((mermaid_bad+1))
            printf '  FAIL  %s (block #%d):\n' "${current_file#$DST_DIR/}" "$block_no"
            sed 's/^/         /' "$tmpd/err" | head -8
          fi
        fi
        block_content=""
        ;;
      *)       block_content+="$line"$'\n' ;;
    esac
  done < "$mermaid_buf"
  # flush trailing block
  if [[ -n $block_content ]]; then
    tmpf="$tmpd/block.mmd"
    printf '%s\n' "$block_content" > "$tmpf"
    if ! selkie render -q -i "$tmpf" -o /dev/null 2>"$tmpd/err" >/dev/null; then
      mermaid_bad=$((mermaid_bad+1))
      printf '  FAIL  %s (block #%d):\n' "${current_file#$DST_DIR/}" "$block_no"
      sed 's/^/         /' "$tmpd/err" | head -8
    fi
  fi
  if [[ $mermaid_bad -eq 0 ]]; then
    ok "all Mermaid blocks parse cleanly"
  else
    bad "$mermaid_bad of $mermaid_total Mermaid blocks failed to parse"
  fi
else
  note "selkie not found on PATH; falling back to regex checks (less reliable)"
  note "install selkie (cargo install selkie-rs) for real Mermaid validation"
  # Heuristic fallback: unquoted multi-word label
  if grep -qE '\[[^"]* [^"]*\]' "$mermaid_buf"; then
    bad "no unquoted multi-word labels (found one or more)"
  else
    ok "no unquoted multi-word labels (regex)"
  fi
  # Heuristic fallback: bad node id at start of line
  if grep -qE '^[[:space:]]*[A-Za-z0-9_]*[ -][A-Za-z0-9_]+\[' "$mermaid_buf"; then
    bad "no hyphen/space in node ids (found one or more)"
  else
    ok "no hyphen/space in node ids (regex)"
  fi
fi

echo
echo "==> Confidence scores"
missing=0
for f in "$DST_DIR/1.Overview.md" "$DST_DIR/2.Architecture.md" "$DST_DIR/3.Workflow.md" \
         "$DST_DIR"/4.Deep-Exploration/*.md "$DST_DIR/5.Boundary-Interfaces.md"; do
  [[ -f $f ]] || continue
  if ! grep -qE 'Confidence score' "$f"; then
    printf '  FAIL  missing confidence score: %s\n' "${f#$DST_DIR/}"
    missing=$((missing+1))
  fi
done
if [[ $missing -eq 0 ]]; then
  ok "all required docs have a confidence score"
else
  bad "all required docs have a confidence score ($missing missing)"
fi

echo
echo "==> Summary: pass=$pass fail=$fail"
exit $(( fail > 0 ? 1 : 0 ))
