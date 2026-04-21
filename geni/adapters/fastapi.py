from __future__ import annotations

import html
from inspect import Parameter, signature
from pathlib import Path
from textwrap import dedent
from typing import Any, Callable, get_type_hints


def generate_ui(fn: Callable[..., Any]) -> str:
    annotations = get_type_hints(fn)
    fields = []
    has_file_input = False

    for parameter in signature(fn).parameters.values():
        annotation = annotations.get(parameter.name, parameter.annotation)
        fields.append(_build_ui_field(parameter, annotation))
        has_file_input = has_file_input or annotation is Path

    function_name = html.escape(fn.__name__)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{function_name} UI</title>\n"
        "  <style>\n"
        "    body { font-family: sans-serif; margin: 0; background: #f6f7f9; color: #1f2933; }\n"
        "    main { max-width: 40rem; margin: 3rem auto; padding: 0 1rem; }\n"
        "    section { background: #ffffff; border: 1px solid #d9e2ec; border-radius: 0.75rem; padding: 1.5rem; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06); }\n"
        "    h1 { margin-top: 0; margin-bottom: 0.5rem; font-size: 1.75rem; }\n"
        "    p { margin-top: 0; color: #52606d; }\n"
        "    .field { margin-bottom: 1rem; }\n"
        "    label { display: block; margin-bottom: 0.35rem; font-weight: 600; }\n"
        "    input[type=text], input[type=number], input[type=file] { width: 100%; box-sizing: border-box; padding: 0.65rem 0.75rem; border: 1px solid #bcccdc; border-radius: 0.5rem; background: #fff; }\n"
        "    .checkbox { display: flex; align-items: center; gap: 0.5rem; }\n"
        "    .checkbox label { margin: 0; }\n"
        "    button { border: 0; border-radius: 0.5rem; background: #1f2933; color: #fff; padding: 0.7rem 1rem; font: inherit; cursor: pointer; }\n"
        "    pre { margin: 1.5rem 0 0; padding: 1rem; min-height: 8rem; background: #f6f7f9; border: 1px solid #d9e2ec; border-radius: 0.5rem; overflow-x: auto; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "<main>\n"
        "<section>\n"
        f"  <h1>{function_name}</h1>\n"
        f"  <p>Submit input to <code>/{function_name}</code>.</p>\n"
        '  <form id="form">\n'
        f"{''.join(fields)}"
        '    <button type="submit">Run function</button>\n'
        "  </form>\n"
        '  <pre id="result">{}</pre>\n'
        "</section>\n"
        "</main>\n"
        "<script>\n"
        'const form = document.getElementById("form");\n'
        'const result = document.getElementById("result");\n'
        'form.addEventListener("submit", async (event) => {\n'
        "  event.preventDefault();\n"
        f'  const useFormData = {"true" if has_file_input else "false"};\n'
        "  let body;\n"
        "  let headers = {};\n"
        "  if (useFormData) {\n"
        "    body = new FormData();\n"
        "    for (const element of form.elements) {\n"
        "      if (!element.name) continue;\n"
        '      const kind = element.dataset.kind;\n'
        '      if (kind === "path") {\n'
        "        if (element.files[0]) body.append(element.name, element.files[0]);\n"
        '      } else if (kind === "bool") {\n'
        "        body.append(element.name, String(element.checked));\n"
        "      } else {\n"
        "        body.append(element.name, element.value);\n"
        "      }\n"
        "    }\n"
        "  } else {\n"
        "    const payload = {};\n"
        "    for (const element of form.elements) {\n"
        "      if (!element.name) continue;\n"
        '      const kind = element.dataset.kind;\n'
        '      if (kind === "bool") payload[element.name] = element.checked;\n'
        '      else if (kind === "int") payload[element.name] = parseInt(element.value, 10);\n'
        '      else if (kind === "float") payload[element.name] = parseFloat(element.value);\n'
        "      else payload[element.name] = element.value;\n"
        "    }\n"
        '    headers = {"Content-Type": "application/json"};\n'
        "    body = JSON.stringify(payload);\n"
        "  }\n"
        f'  const response = await fetch("/{fn.__name__}", {{\n'
        '    method: "POST",\n'
        "    headers,\n"
        "    body,\n"
        "  });\n"
        '  const disposition = response.headers.get("Content-Disposition") || "";\n'
        '  if (disposition.includes("attachment")) {\n'
        "    const blob = await response.blob();\n"
        '    const match = disposition.match(/filename="([^"]+)"/);\n'
        '    const filename = match ? match[1] : "download";\n'
        "    const url = URL.createObjectURL(blob);\n"
        '    const link = document.createElement("a");\n'
        "    link.href = url;\n"
        "    link.download = filename;\n"
        "    link.click();\n"
        "    URL.revokeObjectURL(url);\n"
        "    result.textContent = JSON.stringify({download: filename}, null, 2);\n"
        "    return;\n"
        "  }\n"
        '  const responseType = response.headers.get("Content-Type") || "";\n'
        '  if (responseType.includes("application/json")) result.textContent = JSON.stringify(await response.json(), null, 2);\n'
        "  else result.textContent = await response.text();\n"
        "});\n"
        "</script>\n"
        "</body>\n"
        "</html>\n"
    )


def generate(fn: Callable[..., Any], output_path: Path) -> None:
    module_name = fn.__module__
    function_name = fn.__name__
    annotations = get_type_hints(fn)
    parameters = list(signature(fn).parameters.values())
    ui_html = generate_ui(fn)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if any(annotations.get(parameter.name, parameter.annotation) is Path for parameter in parameters):
        route_signature = []
        route_body = []
        call_arguments = []

        for parameter in parameters:
            annotation = annotations.get(parameter.name, parameter.annotation)
            if annotation is Path:
                route_signature.append(f"{parameter.name}: UploadFile = File(...)")
                route_body.extend(
                    [
                        f"    {parameter.name}_temp = tempfile.NamedTemporaryFile(delete=False)",
                        "    try:",
                        f"        {parameter.name}_temp.write({parameter.name}.file.read())",
                        "    finally:",
                        f"        {parameter.name}_temp.close()",
                        f"    {parameter.name}_path = Path({parameter.name}_temp.name)",
                    ]
                )
                call_arguments.append(f"{parameter.name}={parameter.name}_path")
                continue

            default = "..." if parameter.default is Parameter.empty else repr(parameter.default)
            route_signature.append(
                f"{parameter.name}: {_type_name(annotation)} = Form({default})"
            )
            call_arguments.append(f"{parameter.name}={parameter.name}")

        output = f"""\
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from {module_name} import {function_name}

app = FastAPI()
UI_HTML = {ui_html!r}


@app.get("/ui", response_class=HTMLResponse)
def ui():
    return HTMLResponse(UI_HTML)


@app.post("/{function_name}")
def route(
    {",\n    ".join(route_signature)}
):
{"\n".join(route_body)}
    result = {function_name}({", ".join(call_arguments)})
    if isinstance(result, Path):
        if not result.exists():
            raise HTTPException(status_code=500, detail=f"Returned path does not exist: {{result}}")
        if not result.is_file():
            raise HTTPException(status_code=500, detail=f"Returned path is not a file: {{result}}")
        return FileResponse(
            path=result,
            filename=result.name,
            media_type="application/octet-stream",
        )
    return {{"result": result}}
"""
    else:
        output = f"""\
from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from {module_name} import {function_name}

app = FastAPI()
UI_HTML = {ui_html!r}


@app.get("/ui", response_class=HTMLResponse)
def ui():
    return HTMLResponse(UI_HTML)


@app.post("/{function_name}")
def route(payload: dict):
    result = {function_name}(**payload)
    if isinstance(result, Path):
        if not result.exists():
            raise HTTPException(status_code=500, detail=f"Returned path does not exist: {{result}}")
        if not result.is_file():
            raise HTTPException(status_code=500, detail=f"Returned path is not a file: {{result}}")
        return FileResponse(
            path=result,
            filename=result.name,
            media_type="application/octet-stream",
        )
    return {{"result": result}}
"""

    output_path.write_text(dedent(output), encoding="utf-8")


def _build_ui_field(parameter: Parameter, annotation: Any) -> str:
    kind, input_type, step = _field_kind(annotation)
    label = html.escape(parameter.name)
    name = html.escape(parameter.name)

    if kind == "bool":
        checked = ""
        if parameter.default is not Parameter.empty and parameter.default:
            checked = " checked"
        return (
            '    <div class="field checkbox">\n'
            f'      <input id="{name}" name="{name}" type="checkbox" data-kind="bool"{checked}>\n'
            f'      <label for="{name}">{label}</label>\n'
            "    </div>\n"
        )

    required = " required" if parameter.default is Parameter.empty else ""
    value = ""
    if parameter.default is not Parameter.empty and kind != "path":
        value = f' value="{html.escape(str(parameter.default))}"'
    step_attr = f' step="{step}"' if step else ""
    return (
        '    <div class="field">\n'
        f'      <label for="{name}">{label}</label>\n'
        f'      <input id="{name}" name="{name}" type="{input_type}" data-kind="{kind}"{step_attr}{value}{required}>\n'
        "    </div>\n"
    )


def _field_kind(annotation: Any) -> tuple[str, str, str | None]:
    if annotation is Path:
        return "path", "file", None
    if annotation is bool:
        return "bool", "checkbox", None
    if annotation is int:
        return "int", "number", "1"
    if annotation is float:
        return "float", "number", "any"
    return "str", "text", None


def _type_name(annotation: Any) -> str:
    if annotation is int:
        return "int"
    if annotation is float:
        return "float"
    if annotation is bool:
        return "bool"
    if annotation is Path:
        return "Path"
    return "str"
