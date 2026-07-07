# Go-templating cheatsheet

Context available inside templates (mirrors the `RunFunctionRequest` protobuf):
- `.observed.composite.resource` — the XR
- `.observed.resources.<name>` — each composed resource produced by prior steps, keyed by the resource's `setResourceNameAnnotation "name"` (use `(index $.observed.resources "name")` if `name` contains hyphens or special characters)
- `.observed.resources.<name>.connectionDetails.<key>` — connection detail keys are already base64-encoded
- `.desired.composite.resource` — the desired XR (pipeline accumulates)
- `.desired.composed.<name>` — desired state of each composed resource

## Helpers worth knowing (Sprig)

- `setResourceNameAnnotation "key"` — renders the `gotemplating.fn.crossplane.io/composition-resource-name: key` annotation. Use this on every composed resource. If you emit a resource with the same `apiVersion`/`kind` as the XR and **omit** this annotation, the function treats it as a status update on the composite.
- `dig "a" "b" "default" .x` — safe nested lookup, returns `default` on miss. Always use this over `.x.a.b` to avoid nil errors. The dotted-key form (`dig "a.b" "" .x`) does NOT work — split into separate string args.
- `eq a b` — equality
- `and a b c`, `or a b c` — booleans
- `default "fallback" .x` — provide a default for empty values
- `b64enc`, `b64dec` — base64
- `quote .x` — wrap in quotes
- `toJson .x`, `fromJson "..."` — JSON round-trip
- `list ...`, `first`, `last` — slice ops
- `lower`, `upper`, `title`, `trim` — strings
- `merge $a $b` — deep-merge maps
- `randAlphaNum N` — random alphanumeric string of length N

## Built-in helpers from `function-go-templating`

Defined in `function_maps.go`; available in addition to all Sprig functions except `env` / `expandenv`:

- `randomChoice "a" "b" "c"` — picks one of the given strings. Useful for idempotent label defaults: `{{ dig "resources" $name "resource" "metadata" "labels" "env" (randomChoice "dev" "staging" "prod") $.observed }}` returns the random pick on first render and the persisted value on subsequent reconciles.
- `toYaml .x` / `fromYaml "..."` — YAML round-trip (sibling of `toJson` / `fromJson`).
- `getCompositeResource` — returns `.observed.composite.resource`. Equivalent to writing the path; useful inside sub-templates passed to `include`.
- `getComposedResource "name"` — returns the observed composed resource named via `setResourceNameAnnotation`. Equivalent to `(index $.observed.resources "name")` but null-safe.
- `getComposedConnectionDetails "name"` — returns the connection details of a named composed resource. Use this instead of manually indexing `.connectionDetails` so the call no-ops cleanly when the resource hasn't produced details yet.
- `getResourceCondition "name" "Ready"` — returns the named condition object from a composed resource's `status.conditions`.
- `getExtraResources` — returns extra resources fetched by a `kind: ExtraResources` block in the same step. Indexed by the requirement's `name`.
- `getExtraResourcesFromContext` — returns extra resources that a prior pipeline step wrote into the pipeline context.
- `getCredentialData "name"` — returns the function request's credential data for the named credential (from the function runner).
- `include "name" .` — renders a named sub-template (from a `define` block) and returns the resulting string. Supports recursion up to 1000 deep. Same idea as Helm's `include`.

For the authoritative list and signatures, see `function_maps.go` in <https://github.com/crossplane-contrib/function-go-templating>. The official `example/` directory at the repo root demonstrates each one (`inline/`, `conditions/`, `context/`, `extra-resources/`, `filesystem/`, `custom-delims/`, `recursive/`). Note the upstream `example/` uses the v1 XRD API (`apiextensions.crossplane.io/v1`); the v2 conversions are mechanical (swap `apiVersion`, drop `claimNames`).

## Common gotchas

- `dig` paths use string keys, not dotted paths.
- YAML block scalars: the `template: |` body has the indentation stripped, so leading spaces in your YAML are relative to the template line, not the file.
- `{{ randAlphaNum 24 | b64enc | quote }}` produces a quoted base64 string suitable for a `Secret` `data` field.
- **`.observed.resources` is `nil` on the first reconcile.** `index .observed.resources $key` panics on the first pass. Guard with `{{ if eq $.observed.resources nil }}...{{ else }}...{{ end }}`, or use `with`: `{{ with .observed.resources }}{{ with index . $key }}{{ dig "status" "atProvider" "arn" "" . }}{{ end }}{{ end }}`. The dig call alone (e.g. `dig "status" "vpcId" "" .observed.resources.vpc`) DOES panic because Go templates can't index a nil map with a string field — use `(index $.observed.resources "vpc")` so the nil-receiver is the indexed call, not a field access. The `getComposedResource` helper above is nil-safe and a cleaner substitute.
- **Trim collapse bug — `{{-` on its own line eats the preceding newline.** If a `{{- if }}` or `{{- range }}` sits on its own line as a separate template line, the `{{-` left-trim removes the newline that separates it from the line above. For YAML keys with list values, this collapses the parent key and the first list item onto one line and the k8s.io decoder rejects it with `block sequence entries are not allowed in this context` or `mapping values are not allowed in this context`. The error is reported against the *parent* key (`queue: - id: ...`), not the range directive. Two fixes: put the range on the same line as the parent key (`queue: {{ range $i, $q := $queues }}`), or drop the left-trim and put the range on its own line with `{{ range ... }}` / `{{ end }}` (no trim) and accept the extra blank lines in the output — the decoder ignores them. Same trap applies to `{{- if $x }}` on mapping/filter-style lines where the indent carries the key into the surrounding structure (e.g. `filterSuffix:`): drop the left-trim and use `{{ if $x }}` so the 20-space indent is preserved. **Read SKILL.md §0 first** — this bug will burn you on your first composition.
- **Iterating N composed resources** — use `range` with `{{- range $i := until (.observed.composite.resource.spec.count | int) }}` and give each iteration a unique name via `setResourceNameAnnotation (print "name-" $i)`. Upstream `example/inline/composition.yaml` is the canonical reference; pattern is two resources per iteration (a producer labelled by `testing.upbound.io/example-name: ...`, a dependent that selects the producer by that label), and idempotency comes from `dig` with a `randomChoice` default that stabilizes after the first reconcile.

## Cross-resource status writes (conditions, custom context)

- `apiVersion: meta.gotemplating.fn.crossplane.io/v1alpha1`, `kind: ClaimConditions` with a `conditions:` array writes conditions onto the XR.
- `apiVersion: meta.gotemplating.fn.crossplane.io/v1alpha1`, `kind: Context` with a `data:` map writes to the pipeline context (read in a later step at `.context.<key>`).
- `apiVersion: meta.gotemplating.fn.crossplane.io/v1alpha1`, `kind: ExtraResources` with a `requirements:` array lets the function fetch extra resources into `.extraResources`.
