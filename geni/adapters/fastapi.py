from __future__ import annotations

from inspect import Parameter, signature
from pathlib import Path
from textwrap import dedent
from typing import Any, Callable, get_type_hints


def generate(fn: Callable[..., Any], output_path: Path) -> None:
    module_name = fn.__module__
    function_name = fn.__name__
    annotations = get_type_hints(fn)
    parameters = list(signature(fn).parameters.values())
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
from fastapi import FastAPI, File, Form, UploadFile
import tempfile
from pathlib import Path

from {module_name} import {function_name}

app = FastAPI()


@app.post("/{function_name}")
def route(
    {",\n    ".join(route_signature)}
):
{"\n".join(route_body)}
    result = {function_name}({", ".join(call_arguments)})
    return {{"result": result}}
"""
    else:
        output = f"""\
from fastapi import FastAPI

from {module_name} import {function_name}

app = FastAPI()


@app.post("/{function_name}")
def route(payload: dict):
    result = {function_name}(**payload)
    return {{"result": result}}
"""

    output_path.write_text(dedent(output), encoding="utf-8")


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
