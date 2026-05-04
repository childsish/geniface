from __future__ import annotations

import html
from enum import Enum
from inspect import Parameter, signature
from pathlib import Path
from typing import Any, Callable, get_args, get_type_hints

from geniface.template_utils import render_template


def generate_ui(fn: Callable[..., Any]) -> str:
    annotations = get_type_hints(fn)
    fields = []
    has_file_input = False

    for parameter in signature(fn).parameters.values():
        annotation = annotations.get(parameter.name, parameter.annotation)
        fields.append(_build_ui_field(parameter, annotation))
        has_file_input = has_file_input or _is_path_type(annotation)

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
    enum_imports = _enum_imports(parameters, annotations)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if any(_is_path_type(annotations.get(parameter.name, parameter.annotation)) for parameter in parameters):
        route_signature = []
        route_body = []
        call_arguments = []

        for parameter in parameters:
            annotation = annotations.get(parameter.name, parameter.annotation)
            if _is_path_type(annotation):
                default = "..." if parameter.default is Parameter.empty else "None"
                upload_type = "UploadFile" if parameter.default is Parameter.empty else "UploadFile | None"
                route_signature.append(f"{parameter.name}: {upload_type} = File({default})")
                route_body.extend(_path_route_body(parameter))
                call_arguments.append(f"{parameter.name}={parameter.name}_path")
                continue

            default = _default_expr(parameter, annotation)
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
                "EXTRA_IMPORTS": enum_imports,
            },
        )
    else:
        if any(_is_enum_type(annotations.get(parameter.name, parameter.annotation)) for parameter in parameters):
            route_signature, route_body = _json_route_for_typed_body(parameters, annotations, function_name)
            template_name = "fastapi_json_typed.py.tmpl"
        else:
            route_signature = "    payload: dict"
            route_body = f"    result = {function_name}(**payload)"
            template_name = "fastapi_json.py.tmpl"
        output = render_template(
            template_name,
            {
                "MODULE_NAME": module_name,
                "FUNCTION_NAME": function_name,
                "UI_HTML": repr(ui_html),
                "EXTRA_IMPORTS": enum_imports,
                "ROUTE_SIGNATURE": route_signature,
                "ROUTE_BODY": route_body,
            },
        )

    output_path.write_text(output, encoding="utf-8")


def _build_ui_field(parameter: Parameter, annotation: Any) -> str:
    if _is_enum_type(annotation):
        return _build_enum_field(parameter, annotation)

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


def _build_enum_field(parameter: Parameter, annotation: type[Enum]) -> str:
    label = html.escape(parameter.name)
    name = html.escape(parameter.name)
    required = " required" if parameter.default is Parameter.empty else ""
    default = None
    if parameter.default is not Parameter.empty:
        default = parameter.default.value if isinstance(parameter.default, annotation) else parameter.default
    options = []
    for member in annotation:
        value = html.escape(str(member.value))
        selected = " selected" if member.value == default else ""
        options.append(f'                  <option value="{value}"{selected}>{value}</option>\n')
    return (
        '              <div>\n'
        f'                <label class="form-label" for="{name}">{label}</label>\n'
        f'                <select class="form-select" id="{name}" name="{name}" data-kind="enum"{required}>\n'
        f'{"".join(options)}'
        "                </select>\n"
        "              </div>\n"
    )


def _field_kind(annotation: Any) -> tuple[str, str, str | None]:
    if _is_path_type(annotation):
        return "path", "file", None
    if annotation is bool:
        return "bool", "checkbox", None
    if annotation is int:
        return "int", "number", "1"
    if annotation is float:
        return "float", "number", "any"
    return "str", "text", None


def _type_name(annotation: Any) -> str:
    if _is_enum_type(annotation):
        return annotation.__name__
    if annotation is int:
        return "int"
    if annotation is float:
        return "float"
    if annotation is bool:
        return "bool"
    if _is_path_type(annotation):
        return "Path"
    return "str"


def _default_expr(parameter: Parameter, annotation: Any) -> str:
    if parameter.default is Parameter.empty:
        return "..."
    if _is_enum_type(annotation) and isinstance(parameter.default, annotation):
        return f"{annotation.__name__}.{parameter.default.name}"
    return repr(parameter.default)


def _json_route_for_typed_body(
    parameters: list[Parameter],
    annotations: dict[str, Any],
    function_name: str,
) -> tuple[str, str]:
    body_parameters = []
    embed = ", embed=True" if len(parameters) == 1 else ""
    for parameter in parameters:
        annotation = annotations.get(parameter.name, parameter.annotation)
        default = _default_expr(parameter, annotation)
        body_parameters.append(
            f"    {parameter.name}: {_type_name(annotation)} = Body({default}{embed})"
        )
    call_arguments = ", ".join(f"{parameter.name}={parameter.name}" for parameter in parameters)
    return ",\n".join(body_parameters), f"    result = {function_name}({call_arguments})"


def _enum_imports(parameters: list[Parameter], annotations: dict[str, Any]) -> str:
    enum_types = {
        annotations.get(parameter.name, parameter.annotation)
        for parameter in parameters
        if _is_enum_type(annotations.get(parameter.name, parameter.annotation))
    }
    lines = [
        f"from {enum_type.__module__} import {enum_type.__name__}"
        for enum_type in sorted(enum_types, key=lambda item: (item.__module__, item.__name__))
    ]
    return "\n" + "\n".join(lines) if lines else ""


def _path_route_body(parameter: Parameter) -> list[str]:
    if parameter.default is Parameter.empty:
        return [
            f"    {parameter.name}_temp = tempfile.NamedTemporaryFile(delete=False)",
            "    try:",
            f"        {parameter.name}_temp.write({parameter.name}.file.read())",
            "    finally:",
            f"        {parameter.name}_temp.close()",
            f"    {parameter.name}_path = Path({parameter.name}_temp.name)",
        ]
    return [
        f"    {parameter.name}_path = {_path_default_expr(parameter)}",
        f"    if {parameter.name} is not None:",
        f"        {parameter.name}_temp = tempfile.NamedTemporaryFile(delete=False)",
        "        try:",
        f"            {parameter.name}_temp.write({parameter.name}.file.read())",
        "        finally:",
        f"            {parameter.name}_temp.close()",
        f"        {parameter.name}_path = Path({parameter.name}_temp.name)",
    ]


def _path_default_expr(parameter: Parameter) -> str:
    if parameter.default is None:
        return "None"
    return f"Path({str(parameter.default)!r})"


def _is_enum_type(annotation: Any) -> bool:
    try:
        return issubclass(annotation, Enum)
    except TypeError:
        return False


def _is_path_type(annotation: Any) -> bool:
    args = get_args(annotation)
    return annotation is Path or (Path in args and type(None) in args)
