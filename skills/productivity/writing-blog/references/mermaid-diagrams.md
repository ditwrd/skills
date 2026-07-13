# Mermaid diagrams for blog posts

Reference for creating Mermaid diagrams embedded as ` ```mermaid ` code blocks in Hugo blog posts. Adapted from [imxv/Pretty-mermaid-skills](https://github.com/imxv/Pretty-mermaid-skills).

---

## When to use a diagram

Replace a wall of text when:

- **Process or workflow** — explaining steps, decision trees, or state transitions
- **Architecture** — showing how components relate (microservices, data pipeline, system layout)
- **Interactions** — API calls, message flows, session sequences
- **Data model** — entity relationships, database schema
- **Comparison** — side-by-side of two approaches or timelines

A diagram should replace 3+ paragraphs of descriptive text. If the concept fits in two sentences, don't diagram it.

---

## Diagram type selection

| Content type | Diagram type | When to use |
|---|---|---|
| Process, workflow, decision tree | `flowchart` | Step-by-step procedures, branching logic, pipeline stages |
| API calls, message passing, time-ordered events | `sequenceDiagram` | Multi-party interactions, request-response flows, event chains |
| Lifecycle, state machines | `stateDiagram-v2` | Object or system states and transitions, status flows |
| Object models, architecture, inheritance | `classDiagram` | Component relationships, type hierarchies, plugin systems |
| Database schema, entity relationships | `erDiagram` | Table relationships, data models, schema migrations |

---

## Quick syntax reference

### Flowchart

```
flowchart LR
    A[Start] --> B{Decision}
    B -->|Yes| C[Action]
    B -->|No| D[End]
```

- `LR` = left-to-right (default for blog posts — fits wide screens)
- `TB` / `BT` for tall narrow layouts
- Node shapes: `[ ]` rectangle, `{ }` diamond (decision), `( )` rounded, `[( )]` database

### Sequence diagram

```
sequenceDiagram
    participant U as User
    participant S as Server

    U->>S: POST /api/login
    S-->>U: 200 OK
    Note over U,S: Session established
```

- `->>` solid arrow, `-->>` dashed (response), `-x` error
- `activate` / `deactivate` for processing bars
- `loop`, `alt`/`else`, `opt` for control flow

### State diagram

```
stateDiagram-v2
    [*] --> Idle
    Idle --> Running: start
    Running --> [*]: complete
    Running --> Error: fail
```

- `[*]` for initial / terminal states
- `state` for composite sub-states
- `<<choice>>` for conditional branching

### Class diagram

```
classDiagram
    class Service {
        +run()
        -config
    }
    Service --> Client: uses
```

- `+` public, `-` private, `#` protected
- `--|>` inheritance, `-->` association, `..|>` realization
- Cardinality: `"1" --> "*"` one-to-many

### ER diagram

```
erDiagram
    USER ||--o{ POST : writes
    POST ||--|{ COMMENT : has
```

- `||` one, `}|` one or more, `o{` zero or more
- Attribute blocks with `{}`, PK/FK annotations

---

## Layout best practices

### Direction

- **`LR` (left-to-right)** for most blog diagrams — fits natural reading flow and wide viewports
- **`TB` (top-to-bottom)** for tall hierarchies or narrow mobile-friendly layouts
- Avoid `RL` and `BT` — readers find them confusing

### Node labels

- Use sentence case: "Send request", not "Send Request"
- Keep labels short (3-5 words max). If you need more, use a `Note` or a footnote
- Label edges with verbs or conditions: "returns error", "on success"

### Subgraphs

Group related nodes for clarity:

```
flowchart LR
    subgraph API
        A[Ingest] --> B[Validate]
    end
    subgraph Storage
        C[(DB)]
    end
    B --> C
```

- Use subgraphs at most 2 levels deep
- Name subgraphs with a colon: `subgraph Service Layer`

### Spacing

- Keep diagrams under 25 nodes — beyond that, split into two diagrams
- One subgraph per conceptual layer (or per service in an architecture diagram)
- Avoid crossing lines between subgraphs — restructure to keep edges contained

### Consistency

- Same shape = same type of thing across the diagram (all services are rectangles, all decisions are diamonds)
- Same edge style = same relationship type (solid for direct calls, dashed for async)
- Use `%%` comments for any non-obvious node:

```
%% In-memory cache, TTL 5 minutes
    Cache[(Redis)] --> API
```

---

## What NOT to do

- **Don't use diagrams for trivial concepts** — two sentences of prose is better than a 3-node flowchart
- **Don't exceed 25 nodes** — readers lose track; split into multiple diagrams
- **Don't mix diagram types** — one diagram per concept; prefer `flowchart` over `graph` (cleaner syntax)
- **Don't force aesthetics** — clear labels > colored nodes. The blog's theme handles rendering
