# CRD version upgrades and breaking changes

## When to bump

**Requires a bump** (breaking changes): field renames/removals, type changes,
singleton→list conversion, new required fields.

**No bump needed** (backward compatible): optional new fields, additional enum
values, TF-defaulted fields (defaults applied at runtime, not in CRD schema).

## Version bump procedure

```go
r.Version = "v1beta1"
r.PreviousVersions = []string{"v1alpha1"}
r.Conversions = []config.Conversion{
    {FromVersion: "v1alpha1", ToVersion: "v1beta1", ConvertFn: convertV1Alpha1ToV1Beta1},
}
```

The hub version (default: `r.Version`) is the central conversion point for
all spoke versions. Storage version persists in etcd.

## Breaking change detection (auto-conversion)

Upjet can auto-detect and register conversions when the Terraform provider
schema changes:

1. **Add schemadiff** to `generate/generate.go` after CRD generation:
   ```go
   //go:generate go run github.com/crossplane/upjet/v2/cmd/schemadiff -i ../package/crds -o ../config/crd-schema-changes.json
   ```

2. **Embed the JSON** in `config/provider.go`:
   ```go
   //go:embed crd-schema-changes.json
   var crdSchemaChanges []byte
   ```

3. **Wire in GetProvider()** — Phase 1 excludes type-changed fields from
   identity conversion; Phase 2 handles provider-specific version bumping;
   Phase 3 registers auto-conversions:
   ```go
   ujconfig.ExcludeTypeChangesFromIdentity(pc, crdSchemaChanges)
   // bumpVersionsWithEmbeddedLists(pc)
   ujconfig.RegisterAutoConversions(pc, crdSchemaChanges)  // skip during codegen
   ```

Handles: field additions/deletions (annotation-based preservation), type
changes (string↔number↔bool), singleton list↔embedded object conversions.

## Upjet v1 → v2 upgrade

Upjet v2 introduces namespaced MRs alongside legacy cluster-scoped ones:

- Move `apis/` → `apis/cluster/`, create `apis/namespaced/`
- Update API group markers: `yourprovider.crossplane.io` → `yourprovider.m.crossplane.io`
- Add `ClusterProviderConfig` type to namespaced API group
- Add `SetupGated` variants for controller registration (gates startup behind CRD availability)
- Implement kind-aware ProviderConfig resolution (legacy MRs → legacy PC, modern → modern)
- Add `SafeStart` capability
- Deduplicate config between cluster and namespaced scopes
