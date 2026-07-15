# AWS provider reference

Consolidated AWS-specific content for Crossplane v2 compositions. All patterns assume `provider-family-aws` (upjet-based).

## CRD group convention

Namespaced v2 MRs use `<service>.aws.m.upbound.io/v1beta1`:
- `ec2.aws.m.upbound.io/v1beta1` — VPC, Subnet, InternetGateway, RouteTable, SecurityGroup, etc.
- `s3.aws.m.upbound.io/v1beta1` — Bucket, BucketNotification, etc.
- `sqs.aws.m.upbound.io/v1beta1` — Queue, QueuePolicy, etc.
- `rds.aws.m.upbound.io/v1beta1` — DBInstance, SubnetGroup, etc.
- `cloudwatchlogs.aws.m.upbound.io/v1beta1` — LogGroup, etc.

The legacy cluster-scoped group `<service>.aws.upbound.io` still works for v1-style resources but is deprecated for new work.

Use the Upbound marketplace for the full list:
<https://marketplace.upbound.io/providers/upbound/provider-family-aws/latest/managed-resources>

For the latest field set, check the upstream repo:
<https://github.com/crossplane-contrib/provider-upjet-aws/tree/main/examples>
and the per-resource `.tf` files in `internal/clients/`.

### Active vs Inactive MRDs

Some providers ship CRDs as `Inactive` under safe-start. Activate:
```sh
kubectl patch mrd <name>.<service>.aws.m.upbound.io \
  --type='merge' -p='{"spec":{"state":"Active"}}'
```

## providerConfigRef patterns

### kind requirement

Always include `kind` — omitting it fails with `spec.providerConfigRef.kind: Required value`:

```yaml
providerConfigRef:
  name: default
  kind: ClusterProviderConfig
```

### ClusterProviderConfig vs ProviderConfig

- `ClusterProviderConfig` (cluster-scoped) — preferred. Works across namespaces, no cross-namespace trap.
- `ProviderConfig` (Namespaced) — only when the ProviderConfig is in the same namespace as the managed resource.

### Cross-namespace trap

For `*.aws.m.upbound.io` providers, `ProviderConfig` is `Namespaced` scope. If the managed resource is in namespace X and the `ProviderConfig` only exists in namespace Y, the provider can't authenticate. The MR gets `status: {}` with no conditions (SYNCED and READY columns are blank), and the provider pod logs show "Calling the inner handler for Create event" but never progress beyond that.

**Fix:** use `kind: ClusterProviderConfig` or add `namespace: <providerconfig-ns>` to the MR's `providerConfigRef`.

## Provider default tags

Upjet AWS providers inject three default tags into `forProvider.tags` on every reconcile:

| Tag | Value |
|---|---|
| `crossplane-name` | The MR's `metadata.name` |
| `crossplane-providerconfig` | The `providerConfigRef.name` |
| `crossplane-kind` | `<kind>.<group>` (e.g. `Bucket.s3.aws.m.upbound.io`) |

**The composition template MUST include all three** with matching values. If the template omits them, the provider's Update races with the composition's SSA Apply: the provider writes tags → composition re-applies without them → `Cannot add finalizer: object has been modified`. Generation climbs to 100+ with no resource created.

Common practice — emit tags at the top of the template and reuse:

```yaml
{{- $tags := dict
  "Name" (printf "%s-%s" .observed.composite.resource.metadata.name "bucket")
  "crossplane-name" (printf "%s-%s" .observed.composite.resource.metadata.name "bucket")
  "crossplane-providerconfig" "default"
  "crossplane-kind" "Bucket.s3.aws.m.upbound.io"
}}
```

Some resources don't support `tags` (e.g. QueuePolicy, BucketNotification) — omit the field entirely for those.

## Module path convention

AWS modules live under `modules/aws/<service>-<thing>/`:

```
modules/aws/
  s3-with-policy/
    xrd.yaml
    composition.yaml
    tests/
      example-xr.yaml
      observed-queues.yaml
      s3-with-policy_xprin.yaml
  vpc-basic/
    ...
  postgres/
    ...
```

See [module-folder-structure.md](module-folder-structure.md) for the canonical layout (the `modules/` root pattern is generic; the AWS convention is to group under `modules/aws/`).

## Complete examples

### Example 1: XNetwork — VPC + public subnet + private subnet + IGW + route tables

A foundational network primitive. The render step emits all six resources, and `function-auto-ready` waits for the whole set before marking the XR ready.

#### XRD

```yaml
apiVersion: apiextensions.crossplane.io/v2
kind: CompositeResourceDefinition
metadata:
  name: xnetworks.example.org
spec:
  scope: Namespaced
  group: example.org
  names:
    kind: XNetwork
    plural: xnetworks
  versions:
    - name: v1alpha1
      served: true
      referenceable: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              required: [region]
              properties:
                region:    { type: string }
                cidrBlock: { type: string, default: "10.0.0.0/16" }
            status:
              type: object
              properties:
                vpcId:     { type: string }
                publicSubnetId:  { type: string }
                privateSubnetId: { type: string }
                ready:     { type: boolean }
```

#### Composition

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
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                cidrBlock: {{ default "10.0.0.0/16" .observed.composite.resource.spec.cidrBlock }}
                enableDnsSupport: true
                enableDnsHostnames: true
                tags:
                  Name: {{ .observed.composite.resource.metadata.name }}-vpc
              providerConfigRef:
                name: default
                kind: ClusterProviderConfig
            ---
            apiVersion: ec2.aws.m.upbound.io/v1beta1
            kind: Subnet
            metadata:
              annotations:
                {{ setResourceNameAnnotation "public" }}
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                vpcId: {{ dig "status" "atProvider" "vpcId" "" (index $.observed.resources "vpc") }}
                cidrBlock: 10.0.1.0/24
                mapPublicIpOnLaunch: true
                availabilityZone: {{ .observed.composite.resource.spec.region }}a
                tags:
                  Name: {{ .observed.composite.resource.metadata.name }}-public
              providerConfigRef:
                name: default
                kind: ClusterProviderConfig
            ---
            apiVersion: ec2.aws.m.upbound.io/v1beta1
            kind: Subnet
            metadata:
              annotations:
                {{ setResourceNameAnnotation "private" }}
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                vpcId: {{ dig "status" "atProvider" "vpcId" "" (index $.observed.resources "vpc") }}
                cidrBlock: 10.0.2.0/24
                availabilityZone: {{ .observed.composite.resource.spec.region }}b
                tags:
                  Name: {{ .observed.composite.resource.metadata.name }}-private
              providerConfigRef:
                name: default
                kind: ClusterProviderConfig
            ---
            apiVersion: ec2.aws.m.upbound.io/v1beta1
            kind: InternetGateway
            metadata:
              annotations:
                {{ setResourceNameAnnotation "igw" }}
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                vpcId: {{ dig "status" "atProvider" "vpcId" "" (index $.observed.resources "vpc") }}
                tags:
                  Name: {{ .observed.composite.resource.metadata.name }}-igw
              providerConfigRef:
                name: default
                kind: ClusterProviderConfig
            ---
            apiVersion: ec2.aws.m.upbound.io/v1beta1
            kind: RouteTable
            metadata:
              annotations:
                {{ setResourceNameAnnotation "publicrt" }}
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                vpcId: {{ dig "status" "atProvider" "vpcId" "" (index $.observed.resources "vpc") }}
                route:
                  - cidrBlock: 0.0.0.0/0
                    gatewayId: {{ dig "status" "atProvider" "internetGatewayId" "" (index $.observed.resources "igw") }}
                tags:
                  Name: {{ .observed.composite.resource.metadata.name }}-public
              providerConfigRef:
                name: default
                kind: ClusterProviderConfig
            ---
            apiVersion: ec2.aws.m.upbound.io/v1beta1
            kind: RouteTableAssociation
            metadata:
              annotations:
                {{ setResourceNameAnnotation "publicrta" }}
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                subnetId: {{ dig "status" "atProvider" "subnetId" "" (index $.observed.resources "public") }}
                routeTableId: {{ dig "status" "atProvider" "routeTableId" "" (index $.observed.resources "publicrt") }}
              providerConfigRef:
                name: default
                kind: ClusterProviderConfig

    - step: automatically-detect-ready-composed-resources
      functionRef:
        name: function-auto-ready
```

#### XR

In v2, `XNetwork` is itself the user-facing resource — there is no separate claim.

```yaml
apiVersion: example.org/v1alpha1
kind: XNetwork
metadata:
  name: my-app
  namespace: default
spec:
  region: us-east-1
  cidrBlock: 10.0.0.0/16
```

### Example 2: XPostgres — RDS instance with security group, subnet group, password Secret, and a composed connection Secret

Self-contained: the XR takes `vpcId` and `subnetIds` directly instead of referencing another XR, so the example focuses on the v2 patterns (password via Secret, connection details via a composed `Secret`, readiness via `function-auto-ready`) rather than cross-XR plumbing.

#### XRD

```yaml
apiVersion: apiextensions.crossplane.io/v2
kind: CompositeResourceDefinition
metadata:
  name: xpostgreses.example.org
spec:
  scope: Namespaced
  group: example.org
  names:
    kind: XPostgres
    plural: xpostgreses
  versions:
    - name: v1alpha1
      served: true
      referenceable: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              required: [region, vpcId, subnetIds]
              properties:
                region:        { type: string }
                vpcId:         { type: string }
                subnetIds:
                  type: array
                  items: { type: string }
                version:       { type: string, default: "15.7" }
                instanceClass: { type: string, default: "db.t3.micro" }
                storageGb:     { type: integer, default: 20 }
            status:
              type: object
              properties:
                endpoint: { type: string }
                ready:    { type: boolean }
```

#### Composition

The render step emits a Secret (the generated password), the security group, the RDS instance, the subnet group, and a composed `Secret` that copies `endpoint`/`username`/`password` from the instance's `connectionDetails` on the second reconcile onward.

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: xpostgres-example-org-v1alpha1
spec:
  compositeTypeRef:
    apiVersion: example.org/v1alpha1
    kind: XPostgres
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
            apiVersion: v1
            kind: Secret
            metadata:
              annotations:
                {{ setResourceNameAnnotation "pg-pw" }}
              name: {{ .observed.composite.resource.metadata.name }}-pg-pw
              namespace: crossplane-system
            type: Opaque
            data:
              password: {{ randAlphaNum 24 | b64enc }}
            ---
            apiVersion: ec2.aws.m.upbound.io/v1beta1
            kind: SecurityGroup
            metadata:
              annotations:
                {{ setResourceNameAnnotation "sg" }}
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                vpcId: {{ .observed.composite.resource.spec.vpcId }}
                ingress:
                  - fromPort: 5432
                    toPort: 5432
                    protocol: tcp
                    cidrBlocks: ["10.0.0.0/16"]
                    description: "postgres"
                egress:
                  - fromPort: 0
                    toPort: 0
                    protocol: "-1"
                    cidrBlocks: ["0.0.0.0/0"]
                tags:
                  Name: {{ .observed.composite.resource.metadata.name }}-rds-sg
              providerConfigRef:
                name: default
                kind: ClusterProviderConfig
            ---
            apiVersion: rds.aws.m.upbound.io/v1beta1
            kind: Instance
            metadata:
              annotations:
                {{ setResourceNameAnnotation "pg" }}
            spec:
              writeConnectionSecretToRef:
                name: {{ .observed.composite.resource.metadata.name }}-pg-conn
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                engine: postgres
                engineVersion: {{ default "15.7" .observed.composite.resource.spec.version }}
                instanceClass: {{ default "db.t3.micro" .observed.composite.resource.spec.instanceClass }}
                allocatedStorage: {{ default 20 .observed.composite.resource.spec.storageGb | int64 }}
                dbSubnetGroupName: {{ .observed.composite.resource.metadata.name }}-subnets
                vpcSecurityGroupIds:
                  - {{ dig "status" "atProvider" "securityGroupId" "" (index $.observed.resources "sg") }}
                passwordSecretRef:
                  name: {{ .observed.composite.resource.metadata.name }}-pg-pw
                  namespace: crossplane-system
                  key: password
                publiclyAccessible: false
                skipFinalSnapshot: true
                tags:
                  Name: {{ .observed.composite.resource.metadata.name }}-pg
              providerConfigRef:
                name: default
                kind: ClusterProviderConfig
            ---
            apiVersion: rds.aws.m.upbound.io/v1beta1
            kind: SubnetGroup
            metadata:
              annotations:
                {{ setResourceNameAnnotation "subnets" }}
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                subnetIds:
                  {{ range $i, $s := .observed.composite.resource.spec.subnetIds }}
                  - {{ $s }}
                  {{ end }}
                tags:
                  Name: {{ .observed.composite.resource.metadata.name }}-subnets
              providerConfigRef:
                name: default
                kind: ClusterProviderConfig
            ---
            # Composed Secret — copies endpoint/username/password from the
            # Instance's connectionDetails on the second reconcile onward.
            # The nil-guard prevents panics when the Instance hasn't been
            # created yet (first reconcile).
            {{- $obs := default (dict) $.observed.resources }}
            {{- $pg := dig "pg" (dict) $obs }}
            {{- $conn := $pg.connectionDetails }}
            {{- if $conn }}
            apiVersion: v1
            kind: Secret
            metadata:
              annotations:
                {{ setResourceNameAnnotation "pg-conn" }}
              name: {{ .observed.composite.resource.metadata.name }}-pg-conn
              namespace: default
            type: Opaque
            data:
              endpoint: {{ dig "endpoint" "" $conn | b64enc }}
              username: {{ dig "username" "" $conn | b64enc }}
              password: {{ dig "password" "" $conn | b64enc }}
            {{- end }}

    - step: automatically-detect-ready-composed-resources
      functionRef:
        name: function-auto-ready
```

#### XR

```yaml
apiVersion: example.org/v1alpha1
kind: XPostgres
metadata:
  name: my-app
  namespace: default
spec:
  region: us-east-1
  vpcId: vpc-abc123
  subnetIds:
    - subnet-1
    - subnet-2
```

Read the composed connection details:

```sh
kubectl get secret my-app-pg-conn -n default -o jsonpath='{.data}' | base64 -d
```

On the first reconcile the `data` map is empty (the `pg` instance hasn't produced `connectionDetails` yet) — the nil-guard in the template prevents the `index` call from panicking.
