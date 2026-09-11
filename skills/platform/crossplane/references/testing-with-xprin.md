# Testing with xprin

`crossplane render` is a one-shot preview. For multi-case CI tests (assertions, golden files, hooks), use [xprin](https://github.com/crossplane-contrib/xprin) — a pure-Go test runner that wraps `crossplane render` into declarative YAML test suites (`*_xprin.yaml`). Runs locally with Docker; no cluster required.

```bash
# Install
curl -sL https://raw.githubusercontent.com/crossplane-contrib/xprin/main/install.sh | COMPRESSED=true VERIFY_SHA=true sh
# Verify deps
xprin check   # needs `crossplane` on PATH and a Docker daemon
# Run
xprin test tests/mycomp_xprin.yaml -v --show-render
xprin test examples/... -q       # CI mode: exit code only
```

## Pin engine version with `.xprin.yaml`

Place `.xprin.yaml` at the project root. Without it, the engine inside Docker and the host CLI disagree on feature behaviour and produce odd errors. The `subcommands.render` and `subcommands.validate` entries must pin `--crossplane-version=vX.Y.Z` to match the installed crossplane CLI:

```yaml
# .xprin.yaml
subcommands:
  render: render --include-full-xr --crossplane-version=v2.3.1
  # crossplane CLI v2.3.x has no `beta validate` subcommand — drop `crds:` from
  # tests, or override `validate:` with a subcommand that exists in your CLI:
  # validate: validate --crossplane-version=v2.3.1
```

## Test suite shape

`functions:` accepts either form:
- **A directory** of single-doc Function YAMLs (one per file). Each file is a `Function` resource.
- **A multi-doc YAML** (single file with `---` separators) — works fine as long as the path is **relative**, not absolute.

In a multi-module repo, share one `provider/function.yaml` at the repo root instead of duplicating per module. One bump there updates the whole toolchain, and `mise.toml` at the repo root pins the toolchain version.

```yaml
# tests/mycomp_xprin.yaml
tests:
  - name: "vpc + subnets produces 6 resources"
    inputs:
      xr: example-xr.yaml                                       # sibling under tests/
      composition: ../composition.yaml
      functions: ../../../../provider/function.yaml             # shared multi-doc function file
    assertions:
      xprin:
        - { type: Count, value: 6 }
        - { type: Exists, resource: "VPC/my-vpc" }
        - { type: Exists, resource: "Subnet/public" }
        - { type: Exists, resource: "Subnet/private" }
        - { type: Exists, resource: "InternetGateway/my-igw" }
        - { type: Exists, resource: "RouteTable/public" }
        - { type: Exists, resource: "RouteTableAssociation/public" }
      diff:
        - { name: "matches golden", expected: golden/vpc-and-subnets.yaml }
```

For a single-module repo where you don't share, a directory of single-doc files also works:

```
mycomp/
  functions/
    function-go-templating.yaml   # apiVersion: pkg.crossplane.io/v1, kind: Function
    function-auto-ready.yaml
  tests/
    s3-nq_xprin.yaml             # functions: ../functions/
```

**Relative path depth for `functions:`** — from a test file at `tests/`, count directory segments to repo root. Each `/../` removes one segment: `tests/` → `<thing>/` → `<category>/` → `modules/` → repo root = 4. Always use `../../../../provider/function.yaml` regardless of `modules/aws/` vs `modules/vault/`. Miscount and xprin fails with `functions file or dir not found` — the error message shows the resolved path to diagnose the depth.

## Two-reconcile test pattern

For compositions where step 2+ reads `$.observed.resources` from step 1, one test pass is not enough — step 2's nil-guard fires on the first reconcile and you never see the dependent resources emit. Use two test cases that mirror the two reconciles:

```yaml
# tests/module_xprin.yaml
tests:
  - name: "first reconcile — only step 1 emits"
    id: first_pass
    inputs:
      xr: example-xr.yaml
      composition: ../composition.yaml
      functions: ../../../../provider/function.yaml
    assertions:
      xprin:
        - { type: Count, value: 2, resource: "Queue/*" }
        - { type: Count, value: 0, resource: "QueuePolicy/*" }     # step 2 nil-guards
        - { type: Count, value: 0, resource: "BucketNotification/*" }
  - name: "second reconcile — synthetic observed, all steps fire"
    id: second_pass
    inputs:
      xr: example-xr.yaml
      composition: ../composition.yaml
      functions: ../../../../provider/function.yaml
      observed-resources: observed-queues.yaml                     # sibling under tests/
    assertions:
      xprin:
        - { type: Count, value: 2, resource: "Queue/*" }
        - { type: Count, value: 2, resource: "QueuePolicy/*" }     # step 2 emits
        - { type: Exists, resource: "BucketNotification/*" }
        - { type: Exists, field: "data.queueUrls", resource: "Secret/*" }
```

```yaml
# tests/observed-resources/queue-default.yaml
apiVersion: sqs.aws.m.upbound.io/v1beta1
kind: Queue
metadata:
  annotations:
    crossplane.io/composition-resource-name: queue-default
status:
  atProvider:
    arn: arn:aws:sqs:us-east-1:000000000000:myorg-dev-queue-default
    url: https://sqs.us-east-1.amazonaws.com/000000000000/myorg-dev-queue-default
  conditions:
    - type: Ready
      status: "True"
      reason: Available
    - type: Synced
      status: "True"
      reason: ReconcileSuccess
```

**Common trap:** writing `status.arn` instead of `status.atProvider.arn` — the dig path `dig "resource" "status" "atProvider" "arn" "" $data` returns the default empty string, and the dependent resource silently doesn't render because the ARN lookup produces `""`.


## Foreign-resource reads: the `extra-resources` input

Compositions that emit `ExtraResources` requirements (see [go-templating-cheatsheet.md](go-templating-cheatsheet.md) §ExtraResources) are locally testable: xprin accepts `extra-resources` as a first-class input, same shape as `observed-resources` — per-test or under `common:`.

```yaml
# tests/module_xprin.yaml
tests:
  - name: "image secret present — Deployment renders with the injected image"
    inputs:
      xr: example-xr.yaml
      composition: ../composition.yaml
      functions: ../../../../provider/function.yaml
      extra-resources: secret-image.yaml        # sibling under tests/
    assertions:
      xprin:
        - { type: Exists, resource: "Deployment/*" }
  - name: "fail-safe: Secret missing entirely — requirement unresolved, zero dependents, XR held not-Ready"
    id: failsafe_missing_secret
    inputs:
      xr: example-xr.yaml
      composition: ../composition.yaml
      functions: ../../../../provider/function.yaml
      # no extra-resources input at all — the requirement never resolves
    assertions:
      xprin:
        - { type: NotExists, resource: "Deployment/*" }
  - name: "fail-safe: Secret present but key absent — zero dependents, XR held not-Ready"
    id: failsafe_missing_key
    inputs:
      xr: example-xr.yaml
      composition: ../composition.yaml
      functions: ../../../../provider/function.yaml
      extra-resources: secret-no-image-key.yaml   # Secret without the expected data key
    assertions:
      xprin:
        - { type: NotExists, resource: "Deployment/*" }

```

```yaml
# tests/secret-image.yaml — real objects; requirements match by name.
# Standard Secret wire shape: `data` values are base64-encoded; the
# composition b64decs the key before rendering it into dependents.
apiVersion: v1
kind: Secret
metadata:
  name: demo-app-image
  namespace: demo-ns
type: Opaque
data:
  image: "aW50ZWdyYWwucmVnaXN0cnkuY3ViZS5hc2lhL3BvcnQvZGVtby1hcHA6djEuMi4z"
```

Both fail-safe variants are mandatory pins, not nice-to-haves: they exercise the guarded-read contract (missing requirement resolution AND present-object-missing-key) — a composition that crashes, renders garbage, or renders dependents without the image fails here first.

## Test coverage patterns

For a composition that handles optional fields and defaults, structure tests around the branches the template actually evaluates:

| Pattern | What it exercises | Example |
|---|---|---|
| **Happy path (defaults)** | Composition with all optional fields omitted — confirms defaults work. | No `queues` field → single default queue renders. |
| **Happy path (all features)** | Composition with every optional field set. | Multiple queues with prefix, suffix, debug flags. |
| **Edge cases** | Boundary values that change template behaviour. | Empty array (defaulted to single), single-element array, many elements. |
| **Two-reconcile cycle** | Every XR variant needs pass 1 (no observed state) + pass 2 (synthetic observed state). | Without pass 1 you miss nil-guard bugs; without pass 2 you never see dependent resources. |

xprin cannot test invalid XR inputs (missing required fields, wrong types) because it runs the composition pipeline against the XR — `kubectl apply --dry-run=client` handles schema validation. Keep XR validation separate; xprin tests the *composition*, not the XRD schema.

Each XR variant gets its own test fixture file (`example-xr-<variant>.yaml`) and, for multi-reconcile tests, its own observed-resources file (`observed-<resource>-<variant>.yaml`).

## Assertion coverage: FieldExists + FieldValue

**FieldExists** validates a field path exists on the rendered resource. Catches dropped fields — if a template accidentally omits `spec.path`, the assertion fails.
**FieldValue** validates the field's value matches the expected string/number. Catches wrong values — if a template variable resolves to the wrong name or a typo, the assertion fails.

Use **both** together for MECE (Mutually Exclusive, Collectively Exhaustive) coverage. Neither alone is sufficient: `FieldExists` passes for a field with a garbage value; `FieldValue` panics (not fails) if the entire field is missing — the operator can't compare against nil.

```yaml
assertions:
  xprin:
    # Existence — would catch spec.path being absent from the template
    - name: "VaultStaticSecret has spec.path"
      type: FieldExists
      resource: "VaultStaticSecret/*"
      field: "spec.path"

    # Value — catches spec.path resolving to the wrong vault path
    - name: "VaultStaticSecret path correct"
      type: FieldValue
      resource: "VaultStaticSecret/vso-secret-myapp-prod-db"
      field: "spec.path"
      operator: "=="
      value: "myapp/prod/db"
```

Rules of thumb:
- Use `FieldExists` with wildcard patterns (`Policy/*`, `VaultStaticSecret/*`) to guard every resource of a kind.
- Use `FieldValue` with **explicit resource names** when each resource has a different expected value. Use wildcards only when all matched resources share the same value.
- `FieldExists` without a subsequent `FieldValue` is a regression guard for field removal; `FieldValue` without `FieldExists` crashes on nil. Pair them.
- For resources with auto-generated names (no explicit `metadata.name` in the template), use `FieldValue` with a wildcard pattern (`Policy/*`) — the assertion applies to every match.

**`NotExists` checks resource-level absence, not field-level.** `{type: NotExists, resource: "Queue/my-queue"}` asserts no resource matches the pattern. There is no field-level "this field must be absent" assertion — `{type: NotExists, resource: "...", field: "..."}` is not a supported combination; xprin ignores `field` and evaluates it as a resource-presence check. To guard against a field leaking onto the wrong resource variant, assert the correct variant's expected value with `FieldValue` instead; a field-drop regression on an optional field isn't testable directly with this xprin version.

Pass 2's `observed-resources` is a synthetic YAML that mirrors what the provider would have observed after the underlying resources exist in AWS. Each entry needs:
- The `crossplane.io/composition-resource-name: <key>` annotation matching what step 1 set via `setResourceNameAnnotation`
- `status.atProvider.<field>` populated with the values step 2 expects to read
- `status.conditions[type=Ready]=True` so the auto-ready step considers them ready

## Inspect rendered output

`--show-render` lists resources by Kind/Name but xprin cleans up the temp dir immediately, so you can't see the full YAML. **`hooks:` (top-level or under `common:`) does not execute on xprin v0.2.0** — confirmed: a `post` hook shelling out to `cp`/`echo` produces no file, no error, and no trace under `-v`, `--debug`, or `--show-hooks`. Do not rely on it.

For the full rendered YAML, run `crossplane render` directly with the same inputs (`scripts/render.sh xr.yaml composition.yaml functions.yaml`) — it prints the complete manifest to stdout, no cleanup step to race against.

## When to use xprin vs raw `crossplane render`

Use xprin instead of `crossplane render` when you need any of: assertions on rendered output, golden-file diffs, test chaining via artifact export (`id` + `.Tests.{id}.Outputs.*`), `common` sections to share inputs across cases, or `go test`-style CI output. It is NOT a cluster e2e test — it mocks the cluster and runs Functions locally via Docker.

Pinning: xprin v0.2+ supports Crossplane v2. Its `tests` block accepts the same v2 XRD `apiVersion`. For v1-only assertions on v2 XRDs, run `crossplane render` directly with the version pin from `scripts/render.sh`.

## Gotchas

- **`functions:` absolute path triggers `not a function: /`.** xprin copies the file (or directory) into a temp dir like `/tmp/xprin-testcase-…/inputs/functions/…` and the local crossplane CLI's path parser splits that absolute path on `/`, treating the first `/` as a function package ref. **Always use a relative path** (`functions: ../../../../provider/function.yaml`), not an absolute one.
- **`functions:` works as either a directory of single-doc YAMLs or a single multi-doc YAML** (with `---` separators). The "must be a directory" warning is over-stated — both forms parse as long as the path is relative.
- **`crossplane` CLI v2.3.x has no `beta validate` subcommand.** Drop `crds:` from tests, or override the `validate:` subcommand in `.xprin.yaml` with a subcommand that exists in your CLI version.
- **Without `--crossplane-version`**, the engine inside Docker can disagree with the host CLI on feature behaviour. Pin it in both `subcommands.render` and `subcommands.validate`.
- **One test pass is not enough for multi-step compositions.** Step 2+ nil-guards on the first reconcile; the dependent resources never emit unless you give xprin a synthetic `observed-resources` in a second test case. See the two-reconcile test pattern above.
- **XRD schema violations in example XRs silently pass.** `crossplane render` runs the pipeline templates against the input XR without validating it against the XRD schema. If you rename or remove a field (e.g. `suffix:` → `filters:`), stale example XRs with the old field won't fail — the composition just ignores the unknown field. Always check example XRs match the XRD when changing the schema.
- **No expect-failure assertion type.** `xprin test --help` has no flag for "this render should error," and `make test`'s `xprin test ... || exit 1` per module treats any nonzero exit as a hard break. A `{{ fail "..." }}` template guard can't be committed as a permanent case in the regular suite. Verify it manually with a throwaway `*_xprin.yaml` (outside `tests/`, or deleted before committing), confirm the nonzero exit and error message, then remove the scratch file — `make test`'s glob (`modules/*/*`) would otherwise break on every run.
- **`xprin test` fails with "crossplane: command not found"** — install the `crossplane` CLI 1.15+ and ensure it's on PATH, or set the path in `~/.config/xprin.yaml` under `dependencies.crossplane`. In a project using `mise`, add `crossplane = "<version>"` to `mise.toml` and run `mise exec -- xprin test …`.
- **`xprin test` hangs or "cannot connect to Docker daemon"** — xprin shells out to `crossplane render`, which runs Composition Functions in Docker. Start Docker, or pass `--crossplane-binary` to `crossplane render` for Development-mode functions. Podman works as a Docker alternative.
- **A green suite proves nothing about Kubernetes admission.** xprin runs the composition pipeline in Docker and never validates rendered objects against the k8s API: label and annotation VALUE charset (only alphanumerics, `-`, `_`, `.`; max 63 chars — a repo path like `modules/workloads/app` passes every assertion and is rejected by every live apply), name length, RFC 1123 name segments. Any template code that shapes a name, label, or annotation must be validated on the RENDERED output: run `scripts/render.sh`, split the multi-doc output, `kubectl apply --dry-run=client -f` each doc. Renderable ≠ applyable.
- **Hand-built whole-document JSON expectations: let the first render correct you.** Go `encoding/json` sorts map keys alphabetically, so conditions group as `{"StringEquals":{"aws:PrincipalOrgID":[...],"aws:SourceAccount":[...]}}` — but if you write the expected string before ever rendering, your own assert is the likeliest failure (real case: asserting `NotPrincipal` where the fixture declares `principals`; the render was right). Run the RED render first, diff the actual, pin the corrected string. A render-fatal (YAML breakage) counts as red for the scenario — then fix the composition, not the fixture.
