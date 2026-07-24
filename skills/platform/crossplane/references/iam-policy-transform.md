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
