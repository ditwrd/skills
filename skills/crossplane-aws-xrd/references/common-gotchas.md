# Common gotchas

- **Trim-collapse bug** — `{{-` on its own line eats the preceding newline via the left-trim. For YAML keys with list values, the parent key and the first list item collapse onto one line; the k8s.io decoder rejects with `block sequence entries are not allowed in this context` or `mapping values are not allowed in this context`. The error is reported against the *parent* key (`queue: - id: ...`), not the range directive — confusing.
  **Primary fix: drop the left-trim** — use `{{ range }}` / `{{ end }}` (no `-`).
  **Secondary (can fail):** inline (`queue: {{ range $i, $q := $queues }}`) — the Go template parser may reject with `missing value for range`.
  **Filter lines:** drop `{{-` from `{{- if $x }}` before filter/mapping keys.
  **Data-block collapse:** precompute before the block, not between key and value.
  Read SKILL.md §0 for the full detail.
- **XRD is `apiextensions.crossplane.io/v2`** with `scope: Namespaced` (or `Cluster`). If you set `claimNames` or `connectionSecretKeys` outside `LegacyCluster` scope, the v2 XRD rejects the field.
- **Composition is `apiextensions.crossplane.io/v1`** (the only version that exists). Don't try `apiextensions.crossplane.io/v2` for the Composition.
- **Every composed resource needs `setResourceNameAnnotation "key"`.** Without it, the function either rejects the resource (in newer versions) or mis-routes it as a status update on the XR.
- **`.observed.resources` is nil on first reconcile.** Guard the index call. `dig "status" "vpcId" "" .observed.resources.vpc` panics because Go templates can't field-access a nil map; use `(index $.observed.resources "vpc")` instead so the nil-receiver is the index call, not a field access.
- **`function-auto-ready` is the last step.** Putting it before the render step means it sees no composed resources and the XR will never become ready.
- **`crossplane.io/external-name` missing on a resource?** It will be recreated on every reconcile. Always set it from a stable field on the XR.
- **Indentation off by one space inside `template: |`?** YAML will parse but resources will have wrong fields. Render the template to a file and `kubectl apply --dry-run=client -f -` to validate, or use `crossplane render`.
- **You composed a `Secret` for connection details but the data map is empty?** That's the first reconcile — the underlying instance hasn't produced `connectionDetails` yet. The `{{ if eq $.observed.resources nil }}` (or the more specific `{{ if not (index $.observed.resources "pg") }}`) guard will keep the function from panicking; the map fills in on the next reconcile.
- **Provider CRD not present after install?** Some providers ship CRDs as `Inactive` MRDs under safe-start. Patch the MRD to `Active`, or configure a `ManagedResourceActivationPolicy`.
- **`xprin test` fails with "crossplane: command not found"** — install the `crossplane` CLI 1.15+ and ensure it's on PATH, or set the path in `~/.config/xprin.yaml` under `dependencies.crossplane`.
- **`xprin test` hangs or "cannot connect to Docker daemon"** — xprin shells out to `crossplane render`, which runs Composition Functions in Docker. Start Docker, or pass `--crossplane-binary` to `crossplane render` for Development-mode functions. Podman works as a Docker alternative.
