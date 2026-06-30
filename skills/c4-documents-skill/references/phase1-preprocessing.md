# Stage 1: Preprocessing — Detailed Execution Guide

## Goal
Start from zero and build complete project insight. Provide high-quality context for the research stage.

---

## Step 0: Concrete Setup (do this before any other Step)

The skill's SKILL.md describes this; this Step makes it concrete. **Do not skip this — it is the most common failure mode.**

### 0.1 Confirm `{project_root}`

`{project_root}` is the absolute path to the top of the repo being analyzed. Confirm it exists and is the right repo. Set as an absolute path. Every `{project_root}` in this skill is that absolute path.

### 0.2 Confirm `{output_dir}` with the user

Ask the user where to write the final 6 docs. Default is `{project_root}/c4.docs/`. Accept overrides like `{project_root}/docs/architecture/` or any other path. The user may also say "same as default" or just "go".

Set `{output_dir}` to the chosen absolute path. Use this everywhere a doc is written.

### 0.3 Create the scratch directory

Run:
```
mkdir -p {project_root}/.c4-agent/modules
```

Then check if `{project_root}/.gitignore` exists. If yes and `.c4-agent` is not already ignored, add this line:
```
.c4-agent/
```

If there is no `.gitignore` (rare), skip — the dir is still functional, just not git-ignored.

### 0.4 State the plan back to the user

Output one short paragraph so the user can sanity-check:
```
Project root:    {project_root}
Output dir:      {output_dir}
Scratch dir:     {project_root}/.c4-agent/ (git-ignored, removed after Stage 4)
```

If the user corrects any path, redo Step 0 from 0.2. Otherwise, proceed to Step 1.1.

### 0.5 Use absolute paths from this point on

Every `read_file`, `write_to_file`, `list_files`, and `codebase_search` against the analyzed project must use the absolute `{project_root}` path. Relative paths silently land in the agent's working directory (often the user's home or the previous project), which is how output docs ended up in the wrong place during testing.

---

## Step 1.1: Scan Project Root

Use `list_files(path="{project_root}", recursive=false)` to scan the root directory.

**Identify project type by manifest files**:

| File | Project type |
|------|--------------|
| `Cargo.toml` | Rust |
| `package.json` | Node.js / JavaScript / TypeScript |
| `pom.xml` / `build.gradle` | Java / Kotlin |
| `go.mod` | Go |
| `requirements.txt` / `pyproject.toml` | Python |
| `*.sln` / `*.csproj` | C# / .NET |
| `pubspec.yaml` | Flutter / Dart |
| `CMakeLists.txt` | C / C++ |

**Reading order**:
1. Read the manifest file first (dependencies and metadata)
2. Read `README.md` (if multiple, prefer the target-language one)
3. Identify the main source directory (`src/`, `lib/`, `app/`, `cmd/`, `core/`, etc.)

---

## Step 1.2: Scan Source Directory Structure

Use `list_files(path="{src_dir}", recursive=true)` to scan the source directory. (Use the absolute path for `{src_dir}`, not a relative one.)

**Analysis dimensions**:

### Directory organization pattern
- **Layered** (e.g. `controllers/`, `services/`, `models/`) -> layered architecture
- **Domain-based** (e.g. `payment/`, `user/`, `order/`) -> modular / DDD
- **Type-based** (e.g. `handlers/`, `middleware/`, `utils/`) -> MVC
- **Mixed** -> record the specific structure

### File count summary
```
Total files: X
By language:
  - Rust (.rs): X
  - TypeScript (.ts/.tsx): X
  - ... other languages
Core source file count: X (excludes test/spec files)
```

### Skip rules (do not recurse into)
```
.git/  node_modules/  target/  build/  dist/  .cache/
__pycache__/  vendor/  .svelte-kit/  out/  bin/  obj/
*.test.*  *.spec.*  __tests__/  test/  tests/
```

---

## Step 1.3: Read Core Files Deeply

### Priority 1 (required)
- `README.md` — project description
- Main manifest (`Cargo.toml` / `package.json` / etc.) — dependencies and versions
- Main entry file (`main.rs` / `index.ts` / `main.py` / `Main.java` / `main.go` / etc.)

### Priority 2 (important)
- Module declaration files (`src/lib.rs`, `src/mod.rs`, per-module `mod.rs`)
- Core abstraction files (often under `types/`, `models/`, `interfaces/`)
- Config struct definitions

### Priority 3 (as needed)
- Core business logic files (names contain: `workflow`, `orchestrator`, `service`, `handler`, `processor`)
- Utility files (often reveal cross-cutting concerns)

### Reading tips
- Use `view_file_outline` first to see file structure, then decide whether to read fully
- For files >500 lines, read the first 100 lines plus the outline, then read selected sections
- Use `read_file(start_line_one_indexed, end_line_one_indexed)` for precise reads

---

## Step 1.4: Code Analysis Search Strategy

### Identify core abstractions (interfaces / traits / protocols)
```
grep_search: "pub trait" / "interface " / "abstract class" / "Protocol"
Goal: find the system's core abstraction layer
```

### Identify main data types
```
grep_search: "pub struct" / "data class" / "type.*{" / "class.*:"
Goal: find core data models
```

### Identify key functions / methods
```
codebase_search: "main processing flow" / "core business logic" / "entry function"
grep_search: "pub fn launch" / "async fn main" / "func Run" / "def run"
Goal: find the system entry point and core process functions
```

### Identify module dependencies
```
grep_search: "use crate::" / "import {" / "from . import" / "require("
Goal: understand inter-module dependencies
```

### Identify config and initialization
```
codebase_search: "config initialization" / "context creation" / "dependency injection"
Goal: understand system initialization and dependency management
```

---

## Step 1.5: Build the Preprocessing Report

Compile the analysis into a structured report that becomes baseline context for all later stages.

**Then persist it to the scratch dir before any Stage 2 work begins**:

```
write_to_file("{project_root}/.c4-agent/preprocessing.md", <the report below>)
```

Use an absolute path. The report is now loadable by `read_file` from any later step without re-running the analysis. This is also the file that gates Stage 2: if you cannot write this file, you have not finished Stage 1.

```markdown
# Preprocessing Report

## Project Basic Info
- **Project name**: {from manifest/README}
- **Version**: {from manifest}
- **Project type**: CLI tool / Web service / Library / Desktop app / ...
- **Main language**: {language1 (primary), language2 (secondary)}
- **Core framework / runtime**: {framework list}

## Tech Stack
- **Runtime**: {Rust / Node.js / JVM / Python Runtime / ...}
- **Web framework**: {if applicable}
- **Database**: {if applicable}
- **LLM / AI integration**: {if applicable}
- **Key dependencies**: {top 5-10}

## Directory Structure Summary
```
{project_name}/
├── src/           # {description}
│   ├── module1/   # {description}
│   └── module2/   # {description}
├── docs/          # {description}
└── ...
```

## Identified Core Modules
- **{module1 name}** (`src/module1/`): {one-line responsibility}
- **{module2 name}** (`src/module2/`): {one-line responsibility}
- ...

## Key Files
- Entry file: `{path}`
- Core abstractions: `{path}` (contains {trait/interface list})
- Data types: `{path}` (contains {main type list})

## Dependency Summary
{Main module dependencies, written as prose or a simple list}

## README Highlights
{Key info extracted from README: features, usage, architecture notes}

## Notes
{Any unusual code organization, non-conventional architecture choices, things to pay attention to}
```

---

## Common Challenges and Handling

### Project with no README
Infer purpose from entry file comments, manifest metadata, test descriptions.

### Large monorepo
First scan top-level `packages/`, `apps/`, `services/` to identify subprojects, then analyze core subprojects selectively.

### Multi-language project
Determine primary language by file count distribution, then identify integration patterns (FFI / gRPC / HTTP API / etc.).

### Project with sparse comments
Infer intent from function/class names, directory structure, and test cases.
