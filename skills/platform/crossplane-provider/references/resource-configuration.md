# Resource configuration

Fine-tuning a resource's behavior after generation. Referenced by the `wire`
and `add` branches when external name alone isn't enough.

## Cross-resource referencing

For fields that reference another managed resource:

```go
p.AddResourceConfigurator("aws_iam_access_key", func(r *config.Resource) {
    r.References["user"] = config.Reference{
        TerraformName: "aws_iam_user",  // preferred over deprecated Type field
    }
})
```

`TerraformName` is the Terraform resource name (e.g. `aws_iam_user`). Upjet
resolves it to the correct Go type across groups. This is more stable than the
deprecated `Type` field.

For cross-group references (e.g. KMS key from EBS volume):

```go
r.References["kms_key_id"] = config.Reference{
    TerraformName: "aws_kms_key",
}
```

The auto-reference generator covers most cases from scraped TF examples.
Explicit references are needed when:
- The scraped example doesn't include the dependency.
- The reference could target multiple resource types and the auto-generator
  picks only one, narrowing the pool.

### Removing auto-generated references

When the auto-generator picks a reference that's too narrow (the field could
reference multiple resource types), remove it explicitly:

```go
delete(r.References, "some_field")
```

## Sensitive fields and connection details

Fields marked `Sensitive: true` in the TF schema are auto-converted to
`*SecretRef` in the CRD spec. Their values are stored in the connection
details secret with keys prefixed `attribute.<field_name>`.

To add custom connection detail keys:

```go
r.Sensitive.AdditionalConnectionDetailsFn = func(attr map[string]any) (map[string][]byte, error) {
    conn := map[string][]byte{}
    if a, ok := attr["id"].(string); ok {
        conn["aws_access_key_id"] = []byte(a)
    }
    if a, ok := attr["secret"].(string); ok {
        conn["aws_secret_access_key"] = []byte(a)
    }
    return conn, nil
}
```

## Late initialization

Only needed when there are **conflicting arguments** in the TF config. Error
surfaces during testing:

```
observe failed: cannot run refresh: refresh failed: Invalid combination of
arguments: "address_prefix": only one of `address_prefix,address_prefixes`
can be specified
```

Fix by telling the late-init library to skip the conflicting field:

```go
r.LateInitializer.IgnoredFields = []string{"address_prefix"}
```

## Common resource options (AWS)

Real providers define reusable configurators via `ResourceOption` functions:

- `RegionRequired()` — makes `region` required for resources that have it
- `TagsAllRemoval()` — removes `tags_all` TF accumulator from schema
- `IdentifierAssignedByAWS()` — sets `config.IdentifierFromProvider` as default
- `NamePrefixRemoval()` — removes `name_prefix` from schema
- `KnownReferencers()` — auto-adds references for common field name patterns

Apply as a group:

```go
p.ConfigureResources(RegionRequired(), TagsAllRemoval(), ...)
```

## Custom templates (advanced)

Override code generation templates only when the defaults don't fit. Template
variables are documented in Upjet's docs but **not** covered by API
compatibility guarantees — overrides may break on minor upgrades.

| Template | Config option | File generated |
|---|---|---|
| Controller | `WithControllerTemplate` | `zz_controller.go` |
| Setup aggregator | `WithSetupAggregatorTemplate` | `zz_setup.go` |
| Terraformed | `WithTerraformedTemplate` | `zz_<resource>_terraformed.go` |
| Main | `WithMainTemplate` | `zz_main.go` per API group |

## Monitoring

Upjet-based providers expose Prometheus metrics on the default `/metrics`
endpoint:

| Metric | Type | Description |
|---|---|---|
| `upjet_terraform_cli_duration` | histogram | TF CLI invocation duration (labels: subcommand, mode) |
| `upjet_terraform_active_cli_invocations` | gauge | Active TF CLI invocations |
| `upjet_terraform_running_processes` | gauge | Running TF and provider processes |
| `upjet_resource_ttr` | histogram | Time-to-readiness per resource (labels: group, version, kind) |

Plus all standard controller-runtime metrics.

### API roundtrip testing

After wiring up conversion functions, verify serialization and conversion
cycles don't lose data:

```go
func TestRoundTrip(t *testing.T) {
    schema, err := xpprovider.GetProviderSchema(t.Context())
    rt, err := roundtrip.NewRoundTripTest(provider, providerNamespaced, testScheme)
    t.Run("TestSerializationRoundtrip", rt.TestSerializationRoundtrip)
    t.Run("TestConversionRoundtrip", rt.TestConversionRoundtrip)
}
```

Supports filters (`WithIncludeGroups`, `WithExcludeGroupKinds`), fuzzer
configuration (`FuzzerNilChance`, `FuzzerNumElements`), and comparison
options (`EquateEmptyAndSingleZeroSlice`, etc.).
