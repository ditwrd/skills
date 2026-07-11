#!/usr/bin/env bash
# Symlink every skill directory (containing SKILL.md) under ./skills/ into
# ~/.agents/skills/, flattening nested subdirs into a single flat namespace.
# Re-runnable: existing symlinks that already point to the right target are left alone.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SCRIPT_DIR/skills"
DST_DIR="${HOME}/.agents/skills"

if [[ ! -d "$SRC_DIR" ]]; then
  echo "error: source dir not found: $SRC_DIR" >&2
  exit 1
fi

mkdir -p "$DST_DIR"

linked=0
skipped=0
replaced=0
failed=0

while IFS= read -r entry; do
  name="$(basename "$entry")"
  [[ "$name" == .* ]] && continue
  target="$DST_DIR/$name"

  if [[ -L "$target" ]]; then
    if [[ "$(readlink "$target")" == "$entry" ]]; then
      echo "skip   $name (already linked)"
      skipped=$((skipped + 1))
      continue
    fi
    rm "$target"
    echo "relink $name"
    replaced=$((replaced + 1))
  elif [[ -e "$target" ]]; then
    echo "skip   $name (target exists and is not a symlink)"
    failed=$((failed + 1))
    continue
  else
    echo "link   $name"
    linked=$((linked + 1))
  fi

  ln -s "$entry" "$target"
done < <(find "$SRC_DIR" -name 'SKILL.md' -exec dirname {} + | sort)

echo
echo "linked=$linked  relinked=$replaced  skipped=$skipped  failed=$failed"
