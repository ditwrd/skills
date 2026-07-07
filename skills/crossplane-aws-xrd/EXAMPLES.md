# Examples

Two complete, copy-pastable AWS composites. Each is the minimal viable version — adapt field paths to whatever version of `provider-upjet-aws` you have installed.

## Example 1: XNetwork — VPC + public subnet + private subnet + IGW + route tables

A foundational network primitive. Other composites reference its `vpcId` / `subnetIds` from the connection secret.

### XRD

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: CompositeResourceDefinition
metadata:
  name: xnetworks.example.org
spec:
  group: example.org
  names:
    kind: XNetwork
    plural: xnetworks
  claimNames:
    kind: Network
    plural: networks
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
  connectionSecretKeys:
    - vpcId
    - publicSubnetId
    - privateSubnetId
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
            apiVersion: ec2.aws.upbound.io/v1beta1
            kind: VPC
            metadata:
              name: {{ .observed.composite.resource.metadata.name }}-vpc
              annotations:
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
            apiVersion: ec2.aws.upbound.io/v1beta1
            kind: Subnet
            metadata:
              name: {{ .observed.composite.resource.metadata.name }}-public
              annotations:
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-public
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                vpcId: {{ dig "status" "atProvider" "vpcId" "" .observed.resources.vpc }}
                cidrBlock: 10.0.1.0/24
                mapPublicIpOnLaunch: true
                availabilityZone: {{ .observed.composite.resource.spec.region }}a
                tags:
                  Name: {{ .observed.composite.resource.metadata.name }}-public
              providerConfigRef:
                name: default
            ---
            apiVersion: ec2.aws.upbound.io/v1beta1
            kind: Subnet
            metadata:
              name: {{ .observed.composite.resource.metadata.name }}-private
              annotations:
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-private
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                vpcId: {{ dig "status" "atProvider" "vpcId" "" .observed.resources.vpc }}
                cidrBlock: 10.0.2.0/24
                availabilityZone: {{ .observed.composite.resource.spec.region }}b
                tags:
                  Name: {{ .observed.composite.resource.metadata.name }}-private
              providerConfigRef:
                name: default
            ---
            apiVersion: ec2.aws.upbound.io/v1beta1
            kind: InternetGateway
            metadata:
              name: {{ .observed.composite.resource.metadata.name }}-igw
              annotations:
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-igw
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                vpcId: {{ dig "status" "atProvider" "vpcId" "" .observed.resources.vpc }}
                tags:
                  Name: {{ .observed.composite.resource.metadata.name }}-igw
              providerConfigRef:
                name: default
            ---
            apiVersion: ec2.aws.upbound.io/v1beta1
            kind: RouteTable
            metadata:
              name: {{ .observed.composite.resource.metadata.name }}-public
              annotations:
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-public
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                vpcId: {{ dig "status" "atProvider" "vpcId" "" .observed.resources.vpc }}
                route:
                  - cidrBlock: 0.0.0.0/0
                    gatewayId: {{ dig "status" "atProvider" "internetGatewayId" "" .observed.resources.igw }}
                tags:
                  Name: {{ .observed.composite.resource.metadata.name }}-public
              providerConfigRef:
                name: default
            ---
            apiVersion: ec2.aws.upbound.io/v1beta1
            kind: RouteTableAssociation
            metadata:
              name: {{ .observed.composite.resource.metadata.name }}-public
              annotations:
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-public-rta
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                subnetId: {{ dig "status" "atProvider" "subnetId" "" .observed.resources.public }}
                routeTableId: {{ dig "status" "atProvider" "routeTableId" "" .observed.resources.publicrt }}
              providerConfigRef:
                name: default

    - step: observe-and-report-readiness
      functionRef:
        name: function-go-templating
      input:
        apiVersion: gotemplating.fn.crossplane.io/v1beta1
        kind: GoTemplate
        source: Inline
        inline:
          # v0.12.x: the observe step must emit a `kind: Result` Kubernetes
          # resource (not a bare YAML object). Every resource rendered by a
          # step also needs the `gotemplating.fn.crossplane.io/composition-
          # resource-name` annotation so the function can key it in
          # .observed.resources for downstream steps.
          template: |
            ---
            apiVersion: internal.crossplane.io/v1beta1
            kind: Result
            metadata:
              name: observe
              annotations:
                gotemplating.fn.crossplane.io/composition-resource-name: observe
            status:
              vpcId: {{ dig "status" "atProvider" "vpcId" "" .observed.resources.vpc }}
              publicSubnetId:  {{ dig "status" "atProvider" "subnetId" "" .observed.resources.public }}
              privateSubnetId: {{ dig "status" "atProvider" "subnetId" "" .observed.resources.private }}
              ready: {{ and
                  (eq (dig "status" "conditions" "Ready" "status" "False" .observed.resources.vpc) "True")
                  (eq (dig "status" "conditions" "Ready" "status" "False" .observed.resources.public) "True")
                  (eq (dig "status" "conditions" "Ready" "status" "False" .observed.resources.private) "True")
              }}
              conditions:
                - type: Ready
                  status: "{{ if (and
                      (eq (dig "status" "conditions" "Ready" "status" "False" .observed.resources.vpc) "True")
                      (eq (dig "status" "conditions" "Ready" "status" "False" .observed.resources.public) "True")
                      (eq (dig "status" "conditions" "Ready" "status" "False" .observed.resources.private) "True")
                    ) }}True{{ else }}False{{ end }}"
                  reason: Available
                  message: "vpc and subnets are ready"
                - type: Synced
                  status: "True"
                  reason: ReconcileSuccess
              connectionDetails:
                vpcId:
                  type: FromValue
                  fromValuePath: status.vpcId
                publicSubnetId:
                  type: FromValue
                  fromValuePath: status.publicSubnetId
                privateSubnetId:
                  type: FromValue
                  fromValuePath: status.privateSubnetId
```

### Claim

```yaml
apiVersion: example.org/v1alpha1
kind: Network
metadata:
  name: my-app
  namespace: default
spec:
  region: us-east-1
  cidrBlock: 10.0.0.0/16
```

## Example 2: XPostgres — RDS instance with VPC, subnet group, security group, and a generated password

Shows a multi-resource composite where one MR depends on outputs from another composite (`Network`). Connection secret carries `endpoint`, `username`, `password`.

### XRD

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: CompositeResourceDefinition
metadata:
  name: xpostgreses.example.org
spec:
  group: example.org
  names:
    kind: XPostgres
    plural: xpostgreses
  claimNames:
    kind: Postgres
    plural: postgres
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
              required: [region, networkRef]
              properties:
                region:     { type: string }
                networkRef: { type: object, required: [name], properties: { name: { type: string } } }
                version:    { type: string, default: "15.7" }
                instanceClass: { type: string, default: "db.t3.micro" }
                storageGb:  { type: integer, default: 20 }
            status:
              type: object
              properties:
                endpoint:   { type: string }
                ready:      { type: boolean }
  connectionSecretKeys:
    - endpoint
```

### Composition

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
            apiVersion: ec2.aws.upbound.io/v1beta1
            kind: SecurityGroup
            metadata:
              name: {{ .observed.composite.resource.metadata.name }}-rds-sg
              annotations:
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-rds-sg
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                vpcId: {{ .observed.composite.resource.spec.networkRef.name }}
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
            apiVersion: rds.aws.upbound.io/v1beta1
            kind: SubnetGroup
            metadata:
              name: {{ .observed.composite.resource.metadata.name }}-subnets
              annotations:
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-subnets
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                name: {{ .observed.composite.resource.metadata.name }}-subnets
                description: "rds subnets for {{ .observed.composite.resource.metadata.name }}"
                subnetIds:
                  - {{ .observed.composite.resource.spec.subnetIds.public }}
                  - {{ .observed.composite.resource.spec.subnetIds.private }}
              providerConfigRef:
                name: default
            ---
            apiVersion: rds.aws.upbound.io/v1beta1
            kind: Instance
            metadata:
              name: {{ .observed.composite.resource.metadata.name }}-pg
              annotations:
                crossplane.io/external-name: {{ .observed.composite.resource.metadata.name }}-pg
            spec:
              forProvider:
                region: {{ .observed.composite.resource.spec.region }}
                engine: postgres
                engineVersion: {{ default "15.7" .observed.composite.resource.spec.version }}
                instanceClass: {{ default "db.t3.micro" .observed.composite.resource.spec.instanceClass }}
                allocatedStorage: {{ default 20 .observed.composite.resource.spec.storageGb }}
                username: postgres
                password: {{ randAlphaNum 24 | b64enc | quote }}
                dbName: app
                skipFinalSnapshot: true
                publiclyAccessible: false
                vpcSecurityGroupIds:
                  - {{ dig "status" "atProvider" "id" "" .observed.resources.sg }}
                dbSubnetGroupName: {{ dig "status" "atProvider" "dbSubnetGroupName" "" .observed.resources.subnets }}
              providerConfigRef:
                name: default

    - step: observe-and-report-readiness
      functionRef:
        name: function-go-templating
      input:
        apiVersion: gotemplating.fn.crossplane.io/v1beta1
        kind: GoTemplate
        source: Inline
        inline:
          # v0.12.x: observe step emits a `kind: Result` resource. See
          # Example 1 above for the full pattern + why the annotation is required.
          template: |
            ---
            apiVersion: internal.crossplane.io/v1beta1
            kind: Result
            metadata:
              name: observe
              annotations:
                gotemplating.fn.crossplane.io/composition-resource-name: observe
            status:
              endpoint: {{ dig "status" "atProvider" "endpoint" "" .observed.resources.pg }}
              ready: {{ eq (dig "status" "atProvider" "instanceStatus" "" .observed.resources.pg) "available" }}
              conditions:
                - type: Ready
                  status: "{{ if eq (dig "status" "atProvider" "instanceStatus" "" .observed.resources.pg) "available" }}True{{ else }}False{{ end }}"
                  reason: "{{ if eq (dig "status" "atProvider" "instanceStatus" "" .observed.resources.pg) "available" }}Available{{ else }}Creating{{ end }}"
                - type: Synced
                  status: "True"
                  reason: ReconcileSuccess
              connectionDetails:
                endpoint:
                  type: FromValue
                  fromValuePath: status.endpoint
                username:
                  type: FromValue
                  fromValuePath: status.atProvider.masterUsername
                password:
                  type: FromConnectionSecretKey
                  fromConnectionSecretKey: masterUserPassword
```

### Claim

```yaml
apiVersion: example.org/v1alpha1
kind: Postgres
metadata:
  name: my-app-db
  namespace: default
spec:
  region: us-east-1
  networkRef:
    name: my-app
  version: "15.7"
  instanceClass: db.t3.micro
  storageGb: 20
```

Note: the claim depends on the rendered `Network` XR having published `subnetIds.public` and `subnetIds.private` into its connection secret. Read them with the standard Crossplane resource-reference flow (`resource.attributes.status`).
