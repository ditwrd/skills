# Kubernetes executor pattern (provider-kubernetes)

How to compose **native Kubernetes objects** (Deployment, Service, HTTPRoute, PDB, VPA, an operator's CR — anything with a real k8s API) through Crossplane: wrap each object in a provider-kubernetes `Object` managed resource instead of looking for an upjet provider that doesn't exist.

```yaml
apiVersion: kubernetes.m.crossplane.io/v1alpha1
kind: Object
metadata:
  annotations:
    {{ setResourceNameAnnotation "deployment" }}
  name: {{ $wrapperName }}            # see naming contract below
spec:
  forProvider:
    manifest:
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: my-app                  # the REAL object name lives here
        namespace: {{ $claimNamespace }}
      spec: { ... }                   # the real object spec
  providerConfigRef:
    name: default
    kind: ClusterProviderConfig
  # managementPolicies: leave unset to cascade on claim deletion, or omit
  # "Delete" to orphan the graph — see the deletion contract below.
```

## Wrapper naming contract

Composed Object name: `<namespace>-<claim>-<kind-token>` — **namespace-prefixed AND kind-tokened** (`-deployment`, `-route`, `-pdb`, `-cluster`, ...). The namespace prefix means two same-namespace claims can never collide; the kind token keeps the composed set readable in `kubectl get managed`. The real object name/namespace live under `spec.forProvider.manifest.metadata.*`; force the namespace to the claim's namespace (overwrite whatever the inner manifest carries — a missing one must be added).

## Executor RBAC — the prerequisite that is invisible to render tests

The provider pod's ServiceAccount applies the wrapped objects. The published provider package ships **no RBAC** (upstream suggests cluster-admin — refuse; bind a kind-set ClusterRole instead). The role must list **every composed kind** (get/list/watch/create/update/patch, plus `delete` only if the deletion contract cascades — see below). A role scoped to a previous module's kinds makes every new Object MR fail on **observe** — the XR hangs not-Ready with forbidden errors on the provider, and xprin shows nothing because the render never touches RBAC.

Crossplane **core** (not the function pod) resolves `ExtraResources` requirements — Secret reads in claim namespaces need grants on the core SA, verified separately from the executor role.

## Deletion contract = `managementPolicies`

This is a per-module design decision; state it explicitly:

- **Unset** (defaults to all policies incl. `Delete`): claim deletion **cascades** — the whole composed graph is GC'd with no orphans. Right for stateless workload hosting.
- **Omit `Delete`**: claim deletion **orphans** the graph — the real objects outlive the claim. Right for long-lived stateful resources (databases, message brokers).

Mixing both styles in one fleet is fine; leaving the choice implicit is not.

## Zero-gap RBAC handover (moving grants between ArgoCD apps)

When RBAC moves from one app/repo to another (consolidation, module extraction), objects are briefly owned by two apps:

1. Land the **merged manifest** (old rules + new rules) in the **new** owner first; sync it.
2. Strip the **old** app's tracking-id annotation (`argocd.argoproj.io/tracking-id`) from the live objects.
3. Only then let the old app (typically `prune: true`, self-heal) sync — untracked objects are ignored.

Skip step 2 and the old app's next sync **deletes the live objects** it still tracks.


## Rendered ≠ working

A green xprin suite plus a synced app proves nothing about attach points outside the render path: Gateway API `allowedRoutes` namespace-selector labels (an HTTPRoute can render and never attach), CRD presence for kinds like VPA, admission-time label/annotation value charset. Drill one claim end-to-end on a real cluster before declaring a new module live.
