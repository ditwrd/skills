# Diagnosing reconciliation thrashing

When an XR shows `WatchCircuitOpen` or `Responsive=False`, something is updating a managed resource in a tight loop. The circuit breaker throttles watch events to protect the controller.

## Procedure

### 1. Identify the thrashing resource

The `WatchCircuitOpen` message names the resource:

```bash
kubectl get <xr-kind> --all-namespaces -o json | python3 -c "
import sys, json
d = json.load(sys.stdin)
for item in d.get('items', []):
    name = item['metadata']['name']
    gen = item['metadata']['generation']
    conds = {c['type']: c for c in item.get('status', {}).get('conditions', [])}
    print(f'{name}: gen={gen}')
    for t in ['Synced', 'Ready', 'Responsive']:
        c = conds.get(t, {})
        msg = c.get('message', '')
        if 'WatchCircuit' in msg:
            msg = msg[:150]
        print(f'  {t}: {c.get(\"status\")} reason={c.get(\"reason\")} {msg}')"
```

The message will say e.g. "Too many watch events from BucketNotification/...".

### 2. Find the high-generation resource

Check the named resource's generation — anything >100 within minutes is thrashing:

```bash
kubectl get <resource-type> --all-namespaces -o custom-columns='NAME:.metadata.name,GEN:.metadata.generation,AGE:.metadata.creationTimestamp'
```

Compare against siblings — if one resource has 63k gen while others have 3-4, it's the culprit.

### 3. Check SSA field managers

```bash
kubectl get --raw "/apis/<api-group>/v1beta1/namespaces/<ns>/<resources>/<name>" | python3 -c "
import sys, json
d = json.load(sys.stdin)
mfs = d.get('metadata', {}).get('managedFields', [])
for mf in mfs:
    print(f'  manager={mf.get(\"manager\")} op={mf.get(\"operation\")}')"
```

**Thrashing signature:** `apiextensions.crossplane.io/composed/<hash>` (composition manager) vs `managed.crossplane.io/api-simple-reference-resolver` (reference resolver) competing for the same field.

### 4. Check CRD array list-type

Arrays without `x-kubernetes-list-type` (or with `None`) are SSA-atomic — the entire array is replaced on every apply:

```bash
kubectl get crd <plural>.<group> -o json | python3 -c "
import sys, json
d = json.load(sys.stdin)
queue = d['spec']['versions'][0]['schema']['openAPIV3Schema']\
  ['properties']['spec']['properties']['forProvider']['properties']['<array-field>']
print('x-kubernetes-list-type:', queue.get('x-kubernetes-list-type'))
# None = atomic = entire array replaced by SSA
# map = merge by key = safe
# set = unordered set = safe"
```

## Common patterns

| Pattern | Mechanism | Fix |
|---|---|---|
| **Atomic array + *Ref** | Template renders `queueArnRef` inside an atomic `queue[]` array; reference resolver adds resolved `queueArn`; next SSA apply strips it → loop | Render the resolved field alongside the ref: `queueArn: {{ $arn }}` with `{{- if $arn }}` guard |
| **`crossplane.io/external-name`** | Provider manages external-name; template setting it creates perpetual diff | Remove from template — Crossplane derives it from `metadata.name` |
| **Provider default tags** | Provider injects `crossplane-name`, `crossplane-providerconfig` tags; SSA applies without them → conflict | Include all default tags in the template with matching values |

## Fix: resolved field alongside ref

```yaml
# Before (causes loop):
- id: item-0
  queueArnRef:
    name: my-queue

# After (breaks loop):
{{- $queueArn := dig "resource" "status" "atProvider" "arn" "" $queueData }}
- id: item-0
  queueArnRef:
    name: my-queue
  {{- if $queueArn }}
  queueArn: {{ $queueArn }}
  {{- end }}
```

On pass 1 (no observed state): only `*Ref` renders → reference resolver adds resolved value.
On pass 2+: both render → composition manager's SSA includes resolved value → resolver sees match → no extra write → loop broken.

## Other causes to rule out

| Possible cause | How to check |
|---|---|
| CompositionRevision buildup (issues #4837/#7114) | `kubectl get compositionrevision \| wc -l` — significant if >100 |
| External controller conflict (VSO, etc.) | Check if another operator manages the same resource kind |
| writeConnectionSecretToRef cycle | Check if composed resource generation climbs on every secret write |
| Provider --debug flag | `kubectl get provider -o yaml` — debug only increases log verbosity, not a cause |

## Verify the fix

```bash
make test
# After deploy, check generation stops climbing:
kubectl get <thrashed-resource> -n <ns> <name> -o jsonpath='{.metadata.generation}'
sleep 10
kubectl get <thrashed-resource> -n <ns> <name> -o jsonpath='{.metadata.generation}'
```

If the number doesn't change, the loop is broken.
