# Reference

## 1. XRD anatomy (v2)

```yaml
apiVersion: apiextensions.crossplane.io/v2
kind: CompositeResourceDefinition
metadata:
  name: xnetworks.example.org
spec:
  scope: Namespaced              # Namespaced | Cluster | LegacyCluster (only the last allows claimNames)
  group: example.org
  names:
    kind: XNetwork               # the XR kind users create
    plural: xnetworks
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
                region:    { type: string }
                cidrBlock:
                  type: string
                  default: "10.0.0.0/16"
            status:
              type: object
              properties:
                vpcId:    { type: string }
                subnetIds:
                  type: array
                  items: { type: string }
```

Key v2 points:
- `apiVersion` must be `apiextensions.crossplane.io/v2` (v1 XRDs are still served but emit a deprecation warning).
- `scope` defaults to `Namespaced`. `LegacyCluster` is the only scope that allows `claimNames` and `connectionSecretKeys`, and both are deprecated.
- There is no v2 for `Composition` — it stays at `apiextensions.crossplane.io/v1`.
- The user creates `XNetwork` directly; there is no separate `Network` claim. The two-tier v1 model (XRD → claim) collapses to a single tier in v2.

### Claim schema design rules

- **Required fields sparingly** — once a field is required in a published version you cannot remove it. Prefer optional with a `default`.
- **Avoid booleans** — they box you in. Use a string enum (`speed: Regular | Fast | Slow`) so you can add values without a new version.
- **Prefer arrays over scalars** — if `spec.widget: "foo"` might become `spec.widgets: ["foo", "bar"]` later, start with the array. A single-element array is fine; an array you can extend is much cheaper than a breaking version bump.
- **Leave room for variants** — if you might support MySQL *and* PostgreSQL under one XR, put engine-specific fields in nested objects (`spec.postgresql`, `spec.mysql`) toggled by a top-level `spec.engine` enum. Avoid a flat schema that needs you to add top-level fields per engine.
- **Versions are not a magic escape hatch** — two CRD versions are two views into the same data, and they must round-trip. You can rename or move fields; you cannot drop a previously required field, or add a new required field, without breaking older XRs. Invest in backward-compatible evolution instead of new versions.

## 2. Composition anatomy (v1 API, v2-compatible)

Composition is `apiextensions.crossplane.io/v1` (no v2 version exists). The pipeline has two required steps: a `function-go-templating` step that renders composed resources, and a `function-auto-ready` step that marks readiness.

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: xnetwork-example-org-v1alpha1
spec:
  compositeTypeRef:
    apiVersion: example.org/v1alpha1
    kind: XNetwork
  mode: Pipeline
  pipeline:
    - step: render-resources
      functionRef:
        name: function-go-templating
      input:
        apiVersion: gotemplating.fn.crossplane.io/v1beta1
        kind: GoTemplate
        source: Inline
        inline:
          template: |
            ---
            apiVersion: ec2.aws.m.upbound.io/v1beta1
            kind: VPC
            metadata:
              annotations:
                {{ setResourceNameAnnotation "vpc" }}
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-vpc
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                cidrBlock: {{ .observed.composite.resource.spec.cidrBlock }}
              providerConfigRef:
                name: default
            # ... more composed resources ...

    - step: automatically-detect-ready-composed-resources
      functionRef:
        name: function-auto-ready
```

Key points:
- Name the Composition `<xrd>-<group>-<version>` so multiple versions compose cleanly.
- The render step emits one or more `---`-separated YAML docs. Each becomes a composed resource. Every composed resource needs the `{{ setResourceNameAnnotation "key" }}` helper (or the long-form `gotemplating.fn.crossplane.io/composition-resource-name` annotation) so downstream steps and `function-auto-ready` can reference it.
- The auto-ready step has no `input` block by default — it walks all composed resources produced by the pipeline and checks their standard `status.conditions[type=Ready]` (or built-in health checks for native Kubernetes resources like Deployment/Pod).
- `function-auto-ready` respects the `gotemplating.fn.crossplane.io/ready: "True|False"` annotation. If a render step marks a resource not ready, auto-ready won't override.
- Function pipeline constraints (from the official Compositions docs — they will silently bite you if you ignore them):
  - A function **can** change the XR's `status`, `status.conditions`, and readiness. It can also change composed resources' `metadata` and `spec`.
  - A function **cannot** change composed resources' `status` — Crossplane owns that, populated from what the provider controller observes. Trying to set `status.atProvider` on a managed resource from your template is a no-op.
  - A function **cannot** change the XR's `metadata` or `spec` — only the function's *output* can populate XR status fields. The XR is the user-owned source of truth.
  - A function **must** return the full desired state of composed resources every call. If you set a field once and omit it on the next call, Crossplane deletes the field (server-side apply semantics).

## 3. Go-templating cheatsheet

Context available inside templates (mirrors the `RunFunctionRequest` protobuf):
- `.observed.composite.resource` — the XR
- `.observed.resources.<name>` — each composed resource produced by prior steps, keyed by the resource's `setResourceNameAnnotation "name"` (use `(index $.observed.resources "name")` if `name` contains hyphens or special characters)
- `.observed.resources.<name>.connectionDetails.<key>` — connection detail keys are already base64-encoded
- `.desired.composite.resource` — the desired XR (pipeline accumulates)
- `.desired.composed.<name>` — desired state of each composed resource

Helpers worth knowing:
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

Common gotchas:
- `dig` paths use string keys, not dotted paths.
- YAML block scalars: the `template: |` body has the indentation stripped, so leading spaces in your YAML are relative to the template line, not the file.
- `{{ randAlphaNum 24 | b64enc | quote }}` produces a quoted base64 string suitable for a `Secret` `data` field.
- **`.observed.resources` is `nil` on the first reconcile.** `index .observed.resources $key` panics on the first pass. Guard with `{{ if eq $.observed.resources nil }}...{{ else }}...{{ end }}`, or use `with`: `{{ with .observed.resources }}{{ with index . $key }}{{ dig "status" "atProvider" "arn" "" . }}{{ end }}{{ end }}`. The dig call alone (e.g. `dig "status" "vpcId" "" .observed.resources.vpc`) DOES panic because Go templates can't index a nil map with a string field — use `(index $.observed.resources "vpc")` so the nil-receiver is the indexed call, not a field access.

Cross-resource status writes (conditions, custom context):
- `apiVersion: meta.gotemplating.fn.crossplane.io/v1alpha1`, `kind: ClaimConditions` with a `conditions:` array writes conditions onto the XR.
- `apiVersion: meta.gotemplating.fn.crossplane.io/v1alpha1`, `kind: Context` with a `data:` map writes to the pipeline context (read in a later step at `.context.<key>`).
- `apiVersion: meta.gotemplating.fn.crossplane.io/v1alpha1`, `kind: ExtraResources` with a `requirements:` array lets the function fetch extra resources into `.extraResources`.

## 4. Patterns

### 4.1 Multi-resource dependency

When resource B needs an output of resource A, render A first and have B read A's output via `.observed.resources.a`. For AWS, this is common with:
- VPC → Subnet (for the SubnetGroup) / RouteTable / SecurityGroup
- SecurityGroup → every workload resource that needs ingress/egress rules
- RDS Instance → SubnetGroup, SecurityGroup

The pipeline runs all render steps before the observe step, so split render into multiple `function-go-templating` steps when there are dependencies:

```yaml
pipeline:
  - step: render-producers
    functionRef: { name: function-go-templating }
    input: { ... }
  - step: render-dependents
    functionRef: { name: function-go-templating }
    input: { ... }   # second step reads (index $.observed.resources "vpc") etc.
  - step: automatically-detect-ready-composed-resources
    functionRef: { name: function-auto-ready }
```

### 4.2 Connection secret from composed resources

In v2 there is no `connectionSecretKeys` on the XRD. Compose your own `Secret` resource instead, copying values from the underlying resource's `connectionDetails` map (which is already base64-encoded by the provider controller):

```yaml
---
apiVersion: v1
kind: Secret
metadata:
  annotations:
    {{ setResourceNameAnnotation "connection-secret" }}
  name: {{ .observed.composite.resource.metadata.name }}-pg-conn
  namespace: {{ .observed.composite.resource.metadata.namespace }}
{{ if eq $.observed.resources nil }}
data: {}
{{ else }}
data:
  endpoint: {{ (index $.observed.resources "pg").connectionDetails.endpoint | b64enc }}
  username: {{ (index $.observed.resources "pg").connectionDetails.username | b64enc }}
  password: {{ (index $.observed.resources "pg").connectionDetails.password | b64enc }}
{{ end }}
```

`endpoint`/`username`/`password` are already base64 when read from `connectionDetails`, so the outer `| b64enc` is correct for putting them in a `Secret.data` field (which requires base64). If you instead read raw `status.atProvider.*` values, use `| b64enc` to encode them.

### 4.3 Region / multi-account

Pass through to each MR's `forProvider.region`. If you want a default:

```yaml
{{ default "us-east-1" .observed.composite.resource.spec.region }}
```

For per-account `providerConfigRef`, look up the field from the XR or accept a passthrough:

```yaml
providerConfigRef:
  name: {{ .observed.composite.resource.spec.providerConfigName }}
```

In v2 the default `providerConfigRef` (when omitted on the MR) is `name: default, kind: ClusterProviderConfig`. v2 introduced a second kind, `ProviderConfig`, for namespaced setups — set `kind: ProviderConfig` explicitly when you want a namespaced config.

### 4.4 Optional resources

Wrap the resource in a conditional based on the XR's optional fields:

```yaml
{{ if .observed.composite.resource.spec.logging }}
---
apiVersion: cloudwatchlogs.aws.m.upbound.io/v1beta1
kind: LogGroup
metadata:
  annotations:
    {{ setResourceNameAnnotation "logs" }}
spec:
  forProvider:
    region: {{ .observed.composite.resource.spec.region }}
    retentionInDays: 30
{{ end }}
```

If the resource is conditionally absent, `function-auto-ready` will simply not wait for it. No special handling needed.

### 4.5 Status fields and custom conditions

`function-auto-ready` sets `Ready: True` on the XR when every composed resource is ready. If you want a custom condition (e.g. "BucketReady" with a human-readable reason), use `kind: ClaimConditions` in the same render step as the resources it depends on:

```yaml
{{ if eq (dig "status" "atProvider" "instanceStatus" "" (index $.observed.resources "pg")) "available" }}
---
apiVersion: meta.gotemplating.fn.crossplane.io/v1alpha1
kind: ClaimConditions
conditions:
  - type: PostgresAvailable
    status: "True"
    reason: Available
    message: "RDS instance is up"
    target: CompositeAndClaim
{{ else }}
---
apiVersion: meta.gotemplating.fn.crossplane.io/v1alpha1
kind: ClaimConditions
conditions:
  - type: PostgresAvailable
    status: "False"
    reason: Creating
    message: "waiting for instance to become available"
    target: CompositeAndClaim
{{ end }}
```

For per-resource readiness overrides, set `gotemplating.fn.crossplane.io/ready: "False"` on a resource the function emits and `function-auto-ready` will not flip it to ready even if its standard condition is True.

### 4.6 Cross-XR references (status copy)

If one XR needs another's status fields, declare the reference on the consuming XR's spec (e.g. `spec.networkRef.name`) and use `function-status-transformer` to copy the referenced XR's `status.<field>` into the consumer's `status` (or `spec`). This is the v2 replacement for reading the connection secret of a referenced v1 claim.

## 5. Discovering current CRD fields and previewing renders

CRDs evolve. Always check the installed version, and preview the function pipeline output locally before committing (you do not apply these directly — GitOps syncs them):

```sh
# Find the right MRD / CRD
kubectl get mrd | grep -i rds
kubectl get crd | grep -i rds | grep 'aws\.m\.upbound\.io'

# Check if a specific MRD is active
kubectl get mrd dbinstances.rds.aws.m.upbound.io -o jsonpath='{.spec.state}'
# Activate it if needed (some providers ship CRDs as Inactive under safe-start)
kubectl patch mrd dbinstances.rds.aws.m.upbound.io \
  --type='merge' -p='{"spec":{"state":"Active"}}'

# Dump the schema
kubectl get crd dbinstances.rds.aws.m.upbound.io -o jsonpath='{.spec.versions[0].schema.openAPIV3Schema}' | jq

# For a single field path
kubectl explain dbinstance.rds.aws.m.upbound.io.spec.forProvider.engine

# Preview what your function pipeline will produce (needs the crossplane CLI + Docker)
crossplane render xr.yaml composition.yaml functions.yaml

# Quick schema check without applying
kubectl apply --dry-run=client -f xrd.yaml
```

The namespaced CRD group is `<service>.aws.m.upbound.io/v1beta1` (e.g. `ec2.aws.m.upbound.io/v1beta1`). The legacy cluster-scoped group `<service>.aws.upbound.io` still works for v1-style cluster resources.

For the latest field set, check the upstream repo: https://github.com/crossplane-contrib/provider-upjet-aws/tree/main/examples and the per-resource `.tf` files in `internal/clients/`.

For questions on `function-go-templating` syntax or context shape, web search `crossplane function-go-templating example` — the function's API has changed between minor versions.

Official Crossplane v2.3 docs referenced for this skill:
- Compositions (function pipeline, constraints): https://docs.crossplane.io/v2.3/composition/compositions/
- XRD schema and v2 API: https://docs.crossplane.io/v2.3/guides/upgrade-to-crossplane-v2/
- function-go-templating: https://github.com/crossplane-contrib/function-go-templating
- function-auto-ready: https://github.com/crossplane-contrib/function-auto-ready
- XR API best practices: https://www.upbound.io/blog/crossplane-xr-best-practices
- Configuring Crossplane with Argo CD (for the GitOps side): https://docs.crossplane.io/v2.3/guides/crossplane-with-argo-cd/

## 6. Common validation gotchas

- **XRD is `apiextensions.crossplane.io/v2`** with `scope: Namespaced` (or `Cluster`). If you set `claimNames` or `connectionSecretKeys` outside `LegacyCluster` scope, the v2 XRD rejects the field.
- **Composition is `apiextensions.crossplane.io/v1`** (the only version that exists). Don't try `apiextensions.crossplane.io/v2` for the Composition.
- **Every composed resource needs `setResourceNameAnnotation "key"`.** Without it, the function either rejects the resource (in newer versions) or mis-routes it as a status update on the XR.
- **`.observed.resources` is nil on first reconcile.** Guard the index call. `dig "status" "vpcId" "" .observed.resources.vpc` panics because Go templates can't field-access a nil map; use `(index $.observed.resources "vpc")` instead so the nil-receiver is the index call, not a field access.
- **`function-auto-ready` is the last step.** Putting it before the render step means it sees no composed resources and the XR will never become ready.
- **`crossplane.io/external-name` missing on a resource?** It will be recreated on every reconcile. Always set it from a stable field on the XR.
- **Indentation off by one space inside `template: |`?** YAML will parse but resources will have wrong fields. Render the template to a file and `kubectl apply --dry-run=client -f -` to validate, or use `crossplane render`.
- **You composed a `Secret` for connection details but the data map is empty?** That's the first reconcile — the underlying instance hasn't produced `connectionDetails` yet. The `{{ if eq $.observed.resources nil }}` (or the more specific `{{ if not (index $.observed.resources "pg") }}`) guard will keep the function from panicking; the map fills in on the next reconcile.
- **Provider CRD not present after install?** Some providers ship CRDs as `Inactive` MRDs under safe-start. Patch the MRD to `Active`, or configure a `ManagedResourceActivationPolicy`.
