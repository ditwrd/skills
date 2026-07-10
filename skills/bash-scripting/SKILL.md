---
name: bash-scripting
description: Write safe, legible bash scripts with strict mode, cleanup traps, and ShellCheck enforcement. Use when writing, diagnosing, or reviewing shell scripts.
---

# Bash Scripting

A bash script is **strict**: it fails early and explicitly on the first error, cleans up after itself on every exit path, and passes ShellCheck with zero warnings. Every rule below serves that — make the script strict, and the script stays predictable.

## Pick a branch

- **Write** — build a new script: shebang, strict mode, cleanup trap, main guard, logging, args parsing. Ship nothing that ShellCheck flags.
- **Diagnose** — ladder: `bash -n` for syntax, `shellcheck` for static analysis, `bash -x` for trace. Isolate sections with `set -x`/`set +x`. Then fix.
- **Review** — checklist: strict mode on? cleanup trap covers all exits? every expansion quoted? ShellCheck clean? `printf` over `echo`? long flags? `$()` not backticks?

## Core rules — every script

### Safety baseline — start every script with:

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
```

- `set -e` — exit on the first non-zero status. Use `cmd || true` to tolerate expected failures.
- `set -u` — error on unbound variables. Default optional args: `${1:-"default"}`.
- `set -o pipefail` — the pipeline fails on the first non-zero, not the last command.
- `IFS=$'\n\t'` — split on newlines and tabs only, not spaces. Keeps array iteration predictable.

### Cleanup trap — every temp resource gets cleaned up:

```bash
cleanup() {
  result=$?
  # remove temp files, restore services
  exit "${result}"
}
trap cleanup EXIT
```

The trap fires on every exit path — normal, error, signal. Capture `$?` before doing anything. For background-heavy scripts, also `trap cleanup ERR` but test that the EXIT trap isn't double-firing.

### Quoting — every expansion:

- Always `${var}` form, never `$var`.
- `"${var}"` — quotes prevent word splitting on IFS. `"${@}"` preserves argument boundaries where `$@` does not.
- Globs: `for f in "${dir}"/*.txt; do` — quote the path prefix, not the glob.

### Commands:

- `$(cmd)` — nestable, legible. Never backticks.
- `printf` over `echo` — [portable and predictable output](https://www.in-ulm.de/~mascheck/various/echo+printf/). `echo` varies across shells for flags, backslash sequences, and `-n`.
- `\cmd` to skip alias/builtin lookup: `\time`, `\rm`.

### Structure — functions, scope, and control flow:

- **Functions**: `local` every variable, name positional params for readability:

```bash
ensure_dir() {
  local dir="${1}"
  mkdir -p "${dir}"
}
```

- **Main guard**: sourceable or executable:

```bash
if [[ "${BASH_SOURCE[0]}" = "$0" ]]; then
  main "${@}"
fi
```

- **Long flags** — `rm --recursive --force -- "${dir}"` over `rm -rf`. Readability at a glance.
- **Function for complex conditions** — extract conditional logic into a named test:

```bash
help_wanted() {
  [[ "$#" -ge 1 ]] && [[ "${1}" = '-h' || "${1}" = '--help' || "${1}" = '-?' ]]
}
if help_wanted "${@}"; then usage; exit 0; fi
```

- **Parse args in a function** — `case`/`shift` loop, never positional soup.

### Logging — every script reports what it does:

```bash
info()    { printf "[INFO]    %s\n" "${*}" >&2; }
warning() { printf "[WARNING] %s\n" "${*}" >&2; }
error()   { printf "[ERROR]   %s\n" "${*}" >&2; }
fatal()   { printf "[FATAL]   %s\n" "${*}" >&2; exit 1; }
```

All to stderr so stdout stays clean for piped output. Tee to a log file for long-running or cron scripts: `| tee -a "${LOG_FILE}"` inside each function.

### Directory safety:

```bash
# Subshell — cwd change is local
(
  cd "${target_dir}"
  do_work
)

# Or pushd/popd for the same
pushd "${target_dir}"
  do_work
popd
```

Never `cd "${foo}"; ... ; cd ..` — an error before the `cd ..` lands the script in the wrong directory. The subshell or pushd/popd fixes that.

### Help text — every script documents itself:

```bash
#/ Usage: deploy.sh [--env ENV]
#/ Deploy the application to a target environment.
usage() { grep '^#/' "$0" | cut -c4-; exit 0; }
expr "${*:-}" : ".*--help" > /dev/null && usage
```

Lines starting with `#/` are the help text. The `usage` function strips the prefix and prints them. For full parameter parsing use `while [[ $# -gt 0 ]]; do case "$1" in` — the `#/` pattern is the minimal viable documentation.

## Completion criterion

Every written script:
1. Passes `shellcheck` with zero warnings.
2. Starts with `set -euo pipefail` and `IFS=$'\n\t'`.
3. Includes a cleanup trap consuming all temp resources.
4. Quotes every `${var}` expansion.
5. Writes log output to stderr with level prefixes.
6. Documents itself via `--help`.

Every diagnosed script exits the diagnostic ladder with at least one of [syntax fix, ShellCheck warning fixed, quoting bug fixed] applied.