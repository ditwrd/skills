# Discovering current CRD fields and previewing renders

CRDs evolve. Always check the installed version, and preview the function pipeline output locally before committing (you do not apply these directly — GitOps syncs them):

```sh
# Find the right MRD / CRD
kubectl get mrd | grep -i rds
kubectl get crd | grep -i rds | grep 'aws\.m\.upbound\.io'

# Check if a specific MRD is active
kubectl get mrd dbinstances.rds.aws.m.upbound.io -o jsonpath='{.spec.state}'
# Activate it if needed (some providers ship CRDs as Inactive under safe-start)
kubectl patch mrd dbinstances.rds.aws.m.upbound.io \
  --type='merge' -p='{"spec":{"state":"Active"}}'

# Dump the schema
kubectl get crd dbinstances.rds.aws.m.upbound.io -o jsonpath='{.spec.versions[0].schema.openAPIV3Schema}' | jq

# For a single field path
kubectl explain dbinstance.rds.aws.m.upbound.io.spec.forProvider.engine

# Preview what your function pipeline will produce (needs the crossplane CLI + Docker)
crossplane render xr.yaml composition.yaml functions.yaml

# Quick schema check without applying
kubectl apply --dry-run=client -f xrd.yaml
```

The namespaced CRD group is `<service>.aws.m.upbound.io/v1beta1` (e.g. `ec2.aws.m.upbound.io/v1beta1`). The legacy cluster-scoped group `<service>.aws.upbound.io` still works for v1-style cluster resources.

For the latest field set, check the upstream repo: <https://github.com/crossplane-contrib/provider-upjet-aws/tree/main/examples> and the per-resource `.tf` files in `internal/clients/`.

For questions on `function-go-templating` syntax or context shape, web search `crossplane function-go-templating example` — the function's API has changed between minor versions.

Official Crossplane v2.3 docs referenced for this skill:
- Compositions (function pipeline, constraints): <https://docs.crossplane.io/v2.3/composition/compositions/>
- XRD schema and v2 API: <https://docs.crossplane.io/v2.3/guides/upgrade-to-crossplane-v2/>
- function-go-templating: <https://github.com/crossplane-contrib/function-go-templating>
- function-auto-ready: <https://github.com/crossplane-contrib/function-auto-ready>
- XR API best practices: <https://www.upbound.io/blog/crossplane-xr-best-practices>
- Configuring Crossplane with Argo CD (for the GitOps side): <https://docs.crossplane.io/v2.3/guides/crossplane-with-argo-cd/>
