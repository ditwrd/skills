# Glossary

| Term | Definition |
|---|---|
| **upjet** | The code generation framework and runtime that wraps Terraform providers into Crossplane managed resources. The leading word for all provider-authoring work. |
| **External name** | The `crossplane.io/external-name` annotation identifying the cloud resource. Upjet maps between this and the Terraform state ID. |
| **Scope** | Whether a managed resource is cluster-scoped (legacy, group like `ec2.aws.upbound.io`) or namespaced (modern, group like `ec2.aws.m.upbound.io`). Upjet v2 generates both. |
| **Short group** | The API group segment after the provider root (e.g. `repository` in `repository.github.upbound.io`). Overrides the default derived from the TF type name. |
| **MR** | Managed Resource — a Crossplane CRD that represents a single cloud resource. |
| **MRD** | Managed Resource Definition — the CRD schema for a managed resource. |
| **upjet-provider-template** | The GitHub template repository for bootstrapping a new upjet provider. |
| **uptest** | Automated end-to-end testing framework for upjet providers. |
| **schemadiff** | Upjet CLI tool that compares CRD versions and emits JSON for auto-conversion registration. |
