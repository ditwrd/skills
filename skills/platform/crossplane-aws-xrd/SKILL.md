---
name: crossplane-aws-xrd
description: >
  Crossplane v2 XRDs and Compositions for AWS. Use when writing a Crossplane
  module for an AWS service, creating a CompositeResourceDefinition,
  authoring a Composition pipeline with function-go-templating, building a
  multi-resource AWS composite (VPC+EC2, S3+IAM, S3+notification-queue),
  discovering a provider-aws ManagedResourceDefinition schema,
  diagnosing a WatchCircuitOpen circuit breaker trip,
  auditing a composition for feedback loops or SSA conflicts, or testing
  locally with xprin.
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
5. **Commit to Git, let GitOps sync.** After sync, read live state with `kubectl get <xrd-kind> -A`, `kubectl describe <xr> -n <ns>`, and `kubectl get managed` to see what got rendered. **Watch for Argo CD sync loops:** if the XRD has fields with `default:` (`region`, `debug: false`), Crossplane fills them in on apply — Argo CD sees the live object has fields the manifest lacks, detects drift, and re-syncs. Add `ignoreDifferences` with `jqPathExpressions` for each defaulted path (`.spec.region`, `.spec.queues[].debug`) to the Argo Application.
6. **Iterate** — if the XR hangs, read `status.conditions` on the XR and the failing MR. A missing readiness check, a missing `observed.resources` nil-guard, or the trim-collapse bug in §0 is the usual culprit.

## Hard rules
- **XRD `apiVersion: apiextensions.crossplane.io/v2`** with `scope: Namespaced` (or `Cluster`). No `claimNames`, no `connectionSecretKeys` — both v1-only and rejected by v2 outside `scope: LegacyCluster`.
- **Composition `apiVersion: apiextensions.crossplane.io/v1`** (the only Composition version that exists in v2) with `mode: Pipeline`. `mode: Resources` (native patch-and-transform) is gone.
- **Pipeline must end with `function-auto-ready`**. Render step(s) precede it. The standard 2-step shape is render-then-auto-ready. Prefer a single render step with `*Ref` fields (queueUrlRef, queueArnRef, kmsKeyRef) — Crossplane resolves ordering, and the composition emits everything unconditionally. A second render step is only needed when the dependency can't be expressed as a `*Ref` (rare — e.g. needing a computed string that isn't a Ref target).
- **Every composed resource needs `{{ setResourceNameAnnotation "key" }}`** so downstream steps and `function-auto-ready` can find it. Missing annotation → resource is treated as a status update on the XR.
- **`.observed.resources` is nil on first reconcile** — guard with `default (dict) $.observed.resources`. Use `dig` (safe on nil) not `index` (panics on nil) to extract fields from composed resources. Preferred pattern: `{{- $obs := default (dict) $.observed.resources }}` then `{{- $data := dig "key" (dict) $obs }}` then `{{- $arn := dig "resource" "status" "atProvider" "arn" "" $data }}`. Each line does one thing and is safe at every level.
- **Use the namespaced CRD group** `<service>.aws.m.upbound.io/v1beta1` (e.g. `ec2.aws.m.upbound.io/v1beta1`). The legacy `<service>.aws.upbound.io` is for v1 cluster-scoped resources.
- **`providerConfigRef` MUST include `kind`** — missing `kind` fails with `spec.providerConfigRef.kind: Required value`. Use `kind: ClusterProviderConfig` (cluster-scoped, preferred) for most setups. Use `kind: ProviderConfig` (Namespaced) only when the ProviderConfig is in the same namespace as the managed resource. **Cross-namespace trap:** ProviderConfigs for `*.m.upbound.io` are `Namespaced` scope. If the managed resource is in namespace X and the ProviderConfig is in namespace Y, the provider can't find credentials — the MR gets `status: {}` with no conditions, and provider logs show "Calling the inner handler for Create event" but never progress. Fix: either add `namespace: <providerconfig-ns>` to `providerConfigRef`, or use `kind: ClusterProviderConfig` (cluster-scoped, no namespace boundary).
- **Connection details** — prefer `writeConnectionSecretToRef` on the managed resource (supported by most upjet providers). Each resource publishes its URL/credentials to a Secret automatically. When `writeConnectionSecretToRef` isn't available (no built-in connection detail): emit a manual `Secret` with `{{ setResourceNameAnnotation "connection-secret" }}`. `stringData` values MUST be string scalars — `toJson` on a list fails with `expected string, got array`. See [references/composition-patterns.md §4.2](references/composition-patterns.md).
- **Deterministic names** — set `metadata.name` on every composed resource from a stable field on the XR. NEVER set `crossplane.io/external-name` — the provider manages it automatically; setting it in the template causes a perpetual diff and reconciliation thrashing (see next rule). Always set `forProvider.name` when the CRD supports it — upjet/terraform uses `forProvider.name` for the actual AWS resource name. Missing `forProvider.name` causes terraform to auto-generate a random resource name. Crossplane derives `external-name` from `metadata.name` automatically.
- **Reconciliation thrashing / circuit breaker** — if an XR's status shows `WatchCircuitOpen`, a managed resource is in a tight loop. Root cause: perpetual diff between what the template renders and what Crossplane writes back. Diagnose: (a) find the MR with high `metadata.generation` (100+ within minutes); (b) check the CRD for SSA-atomic arrays — `kubectl get crd <plural>.<group> -o yaml | grep -B5 -A20 forProvider`; arrays missing `x-kubernetes-list-type` (or `x-kubernetes-list-type: None`) are atomic: SSA replaces the full array on every apply; (c) look for `*Ref` fields inside such arrays — the reference resolver (`managed.crossplane.io/api-simple-reference-resolver`) writes resolved values back (e.g. `queueArnRef` → `queueArn`), SSA strips them because the array is atomic, loop. **Fix:** render the resolved field alongside the `*Ref` from observed state with `{{- if $value }}` guard — on pass 1 only the ref renders; on pass 2+ both render so SSA includes the resolved value and the loop breaks. Other causes: `crossplane.io/external-name` overwritten by provider, provider default tags omitted (see next rule).
- **Provider default tags cause SSA conflict loops** — upjet providers inject `crossplane-name`, `crossplane-providerconfig` into `forProvider.tags` on every reconcile. If the composition template omits them, the provider's Update races with the composition's SSA Apply: the provider writes tags → composition re-applies without them → provider's finalizer write fails with `Cannot add finalizer: object has been modified`. Generation climbs to 100+ with no resource created. **Fix:** include ALL provider default tags in every composition template (`crossplane-name`: the MR's metadata.name, `crossplane-providerconfig`: the providerConfig name). The `crossplane-kind` default (`<kind>.<group>`) can be overridden with a custom value if needed.
- **Verify CRD schema before adding fields to templates** — unsupported fields cause the composition controller to reject the resource with `field not declared in schema`. Check with `kubectl get crd <resource-plural>.<group> -o yaml | grep -A 20 forProvider`. Common traps: `tags` is not supported on every resource (e.g. QueuePolicy, BucketNotification), and `bucket`/`bucketRef` is required on BucketNotification.
- **Policy content that references another resource's ARN** (e.g. SQS queue policy referencing the queue ARN) — use `*Ref` fields (queueUrlRef, etc.) for creation ordering, then read the ARN from observed state with the nil-guard above. Always emit `Effect: Allow` with the observed ARN — no conditional Deny/Allow needed because the `*Ref` ensures the dependency exists first. Pattern: `{{- $queueArn := dig "resource" "status" "atProvider" "arn" "" (dig "queue-X" (dict) (default (dict) $.observed.resources)) }}` — or split into three readable lines as shown above.

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
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
              providerConfigRef:
                name: default
                kind: ClusterProviderConfig
    - step: ready
      functionRef: {name: function-auto-ready}
```

For the rare case where `*Ref` can't express the dependency, add a second `function-go-templating` step that reads `$.observed.resources.<aKey>` with a nil-guard. See [references/go-templating-cheatsheet.md gotchas](references/go-templating-cheatsheet.md) for the `observed.resources` nil-on-first-reconcile pattern, [references/composition-patterns.md §4.1](references/composition-patterns.md) for the multi-step shape, and [references/testing-with-xprin.md two-reconcile test pattern](references/testing-with-xprin.md) for how to test it with xprin.

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
- `references/diagnosing-thrashing.md` — step-by-step diagnosis and fix for WatchCircuitOpen reconciliation thrashing
- `references/composition-audit.md` — audit checklist for feedback loops, external controller conflicts, and connection detail thrashing
- `references/makefile-test.md` — Makefile `test` target shape, usage, and when to create it
- `references/generating-readmes.md` — generating READMEs with `crossplane-docs`, fixing multiline table cells
