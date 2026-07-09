# Composition patterns

## 4.1 Multi-resource dependency

**Prefer a single render step with `*Ref` fields.** Crossplane resolves ordering via cross-resource references (queueUrlRef, queueArnRef, etc.) — resources that reference each other can emit together in one step. Use `.observed.resources` + `getResourceCondition` for conditional content (e.g. Deny→Allow policies based on readiness), never for emission gating:

```yaml
{{- $q := index $.observed.resources "queue-mine" }}
{{- $ready := false }}
{{- if $q }}{{- $ready = eq (getResourceCondition "Ready" $q).Status "True" }}{{- end }}
...
"Effect": "{{ if $ready }}Allow{{ else }}Deny{{ end }}",
"Resource": "{{ if $ready }}{{ dig "resource" "status" "atProvider" "arn" "" $q }}{{ else }}*{{ end }}"
```

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
