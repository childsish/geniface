from __future__ import annotations

import argparse
import html
import json
import tempfile
from enum import Enum
from functools import partial, update_wrapper
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from inspect import Parameter, Signature, signature
from pathlib import Path
from typing import Any, Callable, get_type_hints

from geniface.ir import call_function
from geniface.run import coerce_value, load_function, parse_cli_kwargs
from geniface.template_utils import render_template

try:
    import cgi
except ModuleNotFoundError:
    from geniface import _cgi_compat as cgi


def parse_serve_argv(
    argv: list[str] | None = None,
) -> tuple[argparse.Namespace, str, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    server_args, remainder = parser.parse_known_args(argv)

    target_parser = argparse.ArgumentParser()
    target_parser.add_argument("target")
    target_parser.add_argument("function_args", nargs=argparse.REMAINDER)
    target_args = target_parser.parse_args(remainder)
    return server_args, target_args.target, target_args.function_args


def bind_function_args(fn: Callable[..., Any], argv: list[str]) -> Callable[..., Any]:
    if not argv:
        return fn
    kwargs = parse_cli_kwargs(fn, argv)
    bound_fn = partial(fn, **kwargs)
    update_wrapper(bound_fn, fn)
    return bound_fn


def build_handler(fn: Callable[..., Any]) -> type[BaseHTTPRequestHandler]:
    ui_html = build_ui(fn).encode("utf-8")
    annotations = get_type_hints(fn)

    class FunctionHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/ui":
                self.send_error(404)
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(ui_html)))
            self.end_headers()
            self.wfile.write(ui_html)

        def do_POST(self) -> None:
            if self.path != f"/{fn.__name__}":
                self.send_error(404)
                return

            content_type = self.headers.get("Content-Type", "")
            if content_type.startswith("application/json"):
                content_length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(content_length).decode("utf-8")
                try:
                    kwargs = _coerce_json_kwargs(json.loads(body), annotations)
                except ValueError as exc:
                    _send_text_response(self, 400, str(exc))
                    return
            elif content_type.startswith("multipart/form-data"):
                try:
                    kwargs = _parse_multipart_form(
                        self.rfile,
                        self.headers,
                        {
                            "REQUEST_METHOD": "POST",
                            "CONTENT_TYPE": content_type,
                            "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
                        },
                        annotations,
                    )
                except ValueError as exc:
                    _send_text_response(self, 400, str(exc))
                    return
            else:
                self.send_error(415)
                return
            result = call_function(fn, kwargs)
            if isinstance(result, Path):
                if not result.exists():
                    payload = f"Returned path does not exist: {result}".encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                if not result.is_file():
                    payload = f"Returned path is not a file: {result}".encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                with result.open("rb") as handle:
                    payload = handle.read()

                filename = result.name.replace('"', '\\"')
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header(
                    "Content-Disposition",
                    f'attachment; filename="{filename}"',
                )
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            payload = json.dumps({"result": result}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return FunctionHandler


def build_ui(fn: Callable[..., Any]) -> str:
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


def _build_ui_field(parameter: Parameter, annotation: Any) -> str:
    if _is_enum_type(annotation):
        return _build_enum_field(parameter, annotation)

    kind, input_type, step = _field_kind(annotation)
    label = html.escape(parameter.name)
    name = html.escape(parameter.name)
    required = " required" if parameter.default is Parameter.empty and kind != "bool" else ""

    if kind == "bool":
        checked = ""
        if parameter.default is not Parameter.empty and parameter.default:
            checked = " checked"
        return (
            '<div class="form-check form-switch">\n'
            f'  <input class="form-check-input" id="{name}" name="{name}" type="checkbox" data-kind="bool"{checked}>\n'
            f'  <label class="form-check-label" for="{name}">{label}</label>\n'
            "</div>\n"
        )

    if kind == "path":
        return (
            '<div>\n'
            f'  <label class="form-label" for="{name}">{label}</label>\n'
            f'  <input class="form-control" id="{name}" name="{name}" type="file" data-kind="path"{required}>\n'
            "</div>\n"
        )

    value = ""
    if parameter.default is not Parameter.empty:
        value = f' value="{html.escape(str(parameter.default))}"'
    step_attr = f' step="{step}"' if step else ""
    return (
        '<div>\n'
        f'  <label class="form-label" for="{name}">{label}</label>\n'
        f'  <input class="form-control" id="{name}" name="{name}" type="{input_type}" data-kind="{kind}"{step_attr}{value}{required}>\n'
        "</div>\n"
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
        options.append(f'    <option value="{value}"{selected}>{value}</option>\n')
    return (
        '<div>\n'
        f'  <label class="form-label" for="{name}">{label}</label>\n'
        f'  <select class="form-select" id="{name}" name="{name}" data-kind="enum"{required}>\n'
        f'{"".join(options)}'
        "  </select>\n"
        "</div>\n"
    )


def _field_kind(annotation: Any) -> tuple[str, str, str | None]:
    if annotation is Path:
        return "path", "file", None
    if annotation is int:
        return "int", "number", "1"
    if annotation is float:
        return "float", "number", "any"
    if annotation is bool:
        return "bool", "checkbox", None
    if annotation in (Signature.empty, str):
        return "str", "text", None
    return "str", "text", None


def _coerce_json_kwargs(raw_kwargs: dict[str, Any], annotations: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    for name, value in raw_kwargs.items():
        annotation = annotations.get(name, Signature.empty)
        if _is_enum_type(annotation):
            kwargs[name] = coerce_value(annotation, value)
            continue
        kwargs[name] = value
    return kwargs


def _parse_multipart_form(
    fp,
    headers,
    environ: dict[str, str],
    annotations: dict[str, Any],
) -> dict[str, Any]:
    body = fp.read(int(environ["CONTENT_LENGTH"]))
    form = cgi.FieldStorage(fp=BytesIO(body), headers=headers, environ=environ)
    kwargs: dict[str, Any] = {}

    for field in form.list or []:
        annotation = annotations.get(field.name, Signature.empty)
        if getattr(field, "filename", None):
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            try:
                temp_file.write(field.file.read())
            finally:
                temp_file.close()
            kwargs[field.name] = Path(temp_file.name)
            continue

        kwargs[field.name] = coerce_value(annotation, field.value)

    return kwargs


def _send_text_response(
    handler: BaseHTTPRequestHandler,
    status: int,
    message: str,
) -> None:
    payload = message.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _is_enum_type(annotation: Any) -> bool:
    try:
        return issubclass(annotation, Enum)
    except TypeError:
        return False


def run_http_server(
    fn: Callable[..., Any],
    host: str,
    port: int,
) -> None:
    server = HTTPServer((host, port), build_handler(fn))
    server_host, server_port = server.server_address
    print(f"Serving on http://{server_host}:{server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    server_args, target, function_argv = parse_serve_argv(argv)
    fn = load_function(target)
    bound_fn = bind_function_args(fn, function_argv)
    run_http_server(bound_fn, server_args.host, server_args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
