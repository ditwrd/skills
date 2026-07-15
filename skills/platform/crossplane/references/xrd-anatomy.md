# XRD anatomy (v2)

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

## Claim schema design rules

- **Required fields sparingly** — once a field is required in a published version you cannot remove it. Prefer optional with a `default`.
- **Prefer enums over booleans** — booleans box you in. For API evolution, a string enum (`speed: Regular | Fast | Slow`) lets you add values without a new version. Exception: debug toggles and simple feature flags (`debug: true`) are fine as booleans — they are binary by nature and won't grow new values.
- **Prefer arrays over scalars** — if `spec.widget: "foo"` might become `spec.widgets: ["foo", "bar"]` later, start with the array. A single-element array is fine; an array you can extend is much cheaper than a breaking version bump.
- **Leave room for variants** — if you might support MySQL *and* PostgreSQL under one XR, put engine-specific fields in nested objects (`spec.postgresql`, `spec.mysql`) toggled by a top-level `spec.engine` enum. Avoid a flat schema that needs you to add top-level fields per engine.
- **Versions are not a magic escape hatch** — two CRD versions are two views into the same data, and they must round-trip. You can rename or move fields; you cannot drop a previously required field, or add a new required field, without breaking older XRs. Invest in backward-compatible evolution instead of new versions.
- **Use `anyOf` for safe schema migrations** — when a field type must change (e.g., `string` → `object`), wrap both formats in `anyOf`. This keeps existing XRs reconcilable through the composition controller's SSA validation, which validates against the new schema. Remove the old type from `anyOf` once all XRs have been updated.
