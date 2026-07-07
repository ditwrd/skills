---
name: crossplane-aws-xrd
description: >
  Crossplane v2. Authors CompositeResourceDefinitions (XRDs) and Compositions
  for AWS using provider-upjet-aws with function-go-templating and
  function-auto-ready. Use when writing a v2 CompositeResourceDefinition,
  a Composition pipeline using function-go-templating plus function-auto-ready,
  a multi-resource AWS composite (VPC+EC2, S3+IAM, S3+notification-queue),
  discovering the schema of an installed provider-aws ManagedResourceDefinition,
  or testing a Composition locally with xprin.
---

# Crossplane v2 + AWS compositions

Author v2 XRDs and Compositions for AWS. Artifacts are committed to Git and synced via GitOps (ArgoCD / Flux) — do not apply directly with `kubectl apply`. Assumes `function-go-templating v0.12+` and `function-auto-ready v0.7+`.

## §0 The trim-collapse bug (read this first)

This is the #1 thing that will burn you on your first composition. It looks like whitespace; it's structural. The k8s.io decoder fails the *parent* key, not the template directive, so the error message is misleading.

- **`{{-` on its own line eats the preceding newline via the `{{-` left-trim.** If `{{- range }}` or `{{- if }}` is on its own line, the left-trim removes the newline between it and the line above. For YAML keys with list values, the parent key and the first list item collapse onto one line and the k8s.io decoder rejects with `block sequence entries are not allowed in this context` or `mapping values are not allowed in this context`. The error is reported against the *parent* key (`queue: - id: ...`), not the range directive — confusing.
- **Two fixes.** Either inline the range on the same line as the parent key (`queue: {{ range $i, $q := $queues }}`), or use `{{ range ... }}` / `{{ end }}` (no trim) on its own line and accept the extra blank lines — the decoder ignores them.
- **Same trap for `{{- if $x }}` on filter/mapping lines** where the indent carries the key into the surrounding structure (e.g. `filterSuffix:`). Drop the left-trim and use `{{ if $x }}` so the indent is preserved. The closing `{{- end }}` is fine.

Full reference and other gotchas (`.observed.resources` nil on first reconcile, `dig` paths, `connectionDetails` base64) are in [references/go-templating-cheatsheet.md](references/go-templating-cheatsheet.md) and [references/common-gotchas.md](references/common-gotchas.md).

## Workflow

1. **Find the managed resource** for the AWS service. Namespaced v2 MRs are `<service>.aws.m.upbound.io/v1beta1` (e.g. `ec2.aws.m.upbound.io/v1beta1`). Discovery: `kubectl get mrd`, `kubectl explain`, or the marketplace at <https://marketplace.upbound.io/providers/upbound/provider-family-aws/latest/managed-resources>. Schema dump: `scripts/get-crd-field.sh <crd>`.
2. **Design the XR schema** — required fields sparingly, prefer arrays over scalars, avoid booleans, leave room for engine variants. See [references/xrd-anatomy.md claim rules](references/xrd-anatomy.md).
3. **Write the XRD** (`apiextensions.crossplane.io/v2`, `scope: Namespaced`) and the **Composition** (`apiextensions.crossplane.io/v1`, `mode: Pipeline`) — see §1 and §2 below. For full pipeline anatomy and function constraints, see [references/composition-anatomy.md](references/composition-anatomy.md).
4. **Validate locally** before committing:
   - `scripts/render.sh xr.yaml composition.yaml functions.yaml` — one-off preview (pins `--crossplane-version=v2.3.1` because `crossplane render` defaults to v1.x and rejects the v2 XRD schema).
   - `xprin test tests/module_xprin.yaml` — declarative assertions, golden-file diffs, hooks, CI output. See [references/testing-with-xprin.md](references/testing-with-xprin.md).
   - `kubectl apply --dry-run=client -f <file>` to confirm schema and required fields parse.
5. **Commit to Git, let GitOps sync.** After sync, read live state with `kubectl get <xrd-kind> -A`, `kubectl describe <xr> -n <ns>`, and `kubectl get managed` to see what got rendered.
6. **Iterate** — if the XR hangs, read `status.conditions` on the XR and the failing MR. A missing readiness check, a missing `observed.resources` nil-guard, or the trim-collapse bug in §0 is the usual culprit.

## Hard rules

- **XRD `apiVersion: apiextensions.crossplane.io/v2`** with `scope: Namespaced` (or `Cluster`). No `claimNames`, no `connectionSecretKeys` — both v1-only and rejected by v2 outside `scope: LegacyCluster`.
- **Composition `apiVersion: apiextensions.crossplane.io/v1`** (the only Composition version that exists in v2) with `mode: Pipeline`. `mode: Resources` (native patch-and-transform) is gone.
- **Pipeline must end with `function-auto-ready`**. Render step(s) precede it. The standard 2-step shape is render-then-auto-ready; for cross-resource dependencies, split into multiple render steps — see [references/composition-patterns.md §4.1](references/composition-patterns.md).
- **Every composed resource needs `{{ setResourceNameAnnotation "key" }}`** so downstream steps and `function-auto-ready` can find it. Missing annotation → resource is treated as a status update on the XR.
- **`.observed.resources` is nil on first reconcile** — guard with `{{ if eq $.observed.resources nil }}` and use `(index $.observed.resources "key")` (not `.observed.resources.key`, which panics on nil).
- **Composed `Secret` for connection details** — `connectionSecretKeys` is gone in v2. Emit a `Secret` resource with `{{ setResourceNameAnnotation "connection-secret" }}` and a nil-guard on the first reconcile. See [references/composition-patterns.md §4.2](references/composition-patterns.md).
- **Use the namespaced CRD group** `<service>.aws.m.upbound.io/v1beta1` (e.g. `ec2.aws.m.upbound.io/v1beta1`). The legacy `<service>.aws.upbound.io` is for v1 cluster-scoped resources.
- **Deterministic names** — set `metadata.name` and `crossplane.io/external-name` on every composed resource from a stable field on the XR. Random names break re-render diffing and `resourceRefs`.

## §1 XRD (v2) — minimal shape

```yaml
apiVersion: apiextensions.crossplane.io/v2
kind: CompositeResourceDefinition
metadata:
  name: xmything.aws.example.com
spec:
  group: aws.example.com
  names:
    kind: XMyThing
    plural: xmythings
  scope: Namespaced  # v2 default; state explicitly
  versions:
    - name: v1alpha1
      served: true
      referenceable: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              required: [region]
              properties:
                region: {type: string}
```

Users create the XR directly; there is no separate `Claim` kind. Composition name convention: `<xrd>-<group>-<version>` (e.g. `xmythings-aws-example-com-v1alpha1`).

## §2 Composition — standard 2-step pipeline

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: xmything.aws.example.com-v1alpha1
spec:
  compositeTypeRef:
    apiVersion: aws.example.com/v1alpha1
    kind: XMyThing
  mode: Pipeline
  pipeline:
    - step: render
      functionRef: {name: function-go-templating}
      input:
        apiVersion: gotemplating.fn.crossplane.io/v1beta1
        kind: GoTemplate
        source: Inline
        inline:
          template: |
            ---
            apiVersion: s3.aws.m.upbound.io/v1beta1
            kind: Bucket
            metadata:
              annotations:
                {{ setResourceNameAnnotation "bucket" }}
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-bucket
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
              providerConfigRef:
                name: default
    - step: ready
      functionRef: {name: function-auto-ready}
```

For cross-resource dependencies (B reads A's status), add a second `function-go-templating` step that reads `$.observed.resources.<aKey>` with a nil-guard. See [references/go-templating-cheatsheet.md gotchas](references/go-templating-cheatsheet.md) for the `observed.resources` nil-on-first-reconcile pattern, [references/composition-patterns.md §4.1](references/composition-patterns.md) for the multi-step shape, and [references/testing-with-xprin.md two-reconcile test pattern](references/testing-with-xprin.md) for how to test it with xprin.

## See also

- `references/xrd-anatomy.md` — full v2 XRD anatomy, claim schema design rules (required sparingly, avoid booleans, prefer arrays, leave room for variants, version round-tripping)
- `references/composition-anatomy.md` — v1 Composition API, function pipeline constraints (what functions can/cannot change)
- `references/go-templating-cheatsheet.md` — context fields, Sprig helpers, custom built-in helpers from `function_maps.go`, common gotchas (incl. trim-collapse), cross-resource status writes
- `references/composition-patterns.md` — multi-resource dependency (§4.1), connection secrets (§4.2), region/multi-account (§4.3), optional resources (§4.4), status conditions (§4.5), cross-XR references (§4.6)
- `references/mrd-discovery.md` — finding and inspecting provider-aws MRDs, activating Inactive CRDs, `kubectl explain`, marketplace links
- `references/testing-with-xprin.md` — install, `.xprin.yaml` subcommand pin, two-reconcile test pattern, cp-hook for capturing rendered output, gotchas
- `references/common-gotchas.md` — top-level validation gotchas (v1/v2 API rules, external-name, secret guards, MRD state)
- `EXAMPLES.md` — two complete copy-pastable AWS composites: **XNetwork** (VPC + public/private subnets + IGW + route tables + associations) and **XPostgres** (RDS instance with security group, subnet group, generated-password Secret, and a composed connection Secret)
- `scripts/render.sh <xr.yaml> <composition.yaml> <functions.yaml>` — `crossplane render --crossplane-version=v2.3.1` wrapper. The version pin is required; without it the engine inside Docker mismatches the host CLI on v2 XRD schema.
- `scripts/get-crd-field.sh <crd-name> [jsonpath]` — quick look at an installed provider-aws CRD's OpenAPI schema.
