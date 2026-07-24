# Composition audit

## §0 In-cluster health check

When a composition isn't reconciling, follow this order:

1. **XR status** — `kubectl get <xr-kind> -A` — check SYNCED, READY, RESPONSIVE conditions.
2. **Managed resources** — `kubectl get managed -A` — find the MR with missing or error conditions.
3. **Composition revision** — verify `compositionRevisionRef` on the XR matches the active CompositionRevision.
4. **Events** — `kubectl describe <xr> -n <ns>` — events on the XR and its owned managed resources.
5. **Provider logs** — `kubectl logs -l app.kubernetes.io/name=provider-<name>` — controller logs.

Audit a Composition for three categories of conflict.

## 1. Feedback loops

Patterns that create circular update triggers between Crossplane and the provider:

- **`crossplane.io/external-name` annotations**: Upbound providers set external-name independently. Setting it in the template creates a perpetual diff — remove it. Crossplane derives external-name from `metadata.name` automatically.
- **`Deny`/`Allow` conditionals on policy content**: Guards like `"Effect": "{{ if $queueReady }}Allow{{ else }}Deny{{ end }}"` flip on every reconcile as dependencies transition readiness — direct feedback loop. Use `*Ref` fields for ordering and emit the policy unconditionally with `Effect: Allow`.
- **Redundant Crossplane labels**: Crossplane auto-injects `crossplane.io/composite` and similar labels. Compositions should not duplicate them.
- **Provider default tags vs composition tags**: If the provider injects default tags and the composition template omits or mismatches them, every reconcile produces a diff. Include all expected default tags with matching values.

## 2. External controller conflicts

Resources that other controllers or tools may also manage:

- **Authoritative resources**: Some managed resources replace the entire external configuration they control (e.g. `BucketNotification` replaces all S3 notification config). Any other tool (Terraform, AWS console, another operator) managing the same resource will conflict.
- **External-name naming schemes**: Resources named `<team>-<env>-<bucket>-<name>` could collide with existing external resources.
- For provider-specific conflict patterns (AWS `BucketNotification`, `QueuePolicy`, etc.), see the [AWS reference](aws.md).

## 3. Connection detail updates

Check for thrash in connection secrets:

- **`writeConnectionSecretToRef` on stable resources** (URLs, ARNs): Low risk — values don't change after creation.
- **Composite-level `connectionSecretKeys`** (XRD v1) or **`publishConnectionDetailsTo`**: If present, keys producing unstable output (e.g. `queueUrls: []string{}` vs `queueUrls: []` on every reconcile) cause cascading watch events.
- **Synthetic Secret resources** created via template (not via `writeConnectionSecretToRef`): Type mismatches (e.g. `stringData.queueUrls` receiving an array instead of a string) cause `cannot compose resources` errors.

## Reporting

Read `composition.yaml` + `xrd.yaml`. Grep for relevant patterns (`external-name`, `Deny`, `Allow`, `queueArn`, `connectionSecret`). Present findings per category with risk level (Low / Moderate / High).
