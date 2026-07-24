# Troubleshooting

Common failures when building and maintaining upjet providers, their root
causes, and fixes.

## Resource silently skipped — no CRD generated

**Symptom:** `make generate` completes successfully but a resource you configured
has no CRD, no controller, no `examples-generated/` output.

**Root cause:** The resource matched none of the three include lists:
`IncludeList` (CLI/fork), `TerraformPluginSDKIncludeList`, or
`TerraformPluginFrameworkIncludeList`. Upjet silently skips resources that
match no include list — they go into `p.skippedResourceNames`.

Also skipped:
- Resources with empty TF schema (`len(schema) == 0`)
- Resources matching `SkipList` regex patterns

**Fix:** Ensure the resource name appears in exactly one include list. A resource
matching more than one list causes a **panic**, not a skip.

## Late-init conflicts

**Symptom:** Error starting with `observe failed: cannot run refresh: refresh failed:`
followed by Terraform argument conflict messages like:
```
Invalid combination of arguments: "address_prefix": only one of
`address_prefix,address_prefixes` can be specified
```

**Root cause:** The late-initializer populates both sides of a mutually
exclusive argument pair from TF state. On the next reconcile, both are written
to `main.tf.json`, and TF validation rejects the combination.

**Fix:** Skip one side via `LateInitializer.IgnoredFields`:
```go
p.AddResourceConfigurator("azurerm_subnet", func(r *config.Resource) {
    r.LateInitializer = config.LateInitializer{
        IgnoredFields: []string{"address_prefix"},
    }
})
```

- **`IgnoredFields`**: TF field paths (dot-separated) unconditionally skipped.
- **`ConditionalIgnoredFields`**: Skipped only when already set in `spec.initProvider`.

Any unexpected `observe failed:` error after the parameters look correct is
likely a late-init conflict.

## Scraper produces broken provider-metadata.yaml

**Symptom:** After `make generate`, `config/provider-metadata.yaml` contains
entries like `resource Resource - provider:` instead of plain `resource:`.

**Root cause:** The scraper (`cmd/scraper`) falls back to the page title when
it finds no Terraform code blocks in the doc page. Resources without examples
in their TF docs produce malformed YAML keys.

**Fix:** Add a post-process `go:generate` line in `apis/generate.go`:
```go
//go:generate bash -c "sed -i 's/ Resource - terraform-provider-[a-z]*//g' ../config/provider-metadata.yaml"
```

## `make check-diff` fails (dirty tree after generate)

**Symptom:** CI fails with "There are uncommitted changes after running make generate."

**Root cause:** Generated files (`zz_*.go`, `package/crds/*.yaml`,
`examples-generated/*.yaml`) differ from what's committed. Every `make generate`
must produce an identical output to the committed state.

Common causes:
- Changed a resource config but didn't run `make generate` before committing.
- Updated `upjet` dependency without re-running generation.
- Manual edits to generated files (never edit `zz_*` or files under
  `package/crds/` or `examples-generated/` directly).

**Fix:** Run `make generate` and commit the diff. Never manually edit generated files.

## External name misconfiguration

**Symptom:** Resource creates but shows `status.atProvider.id` that looks wrong,
or the resource is destroyed and recreated on every reconcile.

**Root causes (in order of likelihood):**

1. **Wrong pattern** — `NameAsIdentifier` used where `ParameterAsIdentifier`
   belongs (or vice versa). The name vs. the spec field that IS the ID matter.
   Verify by reading the TF provider's `d.SetId()` call in the Create function.

2. **Compound ID with irregular quoting** — using `NameAsIdentifier` or a
   simple template for IDs like `"USER"|"TOKEN"` where the provider normalizes
   quotes internally. Check the provider's `Parse*Identifier` function.

3. **`IdentifierFromProvider` missing stub** — Framework resources with computed
   identifiers need a placeholder stub for initial reads. Use
   `FrameworkResourceWithComputedIdentifier` or
   `identifierFromProviderWithDefaultStub`.

## Framework/SDK include list mismatch

**Symptom:** Generator panics: "resource X is specified in more than one
include list."

**Root cause:** A resource name matches patterns in both
`TerraformPluginSDKIncludeList` and `TerraformPluginFrameworkIncludeList`
(or the CLI `IncludeList`).

**Fix:** Check the TF source for `// @SDKResource` or `// @FrameworkResource`
annotation and add the resource to exactly one list. Remove it from the others.

**Symptom (silent):** Resource added to wrong external name config map. SDK
resources go in `TerraformPluginSDKExternalNameConfigs`; Framework resources
go in `TerraformPluginFrameworkExternalNameConfigs`. The `ResourceConfigurator()`
looks up Framework first, then SDK, then CLI — putting a resource in the wrong
map means it never gets the config you wrote.

## Kind disambiguation

**Symptom:** Two TF resources that would generate the same Kind silently drop
one (no CRD for the second).

**Fix:** Set explicit `r.Kind` in the group configurator:
```go
p.AddResourceConfigurator("snowflake_legacy_service_user", func(r *config.Resource) {
    r.ShortGroup = "user"
    r.Kind = "LegacyServiceUser"
})
```
