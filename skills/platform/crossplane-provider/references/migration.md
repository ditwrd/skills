# Classic to upjet migration

Convert managed resources, composites, and claims from a classic Crossplane
provider (e.g. community/legacy) to an upjet-based provider.

## Architecture

The migration framework has four components:

- **Converters** — per-resource functions that transform one schema to another.
  Three types: `Resource` (MR conversion), `ComposedTemplate` (composition
  template conversion), `PatchSets` (composition patch-set conversion).
- **Registry** — maps `schema.GroupVersionKind` to its converter functions.
- **Source** — reads manifests (filesystem or Kubernetes cluster).
- **Target** — writes converted manifests (filesystem only).

## Converter registration

```go
registry.RegisterAPIConversionFunctions(
    ec2v1beta1.VPCGroupVersionKind,
    ec2.VPCResource,
    migration.DefaultCompositionConverter(nil, common.ConvertComposedTemplateTags),
    common.DefaultPatchSetsConverter,
)
```

## Common conversion tasks

- **Group/Kind renames** — e.g. `ec2.aws.crossplane.io` → `ec2.aws.upbound.io`
- **Field renames** — different json path names between classic and upjet APIs
- **Type changes** — e.g. integer→float64, struct→slice-of-struct (upjet wraps
  all nested structs in slices)
- **External name format changes** — different conventions between providers
- **Composition patches** — convert patch paths, transforms, and patch sets

## Key functions

The `Resource` converter returns zero or more target MRs (one source MR may
split into multiple target MRs). `CopyInto` handles safe field copying with
`skipFieldPaths` for fields that changed incompatibly.

Composition converters are inherently user-specific since every composition is
different. The `DefaultCompositionConverter` handles field path remapping via
a `conversionMap`.

## Sources and targets

- **Filesystem source**: read local files or cloned repos
- **Kubernetes source**: read live resources from cluster (by category or by registered GVK)
- **Multiple sources**: supported via `migration.WithMultipleSources(sources...)`
- **Target**: always filesystem (writes converted YAML manifests)
