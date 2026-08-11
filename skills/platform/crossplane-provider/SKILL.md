---
name: crossplane-provider
description: >
  Scaffolds or extends a Crossplane provider from a Terraform provider
  via code generation. Use when scaffolding a new provider (greenfield),
  adding a resource, configuring a resource, testing, debugging a
  broken resource, migrating from classic providers, upgrading CRD
  versions, or bumping the upjet/crossplane-runtime dependency version.
---
# Upjet-based Crossplane providers

An **upjet** provider wraps a Terraform provider into Crossplane managed
resources via code generation. The framework handles CRD generation, controller
wiring, Terraform state bridging, and late initialization.

When a pattern isn't covered, study the reference providers:
[provider-upjet-aws](https://github.com/crossplane-contrib/provider-upjet-aws) (SDKv2/Framework patterns),
[provider-upjet-azure](https://github.com/crossplane-contrib/provider-upjet-azure) (ARM ID patterns),
[provider-upjet-gcp](https://github.com/crossplane-contrib/provider-upjet-gcp) (GCP path templates).

See [`references/provider-patterns.md`](references/provider-patterns.md) for a
side-by-side comparison of how each provider handles external names, including
provider-specific helpers, template formats, and pattern frequency.
For runtime errors: `references/troubleshooting.md`. Provider-specific
incident notes (e.g. Snowflake): `references/snowflake-provider-notes.md`.
## Branches

Every upjet workflow starts at the Terraform Registry. The resource's **import
section** and **argument reference** determine almost everything you configure.

### greenfield — scaffold a new provider

Generate a new Crossplane provider from a Terraform provider using the
[upjet-provider-template](https://github.com/crossplane/upjet-provider-template).

Completion criterion: provider generates, compiles, and can reconcile one resource end-to-end.

1. **Create repo from template.** Click "Use this template" on `crossplane/upjet-provider-template`. Name `provider-<name>`.
2. **Init submodules:** `make submodules` fetches `crossplane/build`.
3. **Run prepare:** `./hack/prepare.sh` prompts for provider name/group.
4. **Set Makefile vars:** `TERRAFORM_PROVIDER_SOURCE`, `_REPO`, `_VERSION`, `_DOWNLOAD_NAME`, `_NATIVE_PROVIDER_BINARY`, `_DOCS_PATH`.
5. **Configure ProviderConfig setup** in `internal/clients/<name>.go` — iterate known config keys from the ProviderConfig secret, forward to `ps.Configuration`. Non-string schema fields (TypeMap, TypeList, TypeSet) arrive JSON-encoded — decode with `json.Unmarshal` before setting. See the [upjet doc](https://github.com/crossplane/upjet/blob/main/docs/generating-a-provider.md#configure-the-provider-resources) for the base pattern.
6. **Add external name configs** in `config/externalname.go`. Only resources with a config are generated. See `references/external-name-patterns.md`.
7. **Create group configurators** `config/<scope>/<group>/config.go` — each exports `Configure(p *config.Provider)` setting `r.ShortGroup` and refs.

   **Preview vs stable families**: two ShortGroup strategies — per-family groups
   (resource isolation, many groups) or 2-group model (`stable`/`preview`, simpler
   to maintain). Choose based on family size vs API isolation needs.
8. **Register** group configurators in `config/provider.go` — import the package, add to the `for range` loop in both `GetProvider()` and `GetProviderNamespaced()`.
9. **Run `make generate`** (requires `goimports` — `go install golang.org/x/tools/cmd/goimports@latest`; if `command not found`, add `$(go env GOPATH)/bin` to PATH). Verify `apis/`, `internal/controller/`, `package/crds/`, `examples-generated/`. If the scraper produces broken YAML keys, see `references/troubleshooting.md`.
10. **Stage examples** from `examples-generated/` to `examples/<group>/<scope>/v1beta1/`. This is typically a straight copy — generated examples already have correct API group refs (`<provider>.crossplane.io`) and no `-TODO` cleanup. Verify counts match:
    ```shell
    for d in cluster/stable cluster/preview namespaced/stable namespaced/preview; do
      printf "  %-25s %3d\n" "$d" $(ls "examples-generated/$d/v1alpha1/" 2>/dev/null | wc -l)
    done
    ```
    Add dependent resources (secrets, provider config refs) after copying.
11. **Test** — see [test-resource](#test-resource--manual-and-automated-testing).
12. **Run `make reviewable`** (generates, lints, and runs unit tests) before pushing — same as the CI pipeline. For providers with 130+ resources this takes ~3 minutes (generate ~140s, lint ~60s, test ~100s). If `check-diff` fails, `make generate` produced uncommitted changes.

### add — add a new resource

Add a single Terraform resource to an existing upjet provider (brownfield).

Completion criterion: resource generates, CRD compiles, and example stages with `kubectl apply --dry-run=client`.

1. **Find the Terraform resource** on the Terraform Registry. Read the import
   section (determines external name format) and argument reference (required fields, ref targets, conflicting arguments).
2. **Default to the no-fork (in-process) path** — faster than CLI-fork (no
   subprocess spawn, no `main.tf.json` round-trip) and unlocks
   `TerraformConfigurationInjector`/`TerraformCustomDiff`. From TF source:
   `// @SDKResource` → `TerraformPluginSDKIncludeList`; `// @FrameworkResource`
   → `TerraformPluginFrameworkIncludeList`. Stay on the CLI path only per the
   exceptions in
   `references/resource-configuration.md#decision-which-path-for-a-new-brownfield-resource`
   (import fails cleanly, or provider isn't wired for no-fork yet and
   migrating it is out of scope — see
   `references/resource-configuration.md#provider-wide-no-fork-in-process-migration`).
3. **Add external name config** in the correct config map:
   - **`// @SDKResource`** → `TerraformPluginSDKExternalNameConfigs`
   - **`// @FrameworkResource`** → `TerraformPluginFrameworkExternalNameConfigs`

   **Decision tree** — see `references/external-name-patterns.md` for the full
   pattern decision tree with runtime flows, Framework config, and compound ID
   edge cases. Key patterns: `IdentifierFromProvider` (provider assigns ID),
   `TemplatedStringAsIdentifier` (compound with separator),
   `NameAsIdentifier` (user name IS the ID),
   `ParameterAsIdentifier("field")` (a spec field IS the ID).
   Always trace `d.SetId()` in the TF Create function to verify the runtime ID.
4. **Check TF schema for sentinel defaults** — scan optional fields whose
   Default would fail the provider's own `ValidateFunc`/`ValidateDiagFunc`.
   See `references/resource-configuration.md#sentinel-default-values`. All
   paths need `LateInitializer.IgnoredFields` (critical — without it every
   reconcile after the first Create fails); the no-fork path additionally
   needs a schema Default override and `TerraformConfigurationInjector`
   (CLI-path resources skip both — `IgnoredFields` alone suffices there).
5. **Run `make generate`**. Verify generated files: `apis/`, `internal/controller/`,
   `package/crds/`, `examples-generated/`. If a resource is silently skipped,
   `check-diff` fails, or the scraper produces broken YAML, see
   `references/troubleshooting.md`.
6. **Handle warning boxes** — if a field is also a separate TF resource (e.g.
   `route` on `azurerm_iothub`), move to status: `config.MoveToStatus(r.TerraformResource, "route")`.
7. **Stage example** from `examples-generated/` to `examples/`. For multi-scope providers (cluster + namespaced), stage to both `examples/cluster/<group>/v1alpha1/` and `examples/namespaced/<group>/v1alpha1/`. Add dependent resources (secrets, provider config refs), verify with `kubectl apply --dry-run=client`.

   For `NameAsIdentifier` resources, `forProvider: {}` in generated examples is
   normal — `name` is in `OmittedFields`, populated from `metadata.name` at runtime.
8. **Add cross-resource references** if auto-generator missed them. See
   `references/resource-configuration.md`.
9. **Commit** — message: `Configure <Resource>.<group> and add example`.
10. **Run `make reviewable`** before pushing.

### wire — resource configuration

Fine-tune a resource's behavior after generation. See
[`references/resource-configuration.md`](references/resource-configuration.md)
for details on all of the following:

Completion criterion: each listed concern is addressed or explicitly deferred.

1. **Cross-resource referencing** — `r.References["field"] = config.Reference{TerraformName: "..."}`.
   Auto-generator covers most cases from scraped TF examples. Zero `r.References` entries is normal for a fresh provider — the auto-generator may detect references from HCL interpolation and handle them at runtime rather than through Go-level config.
2. **Sensitive fields / connection details** — auto-handled for `Sensitive: true`
   fields; add custom keys via `r.Sensitive.AdditionalConnectionDetailsFn`.
3. **Late init** — `IgnoredFields` for conflicting TF arguments and sentinel
   defaults; `ConditionalIgnoredFields` for fields skipped only when
   `spec.initProvider` already sets them. Late-init copies cloud-provider
   default values into `spec.forProvider` for unset fields, preventing
   perpetual drift. The error signal is `observe failed: cannot run refresh:
   refresh failed:`. See `references/resource-configuration.md#late-initialization`
   for config details and `references/troubleshooting.md#late-init-conflicts`
   for the error pattern.
4. **Diff suppression** — `r.TerraformCustomDiff` suppresses false diffs when TF computes zero-count for unset blocks (SDK path only). `ResourceDiff.Clear`/`.SetNew` inside it only work on `Computed: true` fields — for a ForceNew field Read() never re-sets, see `references/troubleshooting.md`.
5. **Move to status** — `config.MoveToStatus(r.TerraformResource, "field")`
   moves sub-resource-managed fields out of the desired spec.
6. **Pre-reconcile init** — `r.InitializerFns` for custom logic that runs
   before reconciliation (e.g., setting tags from provider metadata).
7. **Config injection** — `r.TerraformConfigurationInjector` for injecting
   values the JSON→TF deserialization drops (SDK/Framework paths only).
8. **Common options** — define `ResourceOption` functions, apply via
   `p.ConfigureResources(RegionRequired(), TagsAllRemoval(), ...)`.
9. **Custom templates** — override generation templates only when defaults
   don't fit. See `references/resource-configuration.md#custom-templates`.
10. **Kind disambiguation** — if two TF resources generate the same Kind,
    the pipeline silently drops one. See `references/troubleshooting.md`.

### test-resource — manual and automated testing
Completion criterion: resource reconciles (SYNCED+READY=True) and passes import survival test.


#### Manual test
> **Warning:** Never change `crossplane.io/external-name` on an existing reconciled resource. See `references/external-name-patterns.md` for details.

1. Apply CRDs: `kubectl apply -f package/crds`
2. Create ProviderConfig with valid credentials
3. Start provider: `make run` (or IDE with `-d`)
4. Apply example: `kubectl apply -f examples/<group>/<scope>/v1beta1/<resource>.yaml`
5. Verify `kubectl get managed -A` — all `SYNCED` and `READY` are `True`
6. Check UpToDate: annotate `upjet.upbound.io/test=true` — all `Test` condition `True`
7. Import test: stop provider → delete conditions → restart → verify same `status.atProvider.id`
8. Delete test: `kubectl delete <resource>.<group>.<provider>.upbound.io/...`

#### Automated test (uptest)

Trigger via PR comment: `/test-examples="examples/redshift"` (file or group).
Do NOT trigger cluster+namespaced variants in parallel (same resource).
Skip resources with annotation `upjet.upbound.io/manual-intervention`.
Run locally: `make uptest-local PROVIDER_NAME=provider-aws EXAMPLE_LIST="..."`.

Debug: `kubectl get <resource> -o yaml`, provider logs (`-d`), GitHub Action artifacts.
See [`references/resource-configuration.md`](references/resource-configuration.md) for API roundtrip testing.

### upgrade — CRD versions and breaking changes

When the underlying Terraform provider schema changes.

Completion criterion: new CRD version generates, conversion compiles, existing resources still reconcile.

**Bump version** when: field renames/removals, type changes, new required fields.
**No bump** for: optional new fields, additional enum values, TF-defaulted fields.

```go
r.Version = "v1beta1"
r.PreviousVersions = []string{"v1alpha1"}
r.Conversions = []config.Conversion{{FromVersion: "v1alpha1", ToVersion: "v1beta1", ConvertFn: convertV1Alpha1ToV1Beta1}}
```

See `references/upgrade.md` for auto-conversion (schemadiff), upjet v1→v2
migration, and upjet dependency version bumps (compat pinning across
crossplane-runtime/controller-runtime/k8s.io, and the v2.3.0 webhook wiring
change) details.

### migrate — classic to upjet migration

Convert managed resources, compositions, and claims from a classic provider to
an upjet-based provider. Uses converters registered per `schema.GroupVersionKind`.

Completion criterion: converter compiles and produces correct target YAML.

Key tasks: group/kind renames, field renames/type changes, external name format
changes, composition patch conversion.

See `references/migration.md` for converter registration, sources, and targets.

