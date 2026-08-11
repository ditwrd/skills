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


## Upjet framework dependency version bump

Bumping `upjet`/`crossplane-runtime`/`controller-runtime` itself (not a CRD
schema version) has compatibility traps go.mod semver ranges don't surface:

1. **Don't trust the newest semver git tag as the safe upgrade target.**
   A tag can sit on a branch that diverged from `main` *before* a needed
   migration landed — verify with
   `git merge-base --is-ancestor <tag> <main-commit>` in both directions;
   mutually non-ancestor means divergent branches, not just "older". The
   reliable target: clone
   [`crossplane/upjet-provider-template`](https://github.com/crossplane/upjet-provider-template)
   (the reference scaffold Crossplane maintainers keep in sync with upjet's
   real integration status) and read
   `git log --oneline --since=<date-this-repo-was-last-bumped>` for the exact
   go.mod pins it resolved to — often a pseudo-version *past* the tag (e.g.
   `v2.4.1-0.20260728103920-4f6e6e10dff2`, not `v2.4.1`). Apply the template's
   exact `go get` pins (upjet, crossplane-runtime/v2, crossplane/apis/v2,
   crossplane-tools) rather than picking versions independently.
2. **Don't trust upjet's declared minimum crossplane-runtime version.** Grep
   the target upjet tag's actual codegen import paths (`pkg/types`) against a
   clone — a newer crossplane-runtime can delete packages upjet's generated
   code still imports (e.g. `apis/common/v1|v2` moved to
   `crossplane/apis/v2/core/v2` in crossplane-runtime v2.3.x) even though
   upjet's own go.mod floor is untouched.
3. **Re-pin k8s.io/api, apimachinery, client-go, apiextensions-apiserver to
   controller-runtime's tested set after any `go get`.** A transitive bump
   past that set breaks controller-runtime's cache package (e.g. a missing
   `HasSyncedChecker` method) even when nothing in the main module changed.
4. **Pin `crossplane-tools` to an exact version, not `@latest`.** It's a
   codegen-only tool (`//go:build generate` in `apis/generate.go`, needed for
   the angryjet step of `make generate`), but its own transitive deps can
   silently re-inflate the k8s.io pins from step 3.
5. **A failed `make generate` mid-run leaves the tree half-deleted** (it wipes
   `apis/`, `internal/controller/`, `examples-generated/`, `package/crds/`
   before regenerating). Restore with
   `git checkout -- apis/ internal/ examples-generated/ package/` before
   retrying rather than patching a partial tree.
6. **v2.3.0 removed `StartWebhooks` from `tjcontroller.Options`**, replacing
   it with generated `SetupWebhookWithManager(mgr)` aggregates per group in
   each `zz_setup.go`. Fix requires two edits:
   - `cmd/provider/main.go`: call the new aggregate functions directly
     (gated on `*certsDir != ""`), remove the old `StartWebhooks` field.
   - Add a no-op `func SetupWebhookWithManager(_ ctrl.Manager) error { return nil }`
     stub to every hand-written, non-generated controller package registered
     in that aggregate loop (e.g. a custom `providerconfig` package) — the
     generated aggregate calls it unconditionally on every sub-package, so
     the build fails with `undefined: <pkg>.SetupWebhookWithManager` otherwise.