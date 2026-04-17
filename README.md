# geni

`geni` turns plain Python functions into small, portable interfaces:

- a command-line runner
- a built-in HTTP server with a browser UI
- generated adapter code such as FastAPI

It stays close to the function signature and uses standard library tooling where possible.

## Installation

`geni` is intended to be installed from PyPI:

```bash
pip install geni
```

Requirements:

- Python 3.10+

Optional packages:

- For development and tests:

```bash
pip install "geni[dev]"
```

- For generated FastAPI adapters, install FastAPI and a server:

```bash
pip install fastapi python-multipart uvicorn
```

## Quick Example

Create a module with a function:

```python
# demo.py
from pathlib import Path


def greet(name: str, excited: bool = False) -> str:
    return f"hello {name}!" if excited else f"hello {name}"


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")
```

## Run

Run a function directly from the command line:

```bash
python -m geni.run demo:greet Ada --excited true
```

Output:

```text
hello Ada!
```

Rules:

- required parameters are positional
- parameters with defaults are passed as flags
- supported primitive CLI types are `str`, `int`, `float`, `bool`, and `pathlib.Path`

Examples:

```bash
python -m geni.run demo:greet Ada
python -m geni.run demo:read_file ./notes.txt
```

## Serve

Start the built-in HTTP server:

```bash
python -m geni.serve --host 127.0.0.1 --port 8000 demo:greet
```

When the server is ready it prints the bound address:

```text
Serving on http://127.0.0.1:8000
```

Available endpoints:

- `POST /<function_name>` executes the function
- `GET /ui` serves a browser form generated from the function signature

For the `greet` example, send JSON to:

```bash
curl -X POST http://127.0.0.1:8000/greet \
  -H "Content-Type: application/json" \
  -d '{"name":"Ada","excited":true}'
```

The response shape is always:

```json
{"result": "hello Ada!"}
```

### Browser UI

Open:

```text
http://127.0.0.1:8000/ui
```

The UI:

- builds a form from the function signature
- supports `str`, `int`, `float`, `bool`, and `pathlib.Path`
- uses file inputs for `Path` parameters
- submits `multipart/form-data` automatically when file inputs are present

## Generate

Generate adapter code from a function:

```bash
python -m geni.generate demo:greet --target fastapi --output generated_api.py
```

Currently supported targets:

- `fastapi`

This writes a Python file that imports the target function and exposes a FastAPI app with a single `POST` endpoint at `/<function_name>`.

For functions without file inputs, the generated adapter accepts JSON.

For functions with `pathlib.Path` parameters, the generated adapter:

- exposes file uploads with `UploadFile = File(...)`
- uses `Form(...)` for non-file parameters
- writes uploaded files to temporary files
- passes `Path` objects into the target function

Run the generated FastAPI app with:

```bash
uvicorn generated_api:app --reload
```

## Notes

- `geni` does not validate beyond the underlying Python call and parser behavior.
- Uploaded files are written to temporary files and are not deleted automatically.
- The package is licensed under the MIT License. See [LICENSE](/home/AD/chili/projects/geni/LICENSE:1).
