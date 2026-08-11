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

Any unexpected `observe failed:` error with argument conflict messages
(`only one of`, `can be specified`) is likely a late-init conflict.
Errors with `expected [...] to be one of [...], got default:` or
`expected [...] to be at least (0), got -1:` are likely sentinel default
values — see [Sentinel default values](resource-configuration.md#sentinel-default-values)
in resource configuration.

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

## Resource stuck in constant update loop / false diff

**Symptom:** Resource shows `SYNCED: True, READY: True` but reconciles every
poll interval with an update. No user change triggered it.

**Root causes:**

1. **Zero-count optional blocks (SDK path)** — The TF plugin computes a
   non-empty diff for unset optional blocks (`# = 0` in state vs `# = 0` in
   config — treated as change). Common with computed nested blocks.

2. **Config-vs-state field mismatch (all paths)** — A single field differs
   between `main.tf.json` and `terraform.tfstate` (e.g. case mismatch
   between a TF schema default like `"ignore"` and what Snowflake returns
   like `"IGNORE"`). The TF provider either lacks a `DiffSuppressFunc` for
   this field or the CLI path doesn't use it.

3. **Case normalization by cloud API** — Snowflake (and other APIs) may
   normalize string values to uppercase. If the TF schema default is
   lowercase, the config has one case and the state another, producing a
   perpetual diff.

**Detection:** Enable `-d` (debug) on the provider and check the diff output
for `# = 0` attributes or fields you didn't change.

For CLI-path resources (the default), compare `main.tf.json` against
`terraform.tfstate` attribute by attribute to spot single-field mismatches.
The workspace path appears in the debug log on the `Running terraform` line:
```shell
# Replace WS with the workspace UUID from the debug log
WS=/tmp/<workspace-uuid>
python3 -c "
import json
with open('$WS/main.tf.json') as f:
    config = json.load(f)
with open('$WS/terraform.tfstate') as f:
    state = json.load(f)

# Extract resource attributes from config (skip meta-args)
config_attrs = {}
for _, cfg in config.get('resource',{}).get('<tf_resource_type>',{}).items():
    config_attrs = {k:v for k,v in cfg.items()
        if k not in ('provider','_meta','lifecycle')}

# Extract resource attributes from state
state_attrs = {}
for r in state.get('resources',[]):
    for inst in r.get('instances',[]):
        state_attrs = inst.get('attributes',{})

# Print only mismatched fields
for k in sorted(set(state_attrs.keys()) & set(config_attrs.keys())):
    sv, cv = state_attrs.get(k), config_attrs.get(k)
    if sv != cv:
        print(f'{k}: state={repr(sv)}  config={repr(cv)}')
"
```

### Fixes

#### SDK path: `TerraformCustomDiff` for zero-count blocks

Add a `TerraformCustomDiff` that removes the zero-count diff entries:
```go
r.TerraformCustomDiff = func(diff *terraform.InstanceDiff, _ any, _ *schema.ResourceData) (*terraform.InstanceDiff, error) {
    delete(diff.Attributes, "enclave_options.#")
    delete(diff.Attributes, "metadata_options.#")
    return diff, nil
}
```

This is a per-resource SDK path fix. Framework resources may need a
different approach (the in-process gRPC path computes diffs differently).

Using `config.MoveToStatus(r.TerraformResource, "field")` as an alternative
moves the field entirely to `status.atProvider`, keeping it out of the diff.

#### CLI path: `LateInitializer.IgnoredFields` (all paths)

For case-normalization mismatches and other config-vs-state field diffs, add
the mismatched field to `IgnoredFields`. This prevents the late-initializer
from copying the field into `spec.forProvider`, keeping it empty. Upjet omits
empty fields when building `main.tf.json`, so terraform never sees a config
value for the field, treats it as computed-only, and never plans a diff:
```go
r.LateInitializer.IgnoredFields = append(r.LateInitializer.IgnoredFields,
    "unsupported_ddl_action",
)
```

**For existing resources**, the CR spec must also be patched to remove the
stale field value — otherwise upjet still reads it from `spec.forProvider`
and includes it in `main.tf.json`:
```shell
kubectl patch <resource>.<group>.<provider>.crossplane.io -n <ns> <name> \
  --type=json -p='[{"op": "remove", "path": "/spec/forProvider/unsupportedDdlAction"}]'
```

This triggers a spec change, upjet regenerates `main.tf.json` without the
field, and the loop stops on the next reconcile.


### Computed status field loop (XRM violation)

**Symptom:** Resource reconciles every poll interval with a diff on a
`status.atProvider` field (not a `spec.forProvider` field). The field is
computed/read-only in the Terraform schema but the TF provider's
**customize diff** function recomputes it based on a spec field. Diff log
shows `NewComputed:true` or `NewRemoved` on status-only keys. Common when a
sub-aspect has a dedicated Terraform resource (e.g. `app_role` on an
Application also managed by `application_app_role`).

**Root cause:** The Crossplane Resource Model (XRM) requires one owner per
aspect. Putting a field in `spec.forProvider` grants ownership to that
resource. If a separate resource also manages the same aspect, two controllers
claim ownership — the XRM violation. The TF provider's customize diff
function (called during `terraform plan`) recomputes a computed status field
based on the spec field, producing a perpetual diff at the HCL/plugin layer
that upjet's reconciler can't filter. Late-initialization can't intercept it
because the diff happens below the CRD struct layer.

**Fix:** Move the field to status, delegating its management to the dedicated
resource.
```go
config.MoveToStatus(r.TerraformResource, "app_role")
```
This is a **breaking API change** — existing manifests with the field in
`spec.forProvider` will fail. Announce in release notes. Users migrate to the
dedicated resource.

**Detection:** The provider debug log shows `Diff detected` on status-field
keys every cycle. Check the TF provider source code for a `customizeDiff`
function that references the computed field. If the field has a dedicated TF
resource, it belongs in status, not spec.

**Prevention:** Before adding a field to `spec.forProvider`, check if the TF
provider has a separate resource for the same sub-aspect. The upjet
[adding-new-resource](https://github.com/crossplane/upjet/blob/main/docs/adding-new-resource.md)
guide flags this as "Warning boxes" — fields mutually exclusive with other
resources should use `MoveToStatus`.


## Resource permanently refuses update — ForceNew field never re-populated by Read()

**Symptom:** `Synced=False` forever (not a perpetual-but-harmless update loop —
every reconcile hard-fails), error:
```
async update failed: refuse to update the external resource because the
following update requires replacing it: cannot change the value of the
argument "X" from "" to "false"
```
No user ever changed `X` in `spec.forProvider` — it may not even appear there.

**Root cause:** `X` is `ForceNew` in the TF schema, but the vendored
provider's `Read` function never calls `d.Set("X", ...)` on refresh — only its
`Import` function derives `X` (typically parsed from the resource's own
compound ID). Confirm by reading the TF provider source: compare the
`Read*`/`Import*` functions for the resource; if `Read*` sets fewer fields
than `Import*` sets, this is the bug. Every reconcile, upjet's diff-vs-state
computation sees `X` as permanently unset (`Old:""` in the raw
`terraform.InstanceDiff`, visible with `-d`) versus the config-resolved
default — and since `X` is ForceNew, upjet's `assertNoForceNew` guard refuses
the update forever. Distinct from
[Update blocked by lifecycle.prevent_destroy](#update-blocked-by-lifecycleprevent_destroy):
that case has no Update function at all; this resource has one, but one field
is falsely flagged as changing.

**Two dead ends — verify against a real running provider, not just unit
tests, before trusting either:**

1. A `managed.Initializer` (`r.InitializerFns`) backfilling `status.atProvider`
   before Observe only fixes the **cold-cache** case (right after a provider
   restart). Upjet's `terraformPluginSDKExternal` only reconstructs its
   Terraform state seed from `atProvider` in `Connect()` when its per-resource
   operation-tracker cache (`OperationTrackerStore`) is empty. Once a resource
   is created (or observed) once in a running process, that cache stays warm
   for the process's lifetime and every later `Observe` seeds its diff from
   the cached (still-incomplete) state, bypassing `atProvider` entirely. A fix
   that passes right after `make run` and fails on a freshly-created resource
   in the same still-running process is this trap.
2. `TerraformCustomDiff` reaching for `ResourceDiff.Clear(key)` or
   `.SetNew(key)` fails immediately — both require the schema field to be
   `Computed: true` (a hard `checkKey()` error in
   `terraform-plugin-sdk/v2` otherwise). Most fields hit by this bug are
   `Optional + Default + ForceNew`, not `Computed`, so this natural first
   instinct is a dead end.

**Fix:** Wrap `r.TerraformResource.ReadContext` — a mutable function field on
the already-live `*schema.Resource`, set once at provider-config time
(`AddResourceConfigurator`/`WithDefaultResourceOptions`), not a vendored
source edit:
```go
p.AddResourceConfigurator("some_resource", func(r *config.Resource) {
    orig := r.TerraformResource.ReadContext
    r.TerraformResource.ReadContext = func(ctx context.Context, d *schema.ResourceData, meta any) diag.Diagnostics {
        diags := orig(ctx, d, meta)
        if diags.HasError() || d.Id() == "" {
            return diags // real error, or upstream deletion — nothing to backfill
        }
        // Backfill X the same way Import derives it (e.g. parsed from d.Id()).
        _ = d.Set("X", deriveXFromID(d.Id()))
        return diags
    }
})
```
This works for both cache states: upjet's `Observe()` diffs against the state
returned by `RefreshWithoutUpgrade` — which invokes `ReadContext` — computed
**after** the refresh and **before** the diff call. The wrapped `Read`
therefore corrects the seed on every reconcile, whether `Connect()`
reconstructed it from `atProvider` or reused the warm operation-tracker cache.

## Out-of-band changes absorbed by late init, not reverted

**Symptom:** You change a resource field via the cloud console/UI (not the CR).
The provider observes the change (`status.atProvider` updates) but does NOT
revert it — the new value persists and eventually appears in
`spec.forProvider` too. You expected the provider to enforce the original CR
value.

**Root cause:** Upjet's late initializer copies the observed state into
`spec.forProvider` for fields that are empty/unset in the CR. After the
out-of-band change:
1. Observe detects the new value in TF state.
2. Late init copies it into `spec.forProvider` (the field was previously empty).
3. Spec now matches state — no diff detected. No revert.

Upjet only manages fields that have **explicit non-empty values** in
`spec.forProvider`. Empty/unset fields are treated as "don't care" — the
provider accepts whatever the cloud API returns.

**Fix:** To enforce a specific value (including empty), set it explicitly in
`spec.forProvider`. This puts it in `main.tf.json`, making Terraform manage
it and revert drift on every reconcile.

```yaml
spec:
  forProvider:
    defaultRole: "SOME_ROLE"  # explicitly managed → drift reverted
```

To enforce an empty/unset value, the field must be explicitly managed. For
some fields, this may require setting them to `""` or a sentinel value that
the TF provider interprets as "no value" — check the TF provider's behavior
for the specific field.

**See also:**
[`references/resource-configuration.md#ignored-fields`](resource-configuration.md#late-initialization)
for how `IgnoredFields` can prevent this auto-sync on specific fields.

## Execution path detection (CLI vs SDK vs Framework)

**Symptom:** A resource config option (`TerraformConfigurationInjector`,
`TerraformCustomDiff`, etc.) doesn't take effect despite being set correctly
in Go code and the provider rebuilding.

**Root cause:** The option only fires in certain execution paths. See
`references/resource-configuration.md#execution-paths` for which hooks fire
where.

**Detection:** Check provider logs with `-d` flag:
- **CLI path** (default, `IncludeList`): logs show `terraform apply
  -refresh-only`, `terraform plan`, etc. — actual subprocess calls.
- **SDK in-process** (`TerraformPluginSDKIncludeList`): no subprocess logs;
  calls `RefreshWithoutUpgrade` and `Apply` directly via Go SDK.
- **Framework in-process** (`TerraformPluginFrameworkIncludeList`): no
  subprocess logs; calls `ReadResource`, `ApplyResourceChange` via gRPC.

Most resources use the CLI path by default unless explicitly moved to SDK
or Framework include lists. If a resource doesn't appear in any include
list, it's skipped silently.

## Provider panics at startup after moving resources to SDK/Framework path

**Symptom:** Provider binary panics immediately on boot after adding
`WithTerraformPluginSDKIncludeList(...)` (or Framework equivalent) to
`config/provider.go`. Panic message references a resource matching more
than one include list.

**Root cause:** `NewProvider()` defaults `IncludeList` to `[]string{".+"}`
(match-all) independent of any other list you set. Adding
`TerraformPluginSDKIncludeList`/`TerraformPluginFrameworkIncludeList`
without also setting `WithIncludeList([]string{})` makes every listed
resource match both — a hard error, not a skip.

**Fix:** Explicitly set `ujconfig.WithIncludeList([]string{})` whenever
`IncludeList` should stop matching anything (i.e. when moving resources
wholesale off the CLI path — the recommended default). See
`references/resource-configuration.md#provider-wide-no-fork-in-process-migration`.

## Reconcile fails with "cannot configure terraform provider" (no-fork path)

**Symptom:** Every resource on `TerraformPluginSDKIncludeList` fails
Observe/Create with an unconfigured-provider error, even though
`ProviderConfig` credentials are valid and CLI-path resources in the same
provider work fine.

**Root cause 1:** `TerraformSetupBuilder` builds `ps.Configuration` but
never calls `ujprovider.TerraformProvider.Configure(...)` /
`.Meta()` — the CLI path never needed this (the `terraform` binary
configures itself), but the in-process path does.

**Root cause 2:** `cmd/provider/main.go` calls `config.GetProvider()`
twice — once for `tjcontroller.Options.Provider`, once for the setup
builder — producing two independent `*schema.Provider` instances.
Configuring one never sets `.Meta()` on the other, since generated
controllers read `o.Provider.Resources[name]` from the instance passed to
`Options`.

**Fix:** Call `GetProvider()`/`GetProviderNamespaced()` exactly once per
scope in `main.go`; pass that same pointer to both `Options.Provider` and
`TerraformSetupBuilder(...)`. See
`references/resource-configuration.md#provider-wide-no-fork-in-process-migration`.


## Config changes not reflected after code edit

**Symptom:** You edit config Go code (`TerraformConfigurationInjector`,
`LateInitializer`, references, etc.), `go vet` and `go build` pass, but the
resource still exhibits the old behavior. The fix compiles but doesn't take
effect.

**Root cause:** The running provider binary in `_output/bin/linux_amd64/provider`
is stale. `make run` rebuilds on restart, but a direct `go build ./cmd/provider`
places the binary elsewhere. The provider must be rebuilt and restarted.

**Fix:**
1. `pkill -f "provider.*<provider-name>"`
2. `go build -o _output/bin/linux_amd64/provider ./cmd/provider/...`
3. `make run` (or run the binary directly with the required flags)
4. If a resource is stuck in deletion with a finalizer, force-remove it:
   `kubectl patch <resource> -n <ns> -p '{"metadata":{"finalizers":[]}}' --type=merge`
5. Re-apply the example from the clean manifest

**Prevention:** After any `config/` Go change, always rebuild and restart the
provider. A `go vet ./config/...` alone is not sufficient.

To verify a config option produced the expected effect, check the generated
`zz_*_terraformed.go` files in `apis/`. For example, `IgnoredFields` produces
`WithNameFilter` calls in `LateInitialize()` — if the filter is missing from
the generated code, the config change wasn't picked up (re-run `make generate`
and rebuild).

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

## Mutually exclusive TF schema fields both set — one silently dropped

**Symptom:** A resource with sibling optional fields inside one block (e.g.
two mutually exclusive "target" fields such as an "all matching objects"
field and a "future matching objects" field) reconciles to
`Synced=True Ready=True`, but only one of the two intended behaviors
actually took effect — e.g. the "future" variant never appears in the cloud
provider, even though the CR spec requests it.

**Root cause:** The Terraform schema marks the sibling fields
`ExactlyOneOf` (grep the vendored provider source for the field name to find
the constraint list). The generated CRD carries no equivalent validation, so
`kubectl apply` accepts both fields set in the same block. The provider's
internal build-switch (whatever code turns the block into a TF/API request)
takes the first matching case in source order and ignores the rest — no
error, no diff, just a quietly incomplete request.

**Detection:** Read the TF resource source for `ExactlyOneOf`/`ConflictsWith`
entries covering the block in question; compare against the applied YAML. If
more than one of the listed fields is set, this bug applies regardless of
what the status conditions say.

**Fix:** Split into one resource per exclusive variant — one resource per
field, never both set in the same block. If the repo already has an
analogous split for a sibling resource, mirror its naming convention.

**Prevention:** When wiring or reviewing a resource whose schema has
`ExactlyOneOf`/`ConflictsWith` groups, treat CRD field presence as
*unenforced advice*, not validation — the same gap as unvalidated enum-style
string fields (see
[External name misconfiguration](#external-name-misconfiguration) and
[Delete fails with empty identifier](#delete-fails-with-empty-identifier-after-patching-a-bulk-grant-resource-under-deletion)
for related CRD-validation-gap bugs). Add an admission-time check only if this
repeatedly bites; otherwise document the constraint in the example/README.

## Delete fails with empty identifier after patching a bulk-grant resource under deletion

**Symptom:** A bulk/wildcard-target resource (a grant, attachment, or
similar resource whose spec targets "all"/"future" matching objects rather
than one named object) is stuck with `deletionTimestamp` set and a `Delete`
error mentioning an empty or malformed identifier, e.g.
`incompatible identifier: ` or similar "identifier is empty/invalid" text.
This typically follows a `spec.forProvider` patch applied to the resource
**while it already had a `deletionTimestamp`** (e.g. to fix an invalid value
caught only at apply/delete time — see
[External name misconfiguration](#external-name-misconfiguration) for the
class of bug that often triggers the patch in the first place).

**Root cause:** The vendored TF provider's `Read` function is a documented
no-op for the "all"/"future" bulk-target configuration of this resource (grep
the source near the refresh/show-request builder for a comment like "read is
a no-op for this configuration" or "changes will not be detected"). Patching
the spec changes upjet's computed Terraform ID mid-flight; the next `Observe`
refreshes state under the new ID, but the no-op `Read` never repopulates the
resource's identifying fields, so the refreshed state comes back empty.
`Delete` then builds its revoke/detach request from that empty state and
fails parsing an empty identifier.

**Detection:** Compare `metadata.annotations['crossplane.io/external-name']`
(frozen at creation), `status.atProvider.id` (mirrors external-name), and
current `spec.forProvider`. If external-name/status still hold the pre-patch
value while spec holds the patched value, and the resource is a bulk/wildcard
grant kind with a documented no-op `Read`, this bug applies.

**Fix:** Not recoverable via the provider's own Delete path — the tracked TF
state is already corrupted. Force-remove the finalizer:
```shell
kubectl patch <resource>.<group>.<provider> -n <ns> <name> \
  --type=merge -p '{"metadata":{"finalizers":[]}}'
```
Acceptable when the underlying grant/attachment was created with an
already-invalid value (the intended revoke was never going to succeed
cleanly anyway); follow up with manual cleanup on the provider's side if
needed.

**Prevention:** Never patch `spec.forProvider` on a bulk/wildcard grant kind
that already has `deletionTimestamp` set — delete and recreate with the
corrected spec instead, so the new resource gets a fresh ID with no
state-desync window. Also note: CRD string fields that mirror free-text TF
schema arguments carry **no enum validation** even when the TF provider only
accepts specific literal forms — a successful `kubectl apply` proves nothing
about API-level correctness; verify against the TF provider's argument
reference. For a concrete instance of this bug (Snowflake's
`on_all`/`on_future` grant kinds and the `objectTypePlural` enum gap), see
[`snowflake-provider-notes.md`](snowflake-provider-notes.md#delete-fails-with-empty-identifier-after-patching-an-on_all-on_future-grant-under-deletion).


## Update blocked by lifecycle.prevent_destroy

**Symptom:** The resource's `status.conditions` shows `Synced=False` with a
message like:
```
observe failed: cannot run plan: plan failed: Instance cannot be destroyed:
Resource <type>.<name> has lifecycle.prevent_destroy set, but the plan calls
for this resource to be destroyed.
```

If the error instead says `refuse to update the external resource ... cannot
change the value of the argument` (no `lifecycle.prevent_destroy` mention),
see
[Resource permanently refuses update — ForceNew field never re-populated by Read()](#resource-permanently-refuses-update--forcenew-field-never-re-populated-by-read)
instead — that resource has an Update function; one field is falsely flagged
as changing.

**Root cause:** Upjet unconditionally sets `"prevent_destroy": true` in the
generated Terraform HCL for every resource that is NOT currently being deleted
(deletion timestamp unset) — see upjet's `pkg/terraform/files.go`. This is an
intentional safety guard: it prevents accidental destroy+recreate on spec
changes.

The error fires when a spec field change causes Terraform's plan to show
destroy+create instead of an in-place update. This happens for any resource
whose TF provider has **no Update function** (only Create and Delete — e.g.
grant/attachment resources like account-role grants, IAM policy attachments,
or role associations). The only way to "update" such a resource in
Terraform is to destroy the old and create a new one.

**Detection:** Read the error from the resource's Synced condition:
```shell
kubectl get <resource>.<group> -n <ns> <name> -o jsonpath='{.status.conditions[?(@.type=="Synced")].message}'
```
The raw Terraform error is in there.

**Fix options (no provider-side code change possible):**

1. **Delete and recreate** — delete the MR (sets `WasDeleted=true`, clearing
   `prevent_destroy`), then recreate with the new spec fields. Terraform
destroys the old resource (REVOKE) and creates the new one (GRANT).

2. **Revert the spec** — change the spec fields back to match the existing
   Terraform state (visible in `status.atProvider`). The plan shows no change,
   and the resource resumes normal reconciliation.

**Upjet reference:** upjet's `docs/testing-with-uptest.md` documents this as a
known error case under "prevent_destroy Case".

## `CannotUpdateManagedResource` warning — benign resourceVersion conflict

**Symptom:** A Warning event with reason `CannotUpdateManagedResource` and
message `Operation cannot be fulfilled on <resource>.<group> "<name>": the
object has been modified; please apply your changes to the latest version and
try again`. `Synced`/`Ready` remain (or return to) `True`.

**Root cause:** This is `crossplane-runtime`'s managed reconciler
(`pkg/reconciler/managed/reconciler.go`, `reasonCannotUpdateManaged`) losing a
standard Kubernetes optimistic-concurrency race: it read the object, did
work, then tried its own `client.Update` (writing a finalizer, an
external-name/late-init annotation, or the spec) — but something else
(another `kubectl apply`/`patch`, a concurrent reconcile) bumped
`resourceVersion` first. Every call site that emits this reason returns
`Requeue: true` — it is not a reconcile failure, just a retry signal.

**Detection:** Reason string alone disambiguates it from a real failure —
`CannotUpdateExternalResource` (or any `async create/update/delete failed`
message) means the Terraform/cloud-API call itself failed;
`CannotUpdateManagedResource` means only the local Kubernetes object write
raced. Confirm by checking `event.count`/`lastTimestamp` against any manual
`kubectl apply`/`patch` issued around the same second, and verifying the
resource is `Synced=True Ready=True` on the next `kubectl get`.

**Fix:** None needed — it self-heals on the next requeue. If it recurs
continuously (not just around a manual edit), suspect two controllers or two
reconcile loops racing the same object, not this benign case.

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

**Detection before generating:** Compute the auto-generated Kinds and check for
duplicates:
```shell
# List all resource names and their PascalCase Kinds:
# Kind = PascalCase(full_resource_name after stripping provider prefix)
python3 -c "
import yaml
with open('config/provider-metadata.yaml') as f:
    data = yaml.safe_load(f)
for name in sorted(data.get('resources', {})):
    stripped = name.replace('<tf_provider_prefix>_', '', 1)  # e.g. "aws_", "azurerm_", "snowflake_"
    kind = ''.join(p.capitalize() for p in stripped.split('_'))
    print(kind, name)
" | sort | uniq -d   # --repeated shows collisions
```
Compare within each ShortGroup — cross-group collisions are safe (different
API groups). Also check generated CRDs for `_2` file name suffix, which upjet
appends to the second Kind on collision.

**Fix:** Set explicit `r.Kind` on BOTH the cluster and namespaced configurators:
```go
p.AddResourceConfigurator("<tf_resource_name>", func(r *config.Resource) {
    r.ShortGroup = "user"
    r.Kind = "LegacyServiceUser"
})
```

## Go `internal` package collision

**Symptom:** `golangci-lint` fails with `use of internal package .../stable/internal not allowed`.
Make generates successfully, but lint fails because the generated package can't be imported.

**Root cause:** A TF resource name contains `internal` (e.g.
`<provider>_stage_internal`). The generator produces a package directory
`internal/` inside the controller tree. Go's `internal` visibility rule blocks
imports from sibling packages — the `zz_setup.go` at
`internal/controller/namespaced/` can't import from
`internal/controller/namespaced/stable/internal/`.

**Detection:** After generating CRDs, check for CRD filenames with
`internals` as the resource plural:
```shell
ls package/crds/*_internals.yaml
```

**Fix:** Override the Kind to a name that doesn't lower-case to `internal`:
```go
p.AddResourceConfigurator("<tf_resource_name>", func(r *config.Resource) {
    r.ShortGroup = shortGroup
    r.Kind = "StageInternal"
})
```
Apply to BOTH `config/cluster/<group>/config.go` and
`config/namespaced/<group>/config.go`, then `make generate` (after cleaning
stale `apis/` dirs that still reference the old Kind).
