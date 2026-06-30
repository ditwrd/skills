---
name: c4-documents-skill
description: This skill should be used when the user asks to "generate project documentation", "analyze codebase architecture", "create C4 architecture diagrams", "document a repository", "generate technical docs", "write docs for this project", "auto-generate documentation", "analyze this codebase", or any request involving automated C4-model documentation generation for a software project. The skill autonomously analyzes any codebase and produces high-quality C4 architecture documentation (Overview, Architecture, Workflow, Deep-Exploration modules, Boundary Interfaces, Database Overview) — equivalent to what deepwiki-rs produces — purely through agent reasoning and tool usage, with no external binary dependency.
version: 3.0.0
---

# C4 Documents Skill (Pure Agent Edition)

> **Port info**: this skill is a pure-agent port of [Litho (deepwiki-rs)](https://github.com/sgr-ksmt/deepwiki-rs). The four-stage documentation pipeline (Preprocess -> Research -> Compose -> Output) and the six output documents mirror the upstream design. No external binary is required — everything runs through the agent's tool calls and reasoning. This is the only place the upstream name is referenced; everywhere else the skill uses the `c4` branding.

**Output** (6 files, written to the output dir chosen in Setup):
- `1.Overview.md` — C4 Context diagram + project summary + business value
- `2.Architecture.md` — C4 Container/Component diagrams + architectural patterns + module responsibilities
- `3.Workflow.md` — sequence diagrams + flowcharts + concurrency model + error handling
- `4.Deep-Exploration/{module_name}.md` — one deep-dive document per domain module
- `5.Boundary-Interfaces.md` — CLI/API/config external interfaces
- `6.Database-Overview.md` — ER diagrams + table structure (conditional)

---

## Setup (do this BEFORE Stage 1)

Two directory decisions must be concrete before any work begins. The agent MUST do these in order, and MUST NOT skip them.

### 1. Identify the project root

The project root is the top of the repo being analyzed. Confirm by checking for a manifest file (`Cargo.toml`, `package.json`, `go.mod`, `pyproject.toml`, `pom.xml`, etc.). Resolve to an absolute path. All subsequent paths in this skill are relative to this root.

### 2. Pick the output directory (ask the user)

Ask the user where to write the final 6 docs. Default is **`{project_root}/c4.docs/`** (matches the upstream CLI convention). User can override.

- Suggested question: "I'll write the 6 docs to `<project_root>/c4.docs/` by default. Want a different path, or is that fine?"
- Do NOT proceed until you have an answer (or the user said "use the default").

### 3. Create the scratch directory

Create `{project_root}/.c4-agent/` for intermediate research artifacts. Add it to `.gitignore` if `.gitignore` exists (most projects have one). The directory holds:

```
.c4-agent/
├── preprocessing.md
├── c1-system-context.md
├── c2-domain-modules.md
├── architecture.md
├── workflow.md
├── boundary.md
├── database.md        # conditional
└── modules/
    ├── llm.md
    └── ...
```

### 4. State the plan back to the user

Before Stage 1, output one short paragraph:
- "Project root: `<abs path>`"
- "Output dir: `<abs path>`"
- "Scratch dir: `<abs path>/.c4-agent/` (will be removed after docs are written)"

If the user corrects either path, restart Setup.

### Anti-patterns (do not do)

- Writing output docs directly into the project root (pollutes the repo)
- Putting `.c4-agent/` in `/tmp` (loses the persistence advantage across stages)
- Skipping the user question and silently defaulting (the user may want a subdir like `docs/architecture/`)
- Deleting `.c4-agent/` mid-pipeline (loses earlier research)

---

## Four-Stage Pipeline Overview

```
Preprocess -> Research -> Compose -> Output
     |             |            |            |
  structural    C1-C4        Markdown      files
   insight      analysis     documents    on disk
```

Detailed execution guides for each stage live in `references/`. Load them on demand. The guidance below is decision-level only.

---

## Stage 1: Preprocess -> Understand the Project

**Decision points**:
- Pick a scanning strategy by project size (see quick-path table below)
- Produce a preprocessing report: project name, language, framework, core module list, README summary
- The report is the foundation for every later stage — keep it accurate

**Quick path by project size**:

| Size | Indicator | Scanning strategy |
|------|-----------|-------------------|
| Small | <100 source files | `list_files` recursive + `read_file` for all core files |
| Medium | 100-500 source files | `list_files` one level + `read_file` for entry/config/README + `codebase_search` semantic |
| Large | >500 source files | README + main config + entry + `view_file_outline` for core modules + `grep_search` for precision |

> Detailed steps in `references/phase1-preprocessing.md`

---

## Stage 2: Research -> C4 Multi-Level Analysis

**Decision points**:
- Order: **C1 -> C2 -> [C3 in parallel]** (matches the upstream pipeline)
- **Full coverage of domain modules required**: every subdirectory under `src/` is a candidate module — group via DDD (core/supporting/generic), no omissions
- **Progressive depth control**: tier analysis by importance score
- Research outputs persist to `.c4-agent/` scratch dir (see persistence strategy below)

**Parallel searches**: steps 2.3 (architecture), 2.4 (workflow), 2.6 (boundary) can run searches concurrently. Step 2.5 (module deep-dive) must run after 2.2 (domain modules).

**Progressive depth**:

| Importance | Depth | Files to read | Mermaid diagrams |
|-----------|-------|---------------|------------------|
| >=7 (core domain) | Deep | 5+ | Full flowchart + interaction table |
| 4-6 (supporting) | Standard | 3 | Trimmed flow |
| <=3 (generic) | Brief | 1-2 | None |

> Detailed steps in `references/phase2-research.md`

---

## Stage 3: Compose -> Generate Markdown Documents

**Decision points**:
- **Generation order**: boundary interfaces -> overview -> module deep-dives (one at a time) -> architecture -> workflow -> database (write least-dependent first)
- **Chunked writes for large docs**: architecture and workflow split into 2-3 writes (scaffold first, then fill sections)
- **One module at a time**: each Deep-Exploration doc is a separate `write_to_file`, then release context
- **Code reference density**: every module doc has >=3 file paths, >=2 type names, component tables include a path column

**Narrative writing style (P0 critical)**:

Generated docs must be **human-friendly reading**, not cold PPT-style bullet points. Core requirements:

1. **Every section opens with a 2-4 sentence narrative summary** — explain what the section covers and why it matters before any table or list
2. **Tables and lists must have interpretation prose around them** — don't just dump structured data, explain what it means and why designed that way
3. **Design decisions must say WHY** — not just "what was chosen" but "what was rejected and why"
4. **Use analogies and metaphors** to build understanding (e.g. memory as a "parcel sorting station", agents as "workers", pipeline as a "production line")
5. **Avoid cold heading stacks** — section titles should naturally lead into prose, not `### 2.1 Core Goals` then jump straight into a list

> Full writing-style guide and templates in `references/phase3-composition.md`

---

## Stage 4: Output -> Verify and Deliver

**Decision points**:
- Mermaid diagram syntax validation (node IDs alphanumeric only, special chars in quotes, `<br/>` for line breaks)
- Each document ends with a confidence score (1-10)
- Generate a final summary report (document list, module coverage, confidence table, items needing human review)

**Database doc trigger** (any of these generates the database overview; otherwise write a brief decleration file):
- `.sql`/`.sqlproj` files | `migrations/`/`sql/`/`db/`/`database/` directories | ORM dependency | DB config files

> Detailed validation checklist in `references/phase4-output.md`

---

## Intermediate Artifact Persistence Strategy (Critical)

### The problem
A single agent conversation has a finite context window. As analysis deepens, early research results may be "forgotten" under context pressure. Research has shown this is the #1 reason agents skip the scratch dir.

### The fix
After each research step, persist key findings to `{project_root}/.c4-agent/` (the dir created in Setup), not just the conversation context.

```
.c4-agent/
├── preprocessing.md        # Stage 1 output
├── c1-system-context.md    # System context report
├── c2-domain-modules.md    # Domain modules report
├── architecture.md         # Architecture research
├── workflow.md             # Workflow research
├── boundary.md             # Boundary interface report
├── database.md             # Database report (conditional)
└── modules/                # Per-module deep reports
    ├── llm.md
    ├── cache.md
    └── ...
```

**How to use it**:
- After each research step finishes -> `write_to_file` the corresponding report into `{project_root}/.c4-agent/`
- During composition, when a report is needed -> `read_file` from `{project_root}/.c4-agent/`
- After all output docs are written -> delete `{project_root}/.c4-agent/` (optional: keep for review)

**Why this works**:
- Frees early research from context pressure; reload on demand
- Research results don't get lost even in very long conversations
- Equivalent to the upstream pipeline's Memory scope mechanism

---

## Tool Usage Priority

1. `codebase_search` — semantic search (find code that "does X")
2. `grep_search` — exact search (find specific symbols/class/function names)
3. `view_file_outline` — quick file structure (no full read)
4. `read_file` — deep read on key files (entry points, core modules)
5. `list_files` — scan directory structure

**Paths are absolute when writing**: when persisting to `.c4-agent/` or writing the final output docs, always pass absolute paths. Relative paths silently land in the agent's cwd, not the project root — this is the failure mode that put docs in the wrong place.

---

## Reference Files (load on demand)

- `references/phase1-preprocessing.md` — preprocessing details + search strategies
- `references/phase2-research.md` — per-agent research guide + output formats
- `references/phase3-composition.md` — document templates + chunked-write strategy + code reference rules
- `references/phase4-output.md` — Mermaid validation checklist + confidence score template
- `references/doc-templates.md` — Mermaid syntax cheat sheet + diagram type guide
