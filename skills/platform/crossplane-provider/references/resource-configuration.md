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

### `IgnoredFields` — unconditional skip

Tells the late-initializer to never copy the field from TF state into spec:
```go
r.LateInitializer.IgnoredFields = []string{"address_prefix"}
```

This converts to `WithNameFilter` calls in the generated `LateInitialize()` method.
The generated code shows exactly which fields are skipped:

```go
func (tr *User) LateInitialize(attrs []byte) (bool, error) {
    params := &UserParameters{}
    if err := json.TFParser.Unmarshal(attrs, params); err != nil {
        return false, errors.Wrap(err, "failed to unmarshal Terraform state parameters for late-initialization")
    }
    opts := []resource.GenericLateInitializerOption{resource.WithZeroValueJSONOmitEmptyFilter(resource.CNameWildcard)}
    // Each ignored field becomes a WithNameFilter call:
    opts = append(opts, resource.WithNameFilter("DisableMfa"))
    opts = append(opts, resource.WithNameFilter("UnsupportedDdlAction"))
    li := resource.NewGenericLateInitializer(opts...)
    return li.LateInitialize(&tr.Spec.ForProvider, params)
}
```

It does NOT affect whether a user-set field value goes into `main.tf.json` —
user-set values are still written to the Terraform config and managed normally.

**For existing resources**, the CR spec must also be patched to remove the
stale field value — otherwise upjet still reads it from `spec.forProvider`
and includes it in `main.tf.json`. `IgnoredFields` doesn't strip fields
that are already set; it only prevents late-init from copying them in:
```shell
kubectl patch <resource>.<group>.<provider>.crossplane.io -n <ns> <name> \
  --type=json -p='[{"op": "remove", "path": "/spec/forProvider/unsupportedDdlAction"}]'
```

### `ConditionalIgnoredFields` — skip only when `initProvider` sets it

Skips late-init only when the field is already populated in
`spec.initProvider`. Useful when users supplying the field via
`initProvider` should prevent late-init from overwriting it, but leaving
it unset should still auto-fill from state:
```go
r.LateInitializer.ConditionalIgnoredFields = []string{"some_field"}
```

## Execution paths

Upjet has three execution paths for communicating with the Terraform plugin.
Which path a resource uses determines what config hooks are available:

| Path | Config list | Mechanism | Hooks available |
|------|------------|-----------|----------------|
| CLI subprocess | `IncludeList` (default `.+`) | Forks `terraform` binary,
  writes `main.tf.json` | None special |
| SDK in-process | `TerraformPluginSDKIncludeList` | Direct Go SDK calls
  (`RefreshWithoutUpgrade`, `Apply`) | `TerraformConfigurationInjector`,
  `TerraformCustomDiff` |
| Framework in-process | `TerraformPluginFrameworkIncludeList` | In-process gRPC
  (`ReadResource`, `ApplyResourceChange`) | `TerraformConfigurationInjector`,
  `TerraformPluginFrameworkIsStateEmptyFn` |

Resources are mutually exclusive across lists — matching more than one causes a
panic in `NewProvider()`. Resources matching none are silently skipped.

The `IncludeList` default of `.+` means every resource is CLI-path by default
unless explicitly added to an SDK or Framework include list.

### Detecting the execution path

Enable `-d` (debug) on the provider binary:
- **CLI path**: logs contain `terraform apply -refresh-only`, `terraform plan`,
  or similar subprocess calls.
- **SDK path**: no subprocess logs; uses in-process Go SDK directly.
- **Framework path**: no subprocess logs; uses in-process gRPC.

### `TerraformCustomDiff` (SDK path only)

Suppresses false diffs when the TF plugin computes zero-count `# = 0` for
unset optional blocks. Common in AWS resources with complex nested blocks:
```go
r.TerraformCustomDiff = func(diff *terraform.InstanceDiff, _ any, _ *schema.ResourceData) (*terraform.InstanceDiff, error) {
    delete(diff.Attributes, "enclave_options.#")
    delete(diff.Attributes, "metadata_options.#")
    return diff, nil
}
```

Framework resources compute diffs via gRPC `PlanResourceChange` — the
custom diff hook does not apply there.

## Sentinel default values

Some TF providers use sentinel Default values that fail the provider's own
validation. Common pattern: string fields defaulting to `"default"` with
`ValidateDiagFunc: validateBooleanString` (expects `"true"`/`"false"`), or
int fields defaulting to `-1` with `ValidateFunc: validation.IntAtLeast(0)`.

### Why sentinel defaults fail in upjet (timing gap)

In normal Terraform, the SDK applies the schema `Default` **after** `ValidateFunc`
runs — so the sentinel never reaches validation. The Snowflake provider depends
on this blind spot.

Upjet breaks this timing: the sentinel enters the config as a user-supplied
value through two distinct paths:
1. **LateInitializer feedback loop** (primary) — TF plugin's Create succeeds because
   the sentinel is applied after SDK validation inside the plugin binary. But the
   plugin writes the sentinel to TF state, and upjet's LateInitializer copies it
   into `spec.forProvider`. On the next reconcile, Terraform sees a user-supplied
   value and runs validation — which rejects the sentinel.
2. **Desired-state reconstruction** — when upjet reconstructs config for diff
   calculation after removing a field from `status.atProvider`, it reads the
   Go-side schema Default. Without the override, this re-introduces the sentinel.

The validation error (`expected ... to be one of ["true" "false"], got default`)
comes from the **TF SDK's own `ValidateFunc`**, not from upjet. Upjet adds no
stricter validation.

### The fix

Upjet's code generator NEVER reads `Default`/`DefaultFunc` from the TF schema.
The TF plugin binary has its OWN schema defaults that operate independently.
Sentinel values enter the system through the **TF state output** — the plugin
writes them to state after a successful Create, then the LateInitializer copies
them into `spec.forProvider`, creating a permanent validation loop on every
subsequent reconcile.

### Fix overview — path-dependent

The fix depends on which execution path the resource uses:

| Path | Config field | Injector works? | Only needs |
|------|-------------|----------------|------------|
| CLI subprocess (default) | `IncludeList` (default `.+`) | **No** | `IgnoredFields` only |
| SDK in-process | `TerraformPluginSDKIncludeList` | **Yes** | All three parts |
| Framework in-process | `TerraformPluginFrameworkIncludeList` | **Yes** | All three parts |

**Detection**: check the provider logs — CLI path shows `terraform apply
-refresh-only` subprocess calls. SDK/Framework paths show in-process calls with
no terraform binary invocation. Most resources use the CLI path by default
(`IncludeList` matches everything not in the other two lists).

### The universal fix: `LateInitializer.IgnoredFields` (all paths)

This is the **critical fix** for every execution path. Without it, the first
Create succeeds but every subsequent Observe fails because sentinel TF state
values leak back into `spec.forProvider`:

```go
r.LateInitializer.IgnoredFields = append(r.LateInitializer.IgnoredFields,
    "disable_mfa", "disabled", "must_change_password",
    "mins_to_bypass_mfa", "mins_to_unlock",
)
```

Field paths are Terraform snake_case names (e.g. `"disable_mfa"`); the pipeline
converts them to Go CamelCase for the `WithNameFilter` in generated code.

### Schema Default override (SDK/Framework paths only)

> **CLI-path resources:** This override is unnecessary when `IgnoredFields` is
> set. `IgnoredFields` prevents the late-initializer from copying sentinels
> into `spec.forProvider`, so those fields stay empty (and are omitted from
> `main.tf.json` via `omitempty`). The reconstruction path never sees them.
> The override is dead code for CLI-path resources with `IgnoredFields`.

For SDK/Framework-path resources, upjet reconstructs the desired Terraform
config for diff calculation after the LateInitializer strips sentinels from
`spec.forProvider`. Without the override, upjet reads `s.Default = "default"`
from its Go-side copy of the schema and re-introduces the sentinel.

Overriding to valid values prevents sentinels from leaking through that path:

```go
for _, tfKey := range []string{"disable_mfa", "disabled", "must_change_password"} {
    if s, ok := r.TerraformResource.Schema[tfKey]; ok {
        s.Default = "false"
        s.DefaultFunc = nil
    }
}
for _, tfKey := range []string{"mins_to_bypass_mfa", "mins_to_unlock"} {
    if s, ok := r.TerraformResource.Schema[tfKey]; ok {
        s.Default = 0
        s.DefaultFunc = nil
    }
}
```

### `TerraformConfigurationInjector` (SDK/Framework paths only)

The injector runs in `getExtendedParameters()` (SDK) /
`getFrameworkExtendedParameters()` (Framework) during `Connect()`, cleaning
the execution params before they reach the TF plugin. It does NOT run for the
CLI subprocess path. It guards against absent keys and sentinel values that the
user might have set in their CR:

```go
r.TerraformConfigurationInjector = func(jsonMap map[string]any, tfMap map[string]any) error {
    v, ok := jsonMap["disableMfa"]
    if !ok || v == "" || v == "default" {
        tfMap["disable_mfa"] = "false"
    }
    v, ok := jsonMap["minsToUnlock"]
    if !ok || v == -1.0 || v == -1 {
        tfMap["mins_to_unlock"] = 0
    }
    return nil
}
```

The injector receives two maps: `jsonMap` (CRD `spec.forProvider` via JSON tags,
camelCase keys) and `tfMap` (Terraform execution params, snake_case keys).
Guard against both the absent key (`!ok`) and the sentinel value itself
(`v == "default"`, `v == -1.0`) — a user might explicitly set the sentinel
value following Terraform docs.

### Error detection

```
observe failed: cannot run refresh: refresh failed: expected [...] to be
one of ["true" "false"], got default:
```

This error means the late-init feedback loop is active. Fix: add
`LateInitializer.IgnoredFields` for the fields listed in the error. If you've
added only the injector and the error persists, the resource uses the CLI path
(most do) and the injector is not being called.

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
