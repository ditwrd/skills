# IAM policy transform

Convert Terraform-style IAM statement objects into IAM JSON format using Go template primitives.

## Template

Input: list of statement objects, each with `effect` (Allow/Deny), `actions` (list), `resources` (list), optional `conditions` (map).

```yaml
{{- $policy := dict "Version" "2012-10-17" "Statement" (list) }}

{{- range $i, $stmt := .observed.composite.resource.spec.policyStatements }}
  {{- $actions := uniq (sortAlpha $stmt.actions) }}
  {{- if $actions }}
    {{- $s := dict "Effect" $stmt.effect "Action" $actions "Resource" $stmt.resources }}
    {{- if $stmt.conditions }}
      {{- $s = merge $s (dict "Condition" $stmt.conditions) }}
    {{- end }}
    {{- $policy = merge $policy (dict "Statement" (append (index $policy "Statement") $s)) }}
  {{- end }}
{{- end }}

spec:
  forProvider:
    policy: {{ $policy | toJson | quote }}
```

## Rules

- **`uniq` + `sortAlpha`** deduplicates action/resource lists (Go template's equivalent of `set`)
- **`dict "Key" $value`** builds a map
- **`append (index $policy "Statement") $s`** adds to the list without replacing prior entries
- **`toJson | quote`** produces a YAML-safe quoted JSON string — use for `forProvider.policy` (a string field)
- **Not for `stringData`** — `toJson` in a `stringData` value produces `expected string, got array`. See composition-patterns §4.2.

## Conditions as test/variable/values tuples

When the XR carries conditions as a list of tuples (`- test: StringEquals` / `variable: aws:SourceAccount` / `values: [...]`) instead of a pre-built map, group them by `test` with MERGE semantics — IAM allows N variables per operator:

```
{{- $conds := dict }}
{{- range $c := $stmt.conditions }}
{{- /* same-test conditions MERGE — plain set is last-write-wins and silently drops variables */ -}}
{{- $vars := default (dict) (get $conds $c.test) }}
{{- $_ := set $vars $c.variable $c.values }}
{{- $conds = set $conds $c.test $vars }}
{{- end }}
{{- $_ := set $s "Condition" $conds }}
```

`default (dict) (get ...)` returns the existing sub-map (mutation is in place — maps are references) or a fresh dict on first sight of a test. A plain `set $conds $c.test (dict $c.variable $c.values)` renders only the LAST variable among same-test conditions, with no error — two statements like `aws:SourceAccount` + `aws:PrincipalOrgID` under one `StringEquals` silently lose the first.

## Emission

- `{{ $policy | toJson | quote }}` and bare `{{ $policy | toJson }}` both emit valid YAML scalars — a JSON string literal is already apostrophe-safe, and the decoded value is identical either way. NEVER hand-wrap interpolation in single quotes: `policy: '{{ $policy }}'` fatals the render on the first apostrophe in user data (a Sid like `DenyNonKms'Actions`), with `did not find expected key`.
