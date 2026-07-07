# Reference

## 1. XRD anatomy

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: CompositeResourceDefinition
metadata:
  name: xnetworks.example.org
spec:
  group: example.org
  names:
    kind: XNetwork           # claim kind
    plural: xnetworks
  claimNames:
    kind: Network            # claim kind users actually write
    plural: networks
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
                region: { type: string }
                cidrBlock:
                  type: string
                  default: "10.0.0.0/16"
            status:
              type: object
              properties:
                vpcId:   { type: string }
                subnetIds: { type: array, items: { type: string } }
  connectionSecretKeys:
    - vpcId
    - subnetIds
```

Key points:
- `claimNames` is the user-facing kind. Keep it short and domain-named.
- Set `referenceable: true` so other XRs can reference this one.
- Put user-visible status fields under `status`. The composition writes into them.
- `connectionSecretKeys` controls which status fields get published as a Secret.

### Claim schema design rules

From the Upbound XR best-practices blog. Apply when deciding the shape of the claim:

- **Required fields sparingly** — once a field is required in a published version you cannot remove it. Prefer optional with a `default`.
- **Avoid booleans** — they box you in. Use a string enum (`speed: Regular | Fast | Slow`) so you can add values without a new claim version.
- **Prefer arrays over scalars** — if `spec.widget: "foo"` might become `spec.widgets: ["foo", "bar"]` later, start with the array. A single-element array is fine; an array you can extend is much cheaper than a breaking version bump.
- **Leave room for variants** — if you might support MySQL *and* PostgreSQL under one XR, put engine-specific fields in nested objects (`spec.postgresql`, `spec.mysql`) toggled by a top-level `spec.engine` enum. Avoid a flat schema that needs you to add top-level fields per engine.
- **Versions are not a magic escape hatch** — two CRD versions are two views into the same data, and they must round-trip. You can rename or move fields; you cannot drop a previously required field, or add a new required field, without breaking older claims. Invest in backward-compatible evolution instead of new versions.

## 2. Composition anatomy

Function pipeline constraints (from the official Compositions docs — they will silently bite you if you ignore them):

- A function **can** change the XR's `status`, `status.conditions`, readiness, and `connectionDetails`. It can also change composed resources' `metadata` and `spec`.
- A function **cannot** change composed resources' `status` or `connectionDetails` — Crossplane owns those, populated from what the provider controller observes. Trying to set `status.atProvider` on a managed resource from your template is a no-op.
- A function **cannot** change the XR's `metadata` or `spec` — only the function's *output* can populate the XR's status fields. The XR is the user-owned source of truth.
- A function **must** return the full desired state of composed resources every call. If you set a field once and omit it on the next call, Crossplane deletes the field (server-side apply semantics).

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: xnetwork-example-org-v1alpha1   # name convention: <xrd>-<group>-<ver>
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
            apiVersion: ec2.aws.upbound.io/v1beta1
            kind: VPC
            metadata:
              name: {{ .observed.composite.resource.metadata.name }}-vpc
              annotations:
                crossplane.io/external-name: {{ .observed.composite.resource.spec.name }}
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                cidrBlock: {{ .observed.composite.resource.spec.cidrBlock }}
                enableDnsSupport: true
                enableDnsHostnames: true
              providerConfigRef:
                name: default
            ---
            apiVersion: ec2.aws.upbound.io/v1beta1
            kind: Subnet
            ...

    - step: observe-and-report-readiness
      functionRef:
        name: function-go-templating
      input:
        apiVersion: gotemplating.fn.crossplane.io/v1beta1
        kind: GoTemplate
        source: Inline
        inline:
          template: |
            status:
              vpcId: {{ (dig "status" "atProvider" "vpcId" "" .observed.resources.vpc) }}
              subnetIds:
                - {{ (dig "status" "atProvider" "subnetId" "" .observed.resources.subnet) }}
              ready: {{ and
                  (eq (dig "status" "conditions" "Ready" "reason" .observed.resources.vpc) "Available")
                  (eq (dig "status" "conditions" "Ready" "reason" .observed.resources.subnet) "Available")
              }}
            conditions:
              - type: Ready
                status: "{{ if ... }}True{{ else }}False{{ end }}"
                reason: Available
                message: "all managed resources are ready"
              - type: Synced
                status: "True"
                reason: ReconcileSuccess
            connectionDetails:
              vpcId:
                type: FromValue
                fromValuePath: status.vpcId
```

Key points:
- Name the Composition `<xrd>-<group>-<version>` so multiple versions compose cleanly.
- The render step emits one or more `---`-separated YAML docs. Each becomes a Managed Resource.
- Naming convention: `<claim-name>-<kind>`, suffixed with `-vpc`, `-subnet`, etc. Keeps `kubectl get` clean.
- Always set `crossplane.io/external-name` so subsequent reconciles are stable.
- Use `spec.providerConfigRef.name: default` unless you have per-region configs.

## 3. Go-templating cheatsheet

Context available inside templates:
- `.observed.composite.resource` — the XR
- `.observed.resources.<name>` — each MR produced by prior steps, keyed by the MR's `metadata.name`
- `.desired.composite.resource` — the desired XR (only after render)

Common functions (sprig + `dig`):
- `dig "a" "b" "default" .x` — safe nested lookup, returns `default` on miss. Always use this over `.x.a.b` to avoid nil errors.
- `eq a b` — equality
- `and a b c`, `or a b c` — booleans
- `default "fallback" .x` — provide a default for empty values
- `b64enc`, `b64dec` — base64
- `quote .x` — wrap in quotes (for shell-style strings in user data, etc)
- `toJson .x`, `fromJson "..."` — JSON round-trip
- `list ...`, `first`, `last` — slice ops
- `lower`, `upper`, `title`, `trim` — strings
- `merge $a $b` — deep-merge maps

Common gotchas:
- `dig` paths use string keys, not dotted paths. `dig "status.atProvider.vpcId" "" .x` does NOT work — split: `dig "status" "atProvider" "vpcId" "" .x`.
- YAML block scalars: the `template: |` body has the indentation stripped, so leading spaces in your YAML are relative to the template line, not the file. Add 12 spaces before the resource metadata.
- Reference a `ref-` field from a prior step: `dig "status" "atProvider" "vpcId" "" .observed.resources.vpc`.

## 4. Patterns

### 4.1 Multi-resource dependency

When resource B needs an output of resource A, render A first and let B reference A's output via the XR's `status` (set in the observe step) or directly from `.observed.resources.a`. For AWS, this is common with:
- VPC → SubnetGroup (RDS) / RouteTable / SecurityGroup
- VPC → Subnet (for the SubnetGroup)
- SecurityGroup → every workload resource that needs ingress/egress rules

If the MR API needs the id, the cleanest way is: have the observe step write the id into `status.vpcId`, then have a second render step that emits the dependent MR using `dig "status" "vpcId" "" .observed.composite.resource`. The pipeline runs all render steps before the observe step, so split render into multiple steps when there are dependencies.

### 4.2 Connection secret from rendered resources

```yaml
connectionDetails:
  username:
    type: FromValue
    fromValuePath: status.atProvider.masterUsername
  password:
    type: FromConnectionSecretKey
    fromConnectionSecretKey: masterUserPassword
```

Use `FromValue` for top-level status fields. Use `FromConnectionSecretKey` to pass through secrets stored in a downstream provider's connection secret (RDS stores the master password in its connection secret).

### 4.3 Region / multi-account

Pass through to each MR's `forProvider.region`. If you want a default:

```yaml
{{ default "us-east-1" .observed.composite.resource.spec.region }}
```

For per-account `providerConfigRef`, look up the field from the claim or accept a passthrough:

```yaml
providerConfigRef:
  name: {{ .observed.composite.resource.spec.providerConfigName }}
```

### 4.4 Optional resources

Use the claim's optional fields and template the resource with a conditional:

```yaml
{{ if .observed.composite.resource.spec.logging }}
---
apiVersion: cloudwatchlogs.aws.upbound.io/v1beta1
kind: LogGroup
...
{{ end }}
```

### 4.5 Status block

Always populate status fields. The observe step is the only place to do it. If you set `status.ready: false` and skip the conditions, the XR will hang and you will not know why.

## 5. Discovering current CRD fields and previewing renders

CRDs evolve. Always check the installed version, and preview the function pipeline output locally before committing (you do not apply these directly — GitOps syncs them):

```sh
# Find the right CRD
kubectl get crd | grep -i rds | grep aws

# Dump the schema
kubectl get crd rds.aws.upbound.io -o jsonpath='{.spec.versions[0].schema.openAPIV3Schema}' | jq

# For a single field path
./scripts/get-crd-field.sh rds.aws.upbound.io .spec.forProvider.engine

# Preview what your function pipeline will produce (needs the crossplane CLI + Docker)
crossplane render xr.yaml composition.yaml functions.yaml

# Quick schema check without applying
kubectl apply --dry-run=client -f xrd.yaml
```

For the latest field set, check the upstream repo:
`https://github.com/crossplane-contrib/provider-upjet-aws/tree/main/examples` and the per-resource `.tf` files in `internal/clients/`.

For questions on `function-go-templating` syntax or context shape, web search `crossplane function-go-templating example` — the function's API has changed between minor versions.

Crossplane official docs referenced for this skill:
- Compositions (function pipeline, constraints): https://docs.crossplane.io/latest/composition/compositions/
- XR best practices (API design, versioning): https://www.upbound.io/blog/crossplane-xr-best-practices
- Configuring Crossplane with Argo CD (for the GitOps side): https://docs.crossplane.io/latest/guides/crossplane-with-argo-cd/

## 6. Common validation gotchas

- `status.ready: true` is computed but no conditions? Add them — controllers watch conditions, not just `ready`.
- `connectionDetails` references a path that does not exist on the MR? The XR will not publish a secret. `kubectl describe` will show no error; check the `connectionDetails` block of the XR.
- `crossplane.io/external-name` missing? Resource will be recreated on every reconcile. Always set it from a stable claim field.
- Indentation off by one space inside the `template: |`? YAML will parse but resources will have wrong fields. Render the template to a file and `kubectl apply --dry-run=client -f -` to validate.

### function-go-templating v0.12.x specifics

- **Observe step must emit a `kind: Result` Kubernetes resource**, not a bare YAML object. The template body is one or more `---`-separated manifests; the observe step produces a single `apiVersion: internal.crossplane.io/v1beta1, kind: Result` whose `.status` carries the conditions, connection details, and any status fields you want on the XR. Older guides show a bare `status: ... conditions: ... connectionDetails: ...` object — that form fails to parse in v0.12.x with `Object 'Kind' is missing`.
- **Every rendered resource needs the `gotemplating.fn.crossplane.io/composition-resource-name` annotation** set to a stable, unique key. Downstream steps read it via `.observed.resources.<key>`. The function renames this to `crossplane.io/composition-resource-name` in the output, but the input annotation key is the long form.
- **`.observed.resources` is `nil` on the first reconcile.** `index .observed.resources $key` panics with "index of untyped nil" on the first pass. Guard with `with`: `{{ with .observed.resources }}{{ with index . $key }}{{ dig "status" "atProvider" "arn" "" . }}{{ end }}{{ end }}`. Use this pattern when reading outputs of resources rendered in a prior step.
- **`ready: <boolean>` is a status field, not a condition.** Set both. The function-go-templating v0.12.x function's `Result` resource needs `status.ready` AND `status.conditions[].type=Ready,status=True/False` for the XR to report readiness correctly.
