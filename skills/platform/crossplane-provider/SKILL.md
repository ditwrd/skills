---
name: crossplane-provider
description: >
  Provider authoring. Builds and maintains a Crossplane provider from a Terraform provider via
  upjet. Use when scaffolding a new provider (greenfield), adding a Terraform
  resource, wiring external name configuration and cross-resource referencing,
  testing with uptest, migrating from classic providers, or managing CRD
  version upgrades and breaking changes. The existing 'crossplane' skill covers
  XRDs and Compositions (provider consumption); this skill covers provider
  authoring.
---

# Upjet-based Crossplane providers

An **upjet** provider wraps a Terraform provider into Crossplane managed
resources via code generation. The framework handles CRD generation, controller
wiring, Terraform state bridging, and late initialization.

When a pattern isn't covered here, study these reference providers:
- [provider-upjet-aws](https://github.com/crossplane-contrib/provider-upjet-aws)
  — SDKv2 and Framework external name patterns, `ResourceOption` helpers,
  tags handling, kind disambiguation. Check `config/externalname.go` and
  `config/<group>/config.go`.
- [provider-upjet-azure](https://github.com/crossplane-contrib/provider-upjet-azure)
  — Azure's fully-qualified ID patterns via `TemplatedStringAsIdentifier`,
  managed identity auth, `MoveToStatus` patterns.
For runtime errors: `references/troubleshooting.md`.

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
5. **Configure ProviderConfig setup** in `internal/clients/<name>.go` — map TF config keys from ProviderConfig secret to `ps.Configuration`. Define constants for each config field, then iterate with a conditional check:
   ```go
   const keyRegion = "region"
   const keyToken  = "token"
   const keyParams = "params" // TypeMap — JSON-encoded string in the secret

   var configKeys = []string{keyRegion, keyToken, keyParams}

   ps.Configuration = make(map[string]any, len(configKeys))
   for _, k := range configKeys {
       v, ok := creds[k]
       if !ok {
           continue
       }
       if k == keyParams {
           var params map[string]string
           if err := json.Unmarshal([]byte(v), &params); err != nil {
               return ps, errors.Wrap(err, "cannot unmarshal params as JSON map")
           }
           ps.Configuration[k] = params
       } else {
           ps.Configuration[k] = v
       }
   }
   ```
   The full set of config keys comes from the Terraform provider's schema docs or source (e.g. a `ConfigDTO` struct with `toml` tags). Only keys present in the secret are forwarded. **Non-string TF schema fields** (TypeMap, TypeList, TypeSet) arrive as JSON-encoded strings from the Kubernetes secret — special-case them with `json.Unmarshal` before setting on `ps.Configuration`. See the [upjet doc](https://github.com/crossplane/upjet/blob/main/docs/generating-a-provider.md#configure-the-provider-resources) for the base pattern.
6. **Add external name configs** in `config/externalname.go`. Only resources with a config are generated. See `references/external-name-patterns.md`.
7. **Create group configurators** `config/<scope>/<group>/config.go` — each exports `Configure(p *config.Provider)` setting `r.ShortGroup` and refs.

   **Preview vs stable families**: when the TF provider marks resources as "Preview" vs "Stable" via doc subcategory frontmatter, use separate ShortGroups (`user` vs `userpreview`) to isolate breaking changes. Preview resources live in their own API group — schema changes never touch the stable CRDs. When preview graduates, add a stable CRD with conversion from the preview version.
8. **Register** group configurators in `config/provider.go` — import the package, add to the `for range` loop in both `GetProvider()` and `GetProviderNamespaced()`.
9. **Run `make generate`** (requires `goimports` — `go install golang.org/x/tools/cmd/goimports@latest`; if `command not found`, add `$(go env GOPATH)/bin` to PATH). Verify `apis/`, `internal/controller/`, `package/crds/`, `examples-generated/`.
   The pipeline auto-generates `config/provider-metadata.yaml` from TF docs via `cmd/scraper`. Check this file — resources with **no example code blocks** produce broken YAML keys (e.g. `resource Resource - provider:` instead of `resource:`). The scraper falls back to the page_title when no terraform code blocks are found. Fix by adding a post-scraper `go:generate` line in `apis/generate.go`:
   ```go
   //go:generate bash -c "sed -i 's/ Resource - terraform-provider-[a-z]*//g' ../config/provider-metadata.yaml"
   ```
10. **Stage examples** from `examples-generated/` to `examples/<group>/<scope>/v1beta1/`. Add dependent resources (secrets, provider config refs).
11. **Test** — see [test-resource](#test-resource--manual-and-automated-testing).
12. **Run `make reviewable`** (generates, lints, and runs unit tests) before pushing — same as the CI pipeline. If `check-diff` fails, `make generate` produced uncommitted changes.

### add — add a new resource

Add a single Terraform resource to an existing upjet provider (brownfield).

Completion criterion: resource generates, compiles, and passes manual or automated testing.

1. **Find the Terraform resource** on the Terraform Registry. Read the import
   section (determines external name format) and argument reference (required fields, ref targets, conflicting arguments).
2. **Determine plugin type** from TF source: `// @SDKResource` or `// @FrameworkResource`.
3. **Add external name config** in the correct config map:
   - **`// @SDKResource`** → `TerraformPluginSDKExternalNameConfigs`. Use the four
     standard patterns: `IdentifierFromProvider`, `NameAsIdentifier`,
     `ParameterAsIdentifier`, `TemplatedStringAsIdentifier`.
   - **`// @FrameworkResource`** → `TerraformPluginFrameworkExternalNameConfigs`.
     Framework resources need additional handling for computed identifiers.
     See `references/external-name-patterns.md` Framework section for
     `FrameworkResourceWithComputedIdentifier`, `identifierFromProviderWithDefaultStub`,
     and `frameworkNameAsIdentifier`.
   See `references/external-name-patterns.md` for all patterns with runtime flow,
   examples, and verification guidance.
   
   For resources with compound or quoted ID formats (e.g. `"USER"|"TOKEN"` or `DB|SCHEMA|POLICY|USER`), verify the config by checking the TF provider's ID parsing code (search for `Parse*Identifier` in the provider source). If the provider normalizes quotes, `NameAsIdentifier` is safe. For pipe-separated IDs with irregular quoting across segments, prefer `IdentifierFromProvider` — templating the format is fragile and breaks if the provider changes internal ID conventions.
   ```go
   "aws_redshift_endpoint_access": config.ParameterAsIdentifier("endpoint_name"),
4. **Run `make generate`**. Verify generated files: `apis/`, `internal/controller/`,
   `package/crds/`, `examples-generated/`. If a resource is silently skipped,
   `check-diff` fails, or the scraper produces broken YAML, see
   `references/troubleshooting.md`.
5. **Handle warning boxes** — if a field is also a separate TF resource (e.g.
   `route` on `azurerm_iothub`), move to status: `config.MoveToStatus(r.TerraformResource, "route")`.
6. **Stage example** from `examples-generated/` to `examples/`. Add dependent
   resources, verify with `kubectl apply --dry-run=client`.

   For `NameAsIdentifier` resources, the generated example may show
   `forProvider: {}` because upjet only uses the first scraped example and
   `name` is in `OmittedFields`. The name comes from `metadata.name` at
   runtime. Stage a richer example manually if needed.
7. **Add cross-resource references** if auto-generator missed them. See
   `references/resource-configuration.md`.
8. **Commit** — message: `Configure <Resource>.<group> and add example`.
9. **Run `make reviewable`** before pushing.

### wire — resource configuration

Fine-tune a resource's behavior after generation. See
[`references/resource-configuration.md`](references/resource-configuration.md)
for details on all of the following:

1. **Cross-resource referencing** — `r.References["field"] = config.Reference{TerraformName: "..."}`.
   Auto-generator covers most cases from scraped TF examples.
2. **Sensitive fields / connection details** — auto-handled for `Sensitive: true`
   fields; add custom keys via `r.Sensitive.AdditionalConnectionDetailsFn`.
3. **Late init** — `r.LateInitializer.IgnoredFields` for conflicting TF arguments.
4. **Common options** — define `ResourceOption` functions, apply via
   `p.ConfigureResources(RegionRequired(), TagsAllRemoval(), ...)`.
5. **Custom templates** — override generation templates (controller, setup,
   terraformed, main) only when defaults don't fit.
6. **Monitoring** — Prometheus metrics at `/metrics` (upjet + controller-runtime).
7. **Kind disambiguation** — when two TF resources generate the same Kind (e.g. `snowflake_service_user` and `snowflake_legacy_service_user` both auto-generate `ServiceUser`), the pipeline silently drops one. Fix with explicit `r.Kind` in the group configurator:
   ```go
   p.AddResourceConfigurator("snowflake_legacy_service_user", func(r *config.Resource) {
       r.ShortGroup = "user"
       r.Kind = "LegacyServiceUser"
   })
   ```

### test-resource — manual and automated testing

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

**Bump version** when: field renames/removals, type changes, new required fields.
**No bump** for: optional new fields, additional enum values, TF-defaulted fields.

```go
r.Version = "v1beta1"
r.PreviousVersions = []string{"v1alpha1"}
r.Conversions = []config.Conversion{{FromVersion: "v1alpha1", ToVersion: "v1beta1", ConvertFn: convertV1Alpha1ToV1Beta1}}
```

See `references/upgrade.md` for auto-conversion (schemadiff) and upjet v1→v2 migration details.

### migrate — classic to upjet migration

Convert managed resources, compositions, and claims from a classic provider to
an upjet-based provider. Uses converters registered per `schema.GroupVersionKind`.

Key tasks: group/kind renames, field renames/type changes, external name format
changes, composition patch conversion.

See `references/migration.md` for converter registration, sources, and targets.

