# Makefile test target

The repo Makefile provides a `test` target that runs xprin with `--config-file .xprin.yaml`. This ensures the pinned crossplane version from `.xprin.yaml` is always used, never the user's `~/.config/xprin.yaml`.

## Usage

```sh
make test                              # all modules
make test MODULES=modules/aws/<module> # single module
```

## Canonical shape

```makefile
# Crossplane module test runner.
MODULES ?= modules/*/*
.PHONY: test
test:
	@for dir in $(MODULES); do \
		if [ -d "$$dir/tests" ]; then \
			xprin test --config-file .xprin.yaml "$$dir/tests" -v --show-render --show-assertions || exit 1; \
		fi; \
	done
```

## Why

- **Discoverable** — any developer or CI pipeline runs `make test`, no flag knowledge required.
- **Version-pinned** — `.xprin.yaml` pins `--crossplane-version`; the Makefile enforces the local config is always passed.
- **Scales** — wildcard loop picks up new module test dirs without Makefile changes.

## When to create

When authoring the first module with xprin tests in a Crossplane composition repo, create the Makefile. When adding a new module with tests, ensure the existing Makefile covers it (the wildcard pattern does automatically).
