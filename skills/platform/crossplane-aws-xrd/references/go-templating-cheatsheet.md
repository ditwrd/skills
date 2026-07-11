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
- `getResourceCondition "Ready" .observed.resources.<key>` returns the named condition object from an observed composed resource. Takes (condition-type, observed-resource-object). Example: `{{ $cond := getResourceCondition "Ready" $queue }}; {{ $cond.Status }}`.
- `getExtraResources` — returns extra resources fetched by a `kind: ExtraResources` block in the same step. Indexed by the requirement's `name`.
- `getExtraResourcesFromContext` — returns extra resources that a prior pipeline step wrote into the pipeline context.
- `getCredentialData "name"` — returns the function request's credential data for the named credential (from the function runner).
- `include "name" .` — renders a named sub-template (from a `define` block) and returns the resulting string. Supports recursion up to 1000 deep. Same idea as Helm's `include`.

For the authoritative list and signatures, see `function_maps.go` in <https://github.com/crossplane-contrib/function-go-templating>. The official `example/` directory at the repo root demonstrates each one (`inline/`, `conditions/`, `context/`, `extra-resources/`, `filesystem/`, `custom-delims/`, `recursive/`). Note the upstream `example/` uses the v1 XRD API (`apiextensions.crossplane.io/v1`); the v2 conversions are mechanical (swap `apiVersion`, drop `claimNames`).

## Common gotchas

- `dig` paths use string keys, not dotted paths.
- YAML block scalars: the `template: |` body has the indentation stripped, so leading spaces in your YAML are relative to the template line, not the file.
- `{{ randAlphaNum 24 | b64enc | quote }}` produces a quoted base64 string suitable for a `Secret` `data` field.
:- **`.observed.resources` is `nil` on the first reconcile.** The cleanest guard: `default (dict) $.observed.resources` then `dig` into it. `dig` is safe on nil maps (returns the default value); `index` panics. Preferred pattern:
  ```
  {{- $obs := default (dict) $.observed.resources }}
  {{- $data := dig "queue-key" (dict) $obs }}
  {{- $arn := dig "resource" "status" "atProvider" "arn" "" $data }}
  ```
  `dig` on a single resource path also works (inner `dig` returns `(dict)` when key missing):
  `{{- $arn := dig "resource" "status" "atProvider" "arn" "" (dig "queue-key" (dict) (default (dict) $.observed.resources)) }}`
  **Legacy patterns** (still work, prefer the above): `{{ if eq $.observed.resources nil }}...{{ else }}...{{ end }}` with `index`, or `{{ with .observed.resources }}{{ with index . $key }}{{ dig "status" "atProvider" "arn" "" . }}{{ end }}{{ end }}`. The `getComposedResource` helper is also nil-safe.
- **Trim collapse bug — `{{-` on its own line eats the preceding newline.** If a `{{- if }}` or `{{- range }}` sits on its own line, the left-trim removes the newline separating it from the line above. For YAML keys with list values, the parent key and the first list item collapse onto one line and the k8s.io decoder rejects with `block sequence entries are not allowed in this context` or `mapping values are not allowed in this context`. The error is reported against the *parent* key (`queue: - id: ...`), not the range directive.
  **Primary fix: drop the left-trim.** Use `{{ range }}` / `{{ end }}` (no `-`) on its own line. Blank lines are valid YAML — the decoder ignores them.
  **Secondary fix (use with care):** Inline the range on the same line as the parent key (`queue: {{ range $i, $q := $queues }}`). **Can fail** with `missing value for range` from the Go template parser when the range pipeline is complex — if so, use the primary fix.
- **`$x := nil` is invalid** — produces `nil is not a command`. Initialize with type-appropriate zero values: `$x := ""` (string), `$x := false` (bool). Nest observed-resource lookups inside `if $.observed.resources`: `{{ if $.observed.resources }}{{ $v := index $.observed.resources "key" }}...{{ end }}`.
  **Filter lines:** `{{- if $x }}` on its own line before `filterSuffix:` — drop the left-trim, use `{{ if $x }}`.
  **Data-block collapse:** Same mechanism when non-emitting directives (assignments, side-effect-only range) sit between a YAML key and its value. Their `{{- ` trims eat newlines, collapsing `data:` into `queueUrls:`. **Fix:** precompute the value before the block, then emit the key:value with no intermediate directives.
- **Never pipe through `indent` in `template: |` blocks** — `{{ include "x" . | indent N }}` uses `|` which the YAML parser interprets as a block scalar indicator, breaking the literal block. Keep `include` for single-value returns in variable assignments only: `{{- $v := include "t" (dict ...) -}}`. For multi-line YAML blocks, inline them directly — no define/include.
- **Iterating N composed resources** — use `range` with `{{- range $i := until (.observed.composite.resource.spec.count | int) }}` and give each iteration a unique name via `setResourceNameAnnotation (print "name-" $i)`. Upstream `example/inline/composition.yaml` is the canonical reference; pattern is two resources per iteration (a producer labelled by `testing.upbound.io/example-name: ...`, a dependent that selects the producer by that label), and idempotency comes from `dig` with a `randomChoice` default that stabilizes after the first reconcile.

## Cross-resource status writes (conditions, custom context)

- `apiVersion: meta.gotemplating.fn.crossplane.io/v1alpha1`, `kind: ClaimConditions` with a `conditions:` array writes conditions onto the XR.
- `apiVersion: meta.gotemplating.fn.crossplane.io/v1alpha1`, `kind: Context` with a `data:` map writes to the pipeline context (read in a later step at `.context.<key>`).
- `apiVersion: meta.gotemplating.fn.crossplane.io/v1alpha1`, `kind: ExtraResources` with a `requirements:` array lets the function fetch extra resources into `.extraResources`.
