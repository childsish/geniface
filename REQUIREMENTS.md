# geniface — Requirements Document

## 1. Overview

`geniface` is a lightweight interface generation and orchestration adapter layer that:

- Treats **Python functions as the primary unit of computation**
- Derives **CLI, REST, UI, and pipeline interfaces** from a single source of truth
- Delegates execution to external systems (e.g. Flyte, Dagster, KFP)
- Avoids implementing its own orchestration engine

The system is designed for:
- Pipeline-centric workflows
- Rapid component development
- Multi-environment execution (local, SLURM, Kubernetes)

---

## 2. Core Design Principles

### 2.1 Single Source of Truth

The canonical definition of a component is:

- Function signature (required)
- Optional schema (e.g. Pydantic)
- Optional metadata

Everything else is derived.

---

### 2.2 Separation of Concerns

| Concern | Responsibility |
|--------|----------------|
| Function | Execution logic |
| Schema | Interface contract |
| IR | Normalized representation |
| Generator | Interface derivation |
| Backend | Execution |

---

### 2.3 No Orchestration Logic

`geniface`:
- DOES NOT schedule tasks
- DOES NOT manage execution state
- DOES NOT manage resources directly

It:
- Generates adapters for orchestrators
- Produces portable definitions

---

### 2.4 Stateless Execution Model

- Components must be treated as **stateless**
- No shared memory between pipeline steps
- All state must be:
  - passed as inputs/outputs
  - or externalized (storage/services)

---

## 3. Developer Workflow

Target development loop:

1. Write a function
2. Test using CLI (`geniface run`)
3. Integrate into pipeline
4. Repeat

Constraints:
- CLI execution must match pipeline execution
- No pipeline-specific wrapping required

---

## 4. Component Model

### 4.1 Minimal Component

```
def ocr(document: Path) -> str:
    ...
```

---

### 4.2 Optional Schema

```
class OCRInput(BaseModel):
    document: Path = Field(..., description="Input file")
```

Schemas provide:
- validation
- JSON Schema
- UI metadata
- OpenAPI compatibility

---

### 4.3 Component Specification

Internal representation:

```
ComponentIR:
    name: str
    description: str | None
    inputs: List[FieldIR]
    outputs: List[FieldIR]
    execution: Dict[str, Any]
    fn: Callable
```

---

### 4.4 Field Representation

```
FieldIR:
    name: str
    type: str                  # normalized type
    python_type: Any
    required: bool
    default: Any
    description: str | None
    examples: List[Any] | None
    enum: List[Any] | None
    constraints: Dict
```

---

### 4.5 Type System

Normalized types:

- string
- integer
- number
- boolean
- path
- object
- artifact (future)

---

## 5. Pipeline Model

### 5.1 Pipeline IR

```
PipelineIR:
    name: str
    description: str | None
    inputs: List[PipelineInputIR]
    outputs: List[PipelineOutputIR]
    nodes: List[NodeIR]
```

---

### 5.2 Node Representation

```
NodeIR:
    id: str
    component: ComponentIR
    inputs: Dict[str, InputBindingIR]
```

---

### 5.3 Input Binding

```
InputBindingIR:
    kind: "literal" | "pipeline_input" | "node_output"
    value: Any
    source_input: str | None
    source_node: str | None
    source_output: str | None
```

---

### 5.4 Constraints

- DAG must be acyclic
- All inputs must be bound
- Types must be compatible
- Node IDs must be unique

---

## 6. Interface Generation

### 6.1 CLI

Command:

```
geniface run module:function --arg value
```

Requirements:
- auto-generated from IR
- consistent with REST/pipeline inputs
- fast startup

---

### 6.2 REST API

Generated via FastAPI:

- POST endpoint per component
- OpenAPI schema from models
- validation via schema

---

### 6.3 UI

Generated from JSON Schema:

- form-based input
- validation rules
- field descriptions

---

### 6.4 Pipelines

Supported backends:

- Flyte (primary)
- Kubeflow Pipelines (optional)
- Dagster (recommended abstraction layer)

---

## 7. Generator Interfaces

### 7.1 CLI Interface

```
geniface build module:function
geniface run module:function
geniface serve module
geniface build module --target flyte
```

---

### 7.2 Python API

```
from geniface import build

build(component_spec)
```

---

### 7.3 Decorator Registration

```
@component
def ocr(...):
    ...
```

---

## 8. Code Generation Strategy

### 8.1 Default Behavior

- Generate interfaces **at runtime**
- Avoid writing files

---

### 8.2 Optional Artifacts

Generate only when needed:

- pipeline specs (YAML, etc.)
- deployment artifacts

Output location:

```
.build/geniface/
```

---

### 8.3 Repository Policy

Generated code:
- should NOT be committed
- must be reproducible

Exceptions:
- required deployment artifacts

---

## 9. Execution Semantics

### 9.1 Task Isolation

- each pipeline node = independent process/container
- no shared memory
- no VRAM persistence across nodes

---

### 9.2 GPU / VRAM Handling

Constraints:
- VRAM tied to process lifetime
- cannot persist across tasks

Implications:
- model loading must occur per task
- or inside a long-lived service

---

### 9.3 Model Execution Patterns

Supported patterns:

1. Load per task (default)
2. Load + run in same task (preferred for GPU)
3. Artifact-based model passing
4. External model service

---

## 10. Execution Metadata

Execution hints:

```
execution = {
    "cpu": int,
    "memory": str,
    "gpu": int,
    "timeout": int,
    "cache": bool,
    "image": str
}
```

Mapped by backend to:
- SLURM
- Kubernetes
- Flyte/KFP

---

## 11. Environment Portability

Target environments:

- Local (dev)
- SLURM (dev/compute)
- Kubernetes (prod)

---

### Requirements

- no local filesystem assumptions
- use shared/object storage
- containerized or reproducible environments
- resource abstraction (CPU/GPU)

---

## 12. Storage Model

- Inputs/outputs must be serializable
- Avoid local disk reliance
- Prefer:
  - S3 / GCS / MinIO
  - artifact systems

---

## 13. Validation

System must validate:

- pipeline structure
- input bindings
- type compatibility
- missing references
- cycles

---

## 14. Extensibility

Future extensions:

- artifact typing (model, dataset, etc.)
- conditional execution
- parallel/map nodes
- sub-pipelines
- streaming support

---

## 15. Non-Goals

`geniface` will NOT:

- implement a scheduler
- manage distributed execution
- manage cluster resources
- provide persistent runtime state
- replace Flyte/KFP/Dagster

---

## 16. Key Design Constraints

- IR must remain backend-agnostic
- CLI/REST/UI must be consistent
- generator must be deterministic
- function execution must be identical across interfaces

---

## 17. Summary

`geniface` is:

- a **contract-first interface generator**
- built around **functions + schemas**
- producing **multi-surface interfaces**
- targeting **pipeline composition**
- while delegating execution to **external orchestrators**

Primary success criteria:

- minimal developer friction
- consistent interfaces
- portability across environments
- clean separation between definition and execution