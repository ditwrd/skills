#!/usr/bin/env bash
# Inspect an installed provider-aws CRD's OpenAPI schema.
# Usage: ./get-crd-field.sh <crd-name> [jsonpath]
# Example: ./get-crd-field.sh rds.aws.upbound.io
# Example: ./get-crd-field.sh rds.aws.upbound.io .spec.versions[0].schema.openAPIV3Schema.properties.spec.properties.forProvider
set -euo pipefail

CRD="${1:-}"
PATH_ARG="${2:-.spec.versions[0].schema.openAPIV3Schema}"

if [[ -z "$CRD" ]]; then
  echo "usage: $0 <crd-name> [jsonpath]" >&2
  exit 2
fi

if ! kubectl get crd "$CRD" >/dev/null 2>&1; then
  echo "crd $CRD not found. did you install provider-upjet-aws?" >&2
  echo "list candidates: kubectl get crd | grep '\.aws\.upbound\.io$'" >&2
  exit 1
fi

kubectl get crd "$CRD" -o "jsonpath=$PATH_ARG" | jq
