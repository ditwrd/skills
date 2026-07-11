# Module folder structure

The canonical layout for an AWS composite module in this repo. Every module follows the same shape so a reader can navigate without learning a new convention. `modules/aws/s3-with-policy/` is the minimal working example.

```
<repo>/
  mise.toml                      # crossplane + xprin pinned (one per repo)
  .xprin.yaml                    # xprin subcommand config (one per repo)
  provider/
    function.yaml                # shared function packages (multi-doc, one per repo)
  modules/aws/<service>-<thing>/
    xrd.yaml                     # CompositeResourceDefinition, apiextensions.crossplane.io/v2
    composition.yaml             # Composition, apiextensions.crossplane.io/v1, mode: Pipeline
    tests/
      example-xr.yaml            # a working XR, fits the composition's contract
      observed-<resource>.yaml   # synthetic observed state for the second-reconcile test pass
      <thing>_xprin.yaml         # xprin test suite (common inputs, 2 test cases)
```

## Why each piece is where it is

### `<repo>/mise.toml` — toolchain pin

```toml
[tools]
crossplane = "2.3.1"
"github:crossplane-contrib/xprin" = "latest"
```

The team contract for which `crossplane` and `xprin` binaries are on `$PATH`. `mise exec -- xprin test …` in CI and on dev laptops pulls the same versions. Without this, the host CLI and the engine inside Docker can mismatch (the `not a function: /` and `unexpected argument beta` failures come from this).

### `<repo>/.xprin.yaml` — subcommand config

```yaml
dependencies:
  crossplane: crossplane

subcommands:
  render: render --include-full-xr --crossplane-version=v2.3.1
  # crossplane CLI v2.3.x has no `beta validate` subcommand — drop `crds:` from
  # tests, or override `validate:` with a subcommand that exists in your CLI:
  # validate: validate --crossplane-version=v2.3.1
```

xprin-specific config: which flags get passed to `crossplane render` and (optionally) `crossplane validate`. The version pin matches the engine version that ships in the Docker image, so the local CLI and the engine agree on the v2 XRD schema. If your CLI is newer and has `beta validate`, uncomment it here.

### `<repo>/provider/function.yaml` — shared function packages

```yaml
apiVersion: pkg.crossplane.io/v1
kind: Function
metadata:
  name: function-go-templating
spec:
  package: xpkg.upbound.io/upbound/function-go-templating:v0.12.1
---
apiVersion: pkg.crossplane.io/v1
kind: Function
metadata:
  name: function-auto-ready
spec:
  package: xpkg.upbound.io/upbound/function-auto-ready:v0.6.5
```

One multi-doc file, one bump updates the whole toolchain across every module. The Upbound registry (`xpkg.upbound.io/upbound/...`) is the canonical mirror of crossplane-contrib; prefer it over `ghcr.io/crossplane-contrib/...` for new work. Each test references this file via a relative path (e.g. `../../../../provider/function.yaml`) — never an absolute path, which trips up xprin's path parser.

### `<module>/xrd.yaml` — CompositeResourceDefinition

```yaml
apiVersion: apiextensions.crossplane.io/v2
kind: CompositeResourceDefinition
metadata:
  name: x<thing>.<group>          # convention: <plural>-<group>-<version>
spec:
  scope: Namespaced              # v2 default; state explicitly
  group: <group>
  names:
    kind: X<Thing>
    plural: x<things>
  versions:
    - name: v1alpha1
      served: true
      referenceable: true
      schema:
        openAPIV3Schema:
          type: object
          properties: { spec: { type: object, required: [...], properties: {...} } }
```

No `claimNames`, no `connectionSecretKeys` (v1-only, rejected in v2 outside `scope: LegacyCluster`). The composition name mirrors this: `x<things>.<group>-<version>`.

### `<module>/composition.yaml` — Composition

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: x<things>.<group>-<version>
spec:
  compositeTypeRef:
    apiVersion: <group>/v1alpha1
    kind: X<Thing>
  mode: Pipeline
  pipeline:
    - step: render-resources-with-no-observed-deps
      functionRef: { name: function-go-templating }
      input: { ... }
    - step: render-resources-that-need-observed-state
      functionRef: { name: function-go-templating }
      input: { ... }
    - step: ready
      functionRef: { name: function-auto-ready }
```

The two-step render is the standard pattern. Step 1 emits resources with no observed state dependency. Step 2 nil-guards on `$.observed.resources` and emits dependent resources (BucketPolicy, BucketNotification, etc.) after the provider has observed the step-1 resources in AWS. The `ready` step is always last and always `function-auto-ready` — never configure it. See [references/testing-with-xprin.md](testing-with-xprin.md) for the xprin test pattern that exercises this.

### `<module>/tests/` — test fixtures, self-contained

```
tests/
  example-xr.yaml            # a valid XR, applies cleanly with `kubectl apply --dry-run=client`
  observed-<resource>.yaml  # synthetic observed state for pass 2 of the xprin test
  <thing>_xprin.yaml         # the xprin test suite
```

Everything the test needs is in `tests/`. `cd tests && ls` is a complete inventory. The XR and the synthetic observed resources both live here because they're test data — production inputs are different and live in user-managed repos.

### Test paths in `<thing>_xprin.yaml`

```yaml
common:
  inputs:
    xr: example-xr.yaml                                  # sibling under tests/
    composition: ../composition.yaml                    # up one, module root
    functions: ../../../../provider/function.yaml        # up four, repo-root provider
```

All paths relative to the test file. **Never use absolute paths** — xprin copies the input into a temp dir and the resulting absolute path trips up the local crossplane CLI's path parser (the `not a function: /` bug).

## TDD workflow for a new module

Build the module in the order below, in small commits. Each step's test should fail before its code, then pass after.

1. **Empty module** — `mkdir -p modules/aws/<thing>/tests/`. Run `xprin test` against a non-existent composition. Confirms the test harness works and the path to `provider/function.yaml` is right.
2. **Write the xprin test first** — `tests/<thing>_xprin.yaml` with the two-reconcile cases (pass 1 no observed, pass 2 with observed). Run it. It fails because the composition doesn't exist.
3. **Write `xrd.yaml`** — the schema. Re-run the test. Still fails (composition missing). The XRD is the contract; the test is the consumer of the contract.
4. **Write the minimum `composition.yaml`** — one function-go-templating step for step-1 resources, no step 2 yet, plus `function-auto-ready` at the end. Re-run. Pass 1 should go green; pass 2 fails because there's no step 2 yet.
5. **Add step 2** — emits the resources that depend on observed state. Use `{{ if eq $.observed.resources nil }}...{{ else }}...{{ end }}` to guard. Re-run. Both passes should be green.
6. **Add resource-content assertions** — post-test `grep` hooks for any string-content checks that xprin's `FieldValue` can't do (e.g. substring matching inside a multi-line JSON policy). xprin only supports `==` and `is` for `FieldValue`, so anything more nuanced lives in a hook.

Each step is a small commit: test-red, code, test-green, commit. If a test ever regresses, `git bisect` lands on the offending change.

## Adding a new module — checklist

- [ ] `mkdir -p modules/aws/<thing>/tests/`
- [ ] Write `tests/<thing>_xprin.yaml` referencing `../../../../provider/function.yaml` (path from `tests/` to repo-root)
- [ ] Write `tests/example-xr.yaml` (sibling of the test)
- [ ] Write `tests/observed-<resource>.yaml` (synthetic observed state for pass 2)
- [ ] Run `xprin test --config-file ../../../../.xprin.yaml tests/<thing>_xprin.yaml` — must fail because the composition is missing
- [ ] Write `xrd.yaml` (`apiextensions.crossplane.io/v2`, `scope: Namespaced`, no claimNames/connectionSecretKeys)
- [ ] Write `composition.yaml` starting with step 1 only + ready. Re-run. Pass 1 green, pass 2 red.
- [ ] Add step 2. Re-run. Both green.
- [ ] `git add && git commit` per step
- [ ] Done. CI runs `xprin test` on every PR; the suite is the safety net.

## What not to do

- **No per-module `functions/` directory.** Share `provider/function.yaml`. One bump, all modules.
- **No `out.yaml`** in the module root as a hand-rolled "expected output". The xprin test IS the expected output. If you need to inspect a render, copy the temp file via a post-test hook or run `crossplane render` directly with `--include-full-xr`.
- **No `kubectl apply` in tests.** xprin is a mock — no cluster, no real resources. The test runs entirely in Docker with the engine inside.
- **No absolute paths in the test.** Always relative to the test file.
- **No `mode: Resources`** (the old P&T mode) — gone in v2.
- **No `claimNames` or `connectionSecretKeys`** in the XRD — v1-only, rejected in v2.
- **No `CompositeConnectionDetails` meta-resource** in the composition — gone in v2. Emit a real `Secret` instead.
