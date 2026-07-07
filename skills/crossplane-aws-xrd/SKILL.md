---
name: crossplane-aws-xrd
description: Author Crossplane CompositeResourceDefinitions (XRDs) and Compositions for AWS using provider-upjet-aws and function-go-templating. Use when creating new crossplane claim APIs, writing `CompositeResourceDefinition` YAML, writing `Composition` YAML with `function-go-templating`, building multi-resource AWS composites (VPC+RDS, S3+policy), or discovering installed provider-aws CRD fields.
---

# Crossplane AWS XRD

Author XRDs and Compositions for AWS. Artifacts are committed to Git and synced via GitOps (ArgoCD / Flux) — do not apply directly with `kubectl apply`. Assumes Crossplane, provider-upjet-aws, and function-go-templating are already installed.

## Workflow

1. **Find the managed resource** for the AWS service. List candidates:
   `kubectl get crd -l provider.upbound.io/provider-aws --no-headers | awk '{print $1}'` or
   `kubectl get crd | grep '\.aws\.upbound\.io$'`. Full schema:
   `kubectl get crd <name> -o jsonpath='{.spec.versions[0].schema.openAPIV3Schema}' | jq`.
   CRD names: `<service>.<group>.upbound.io` (e.g. `rds.aws.upbound.io`, `vpc.aws.upbound.io`, `s3.aws.upbound.io`).
2. **Design the claim shape** — what does a user write? Follow the API-design rules in [REFERENCE.md §1](REFERENCE.md#1-xrd-anatomy): required fields sparingly, prefer arrays over scalars, avoid booleans.
3. **Write the XRD** — see [REFERENCE.md §1](REFERENCE.md#1-xrd-anatomy).
4. **Write the Composition** — `mode: Pipeline` with `function-go-templating` steps, see [REFERENCE.md §2](REFERENCE.md#2-composition-anatomy) and the [templating cheatsheet](REFERENCE.md#3-go-templating-cheatsheet).
5. **Validate locally** before committing:
   - `crossplane render xr.yaml composition.yaml functions.yaml` to preview what the function pipeline produces. Install crossplane CLI from [crossplane/docs](https://docs.crossplane.io/latest/cli/).
   - `kubectl apply --dry-run=client -f <file>` to confirm schema and required fields parse.
   - `kubeconform -summary <file>` (or your usual yaml linter) for the rest.
6. **Commit to Git, let GitOps sync.** Push XRD, Composition, and (optionally) a sample claim to the repo your GitOps controller watches. After the sync, read the live state with:
   - `kubectl get <xrd-kind> -A` and `kubectl describe <claim> -n <ns>`
   - `kubectl get managed` to see what got rendered
7. **Iterate** — if the claim hangs: read the `status.conditions` of the XR and the failing MR; missing readiness or `connectionDetails` is the usual culprit. See [REFERENCE.md §6](REFERENCE.md#6-common-validation-gotchas).

## Hard rules

- Use `mode: Pipeline` with `function-go-templating`. Do not use patch-and-transform + env vars style.
- One render-resources step, one observe-and-report-readiness step. Optionally one resolve-connection-secret step.
- Always set composite `conditions` explicitly in the observe step. Do not rely on auto-detection from readiness alone.
- The function-go-templating input is `apiVersion: gotemplating.fn.crossplane.io/v1beta1, kind: GoTemplate, source: Inline, inline.template: | ...`. The template body must be valid YAML for the rendered resources.

See [REFERENCE.md](REFERENCE.md) for full anatomy and [EXAMPLES.md](EXAMPLES.md) for 2 worked AWS composites.
