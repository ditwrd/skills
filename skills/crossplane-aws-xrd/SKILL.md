---
name: crossplane-aws-xrd
description: >
  Creates Crossplane v2 CompositeResourceDefinitions (XRDs) and Compositions
  for AWS using provider-upjet-aws with function-go-templating and
  function-auto-ready. Use when creating or updating a Crossplane module for an
  AWS service, writing a v2 CompositeResourceDefinition,
  writing a Composition pipeline using function-go-templating plus
  function-auto-ready, building a multi-resource AWS composite (VPC+EC2,
  S3+IAM, S3+notification-queue), discovering the schema of an installed
  provider-aws ManagedResourceDefinition, or testing locally with xprin.
---

# Crossplane v2 + AWS compositions

Author v2 XRDs and Compositions for AWS. Artifacts are committed to Git and synced via GitOps (ArgoCD / Flux) — do not apply directly with `kubectl apply`. Assumes `function-go-templating v0.12+` and `function-auto-ready v0.7+`.

## §0 The trim-collapse bug (read this first)

This is the #1 thing that will burn you on your first composition. It looks like whitespace; it's structural. The k8s.io decoder fails the *parent* key, not the template directive, so the error message is misleading.

- **`{{-` on its own line eats the preceding newline via the `{{-` left-trim.** If `{{- range }}` or `{{- if }}` is on its own line, the left-trim removes the newline between it and the line above. For YAML keys with list values, the parent key and the first list item collapse onto one line and the k8s.io decoder rejects with `block sequence entries are not allowed in this context` or `mapping values are not allowed in this context`. The error is reported against the *parent* key (`queue: - id: ...`), not the range directive — confusing.
- **Primary fix: drop the left-trim.** Use `{{ range $i, $q := $queues }}` / `{{ end }}` (no `-`) on its own line. The blank lines between the parent key and the first list item are valid YAML — the decoder ignores them. This is the safest fix.
- **Secondary fix (use with care):** Inline the range on the same line as the parent key (`queue: {{ range $i, $q := $queues }}`). **This can fail** with `missing value for range` from the Go template parser when the range pipeline is complex (e.g. inside a `with` block, or when the variable was set by a `default` function call). If you hit this error, use the primary fix.
- **Data-block collapse:** Same trap for non-emitting template directives (variable assignments, `range` that only produces side effects, `if` without inline value) between a YAML key and its value. `{{- $urls := list }}` between `data:` and `queueUrls:` eats the newlines and collapses both keys onto one line: `data:queueUrls: ...`. **Fix:** precompute values before the `data:` block, then emit the block with no intermediate directives. See [references/go-templating-cheatsheet.md](references/go-templating-cheatsheet.md) data-block pattern.
- **Filter/mapping lines:** Same trap for `{{- if $x }}` on filter or mapping lines (e.g. `filterSuffix:`). Drop the left-trim — `{{ if $x }}` preserves the blank line. The closing `{{- end }}` is fine.

## Workflow

1. **Find the managed resource** for the AWS service. Namespaced v2 MRs are `<service>.aws.m.upbound.io/v1beta1` (e.g. `ec2.aws.m.upbound.io/v1beta1`). Discovery: `kubectl get mrd`, `kubectl explain`, or the marketplace at <https://marketplace.upbound.io/providers/upbound/provider-family-aws/latest/managed-resources>. Schema dump: `scripts/get-crd-field.sh <crd>`.
2. **Design the XR schema** — required fields sparingly, prefer arrays over scalars, prefer enums over booleans (except for debug/feature toggles), leave room for engine variants. See [references/xrd-anatomy.md claim rules](references/xrd-anatomy.md).
3. **Write the XRD** (`apiextensions.crossplane.io/v2`, `scope: Namespaced`) and the **Composition** (`apiextensions.crossplane.io/v1`, `mode: Pipeline`) — see §1 and §2 below. For full pipeline anatomy and function constraints, see [references/composition-anatomy.md](references/composition-anatomy.md).
4. **Validate locally** before committing:
   - `scripts/render.sh xr.yaml composition.yaml functions.yaml` — one-off preview (pins `--crossplane-version=v2.3.1` because `crossplane render` defaults to v1.x and rejects the v2 XRD schema).
   - `kubectl apply --dry-run=client -f <file>` to confirm schema and required fields parse.
   - Before running xprin, check `.xprin.yaml` exists at the repo root with the correct `subcommands.render` and `subcommands.validate` pins (`--crossplane-version=v2.3.1`). Without this, xprin v0.2 invokes `crossplane internal render` internally but the crossplane CLI v2.3.x has no `internal` subcommand, producing `unexpected argument internal`. See [references/testing-with-xprin.md pin section](references/testing-with-xprin.md).
   - Use `make test` (or `make test MODULES=modules/aws/<module>`) to run all xprin suites via the repo Makefile, which pins `--config-file .xprin.yaml` by construction. This avoids accidentally falling back to `~/.config/xprin.yaml`. See [references/makefile-test.md](references/makefile-test.md) for the canonical Makefile shape.
5. **Commit to Git, let GitOps sync.** After sync, read live state with `kubectl get <xrd-kind> -A`, `kubectl describe <xr> -n <ns>`, and `kubectl get managed` to see what got rendered.
6. **Iterate** — if the XR hangs, read `status.conditions` on the XR and the failing MR. A missing readiness check, a missing `observed.resources` nil-guard, or the trim-collapse bug in §0 is the usual culprit.

## Hard rules
- **XRD `apiVersion: apiextensions.crossplane.io/v2`** with `scope: Namespaced` (or `Cluster`). No `claimNames`, no `connectionSecretKeys` — both v1-only and rejected by v2 outside `scope: LegacyCluster`.
- **Composition `apiVersion: apiextensions.crossplane.io/v1`** (the only Composition version that exists in v2) with `mode: Pipeline`. `mode: Resources` (native patch-and-transform) is gone.
- **Pipeline must end with `function-auto-ready`**. Render step(s) precede it. The standard 2-step shape is render-then-auto-ready; for cross-resource dependencies, split into multiple render steps — see [references/composition-patterns.md §4.1](references/composition-patterns.md).
- **Every composed resource needs `{{ setResourceNameAnnotation "key" }}`** so downstream steps and `function-auto-ready` can find it. Missing annotation → resource is treated as a status update on the XR.
- **`.observed.resources` is nil on first reconcile** — guard with `{{ if eq $.observed.resources nil }}` and use `(index $.observed.resources "key")` (not `.observed.resources.key`, which panics on nil).
- **Use the namespaced CRD group** `<service>.aws.m.upbound.io/v1beta1` (e.g. `ec2.aws.m.upbound.io/v1beta1`). The legacy `<service>.aws.upbound.io` is for v1 cluster-scoped resources.
- **`providerConfigRef` MUST include `kind: ProviderConfig`** — Upbound providers in Crossplane v2 require it. Missing `kind` fails with `spec.providerConfigRef.kind: Required value`.
- **Composed `Secret` for connection details** — `connectionSecretKeys` is gone in v2. Emit a `Secret` resource with `{{ setResourceNameAnnotation "connection-secret" }}` and a nil-guard on the first reconcile. `stringData` values MUST be string scalars — `toJson` on a list produces a JSON array that Crossplane's typed patch reinterprets as `[]interface{}`, failing with `expected string, got array`. Use individual keys (`queueUrls-<name>`) or `join` to produce a scalar. See [references/composition-patterns.md §4.2](references/composition-patterns.md).
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
                kind: ProviderConfig
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
- `references/testing-with-xprin.md` — install, `.xprin.yaml` subcommand pin, two-reconcile test pattern, FieldExists/FieldValue assertion coverage, cp-hook for capturing rendered output, gotchas
- `references/module-folder-structure.md` — the canonical module layout (`modules/aws/<thing>/` + `tests/`), the TDD workflow for a new module, what NOT to do (no per-module `functions/`, no absolute paths, no `out.yaml` hand-rolled)
- `references/common-gotchas.md` — top-level validation gotchas (v1/v2 API rules, external-name, secret guards, MRD state)
- `EXAMPLES.md` — two complete copy-pastable AWS composites: **XNetwork** (VPC + public/private subnets + IGW + route tables + associations) and **XPostgres** (RDS instance with security group, subnet group, generated-password Secret, and a composed connection Secret)
- `scripts/render.sh <xr.yaml> <composition.yaml> <functions.yaml>` — `crossplane render --crossplane-version=v2.3.1` wrapper. The version pin is required; without it the engine inside Docker mismatches the host CLI on v2 XRD schema.
- `scripts/get-crd-field.sh <crd-name> [jsonpath]` — quick look at an installed provider-aws CRD's OpenAPI schema.
- `references/makefile-test.md` — Makefile `test` target shape, usage, and when to create it
- `references/generating-readmes.md` — generating READMEs with `crossplane-docs`, fixing multiline table cells
