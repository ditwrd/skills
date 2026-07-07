---
name: crossplane-aws-xrd
description: Crossplane v2. Authors CompositeResourceDefinitions (XRDs) and Compositions for AWS using provider-upjet-aws with function-go-templating and function-auto-ready. Use when writing a v2 `CompositeResourceDefinition`, a `Composition` pipeline using `function-go-templating` plus `function-auto-ready`, a multi-resource AWS composite (VPC+EC2, S3+IAM), or discovering the schema of an installed provider-aws ManagedResourceDefinition.
---

# Crossplane AWS XRD

Author v2 XRDs and Compositions for AWS. Artifacts are committed to Git and synced via GitOps (ArgoCD / Flux) — do not apply directly with `kubectl apply`. Assumes Crossplane v2.x, provider-upjet-aws v2.x, function-go-templating v0.11+, and function-auto-ready v0.7+ are installed.

## Workflow

1. **Find the managed resource** for the AWS service. Namespaced v2 MRs live at `<service>.aws.m.upbound.io` (e.g. `ec2.aws.m.upbound.io/v1beta1`, `rds.aws.m.upbound.io/v1beta1`, `s3.aws.m.upbound.io/v1beta1`). Discover the schema with one of:
   - `kubectl get mrd` — lists every ManagedResourceDefinition; pick the one you need.
   - `kubectl get crd <name>` and read `.spec.versions[0].schema.openAPIV3Schema`, or use `kubectl explain <name>.<group>`.
   - Browse the marketplace: https://marketplace.upbound.io/providers/upbound/provider-family-aws/latest/managed-resources
2. **Design the XR shape** — what does the user write? Follow the API-design rules in [REFERENCE.md §1](REFERENCE.md#1-xrd-anatomy): required fields sparingly, prefer arrays over scalars, avoid booleans.
3. **Write the XRD** — `apiextensions.crossplane.io/v2`, `scope: Namespaced` (or `Cluster`). No `claimNames`, no `connectionSecretKeys`. See [REFERENCE.md §1](REFERENCE.md#1-xrd-anatomy).
4. **Write the Composition** — `apiextensions.crossplane.io/v1` (the only Composition version that exists in v2), `mode: Pipeline`, with a `function-go-templating` step to render composed resources and a `function-auto-ready` step to mark readiness. See [REFERENCE.md §2](REFERENCE.md#2-composition-anatomy) and the [templating cheatsheet](REFERENCE.md#3-go-templating-cheatsheet).
5. **Validate locally** before committing:
   - `crossplane render xr.yaml composition.yaml functions.yaml` to preview what the function pipeline produces. Install crossplane CLI from [crossplane/docs](https://docs.crossplane.io/v2.3/cli/).
   - `kubectl apply --dry-run=client -f <file>` to confirm schema and required fields parse.
   - `kubeconform -summary <file>` (or your usual yaml linter) for the rest.
6. **Commit to Git, let GitOps sync.** Push the XRD and Composition (and an XR sample if you want) to the repo your GitOps controller watches. After the sync, read the live state with:
   - `kubectl get <xrd-kind> -A` and `kubectl describe <xr> -n <ns>`
   - `kubectl get managed` to see what got rendered
7. **Iterate** — if the XR hangs: read the `status.conditions` of the XR and the failing MR; missing readiness check or an `observed.resources` nil-guard is the usual culprit. See [REFERENCE.md §6](REFERENCE.md#6-common-validation-gotchas).

## Hard rules

- Use XRD `apiVersion: apiextensions.crossplane.io/v2` with `scope: Namespaced` (or `Cluster`). No `claimNames`, no `connectionSecretKeys` — these are deprecated in v2 outside `scope: LegacyCluster`. Legacy v1 XRDs and the claim pattern are not supported.
- Composition is `apiextensions.crossplane.io/v1` (the only Composition version that exists in v2) with `mode: Pipeline`. `mode: Resources` (native patch-and-transform) is gone.
- Pipeline has two required steps: a `function-go-templating` step that renders composed resources (using `{{ setResourceNameAnnotation "key" }}` on each one) and a `function-auto-ready` step as the last step. Do not hand-roll readiness with a `kind: Result` resource — that was the v1 pattern and `function-auto-ready` replaces it.
- For cross-resource dependencies (B reads A's output), render B in a second `function-go-templating` step that reads `.observed.resources` from the first step. Always guard with `{{ if eq $.observed.resources nil }}` because observed state is empty on the first reconcile.
- Compose connection details explicitly as a `Secret` resource (with `{{ setResourceNameAnnotation "connection-secret" }}` and a nil-guard on first reconcile). Don't rely on `connectionSecretKeys` on the XRD — it's deprecated in v2.
- Use the namespaced CRD group for AWS MRs: `<service>.aws.m.upbound.io/v1beta1` (e.g. `ec2.aws.m.upbound.io/v1beta1`). The legacy `<service>.aws.upbound.io` group is for v1 cluster-scoped resources.

See [REFERENCE.md](REFERENCE.md) for full anatomy and [EXAMPLES.md](EXAMPLES.md) for 2 worked AWS composites.
