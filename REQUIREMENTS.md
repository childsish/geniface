# geni — Requirements Document

## 1. Overview

`geni` is a lightweight interface generation layer that:

- Treats **Python functions as the primary unit of computation**
- Derives **multiple execution interfaces** (CLI, HTTP, UI, composition) from a single definition
- Adapts functions to different execution environments
- Avoids implementing its own execution or scheduling system

The system is designed for:

- Rapid function development and testing
- Consistent interaction patterns across environments
- Reuse of logic across local, service, and distributed contexts

---

## 2. Core Design Principles

### 2.1 Single Source of Truth

The canonical definition of a unit is:

- Function signature (required)
- Optional schema
- Optional metadata

All interfaces are derived from this definition.

---

### 2.2 Separation of Concerns

| Concern | Responsibility |
|--------|----------------|
| Function | Execution logic |
| Schema | Input/output structure |
| Specification | Normalized representation |
| Generator | Interface derivation |
| Runtime | Execution |

---

### 2.3 No Execution Ownership

`geni`:

- DOES NOT schedule execution
- DOES NOT manage runtime state
- DOES NOT manage infrastructure

It:

- Generates interface adapters
- Produces portable definitions

---

### 2.4 Stateless Model

- Functions are treated as **stateless**
- No shared memory across executions
- All data must be:
  - passed explicitly
  - or externalized

---

## 3. Developer Workflow

Target loop:

1. Write a function  
2. Test via CLI  
3. Compose with other functions  
4. Repeat  

Constraints:

- All interfaces must execute the same logic
- No environment-specific rewrites

---

## 4. Function Model

### 4.1 Minimal Example

```
def transform(input: str) -> str:
    ...
```

---

### 4.2 Optional Schema

```
class InputModel(BaseModel):
    input: str = Field(..., description="Input value")
```

Schemas provide:

- validation
- structured metadata
- compatibility with external tools

---

### 4.3 Function Specification

```
FunctionSpec:
    name: str
    inputs: List[FieldSpec]
    output: FieldSpec
    metadata: Dict[str, Any]
    fn: Callable
```

---

### 4.4 Field Specification

```
FieldSpec:
    name: str
    type: str
    python_type: Any
    required: bool
    default: Any
    description: str | None
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

## 5. Composition Model

### 5.1 Sequence Representation

```
SequenceSpec:
    steps: List[StepSpec]
```

---

### 5.2 Step Representation

```
StepSpec:
    name: str
    fn: Callable
    inputs: Dict[str, str]
```

---

### 5.3 Input Binding

- literal value
- external input
- output of previous step

---

### 5.4 Constraints

- no cycles
- unique step names
- all inputs must resolve
- types should be compatible

---

## 6. Interface Generation

### 6.1 CLI

Command:

```
geni run module:function --arg value
```

Requirements:

- derived from function specification
- consistent argument mapping
- minimal startup overhead

---

### 6.2 HTTP Interface

Generated via FastAPI:

- POST endpoint per function
- JSON input/output
- automatic validation (optional)

---

### 6.3 UI

Derived from schema:

- form-based input
- validation hints
- field descriptions

---

### 6.4 Composition Execution

- sequential execution of steps
- deterministic order
- no parallelism required

---

## 7. Generator Interfaces

### 7.1 CLI

```
geni run module:function
geni build module:function
geni serve module
```

---

### 7.2 Python API

```
from geni import build

build(function_spec)
```

---

### 7.3 Optional Registration

```
@register
def transform(...):
    ...
```

---

## 8. Code Generation Strategy

### 8.1 Default Behavior

- Generate interfaces at runtime
- Avoid persistent artifacts

---

### 8.2 Optional Output

Generate files only when needed:

- wrappers
- service entrypoints

Output location:

```
.build/geni/
```

---

### 8.3 Repository Policy

Generated code:

- should not be committed
- must be reproducible

---

## 9. Execution Semantics

### 9.1 Isolation

- each execution is independent
- no shared memory
- no persistent state

---

### 9.2 Resource Constraints

- memory and compute are external concerns
- execution context defines limits

---

### 9.3 Execution Patterns

Supported:

1. direct execution
2. batched execution within a single call
3. external service execution

---

## 10. Execution Metadata

Optional hints:

```
execution = {
    "cpu": int,
    "memory": str,
    "gpu": int,
    "timeout": int
}
```

Used by external systems.

---

## 11. Environment Portability

Target environments:

- local
- batch systems
- containerized systems

---

### Requirements

- no reliance on local filesystem
- explicit data handling
- reproducible environments

---

## 12. Data Handling

- inputs/outputs must be serializable
- avoid implicit state
- support external storage references

---

## 13. Validation

System must validate:

- function structure
- input resolution
- composition correctness
- cycles
- missing dependencies

---

## 14. Extensibility

Future extensions:

- richer type system
- structured artifacts
- conditional execution
- parallel execution
- nested compositions

---

## 15. Non-Goals

`geni` will NOT:

- implement scheduling
- manage distributed systems
- manage infrastructure
- provide persistent runtime services

---

## 16. Key Constraints

- specification must be backend-agnostic
- interfaces must be consistent
- behavior must be deterministic
- execution must be identical across interfaces

---

## 17. Summary

`geni` is:

- a **function-centric interface generator**
- based on **introspection and optional schemas**
- producing **multiple interaction surfaces**
- enabling **composition without tight coupling**

Primary success criteria:

- minimal developer friction
- consistent behavior
- portability across environments
- clear separation between definition and execution