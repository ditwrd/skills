# Provider-specific external name patterns

The three major upjet providers (AWS, Azure, GCP) each handle external names
differently because their Terraform providers use fundamentally different ID
formats. This file documents the patterns unique to each provider as a
reference for writing a new provider or adding resources to one.

The canonical decision tree and standard patterns (`IdentifierFromProvider`,
`NameAsIdentifier`, `ParameterAsIdentifier`, `TemplatedStringAsIdentifier`,
`FormattedIdentifierFromProvider`) are in
[`external-name-patterns.md`](external-name-patterns.md). This file covers
what each provider **adds on top** of those standard patterns.

---

## AWS (`provider-upjet-aws`)

AWS's Terraform provider has ~4000 resources. The external name config file
(`config/externalname.go`) is the largest of the three — ~4000 lines, split
into SDK and Framework maps.

### Dominant patterns by frequency

| Pattern | Usage | Typical examples |
|---|---|---|
| `IdentifierFromProvider` | **Hundreds** | Most resources — ARNs, UUIDs, URLs |
| `TemplatedStringAsIdentifier` | Common | Compound IDs with `/` or `,` separator |
| `ParameterAsIdentifier` | Common | Named resources where a spec field IS the ID |
| `NameAsIdentifier` | Occasional | Resources where `name` IS the ID |
| `FormattedIdentifierFromProvider` | Moderate | Multi-key IDs assembled from TF state fields |

### ARN helper templates

AWS defines helper functions for ARN-based ID templates:

```go
// Full ARN: arn:{partition}:{service}:{region}:{account_id}:{resource}
// e.g. arn:aws:batch:us-west-2:123456789012:job-queue/my-queue
fullARNTemplate("batch", "job-queue/{{ .external_name }}")

// Regionless ARN: arn:{partition}:{service}::{account_id}:{resource}
// e.g. arn:aws:iam::123456789012:role/my-role
regionlessARNTemplate("iam", "role/{{ .external_name }}")

// Generic: customizable with/without region
genericARNTemplate(service, resource, elideRegion bool)
```

Template variables used by these helpers:

- `{{ .setup.client_metadata.partition }}` — AWS partition (`aws`, `aws-cn`, `aws-us-gov`)
- `{{ .setup.configuration.region }}` — provider region
- `{{ .setup.client_metadata.account_id }}` — AWS account ID

### Framework resource helpers

For Terraform Plugin Framework resources (`// @FrameworkResource`), AWS
provides custom helpers not in the upjet stdlib:

```go
// Computed identifier with a placeholder stub for initial read
// attr: the computed attribute name (e.g. "identifier")
// placeholder: stub value that passes TF validation (e.g. "artix3b6...")
config.FrameworkResourceWithComputedIdentifier("identifier", "artix3b6dqiognkp7732wzhroi")

// IdentifierFromProvider variant where TF rejects empty IDs entirely
identifierFromProviderWithDefaultStub("bedrock12345")

// NameAsIdentifier variant reading from TF state "name" instead of "id"
// Framework providers sometimes don't populate "id" in state
frameworkNameAsIdentifier()
```

The `frameworkNameAsIdentifier()` implementation:

```go
func frameworkNameAsIdentifier() config.ExternalName {
    e := config.NameAsIdentifier
    e.OmittedFields = []string{}
    e.GetIDFn = func(_ context.Context, _ string, _ map[string]any, _ map[string]any) (string, error) {
        return "", nil
    }
    e.GetExternalNameFn = func(tfstate map[string]any) (string, error) {
        name, ok := tfstate["name"].(string)
        if !ok {
            return "", errors.New("name field missing from tfstate")
        }
        return name, nil
    }
    return e
}
```

### Custom compound ID patterns

When the TF import format doesn't match any upjet stdlib pattern, AWS defines
custom functions that assemble IDs from multiple TF state fields:

```go
// API Gateway v1: reads state fields (rest_api_id, resource_id, http_method)
// and joins them. The internal TF ID uses "-" separator but import format uses "/".
func apiGatewayFormattedIdentifier(prefix string, keys ...string) config.ExternalName

// EKS Capability: compound ID from cluster_name + "," + capability_name
func eksCapability() config.ExternalName

// EKS Pod Identity: uses stub for association_id to pass TF validation,
// replaces stub with real external name after creation
func eksPodIdentityAssociation() config.ExternalName

// Network Monitor Probe: compound ID from monitor_name + "," + probe_id
func networkmonitorProbe() config.ExternalName

// WAFv2 WebACL Rule Group Association: 4-part composite key
// web_acl_arn,rule_name,custom|managed,identifier
func wafv2WebACLRuleGroupAssociation() config.ExternalName

// S3 Vectors: computed ARN identifier with region-aware stub
func s3vectorsComputedARNIdentifier(attr, stubSuffix string) config.ExternalName

// ECS Task Definition: seeds params["arn"] from external name on cold start
// to prevent empty-identifier API call failures
func ecsTaskDefinition() config.ExternalName
```

### Resource-level conventions

AWS applies `region` to `IdentifierFields` for **every** resource globally
in the `ResourceConfigurator()`:

```go
func ResourceConfigurator() config.ResourceOption {
    return func(r *config.Resource) {
        // ...
        // We had injected region as a parameter for all resources to be
        // consistent with the native aws provider, and now, we need to add
        // manually it to the identifier fields for all resources.
        r.ExternalName.IdentifierFields = append(r.ExternalName.IdentifierFields, "region")
    }
}
```

This means `region` is always part of the external name identity for AWS
resources, preventing cross-region name collisions.

### SDK vs Framework split

AWS maintains three separate config maps with a priority order:

1. `TerraformPluginFrameworkExternalNameConfigs` — highest priority
2. `TerraformPluginSDKExternalNameConfigs` — medium priority
3. `CLIReconciledExternalNameConfigs` — fallback

The `ResourceConfigurator()` checks them in order. A resource MUST appear in
**exactly one** map, or the generator panics.

### Key insight: ARN-based identity is the default

Most AWS resources use `IdentifierFromProvider` because the Terraform ID is
an ARN, which is provider-assigned. The ARN contains the region, account ID,
and resource type — so it serves as a globally unique identifier. This makes
AWS the simplest case for external name configuration: you often don't need
to configure anything beyond `IdentifierFromProvider`.

---

## Azure (`provider-upjet-azure`)

Azure's Terraform provider uses Azure Resource Manager (ARM) resource IDs
exclusively. Every resource's ID is a URL path like:

```
/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.X/{type}/{name}
```

### Dominant pattern: `TemplatedStringAsIdentifier` with ARM paths

**90%+ of Azure resources** use `TemplatedStringAsIdentifier` with an ARM
resource path template. The template always includes:

```go
config.TemplatedStringAsIdentifier("name", "/subscriptions/{{ .setup.configuration.subscription_id }}/resourceGroups/{{ .parameters.resource_group_name }}/providers/Microsoft.ApiManagement/service/{{ .external_name }}")
```

Template variables used:

- `{{ .setup.configuration.subscription_id }}` — from provider config
- `{{ .parameters.resource_group_name }}` — the resource group (always a parameter)
- `{{ .parameters.<field> }}` — parent resource names in the ARM path hierarchy
- `{{ .external_name }}` — the resource's name (the last path segment)

### Nested resource paths

For sub-resources (child resources under a parent), the template extends the
path with more segments:

```go
// 3 levels deep: service/{svc}/apis/{api}/operations/{op}
config.TemplatedStringAsIdentifier("operation_id",
    "/subscriptions/{{ .setup.configuration.subscription_id }}" +
    "/resourceGroups/{{ .parameters.resource_group_name }}" +
    "/providers/Microsoft.ApiManagement/service/{{ .parameters.api_management_name }}" +
    "/apis/{{ .parameters.api_name }}/operations/{{ .external_name }}")
```

### Delegation helpers for non-standard ID formats

Some Azure resources deviate from the ARM path pattern (Key Vault URLs,
Storage URLs, policy definitions). Azure defines custom helpers for these:

```go
// Key Vault secrets/keys/certificates: https://{vault}.vault.azure.net/{type}/{name}
func keyVaultURLIDConf(resourceType string) config.ExternalName

// Key Vault without version: reads name from state, constructs URL from
// keyVaultName + suffix + resourceType
func keyVaultURLIDWithoutVersionConfFn(resourceType string) config.ExternalName

// Storage Blob: https://{account}.blob.{suffix}/{container}/{blob}
func storageBlob() config.ExternalName

// Storage Container: https://{account}.blob.{suffix}/{container}
func storageContainer() config.ExternalName

// Storage Queue: https://{account}.queue.{suffix}/{queue}
func storageQueue() config.ExternalName

// Storage File Share: https://{account}.file.{suffix}/{share}
func storageShare() config.ExternalName

// Storage Data Lake Gen2: https://{account}.dfs.{suffix}/{filesystem}
func storageDataLakeGen2Filesystem() config.ExternalName
```

These storage helpers use `getStorageSuffix(terraformProviderConfig)` to
determine the correct blob/queue/file suffix for the Azure environment
(public, government, China):

```go
func getStorageSuffix(conf map[string]any) string {
    storageSuffixByEnvironment := map[string]string{
        "public": "core.windows.net",
        "usgovernment": "core.usgovcloudapi.net",
        "china": "core.chinacloudapi.cn",
    }
    // ...
}
```

### Policy definitions with scope routing

Policy definitions can be at subscription or management group level. The
custom `policyDefinitionExternalName()` helper handles both:

```go
func policyDefinitionExternalName(resourceType string) config.ExternalName {
    // If management_group_id is set, constructs:
    //   /providers/Microsoft.Management/managementgroups/{mg}/providers/{type}/{name}
    // Otherwise, constructs subscription-level path from provider config
}
```

### Resource-group-from-parent extraction

Some Azure resources don't have a `resource_group_name` parameter (the
resource group comes from a parent resource ID). Custom helpers extract it:

```go
func aiFoundryProjectExternalName() config.ExternalName {
    // ai_services_hub_id contains the resource group and subscription
    // Parse them from the hub ID to construct the project's resource ID
}

func mssqlManagedInstanceFailoverGroupExternalName() config.ExternalName {
    // managed_instance_id contains the resource group and subscription
    // Also normalizes location (e.g. "West Europe" → "westeurope")
}
```

### Key insight: the resource name is always the last path segment

For almost every Azure resource, `{{ .external_name }}` is the last segment
of the ARM resource path. The `GetExternalNameFn` typically extracts it from
the TF state ID by splitting on `/` and taking the last element. The `GetIDFn`
reconstructs the full ARM path by substituting the subscription, resource
group, parent names, and external name into the template.

Azure almost never uses `NameAsIdentifier` or `ParameterAsIdentifier` —
almost everything goes through `TemplatedStringAsIdentifier` because the
ARM path includes the subscription and resource group, making a simple name
insufficient as a unique identifier.

---

## GCP (`provider-upjet-gcp`)

GCP's Terraform provider uses resource paths in the format:

```
projects/{project}/locations/{location}/.../{name}
```

### Dominant pattern: `TemplatedStringAsIdentifier` with GCP paths

GCP resources use `TemplatedStringAsIdentifier` extensively with paths that
include the project from provider config:

```go
// Basic: projects/{project}/locations/{location}/services/{name}
config.TemplatedStringAsIdentifier("name",
    "projects/{{ .setup.configuration.project }}" +
    "/locations/{{ .parameters.location }}/services/{{ .external_name }}")

// Global (no location): projects/{project}/global/networks/{name}
config.TemplatedStringAsIdentifier("name",
    "projects/{{ .setup.configuration.project }}/global/networks/{{ .external_name }}")
```

### Conditional project in templates

Some GCP resources allow overriding the project at the resource level. The
templates use Go template conditionals:

```go
// projects/{{ parameters.project or setup.configuration.project }}/...
config.TemplatedStringAsIdentifier("name", "projects/" +
    "{{ if .parameters.project }}" +
    "{{ .parameters.project }}" +
    "{{ else }}" +
    "{{ .setup.configuration.project }}" +
    "{{ end }}" +
    "/locations/{{ .parameters.location }}/certificates/{{ .external_name }}")
```

This pattern appears for resources where the project can be overridden per
resource (common in GCP since resources from one project can reference
resources in another).

### IdentifierFromProvider usage

GCP uses `IdentifierFromProvider` for:

- **IAM members** (bindings, audit configs) — compound IDs with role/user info
- **Resources that don't support import** (no import section in TF docs)
- **Data Loss Prevention resources** — parent ID includes organization/project
- **Cloud Identity resources** — ID is a provider-assigned UUID
- **Compute resources with compound state** — disk attachments, network endpoints

### No-Name template helper

GCP defines a helper for templates where the resource has no user-defined
name parameter:

```go
func TemplatedStringAsIdentifierWithNoName(tmpl string) config.ExternalName {
    e := config.TemplatedStringAsIdentifier("", tmpl)
    e.DisableNameInitializer = true
    return e
}
```

Used for resources like `google_project_default_service_accounts` where the
ID is purely provider-defined.

### Apigee non-normalized ID handlers

Apigee resources have a non-normalized TF schema where the ID includes the
resource name but TF Read retrieves it from a `name` attribute:

```go
func apigeeInstanceAttachment() config.ExternalName {
    // Extracts name from external name (e.g. "instance/attachments/name")
    // and sets it on base["name"] for the Read to find
}

func apigeeOrganization() config.ExternalName {
    // Same pattern: extracts from "organizations/{name}"
}

func apigeeEnvgroupAttachment() config.ExternalName {
    // Same pattern: extracts from "{envgroup}/attachments/{name}"
}
```

### Cloud Identity fix

Google Cloud Identity resources use `IdentifierFromProvider` with a custom
`SetIdentifierArgumentFn` that sets `base["name"] = externalName`. This is
because the TF Read function uses `name` (a computed attribute) to find the
resource, not the ID field. Without this fix, the resource recreates on every
reconciliation after pod restart.

### Key insight: project is the common prefix

Unlike Azure's full-ARM-path approach or AWS's ARN approach, GCP paths are
shorter and usually follow `projects/{project}/{scope}/{type}/{name}`. The
project comes from provider config (`{{ .setup.configuration.project }}`) but
can be overridden per resource. The `location` parameter is optional for
global resources.

GCP uses `IdentifierFromProvider` more than Azure but less than AWS — roughly
half of resources use it, mostly for multi-key IDs (IAM, associations) and
resources lacking import support.

---

## Pattern comparison

| Dimension | AWS | Azure | GCP |
|---|---|---|---|
| **Typical ID format** | ARN or UUID | ARM resource path | GCP resource path |
| **Dominant pattern** | `IdentifierFromProvider` | `TemplatedStringAsIdentifier` | `TemplatedStringAsIdentifier` |
| **Account/Subscription** | From `client_metadata.account_id` | From `configuration.subscription_id` | From `configuration.project` |
| **Region** | Injected globally to `IdentifierFields` | Embedded in ARM path | Via `location` parameter |
| **Custom helpers** | ARN templates, Framework stubs | Storage URLs, Key Vault URLs, policy definitions | Conditionals, NoName, cloud identity, Apigee |
| **NameAsIdentifier usage** | Occasional (some serverless resources) | Almost never | Rare (logging metric) |
| **ParameterAsIdentifier usage** | Common (S3 bucket, Lambda function) | Almost never | Rare |
| **Framework resource handling** | Separate config map + 3 custom helpers | No Framework resources yet | 1 Framework resource |
| **Traps** | Stub values for computed Framework IDs | ARM path construction from parent IDs | Conditional project in templates |
