# Mermaid Diagram Syntax Cheat Sheet and Type Guide

> Full document templates are embedded in the Step sections of `phase3-composition.md`.

---

## Diagram Type Guide

| Scenario | Recommended diagram | Keywords |
|----------|--------------------|----------|
| System boundary + external users/systems | `C4Context` | Person, System, System_Ext, Rel |
| Internal main subsystems | `C4Container` | Container, Container_Boundary, ContainerDb |
| Inside a module | `C4Component` | Component, Rel |
| Process flow with conditional branches | `flowchart TD` | `--> `, `-->|label|--> ` |
| Left to right data flow | `flowchart LR` | `-->` |
| Multi-system / component sequence interactions | `sequenceDiagram` | participant, `->>`, `-->>` |
| Module dependency graph | `graph LR` | `-->` |
| Database table relationships | `erDiagram` | `}|--|{`, `TABLE {` |
| System state machine | `stateDiagram-v2` | state, `-->` |

---

## Core Syntax Rules

### Node IDs: only alphanumeric + underscores
```
Correct: A, B1, myNode, LLClient
Wrong:   My Node, node-1, @user, node.1
```

### Node labels: double-quote when special chars are present
```
Correct: A["LLM Client<br/>unified interface"]
Wrong:   A[LLM Client<br/>unified interface]
```

### Line breaks inside labels: use `<br/>`
```
Correct: A["first line<br/>second line"]
Wrong:   A["first line\nsecond line"]
```

### Flowchart arrow syntax
```
Correct: A --> B           # no label
Correct: A -->|"description"| B  # with label
Wrong:   A -> B             # flowchart uses --> not ->
```

### sequenceDiagram message syntax
```
Correct: A->>B: synchronous message
Correct: A-->>B: return message
Correct: loop description ... end
Correct: alt condition ... else ... end
```

### erDiagram relationship symbols
```
||--||   one-to-one
||--o{   one-to-many (zero or more)
||--|{   one-to-many (one or more)
}|--|{   many-to-many
```

### C4 diagram structure
```
C4Context
    title Title
    Person(id, "Name", "Description")
    System(id, "Name", "Description")
    System_Ext(id, "Name", "Description")
    Rel(from, to, "Relationship", "Technology")

C4Container
    title Title
    System_Boundary(id, "Name") { Container(...) }
    ContainerDb(id, "Name", "Technology", "Description")
```

---

## Quick Fixes for Common Errors

| Error | Fix |
|-------|-----|
| Node ID contains spaces or hyphens | Use camelCase: `my-node` -> `myNode` |
| Label has parens / colons not in quotes | Wrap in double quotes: `A[System(core)]` -> `A["System(core)"]` |
| Subgraph name has spaces | Add quoted alias: `subgraph Input Layer` -> `subgraph inputLayer["Input Layer"]` |
| C4 diagram has too many nodes | Merge similar containers, keep < 15 nodes |
| erDiagram field types have special chars | Wrap type names in quotes |
