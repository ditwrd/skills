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
| **Execution path** | How upjet communicates with the Terraform plugin: CLI subprocess (
`IncludeList`, forks `terraform` binary), SDK in-process
(`TerraformPluginSDKIncludeList`, direct Go SDK calls), or Framework in-process
(`TerraformPluginFrameworkIncludeList`, in-process gRPC). Determines which fixes
take effect — `TerraformConfigurationInjector` only fires in SDK/Framework paths. |
| **Sentinel default** | A Terraform schema `Default` value that is valid for
the schema (e.g. `BooleanDefault = "default"`) but fails the provider's own
`ValidateFunc`/`ValidateDiagFunc`. The TF plugin treats it as "no user value,
use server default" but passes it down to validation as the literal string.
Must be handled via `LateInitializer.IgnoredFields` in upjet providers. |
| **Identity cardinality** | How many resource instances legitimately share one candidate identity field. A field with 1:1 cardinality (each value maps to exactly one resource) is safe as a `TemplatedStringAsIdentifier`/`OneOfIdentifier` nameField. A field with many:1 cardinality (TF's own examples `for_each` over another field while holding this one fixed — e.g. granting one role to N grantees) is NOT safe: `OmittedFields` ties it to `metadata.name`/`crossplane.io/external-name`, so only one resource per value survives without manual annotation overrides. Check cardinality before reaching for `OneOfIdentifier`; see external-name-patterns.md §4.5/§4.6. |
| **schemadiff** | Upjet CLI tool that compares CRD versions and emits JSON for auto-conversion registration. |
