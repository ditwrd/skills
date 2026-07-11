# Generating module READMEs

Uses [`crossplane-docs`](https://github.com/Kavinraja-G/crossplane-docs) (XDocs) to generate markdown documentation from XRDs. Output is post-processed to fix multiline table cell rendering.

## Usage

```sh
make readme           # all modules
make readme           # re-run after XRD changes
```

## How it works

1. `crossplane-docs md <module> -o <module>/README.md --xrd-only` — generates XRD schema docs in markdown
2. Post-processing fixes:
   - Collapses multiline YAML descriptions into single table cells
   - Splits inline headings that bleed into the previous table row

### Post-processing script

The `scripts/generate-module-readmes.sh` runs `crossplane-docs` then applies this Python fix:

```python
import os

for root, dirs, files in os.walk('modules'):
    for fname in files:
        if fname != 'README.md':
            continue
        path = os.path.join(root, fname)
        with open(path) as f:
            lines = f.readlines()
        result = []
        in_table = False
        for line in lines:
            stripped = line.rstrip('\n')
            if stripped.lstrip().startswith('|---'):
                in_table = True
                result.append(stripped)
            elif in_table and stripped.lstrip().startswith('|'):
                if '#' in stripped:
                    idx = stripped.find('#')
                    before = stripped[:idx].rstrip()
                    after = stripped[idx:]
                    if before:
                        result.append(before)
                    result.append(after)
                else:
                    result.append(stripped)
                in_table = False if not stripped.endswith('|') else True
            elif in_table and stripped and not stripped.lstrip().startswith('|') and not stripped.startswith('#'):
                result[-1] += ' ' + stripped.lstrip()
            else:
                in_table = False
                result.append(stripped)
        with open(path, 'w') as f:
            f.write('\n'.join(result) + '\n')
```

The script collapses multiline YAML descriptions into single table cells and splits `####`/`#####` headings that bleed into the previous table row.

## Prerequisites

- `crossplane-docs` installed via `mise` or on `$PATH`
- Each module directory must have an `xrd.yaml`

## Known limitations

- `crossplane-docs` v0.1.x doesn't support Pipeline-mode Compositions — use `--xrd-only` to skip the composition and document just the XRD schema
- Long descriptions in markdown table cells may wrap differently across viewers; the backtick-wrapping of API event names (e.g. `` `s3:ObjectCreated:Put` ``) prevents colon misinterpretation
