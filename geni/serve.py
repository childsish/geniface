from __future__ import annotations

import argparse
import html
import json
from functools import partial, update_wrapper
from http.server import BaseHTTPRequestHandler, HTTPServer
from inspect import Parameter, Signature, signature
from typing import Any, Callable, get_type_hints

from geni.ir import call_function
from geni.run import load_function, parse_cli_kwargs


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

            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length).decode("utf-8")
            kwargs = json.loads(body)
            result = call_function(fn, kwargs)
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

    for parameter in signature(fn).parameters.values():
        fields.append(_build_ui_field(parameter, annotations.get(parameter.name, parameter.annotation)))

    return (
        "<!doctype html>\n"
        "<html>\n"
        "<body>\n"
        f"<h1>{html.escape(fn.__name__)}</h1>\n"
        '<form id="form">\n'
        f"{''.join(fields)}"
        '<button type="submit">Submit</button>\n'
        "</form>\n"
        '<pre id="result"></pre>\n'
        "<script>\n"
        'const form = document.getElementById("form");\n'
        'const result = document.getElementById("result");\n'
        'form.addEventListener("submit", async (event) => {\n'
        "  event.preventDefault();\n"
        "  const payload = {};\n"
        "  for (const element of form.elements) {\n"
        "    if (!element.name) continue;\n"
        '    const kind = element.dataset.kind;\n'
        '    if (kind === "bool") payload[element.name] = element.checked;\n'
        '    else if (kind === "int") payload[element.name] = parseInt(element.value, 10);\n'
        '    else if (kind === "float") payload[element.name] = parseFloat(element.value);\n'
        "    else payload[element.name] = element.value;\n"
        "  }\n"
        f'  const response = await fetch("/{fn.__name__}", {{\n'
        '    method: "POST",\n'
        '    headers: {"Content-Type": "application/json"},\n'
        "    body: JSON.stringify(payload),\n"
        "  });\n"
        "  result.textContent = JSON.stringify(await response.json(), null, 2);\n"
        "});\n"
        "</script>\n"
        "</body>\n"
        "</html>\n"
    )


def _build_ui_field(parameter: Parameter, annotation: Any) -> str:
    kind, input_type, step = _field_kind(annotation)
    label = html.escape(parameter.name)
    name = html.escape(parameter.name)
    required = " required" if parameter.default is Parameter.empty and kind != "bool" else ""

    if kind == "bool":
        checked = ""
        if parameter.default is not Parameter.empty and parameter.default:
            checked = " checked"
        return (
            f'<label>{label} '
            f'<input name="{name}" type="checkbox" data-kind="bool"{checked}>'
            "</label><br>\n"
        )

    value = ""
    if parameter.default is not Parameter.empty:
        value = f' value="{html.escape(str(parameter.default))}"'
    step_attr = f' step="{step}"' if step else ""
    return (
        f'<label>{label} '
        f'<input name="{name}" type="{input_type}" data-kind="{kind}"{step_attr}{value}{required}>'
        "</label><br>\n"
    )


def _field_kind(annotation: Any) -> tuple[str, str, str | None]:
    if annotation is int:
        return "int", "number", "1"
    if annotation is float:
        return "float", "number", "any"
    if annotation is bool:
        return "bool", "checkbox", None
    if annotation in (Signature.empty, str):
        return "str", "text", None
    return "str", "text", None


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
