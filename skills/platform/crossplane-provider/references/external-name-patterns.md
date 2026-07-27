# External name patterns

Every upjet resource needs an external name config. The Terraform ID format
from the import section determines which pattern to use. To confirm the
pattern, check the TF provider source's `d.SetId()` call — it tells you
exactly what format the ID takes at runtime.


## Verifying the ID format

The Terraform import section tells you the shape of the ID, but the exact
format lives in the TF provider source. Verify by reading the Create
function:

1. **Find the TF provider source** on GitHub at the version matching your
   `TERRAFORM_PROVIDER_VERSION`. Read the resource's `.go` file under
   `pkg/resources/` (SDKv2) or the framework equivalent.

2. **Find `d.SetId()` in the Create function** — this call sets the TF state
   ID. Whatever string it receives is the external name format at runtime.

3. **Trace helper functions**: Many providers use encoding helpers that
   transform identifiers before joining them:
   - `AccountObjectIdentifier.FullyQualifiedName()` → `"NAME"` (SQL-quoted)
   - `SchemaObjectIdentifier.FullyQualifiedName()` → `"DB"."SCHEMA"."NAME"` (each segment quoted, dot-joined)
   - `EncodeResourceIdentifier` with `T=string` joins parts with `|` as-is.
     `T=AccountObjectIdentifier` uses bare `.Name()`;
     `T=SchemaObjectIdentifier` uses `.FullyQualifiedName()`.
   - The generic type parameter `T` is deduced from the argument type: pass
     a raw string → `T=string`; pass an identifier struct → `T=Identifier`.
   - Legacy encoders exist in some providers (e.g. an older encoder might join
     parts with `|` without quoting, while the newer encoder adds SQL-style
     quoting). Prefer the newer encoder when both exist — consistent quoting
     prevents false drifts on reconcile.

4. **Check the import function**: The `Importer.StateContext` typically calls
   `ParseResourceIdentifier(d.Id())` to split the ID on the separator. The
   number of parts tells you the compound structure.

5. **Confirm the pattern** against the decision tree below.

## Decision tree

```go
// Decision logic for Upjet External Name Configuration
// Read the Terraform import section, then trace d.SetId() in the Create function.

IF (provider generates the ID — ARN, URL, UUID, hash)
    USE config.IdentifierFromProvider

ELSE IF (compound ID with separator — pipe, colon, slash)
    USE config.TemplatedStringAsIdentifier("name", "template")
    // Azure-style: name is one segment of full resource ID
    // → config.NameAsIdentifier + GetExternalNameFn(extract name from ID) + GetIDFn(reconstruct full ID from name)

ELSE IF (bare name IS the identifier)
    USE config.NameAsIdentifier
    // name omitted from spec via OmittedFields, set via metadata.name

    IF (TF argument is NOT called "name")
        IF (TF argument is a visible spec field — e.g. "bucket" for S3)
            USE config.ParameterAsIdentifier("field_name")
            // Field stays in spec.forProvider
        ELSE
            // TF argument diverges from both "name" and a spec-visible field
            USE config.NameAsIdentifier + custom SetIdentifierArgumentFn + OmittedFields
            // metadata.name drives the ID, mapped to the non-standard TF argument name
        END IF
    END IF

ELSE IF (no import section)
    // The import section is absent, but d.SetId() in the Create function still
    // tells you the format. Read the TF source — the ID is determinable from code.
    IF (d.SetId() receives a provider-generated value — ARN, UUID, URL)
        USE config.IdentifierFromProvider
    ELSE IF (d.SetId() receives a compound of user-supplied parameters)
        USE config.TemplatedStringAsIdentifier("name", "template")
        // e.g. EncodeResourceIdentifier(user.FQN(), policy.FQN())
        // → TemplatedStringAsIdentifier with the FQN passed through as parameter
    END IF
```

Verify by tracing `d.SetId()` in the TF provider's Create function — whatever string it receives is the external name format.



## Patterns

### 1. IdentifierFromProvider — provider generates the ID

The provider assigns the ID (ARN, URL, UUID, random hash). The user's chosen
name is just a parameter in `spec.forProvider`, not the identifier.

**Config:** `config.IdentifierFromProvider`

**Runtime:** The external name is the provider-generated ID. `DisableNameInitializer: true` — `metadata.name` is just the K8s resource name.

**AWS examples:** `aws_sqs_queue`, `aws_vpc`, `aws_db_instance`, `aws_lb`, `aws_cloudfront_distribution`, `aws_acm_certificate` (hundreds of resources)

```yaml
kind: Queue
metadata:
  name: example          # just the K8s resource name
spec:
  forProvider:
    name: upbound-sqs    # the queue name (not the ID)
```

**How to verify:** The Terraform import section shows a URL, ARN, or UUID.
The provider source calls `d.SetId()` with a compound string (e.g. a URL).

---

### 2. NameAsIdentifier — user name IS the ID

The user chooses the name and it IS the identifier. No extra layer (ARN,
URL, UUID) from the provider.

**Config:** `config.NameAsIdentifier`

**Runtime:** `name` is omitted from `spec.forProvider` (in `OmittedFields`).
The `NewNameAsExternalName` initializer copies `metadata.name` to the
`crossplane.io/external-name` annotation. The framework reads the annotation
and passes it to `SetIdentifierArgumentFn`, which sets `name = externalName`
in the Terraform config.

```mermaid
sequenceDiagram
    User->>K8s: kubectl apply with metadata.name: "my-resource"
    K8s->>Initializer: NewNameAsExternalName
    Initializer->>K8s: Sets crossplane.io/external-name="my-resource"
    K8s->>Reconciler: Reads annotation
    Reconciler->>Terraform: SetIdentifierArgumentFn(name="my-resource")
    Terraform->>Provider: Create resource "my-resource"
    Provider->>Terraform: SetId("my-resource")
```

**AWS examples:** `aws_elasticache_serverless_cache`, `aws_opensearchserverless_access_policy`, `aws_opensearchserverless_lifecycle_policy`, `aws_opensearchserverless_security_policy`, `aws_codeguruprofiler_profiling_group`

```yaml
kind: ServerlessCache
metadata:
  name: example-cache    # THIS is the cache name (no spec.forProvider.name)
spec:
  forProvider:
    engine: memcached
```

**⚠️ Warnings:**

- **Don't change `crossplane.io/external-name` on an existing resource.** The
  annotation is the identity key in Terraform state. Changing it tells upjet
  to abandon the old resource and adopt a new name that doesn't exist yet,
  causing an import failure loop that trips the Crossplane circuit breaker.
  Set it at creation (or let the initializer set it) and never touch it again.

- **Generated examples may be empty.** Upjet only uses
  `MetaResource.Examples[0]` from the scraped metadata. If the Terraform
  doc's first example is minimal (only sets `name`), the generated example
  will show `forProvider: {}` for `NameAsIdentifier` resources because
  `name` is in `OmittedFields`. The example is technically correct — the
  name comes from `metadata.name` — but it's not a helpful starting point.
  Stage a richer example manually.

**How to verify:** The Terraform import section shows a bare name. The
provider source calls `d.SetId()` with a bare name (no ARN, no URL, no
quoting).

---

### 3. ParameterAsIdentifier — a spec field IS the ID

A specific field in `spec.forProvider` doubles as the identifier. The field
stays visible in the spec and is NOT omitted.

**Config:** `config.ParameterAsIdentifier("field_name")`

**Runtime:** `DisableNameInitializer: true`. The external name is the value
of the specified field. The field remains in `spec.forProvider` and can be
changed to recreate the resource.

**AWS examples:** `aws_s3_bucket` (field `bucket`), `aws_lambda_function`
(field `function_name`), `aws_redshift_cluster` (field `cluster_identifier`),
`aws_transcribe_vocabulary` (field `vocabulary_name`)

```yaml
kind: Bucket
metadata:
  name: example          # just the K8s resource name
spec:
  forProvider:
    bucket: my-bucket    # THIS is the bucket name and the identifier
    region: us-west-1
```

**How to verify:** The Terraform import section shows a bare field value.
The provider source calls `d.SetId()` with the value of that specific field.

---

### 4. TemplatedStringAsIdentifier / FormattedIdentifierFromProvider — compound IDs

The external name is built from multiple fields using a template with a
separator.

**Config:** `config.TemplatedStringAsIdentifier("name", "template")` or
`FormattedIdentifierFromProvider("separator", "field1", "field2", ...)`

**Runtime:** The template is evaluated at import time. `{{ .external_name }}`
is the Crossplane external-name annotation value. `{{ .parameters.<field> }}`
reads from `spec.forProvider`. `{{ .setup.client_metadata.account_id }}`
reads from provider metadata.

**AWS examples:** `aws_accessanalyzer_archive_rule` (template
`analyzer_name/rule_name`), `aws_s3_bucket_metric` (separator `:`,
fields `bucket` and `name`), `aws_rds_cluster_role_association` (separator `,`,
fields `db_cluster_identifier` and `role_arn`)

```go
config.TemplatedStringAsIdentifier(
    "rule_name",
    "{{ .parameters.analyzer_name }}/{{ .external_name }}",
)
```

Available template variables:

- `{{ .parameters.<field> }}` — any Terraform argument
- `{{ .external_name }}` — the Crossplane external-name annotation value
- `{{ .terraformProviderConfig.<field> }}` — provider config values
- `{{ .setup.client_metadata.account_id }}` — provider client metadata

**How to verify:** The Terraform import section shows a compound format
(e.g. `field1|field2`, `field1/field2`, `field1:field2`). Check the provider
source for `ParseResourceIdentifier` or equivalent splitting logic.

Edge case — quoted compound IDs: the key distinction is whether quoting is
**uniform** (all segments get the same treatment) or **mixed** (some quoted,
some bare).

- **Uniform quoting** (e.g. `"USER"|"TOKEN"`, `name1:name2`): both segments
  are quoted or both bare. `TemplatedStringAsIdentifier` works cleanly; add
  the quotes to the template:
  `"\"{{ .parameters.user }}\"|\"{{ .external_name }}\""`. The reverse
  extraction (`GetExternalNameFromTemplated`) handles literal double-quotes
  as delimiters.

- **Mixed quoting** (e.g. `"user"|"db"."schema"."policy"` — first segment
  SQL-quoted, second is a multi-segment FQN with its own quoting):
  `TemplatedStringAsIdentifier` still works IF the second segment arrives as
  a single parameter value (the FQN already including its own quoting).
  Pass it through directly — the template doesn't need to understand or
  reproduce the FQN's internal structure:
  `"\"{{ .external_name }}\"|{{ .parameters.policy_name }}"`.
  Only fall back to `IdentifierFromProvider` when the template would need to
  reconstruct the internal quoting of a parameter from multiple sub-fields.

Check the TF provider's `Parse*Identifier` function to understand how it
splits and normalizes the ID. If the provider removes quotes internally,
`NameAsIdentifier` may also be a safe simplification.

### 4.5. Conditional compound IDs — one-of-many mutually-exclusive parameters

Some resources build their ID from the external name plus exactly one of
several mutually-exclusive parameters (e.g. a grant resource where the
grantee is a role, user, database_role, or share — only one is set at a
time). The TF schema marks these with `ExactlyOneOf`.

**Config:** provider-local `OneOfIdentifier` helper. Define once in
`config/external_name.go`, then use for every resource with this pattern.

The helper takes a prefix template and a map of parameter → prefix labels,
then builds a `TemplatedStringAsIdentifier` with a sorted-key conditional
chain (`if / else if / end`, no bare else fallback — safe because the
parameters are ExactlyOneOf).

**Example (Snowflake grant_database_role):**
```go
func OneOfIdentifier(nameField, prefix string, params map[string]string) config.ExternalName {
    keys := slices.Sorted(maps.Keys(params))
    var tmpl strings.Builder
    tmpl.WriteString(prefix)
    for i, k := range keys {
        if i == 0 {
            fmt.Fprintf(&tmpl, `{{ if .parameters.%s }}%s|"{{ .parameters.%s }}"`, k, params[k], k)
        } else {
            fmt.Fprintf(&tmpl, `{{ else if .parameters.%s }}%s|"{{ .parameters.%s }}"`, k, params[k], k)
        }
    }
    tmpl.WriteString(`{{ end }}`)
    return config.TemplatedStringAsIdentifier(nameField, tmpl.String())
}
```

**Usage:**
```go
// ID: '<db_role_fqn>|ROLE|<parent_role>' or '|DATABASE_ROLE|<parent_db_role>' or '|SHARE|<share>'
"snowflake_grant_database_role": OneOfIdentifier("database_role_name",
    `{{ .external_name }}|`,
    map[string]string{
        "parent_role_name":          "ROLE",
        "parent_database_role_name": "DATABASE_ROLE",
        "share_name":                "SHARE",
    },
),
```

When the prefix needs a fixed parameter inline (e.g. `privileges` before the
conditional chain), include it in the prefix template string.

**Why a helper:** Without it, `TemplatedStringAsIdentifier` with 6-9
conditional branches produces unreadable 400+ char inline template strings.
The helper compresses the same logic into ~10 readable lines.

**How to verify:** Check the TF source for `ExactlyOneOf` constraints on the
parameters. The template tests each parameter; at most one will be non-empty.


### 5. Binding/Attachment resources — parent identity as identifier

Resources that "attach" or "bind" one resource to another (policy attachments,
role associations, etc.) often use compound IDs where one part identifies the
parent and another identifies the child. The parent identity functions as the
resource identifier (1:1 cardinality per parent per type), and the child FQN
is a template parameter.

**Config:** `config.TemplatedStringAsIdentifier("parent_field", "template")`

**Runtime:** The parent field (e.g. `user_name`) becomes the identifier —
omitted from `spec.forProvider`, set via `metadata.name` → `external-name`
annotation. The child FQN stays in `spec.forProvider` as a regular parameter.
The template reconstructs the exact Terraform ID at create/import time.

**Example (WAFv2 rule group association):**

```go
// The parent (web ACL ARN) becomes the identifier.
// The template reconstructs the compound ID: web_acl_arn,rule_name,type,identifier
config.TemplatedStringAsIdentifier(
    "",
    "{{ .parameters.web_acl_arn }},{{ .parameters.rule_name }},custom,{{ .external_name }}",
)
```

For a real implementation that handles both custom and managed rule groups
with state-based disambiguation, see `wafv2WebACLRuleGroupAssociation()` in
the AWS provider's `config/externalname.go`.

**How to verify:** The TF Create function calls `d.SetId()` with a compound
string joining parent and child identifiers. The Read function splits on the
separator (`,` `/` `|`). Expect the same number of parts as the template.

---

## Quick reference

For the canonical decision tree, see [Decision tree](#decision-tree) at the top of this file.


## Framework resources

For Terraform Plugin Framework resources (`// @FrameworkResource` in TF source),
the standard patterns above still work: `NameAsIdentifier`, `ParameterAsIdentifier`,
`IdentifierFromProvider`, `TemplatedStringAsIdentifier`. But Framework resources
need additional handling for computed identifiers and stricter input validation.

Framework resources use **separate config maps and include lists** from SDK
resources — `TerraformPluginFrameworkExternalNameConfigs` and
`TerraformPluginFrameworkIncludeList`. A resource MUST appear in at most one
include list (SDK, Framework, or CLI) or the generator panics.

### Framework-specific patterns (from provider-aws)

| Pattern | When to use | Real example |
|---|---|---|
| `FrameworkResourceWithComputedIdentifier(attr, placeholder)` | Provider assigns the ID (ARN, UUID); TF validation needs a stub during initial read. Sets `ComputedIdentifierAttributes` to strip the field from desired-state config, preventing drift false-positives. | `aws_dsql_cluster` — stub `"artix3b6..."` for `identifier` attribute |
| `identifierFromProviderWithDefaultStub(stub)` | `IdentifierFromProvider` variant where TF rejects empty IDs outright. Stub passes validation during initial read before the real ID exists. | `aws_bedrock_inference_profile` — stub `"bedrock12345"` |
| `frameworkNameAsIdentifier()` | `NameAsIdentifier` variant but reads external name from `name` in TF state instead of `id` (Framework providers sometimes don't populate `id`). | `aws_bedrockagentcore_api_key_credential_provider` |
| Custom (provider-specific) | Computed ARN identifier with region-aware stub to avoid API rejection | `aws_s3vectors_vector_bucket` — stub ARN includes correct region |

### How to decide

1. Check TF source for `// @FrameworkResource` or `// @SDKResource` annotation.
2. Check the import section on the Terraform Registry for ID format.
3. If `IdentifierFromProvider` and Framework: use `FrameworkResourceWithComputedIdentifier`
   when the provider generates a computed attribute (ARN, gateway_id). Use
   `identifierFromProviderWithDefaultStub` when the provider rejects empty IDs
   entirely.
4. If `NameAsIdentifier` and Framework: check whether the provider populates `id`
   in TF state. If not, use the `frameworkNameAsIdentifier()` helper (copy the
   pattern from provider-aws; it's not in the upjet stdlib).
5. Add the resource to `TerraformPluginFrameworkExternalNameConfigs` (not
   `TerraformPluginSDKExternalNameConfigs` or CLI `ExternalNameConfigs`).

### Framework-only options

- **`ComputedIdentifierAttributes`**: List of computed attribute names the
  controller strips from desired-state config during drift calculation.
  `FrameworkResourceWithComputedIdentifier` sets this automatically.
- **`IsNotFoundDiagnosticFn`**: Some Framework Read implementations return
  error diagnostics for missing resources instead of empty state. Set this
  on `ExternalName` to suppress them.
- **`TerraformPluginFrameworkIsStateEmptyFn`**: Custom logic for when Framework
  state should be treated as "resource doesn't exist." Set on `config.Resource`.
