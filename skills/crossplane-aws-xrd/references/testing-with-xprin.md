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

Pass 2's `observed-resources` is a synthetic YAML that mirrors what the provider would have observed after the underlying resources exist in AWS. Each entry needs:
- The `crossplane.io/composition-resource-name: <key>` annotation matching what step 1 set via `setResourceNameAnnotation`
- `status.atProvider.<field>` populated with the values step 2 expects to read
- `status.conditions[type=Ready]=True` so the auto-ready step considers them ready

## Inspect rendered output (cp-hook trick)

`--show-render` lists resources by Kind/Name but xprin cleans up the temp dir immediately, so you can't see the full YAML. Add a post-test hook to copy it before cleanup:

```yaml
hooks:
  post:
    - run: "cp /tmp/xprin-testcase-*/outputs/rendered.yaml ./last-render.yaml"
```

## When to use xprin vs raw `crossplane render`

Use xprin instead of `crossplane render` when you need any of: assertions on rendered output, golden-file diffs, pre/post test hooks, test chaining via artifact export (`id` + `.Tests.{id}.Outputs.*`), `common` sections to share inputs across cases, or `go test`-style CI output. It is NOT a cluster e2e test — it mocks the cluster and runs Functions locally via Docker.

Pinning: xprin v0.2+ supports Crossplane v2. Its `tests` block accepts the same v2 XRD `apiVersion`. For v1-only assertions on v2 XRDs, run `crossplane render` directly with the version pin from `scripts/render.sh`.

## Gotchas

- **`functions:` absolute path triggers `not a function: /`.** xprin copies the file (or directory) into a temp dir like `/tmp/xprin-testcase-…/inputs/functions/…` and the local crossplane CLI's path parser splits that absolute path on `/`, treating the first `/` as a function package ref. **Always use a relative path** (`functions: ../../../../provider/function.yaml`), not an absolute one.
- **`functions:` works as either a directory of single-doc YAMLs or a single multi-doc YAML** (with `---` separators). The "must be a directory" warning is over-stated — both forms parse as long as the path is relative.
- **`crossplane` CLI v2.3.x has no `beta validate` subcommand.** Drop `crds:` from tests, or override the `validate:` subcommand in `.xprin.yaml` with a subcommand that exists in your CLI version.
- **Without `--crossplane-version`**, the engine inside Docker can disagree with the host CLI on feature behaviour. Pin it in both `subcommands.render` and `subcommands.validate`.
- **One test pass is not enough for multi-step compositions.** Step 2+ nil-guards on the first reconcile; the dependent resources never emit unless you give xprin a synthetic `observed-resources` in a second test case. See the two-reconcile test pattern above.
- **`xprin test` fails with "crossplane: command not found"** — install the `crossplane` CLI 1.15+ and ensure it's on PATH, or set the path in `~/.config/xprin.yaml` under `dependencies.crossplane`. In a project using `mise`, add `crossplane = "<version>"` to `mise.toml` and run `mise exec -- xprin test …`.
- **`xprin test` hangs or "cannot connect to Docker daemon"** — xprin shells out to `crossplane render`, which runs Composition Functions in Docker. Start Docker, or pass `--crossplane-binary` to `crossplane render` for Development-mode functions. Podman works as a Docker alternative.
