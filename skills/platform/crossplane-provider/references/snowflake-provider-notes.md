# Snowflake provider notes

Concrete incidents from `provider-upjet-snowflake` illustrating the generic
bug classes in [`troubleshooting.md`](troubleshooting.md). Read the generic
section first; this file only fills in the provider-specific mechanics.

## Delete fails with empty identifier after patching an `on_all`/`on_future` grant under deletion

Generic pattern: [Delete fails with empty identifier after patching a bulk-grant resource under deletion](troubleshooting.md#delete-fails-with-empty-identifier-after-patching-a-bulk-grant-resource-under-deletion).

Snowflake specifics:

- The affected resources are `GrantPrivilegesTo*Role` kinds configured with
  an `on_all`/`on_future` schema-object or schema grant. The vendored
  `terraform-provider-snowflake` source documents the no-op `Read` with a
  comment near the show-grants request builder, e.g. `"Show with on_all
  option is skipped. No changes in privileges in Snowflake will be
  detected."`
- The empty-identifier error surfaces from the SDK's identifier parser
  (`pkg/sdk/identifier_parsers.go`, `ParseIdentifierStringWithOpts`) as
  `incompatible identifier: ` (trailing empty string) when `Delete` builds a
  revoke request from the empty refreshed state.
- A common trigger for the mid-deletion patch: `objectTypePlural` (and
  similar free-text CRD fields mirroring TF arguments) has **no enum
  validation** in the generated CRD, even though Snowflake's grant SQL only
  accepts the plural literal form (e.g. `TABLES`, not `TABLE`). A `kubectl
  apply` with the singular form succeeds silently; the error only surfaces
  at apply/delete time as a Snowflake SQL syntax error (`unexpected 'TABLE',
  expects 'TABLES'`).
- Fix/prevention: same as the generic entry — force-remove the finalizer,
  recreate rather than patch in place. For the `objectTypePlural` case
  specifically, validate against the Snowflake grant SQL reference (plural
  forms only) before applying.

## Mutually exclusive schema fields both set — `on_schema` block

Generic pattern: [Mutually exclusive TF schema fields both set — one silently dropped](troubleshooting.md#mutually-exclusive-tf-schema-fields-both-set--one-silently-dropped).

Snowflake specifics: `grant_privileges_to_database_role`'s (and
`grant_privileges_to_account_role`'s) `on_schema` block schema marks
`schema_name` / `all_schemas_in_database` / `future_schemas_in_database` /
`inherited` as `ExactlyOneOf`. Setting both `allSchemasInDatabase` and
`futureSchemasInDatabase` in one CR's `onSchema` block is accepted by the CRD;
the provider's build-switch takes `all_schemas_in_database` first and
silently drops the future-schemas grant. Fix by splitting into two
resources, mirroring the repo's own `*-grants-all` / `*-grants-future`
naming convention already used for schema-object grants.

