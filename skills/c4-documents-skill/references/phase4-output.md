# Stage 4: Output Specification and Validation Guide

## Setup Reminder

`{output_dir}` = absolute path chosen in Stage 1 Step 0.2 (default `{project_root}/c4.docs/`). Every write in this stage uses that absolute path. Do NOT write to the project root.

## Output File List

| File | Required | Source |
|------|-----------|--------|
| `{output_dir}/1.Overview.md` | Required | C1 system context report + preprocessing report |
| `{output_dir}/2.Architecture.md` | Required | Architecture research report + domain modules report |
| `{output_dir}/3.Workflow.md` | Required | Workflow research report |
| `{output_dir}/4.Deep-Exploration/{module_name}.md` | Required | Per-module deep report (one file per module) |
| `{output_dir}/5.Boundary-Interfaces.md` | Required | Boundary interface report |
| `{output_dir}/6.Database-Overview.md` | Conditional | Database overview report |

### Database Doc Trigger Conditions (relaxed, matches deepwiki-rs)

deepwiki-rs's `has_database_files()` checks `.sql` files, directory names, and code classification. The agent should use the same relaxed conditions:

**Generate the database doc if any of these is true**:
- `.sql` or `.sqlproj` files present
- `migrations/`, `sql/`, `db/`, or `database/` directories present
- Directory name contains `database` or `db` (case-insensitive)
- ORM framework in dependencies: diesel / sqlx / prisma / typeorm / sequelize / hibernate / sqlalchemy / mongoose etc.
- Project contains `CodePurpose::Database` type files (migrations, schema definitions)
- Database config files present (e.g. `database.yml`, `dbconfig.json`)

**When not triggered**: generate a minimal `6.Database-Overview.md` declaring "no database-related files detected in this project"

---

## Write Order

Write in the following order (to avoid depending on unbuilt content). Each `write_to_file` uses the absolute path under `{output_dir}`:

1. Create the output dir: `mkdir -p {output_dir}` then `write_to_file` writes `{output_dir}/1.Overview.md`
2. Write `{output_dir}/2.Architecture.md`
3. Write `{output_dir}/3.Workflow.md`
4. Create the deep-dive subdir: `mkdir -p {output_dir}/4.Deep-Exploration/`
5. Write each module doc `{output_dir}/4.Deep-Exploration/{module_name}.md` one at a time
6. Write `{output_dir}/5.Boundary-Interfaces.md`
7. If applicable: write `{output_dir}/6.Database-Overview.md`
8. **Cleanup**: delete `{project_root}/.c4-agent/` (the scratch dir). Optional: keep it for review, but say so in the summary report.

---

## Mermaid Diagram Validation Checklist

Before writing each document, run these checks on every Mermaid block:

### General checks
- [ ] Code block starts with the correct diagram type keyword (`flowchart TD`, `sequenceDiagram`, `C4Context`, etc.)
- [ ] All node IDs use only letters, digits, underscores (no spaces, hyphens, or special chars)
- [ ] Node labels with special chars are wrapped in double quotes: `A["label (with special chars)"]`
- [ ] Line breaks inside labels use `<br/>`, not actual newlines

### Flowchart checks
- [ ] Arrow syntax correct: `--> ` or `-->|label|--> `
- [ ] Subgraph syntax: `subgraph name` ... `end`
- [ ] Decision nodes use diamond: `{condition?}` (include the question mark)

### sequenceDiagram checks
- [ ] All participants declared: `participant A as Name`
- [ ] Message syntax: `A->>B: message` or `A-->>B: return`
- [ ] `loop` / `alt` / `opt` blocks have matching `end`

### C4 diagram checks
- [ ] `C4Context` / `C4Container` / `C4Component` keywords correct
- [ ] Person / System / Container / Component definitions complete
- [ ] `Rel(src, dst, "label")` syntax correct

### erDiagram checks
- [ ] Entity names and relationships use correct syntax
- [ ] Relationship symbols: `}|--||`, `}|--|{`, `||--o{` etc.

### Common Fixes

**Problem: node label contains parens or full-width colons**
```
Wrong:   A[User(User)] --> B[System: backend]
Correct: A["User(User)"] --> B["System: backend"]
```

**Problem: node ID contains hyphens**
```
Wrong:   my-node --> other-node
Correct: myNode --> otherNode
```

**Problem: subgraph name contains spaces**
```
Wrong:   subgraph Input Layer
Correct: subgraph inputLayer["Input Layer"]
```

---

## Content Quality Validation Checklist

### Narrative style validation (P0 critical)
- [ ] Does every section open with a 2-4 sentence narrative summary (not a jump to tables/lists)?
- [ ] Do tables have interpretation prose around them (not isolated)?
- [ ] Do architecture decisions say "chose what, rejected what, why"?
- [ ] Are analogies / metaphors used to explain key concepts?
- [ ] Do module deep-dive docs open with "what this module does"?
- [ ] Do workflows use metaphor / narrative first to build overall understanding?
- [ ] Do parameter tables have a "meaning" column rather than just tech description?
- [ ] Does the doc read like a "technical article" rather than a "slide outline"?

### 1.Overview.md
- [ ] Contains an executive summary (not vague description)
- [ ] Contains user role analysis (at least 1 role)
- [ ] Contains C4Context Mermaid diagram
- [ ] Contains system scope and boundary statement
- [ ] Tech stack info is based on actual code (not guess)

### 2.Architecture.md
- [ ] Contains architectural design philosophy (concrete principles, not generic)
- [ ] Contains C4Container or equivalent architecture diagram
- [ ] Contains module responsibility table
- [ ] Contains at least one sequence diagram or flow chart
- [ ] Architecture decisions are based on code observation (not guess)

### 3.Workflow.md
- [ ] Contains end-to-end flow chart (Mermaid flowchart)
- [ ] Contains sequence diagram (Mermaid sequenceDiagram)
- [ ] Flow steps correspond to real functions / modules (not abstract description)

### 4.Deep-Exploration/
- [ ] **Every identified domain module has a corresponding document** (full coverage, no omissions)
- [ ] Each module doc includes an internal data flow diagram
- [ ] Component tables reference **actual file paths** (at least one per row)
- [ ] Each module doc references at least 3 specific file paths
- [ ] Each module doc references at least 2 specific type / function names
- [ ] Each module doc ends with a **confidence score** (1-10)
- [ ] Document count matches the number of modules in the domain modules report

### 5.Boundary-Interfaces.md
- [ ] Covers all external interface types (CLI / API / config etc.)
- [ ] Every interface has complete parameter description
- [ ] Contains usage examples

### 6.Database-Overview.md (if generated)
- [ ] Contains ER diagram (Mermaid erDiagram)
- [ ] Table structure description complete (fields, types, constraints)

---

## Output Summary Report Format

After all docs are written, output an execution summary to the user:

```markdown
## Documentation Generation Complete

**Project**: {project name}
**Output directory**: `{output_dir}/`
**Generation time**: {timestamp}

### Generated Documents

| Document | Path | Status |
|----------|------|--------|
| Project Overview | `{output_dir}/1.Overview.md` | OK |
| Architecture | `{output_dir}/2.Architecture.md` | OK |
| Workflow | `{output_dir}/3.Workflow.md` | OK |
| Deep Exploration ({N} modules) | `{output_dir}/4.Deep-Exploration/` | OK |
| Boundary Interfaces | `{output_dir}/5.Boundary-Interfaces.md` | OK |
| Database Overview | `{output_dir}/6.Database-Overview.md` | {OK / N/A} |

### Analysis Summary

- **Main language**: {language list}
- **Core modules identified**: {module count} ({module name list})
- **External dependencies**: {main external deps}
- **Architecture pattern**: {identified pattern}

### Items Needing Human Review

> The following may need human verification or supplementation:

- {possibly inaccurate inferences}
- {items needing supplementation}

### Confidence Scores

| Document | Confidence | Notes |
|----------|-----------|-------|
| `1.Overview.md` | {X}/10 | {based on README + manifest, high confidence} |
| `2.Architecture.md` | {X}/10 | {based on code analysis depth} |
| `3.Workflow.md` | {X}/10 | {based on main flow code tracing} |
| `4.Deep-Exploration/*.md` | {per-module} | {core modules high, auxiliary may be lower} |
| `5.Boundary-Interfaces.md` | {X}/10 | {based on CLI / API definition files} |
```

---

## Multi-Language Output

The default output language is English. If the user asks for another language, translate the doc body and the section titles; keep the numbered file structure (e.g. `1.Overview.md` becomes `1.<localized-name>.md` in the target language). Technical terms (function names, class names, framework names) stay in the original regardless of output language.
