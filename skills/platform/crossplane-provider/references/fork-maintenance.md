# Fork maintenance — `provider-upjet-snowflake`

The public fork has no true upstream remote and its early history was squashed
(e.g. `Feat/initialize poc (#2)`). That shapes how code and comment changes
must be classified and gated.

## Classifying fork text vs template boilerplate

`git blame` cannot separate fork-written comments from
[upjet-provider-template](https://github.com/crossplane/upjet-provider-template)
boilerplate: the squash attributes template text like `// $ is added to match
the exact string since the format is regex.` and the
`ExternalNameConfigs`/`Configured`/`Configurations` doc comments to the fork's
single author. `origin/main` is useless as an upstream reference: its `config/`
is fork-authored text plus squashed template boilerplate, with no remote to
tell them apart.

Before a comment-rewrite or scrub pass, extract the template's comment lines
into a reference set and protect them:

```shell
for f in config/external_name.go config/provider.go; do
  curl -sL "https://raw.githubusercontent.com/crossplane/upjet-provider-template/main/$f"
done | grep -oE '//.*' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | sort -u > /tmp/template-comments.txt
```

Treat only non-template lines as rewrite candidates. To undo rewrites of
protected text in an already-produced diff, classify each hunk by whether its
removed lines hit the reference set and revert only those hunks with
`git apply -R` — hunks are independent in comment regions, so a selective
reverse-apply applies cleanly.

## Gating per-branch CI

Each stacked PR on the fork runs its own CI. A `goconst` failure fired on the
bottom branch (5 literal occurrences of a map key in
`config/external_name_test.go`) while a tip-only local lint reported clean.
Before pushing a stack, run `gofmt -l`, `go test`, and `golangci-lint run` in a
worktree checkout of every head, not just the tip.
