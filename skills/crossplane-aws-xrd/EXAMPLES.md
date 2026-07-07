# Examples

Two complete, copy-pastable AWS composites for Crossplane v2. Each is the minimal viable version — adapt field paths to whatever version of `provider-upjet-aws` you have installed.

## Example 1: XNetwork — VPC + public subnet + private subnet + IGW + route tables

A foundational network primitive. The render step emits all six resources, and `function-auto-ready` waits for the whole set before marking the XR ready.

### XRD

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

### Composition

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
                cidrBlock: {{ default "10.0.0.0/16" .observed.composite.resource.spec.cidrBlock }}
                enableDnsSupport: true
                enableDnsHostnames: true
                tags:
                  Name: {{ .observed.composite.resource.metadata.name }}-vpc
              providerConfigRef:
                name: default
            ---
            apiVersion: ec2.aws.m.upbound.io/v1beta1
            kind: Subnet
            metadata:
              annotations:
                {{ setResourceNameAnnotation "public" }}
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-public
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
            ---
            apiVersion: ec2.aws.m.upbound.io/v1beta1
            kind: Subnet
            metadata:
              annotations:
                {{ setResourceNameAnnotation "private" }}
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-private
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
            ---
            apiVersion: ec2.aws.m.upbound.io/v1beta1
            kind: InternetGateway
            metadata:
              annotations:
                {{ setResourceNameAnnotation "igw" }}
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-igw
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                vpcId: {{ dig "status" "atProvider" "vpcId" "" (index $.observed.resources "vpc") }}
                tags:
                  Name: {{ .observed.composite.resource.metadata.name }}-igw
              providerConfigRef:
                name: default
            ---
            apiVersion: ec2.aws.m.upbound.io/v1beta1
            kind: RouteTable
            metadata:
              annotations:
                {{ setResourceNameAnnotation "publicrt" }}
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-public
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
            ---
            apiVersion: ec2.aws.m.upbound.io/v1beta1
            kind: RouteTableAssociation
            metadata:
              annotations:
                {{ setResourceNameAnnotation "publicrta" }}
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-public-rta
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                subnetId: {{ dig "status" "atProvider" "subnetId" "" (index $.observed.resources "public") }}
                routeTableId: {{ dig "status" "atProvider" "routeTableId" "" (index $.observed.resources "publicrt") }}
              providerConfigRef:
                name: default

    - step: automatically-detect-ready-composed-resources
      functionRef:
        name: function-auto-ready
```

### XR

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

## Example 2: XPostgres — RDS instance with security group, subnet group, password Secret, and a composed connection Secret

Self-contained: the XR takes `vpcId` and `subnetIds` directly instead of referencing another XR, so the example focuses on the v2 patterns (password via Secret, connection details via a composed `Secret`, readiness via `function-auto-ready`) rather than cross-XR plumbing.

### XRD

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

### Composition

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
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-rds-sg
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
            ---
            apiVersion: rds.aws.m.upbound.io/v1beta1
            kind: SubnetGroup
            metadata:
              annotations:
                {{ setResourceNameAnnotation "subnets" }}
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-subnets
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                name: {{ .observed.composite.resource.metadata.name }}-subnets
                description: "rds subnets for {{ .observed.composite.resource.metadata.name }}"
                subnetIds: {{ toJson .observed.composite.resource.spec.subnetIds }}
              providerConfigRef:
                name: default
            ---
            apiVersion: rds.aws.m.upbound.io/v1beta1
            kind: Instance
            metadata:
              annotations:
                {{ setResourceNameAnnotation "pg" }}
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-pg
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                engine: postgres
                engineVersion: {{ default "15.7" .observed.composite.resource.spec.version }}
                instanceClass: {{ default "db.t3.micro" .observed.composite.resource.spec.instanceClass }}
                allocatedStorage: {{ default 20 .observed.composite.resource.spec.storageGb }}
                username: postgres
                passwordSecretRef:
                  name: {{ .observed.composite.resource.metadata.name }}-pg-pw
                  key: password
                  namespace: crossplane-system
                dbName: app
                skipFinalSnapshot: true
                publiclyAccessible: false
                vpcSecurityGroupIds:
                  - {{ dig "status" "atProvider" "id" "" (index $.observed.resources "sg") }}
                dbSubnetGroupName: {{ .observed.composite.resource.metadata.name }}-subnets
              providerConfigRef:
                name: default
              writeConnectionSecretToRef:
                name: {{ .observed.composite.resource.metadata.name }}-pg
                namespace: crossplane-system
            ---
            apiVersion: v1
            kind: Secret
            metadata:
              annotations:
                {{ setResourceNameAnnotation "connection-secret" }}
              name: {{ .observed.composite.resource.metadata.name }}-pg-conn
              namespace: {{ .observed.composite.resource.metadata.namespace }}
            {{ if eq $.observed.resources nil }}
            data: {}
            {{ else }}
            data:
              endpoint: {{ (index $.observed.resources "pg").connectionDetails.endpoint | b64enc }}
              username: {{ (index $.observed.resources "pg").connectionDetails.username | b64enc }}
              password: {{ (index $.observed.resources "pg").connectionDetails.password | b64enc }}
            {{ end }}

    - step: automatically-detect-ready-composed-resources
      functionRef:
        name: function-auto-ready
```

### XR

```yaml
apiVersion: example.org/v1alpha1
kind: XPostgres
metadata:
  name: my-app-db
  namespace: default
spec:
  region: us-east-1
  vpcId: vpc-0123456789abcdef0
  subnetIds:
    - subnet-aaa
    - subnet-bbb
  version: "15.7"
  instanceClass: db.t3.micro
  storageGb: 20
```

Read the composed connection details with `kubectl get secret my-app-db-pg-conn -n default -o jsonpath='{.data}' | base64 -d`. On the first reconcile the `data` map is empty (the `pg` instance hasn't produced `connectionDetails` yet) — the nil-guard in the template prevents the `index` call from panicking.
