# Composition patterns

## 4.1 Multi-resource dependency

:**Prefer a single render step with `*Ref` fields.** Crossplane resolves ordering via cross-resource references (queueUrlRef, queueArnRef, etc.) — resources that reference each other can emit together in one step. When a policy needs another resource's ARN, read it from observed state with nil-guard and emit unconditionally:

```yaml
{{- $obs := default (dict) $.observed.resources }}
{{- $data := dig "queue-mine" (dict) $obs }}
{{- $arn := dig "resource" "status" "atProvider" "arn" "" $data }}
"Effect": "Allow",
"Resource": "{{ $arn }}",
```
The `*Ref` field (e.g. `queueUrlRef`) ensures Crossplane creates the dependency first, so `$arn` is populated by the time the policy resource is applied. No conditional Deny/Allow needed. `getResourceCondition` is not needed — the `*Ref` handles ordering.

When `*Ref` fields can't express the dependency (e.g. needing a computed value that isn't a Ref target), split render into multiple `function-go-templating` steps:
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

## 4.2 Connection details

**Prefer `writeConnectionSecretToRef` on the managed resource.** Most upjet providers support this field — set it on the resource that produces connection details (Queue, RDS Instance, etc.). The provider creates and manages the Secret automatically. No nil-guard, no encoding needed:

```yaml
writeConnectionSecretToRef:
  name: {{ .observed.composite.resource.metadata.name }}-conn
```

**When `writeConnectionSecretToRef` isn't available**, compose a v1/Secret manually. In v2 there is no `connectionSecretKeys` on the XRD:

`endpoint`/`username`/`password` are already base64 when read from `connectionDetails`, so the outer `| b64enc` is correct for putting them in a `Secret.data` field (which requires base64). If you instead read raw `status.atProvider.*` values, use `| b64enc` to encode them.

**Alternative: use `stringData`** for raw values that aren't already base64. Kubernetes accepts `stringData` on Secret create/update and automatically encodes to `data`. This avoids manual `| b64enc` when reading from `status.atProvider` fields. Always emit the key with a default empty value to keep the Secret shape stable across reconciles:

```yaml
stringData:
{{ range $i, $queue := $queues }}
  queueUrls-{{ $i }}: {{ dig "status" "atProvider" "url" "" (index $.observed.resources "queue-{{ $i }}") }}
{{ end }}
```

**Never use `toJson` on a list inside `stringData`.** `toJson` produces a JSON array (`["url1","url2"]`) that Crossplane's typed patch reinterprets as `[]interface{}` instead of a string, failing with `expected string, got array`. Use individual keys per queue index or `join ","` to produce a scalar string.
When to use each: `data` + `| b64enc` for `connectionDetails` values (already base64). `stringData` for raw values from `status.atProvider.*` or computed Go template output. Do not mix — either all `data` or all `stringData` on a single Secret.


## 4.3 Region / multi-account

Pass through to each MR's `forProvider.region`. If you want a default:

```yaml
{{ default "us-east-1" .observed.composite.resource.spec.region }}
```

For per-account `providerConfigRef`, look up the field from the XR or accept a passthrough:

```yaml
providerConfigRef:
  name: {{ .observed.composite.resource.spec.providerConfigName }}
```

For `*.m.upbound.io` providers, `ProviderConfig` is `Namespaced` scope and `ClusterProviderConfig` is cluster-scoped. Use `ClusterProviderConfig` when multiple namespaces need the same credentials (avoids the cross-namespace trap). Use `ProviderConfig` only when the ProviderConfig is in the same namespace as the managed resource. The `kind` field is required on every `providerConfigRef` — omitting it fails with `spec.providerConfigRef.kind: Required value`.

## 4.4 Optional resources

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

## 4.5 Status fields and custom conditions

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

## 4.6 Cross-XR references (status copy)

If one XR needs another's status fields, declare the reference on the consuming XR's spec (e.g. `spec.networkRef.name`) and use `function-status-transformer` to copy the referenced XR's `status.<field>` into the consumer's `status` (or `spec`). This is the v2 replacement for reading the connection secret of a referenced v1 claim.

## 4.7 Deletion lifecycle: orphaning

`deletionPolicy` (default `Delete`) lives on each **composed managed resource**, not on the composition or XR. When the XR is deleted, Crossplane GC deletes the composed MRs; each MR's policy decides whether the provider deletes the external (`Delete`) or leaves it running (`Orphan`).

**Native compositions cannot orphan Kubernetes-native resources.** `deletionPolicy` is unrenderable on a raw CR emitted by a go-templating step (crossplane#7146) — the XR delete force-deletes it. To orphan k8s-native resources, compose them through **provider-kubernetes `Object` MRs**. Two variants exist — a namespaced one (`kubernetes.m.crossplane.io/v1alpha1`, pairs with Namespaced v2 XRDs) and a cluster-scoped one (`kubernetes.crossplane.io/v1alpha2`, shown below); they orphan through different mechanisms, see the mapping after the example:

```yaml
apiVersion: kubernetes.crossplane.io/v1alpha2
kind: Object
metadata:
  annotations:
    {{ setResourceNameAnnotation "cluster" }}
spec:
  providerConfigRef:
    name: default
    kind: ProviderConfig
  readiness:
    policy: DeriveFromObject  # mirrors the wrapped object's Ready condition
  forProvider:
    manifest:
      apiVersion: postgresql.cnpg.io/v1
      kind: Cluster
      metadata:
        name: {{ $name }}
      # ... full object spec indented here
  deletionPolicy: Orphan
```

Scope/group mapping — the orphan mechanism differs by variant (verified against the live CRDs, don't mix them):

- **`kubernetes.crossplane.io/v1alpha2` `Object` is cluster-scoped and HAS `deletionPolicy`.** Its config group defines only `ProviderConfig` (cluster-scoped) — `providerConfigRef.kind: ProviderConfig`.
- **`kubernetes.m.crossplane.io/v1alpha1` `Object` is namespaced and has NO `deletionPolicy` field** (spec offers only `managementPolicies`). Orphan there = omit `Delete` from `managementPolicies`:
  ```yaml
  managementPolicies: [Observe, Create, Update, LateInitialize]  # Delete omitted = orphan
  ```
  Its `providerConfigRef` takes `kind: ClusterProviderConfig` (cluster-scoped, shared across namespaces, the standard `in-cluster` config) or a namespaced `ProviderConfig`.
- **`providerConfigRef` MUST always set `kind`.** On the `.m.` Object the CRD marks `[kind, name]` required and the schema default is suppressed once the object is partially set — composing only `name: in-cluster` passes xprin green but fails live with `spec.providerConfigRef.kind: Required value` on every composed MR.

Readiness: `DeriveFromObject` for the long-running wrapped object (mirrors its `Ready` condition); leave the default (`SuccessfulCreate`) on static objects — Secrets, RBAC — which are Available as soon as created.

Operational consequences once Orphan fires (claim deleted):

- **Every composed MR object is gone.** Cleanup tooling must target *externals*: plain `kubectl` for k8s-native externals, the provider's cloud CLI for externals that are not k8s objects (e.g. an upjet EKS PodIdentityAssociation MR orphans to a bare AWS association — delete it with `aws eks delete-pod-identity-association`, not kubectl).
- **Mid-deletion gate**: XR/claim absent but the composed MRs still present means GC is in flight — wait until `kubectl get objects.kubernetes.m.crossplane.io -A | grep <name>` is empty before touching externals. Bare `objects` polls the wrong kind, so always qualify `.m.`. GC is not instant: the XR finalizer holds until the wrapped MRs settle their no-delete semantics (observed ~4–5 min for a full backup graph), so poll, don't assume.
- Orphan is **per-resource**: orphaning the main resource while dependents cascade-delete strands a half-alive graph. Apply the orphan mechanism to every composed resource that must survive — `deletionPolicy: Orphan` on v1alpha2 Objects, `managementPolicies` minus `Delete` on `.m.` Objects — across the whole graph (e.g. Cluster + Archive + ScheduledBackup + Secrets + RBAC).
- **Legacy-adopted externals keep old ownership.** A claim migrated onto a `.m.` executor from a composition that wrote ownerRefs/`crossplane.io/*` fields directly onto externals keeps those fields: the `.m.` composed controller never writes them and does not strip them on adoption. Deleting such a legacy claim can cascade-delete the externals (k8s GC on the ownerRef) instead of orphaning. Gate on ownerReferences before trusting orphan semantics on adopted claims.
- **Verify the orphan design with a throwaway XR before trusting it on a real claim.** Create an XR mirroring the real spec in an isolated namespace, let it reach Ready, delete it, then assert the externals survive with **zero** Crossplane ownership: no `crossplane.io/*` labels, no annotations, no ownerRefs on the wrapped objects. Only then does an orphan gate count as passed.
