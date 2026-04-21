from __future__ import annotations

import html
from inspect import Parameter, signature
from pathlib import Path
from typing import Any, Callable, get_type_hints

from geni.template_utils import render_template


def generate_ui(fn: Callable[..., Any]) -> str:
    annotations = get_type_hints(fn)
    fields = []
    has_file_input = False

    for parameter in signature(fn).parameters.values():
        annotation = annotations.get(parameter.name, parameter.annotation)
        fields.append(_build_ui_field(parameter, annotation))
        has_file_input = has_file_input or annotation is Path

    return render_template(
        "fastapi_ui.html.tmpl",
        {
            "FUNCTION_LABEL": html.escape(fn.__name__),
            "FUNCTION_ROUTE": fn.__name__,
            "FIELDS": "".join(fields),
            "USE_FORM_DATA": "true" if has_file_input else "false",
        },
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

        output = render_template(
            "fastapi_multipart.py.tmpl",
            {
                "MODULE_NAME": module_name,
                "FUNCTION_NAME": function_name,
                "UI_HTML": repr(ui_html),
                "ROUTE_SIGNATURE": ",\n".join(f"    {item}" for item in route_signature),
                "ROUTE_BODY": "\n".join(route_body),
                "CALL_ARGUMENTS": ", ".join(call_arguments),
            },
        )
    else:
        output = render_template(
            "fastapi_json.py.tmpl",
            {
                "MODULE_NAME": module_name,
                "FUNCTION_NAME": function_name,
                "UI_HTML": repr(ui_html),
            },
        )

    output_path.write_text(output, encoding="utf-8")


def _build_ui_field(parameter: Parameter, annotation: Any) -> str:
    kind, input_type, step = _field_kind(annotation)
    label = html.escape(parameter.name)
    name = html.escape(parameter.name)
    required = " required" if parameter.default is Parameter.empty else ""

    if kind == "bool":
        checked = ""
        if parameter.default is not Parameter.empty and parameter.default:
            checked = " checked"
        return (
            '              <div class="form-check form-switch">\n'
            f'                <input class="form-check-input" id="{name}" name="{name}" type="checkbox" data-kind="bool"{checked}>\n'
            f'                <label class="form-check-label" for="{name}">{label}</label>\n'
            "              </div>\n"
        )

    if kind == "path":
        return (
            '              <div>\n'
            f'                <label class="form-label" for="{name}">{label}</label>\n'
            f'                <input class="form-control" id="{name}" name="{name}" type="file" data-kind="path"{required}>\n'
            "              </div>\n"
        )

    value = ""
    if parameter.default is not Parameter.empty and kind != "path":
        value = f' value="{html.escape(str(parameter.default))}"'
    step_attr = f' step="{step}"' if step else ""
    return (
        '              <div>\n'
        f'                <label class="form-label" for="{name}">{label}</label>\n'
        f'                <input class="form-control" id="{name}" name="{name}" type="{input_type}" data-kind="{kind}"{step_attr}{value}{required}>\n'
        "              </div>\n"
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
