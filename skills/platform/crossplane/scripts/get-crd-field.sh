#!/usr/bin/env bash
# Inspect an installed provider CRD's OpenAPI schema.
# Usage: ./get-crd-field.sh <crd-name> [jsonpath]
# Example: ./get-crd-field.sh dbinstances.rds.aws.m.upbound.io

CRD="${1:-}"
PATH_ARG="${2:-.spec.versions[0].schema.openAPIV3Schema}"

if [[ -z "$CRD" ]]; then
  echo "usage: $0 <crd-name> [jsonpath]" >&2
  exit 2
fi

if ! kubectl get crd "$CRD" >/dev/null 2>&1; then
  echo "crd $CRD not found. did you install the provider?" >&2
  echo "list candidates: kubectl get crd | grep '\.<provider>\.upbound\.io$' (e.g. 'aws')" >&2
  exit 1
fi

kubectl get crd "$CRD" -o "jsonpath=$PATH_ARG" | jq
