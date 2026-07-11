#!/usr/bin/env bash
# Render a Crossplane v2 composition. Always pins --crossplane-version=v2.3.1
# because `crossplane render` defaults to v1.x, where the v2 XRD schema
# (`apiextensions.crossplane.io/v2`, `scope: Namespaced`, no claimNames) is
# rejected. Without the version pin the agent ends up creating a Go project
# from scratch just to render a v2 composition — that path is unnecessary.
#
# Usage: scripts/render.sh <xr.yaml> <composition.yaml> <functions.yaml> [<functions.yaml> ...]
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <xr.yaml> <composition.yaml> <functions.yaml> [<functions.yaml> ...]" >&2
  exit 1
fi

exec crossplane render --crossplane-version=v2.3.1 "$@"
