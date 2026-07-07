# Composition anatomy (v1 API, v2-compatible)

Composition is `apiextensions.crossplane.io/v1` (no v2 version exists). The pipeline has two required steps: a `function-go-templating` step that renders composed resources, and a `function-auto-ready` step that marks readiness.

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: xnetwork-example-org-v1alpha1
spec:
  compositeTypeRef:
    apiVersion: example.org/v1alpha1
    kind: XNetwork
  mode: Pipeline
  pipeline:
    - step: render-resources
      functionRef:
        name: function-go-templating
      input:
        apiVersion: gotemplating.fn.crossplane.io/v1beta1
        kind: GoTemplate
        source: Inline
        inline:
          template: |
            ---
            apiVersion: ec2.aws.m.upbound.io/v1beta1
            kind: VPC
            metadata:
              annotations:
                {{ setResourceNameAnnotation "vpc" }}
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-vpc
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                cidrBlock: {{ .observed.composite.resource.spec.cidrBlock }}
              providerConfigRef:
                name: default
            # ... more composed resources ...

    - step: automatically-detect-ready-composed-resources
      functionRef:
        name: function-auto-ready
```

Key points:
- Name the Composition `<xrd>-<group>-<version>` so multiple versions compose cleanly.
- The render step emits one or more `---`-separated YAML docs. Each becomes a composed resource. Every composed resource needs the `{{ setResourceNameAnnotation "key" }}` helper (or the long-form `gotemplating.fn.crossplane.io/composition-resource-name` annotation) so downstream steps and `function-auto-ready` can reference it.
- The auto-ready step has no `input` block by default — it walks all composed resources produced by the pipeline and checks their standard `status.conditions[type=Ready]` (or built-in health checks for native Kubernetes resources like Deployment/Pod).
- `function-auto-ready` respects the `gotemplating.fn.crossplane.io/ready: "True|False"` annotation. If a render step marks a resource not ready, auto-ready won't override.
- Function pipeline constraints (from the official Compositions docs — they will silently bite you if you ignore them):
  - A function **can** change the XR's `status`, `status.conditions`, and readiness. It can also change composed resources' `metadata` and `spec`.
  - A function **cannot** change composed resources' `status` — Crossplane owns that, populated from what the provider controller observes. Trying to set `status.atProvider` on a managed resource from your template is a no-op.
  - A function **cannot** change the XR's `metadata` or `spec` — only the function's *output* can populate XR status fields. The XR is the user-owned source of truth.
  - A function **must** return the full desired state of composed resources every call. If you set a field once and omit it on the next call, Crossplane deletes the field (server-side apply semantics).
