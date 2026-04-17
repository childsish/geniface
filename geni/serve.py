from __future__ import annotations

import argparse
import html
import json
import tempfile
from functools import partial, update_wrapper
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from inspect import Parameter, Signature, signature
from pathlib import Path
from typing import Any, Callable, get_type_hints

from geni.ir import call_function
from geni.run import coerce_value, load_function, parse_cli_kwargs

try:
    import cgi
except ModuleNotFoundError:
    from geni import _cgi_compat as cgi


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
                kwargs = json.loads(body)
            elif content_type.startswith("multipart/form-data"):
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
            else:
                self.send_error(415)
                return
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
    has_file_input = False

    for parameter in signature(fn).parameters.values():
        annotation = annotations.get(parameter.name, parameter.annotation)
        fields.append(_build_ui_field(parameter, annotation))
        has_file_input = has_file_input or annotation is Path

    return (
        "<!doctype html>\n"
        '<html lang="en" data-bs-theme="light">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{html.escape(fn.__name__)} UI</title>\n"
        '  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB" crossorigin="anonymous">\n'
        "  <style>\n"
        "    body { background: var(--bs-tertiary-bg); }\n"
        "    .result-box { min-height: 10rem; white-space: pre-wrap; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        '  <main class="container py-5">\n'
        '    <div class="row justify-content-center">\n'
        '      <div class="col-12 col-lg-8 col-xl-7">\n'
        '        <section class="card border-0 shadow-sm">\n'
        '          <div class="card-body p-4 p-md-5">\n'
        '            <div class="mb-4">\n'
        f'              <p class="text-uppercase text-secondary small fw-semibold mb-2">Browser UI</p>\n'
        f'              <h1 class="h3 mb-2">{html.escape(fn.__name__)}</h1>\n'
        f'              <p class="text-body-secondary mb-0">Submit input to <code>/{html.escape(fn.__name__)}</code>.</p>\n'
        "            </div>\n"
        '            <form id="form" class="vstack gap-3">\n'
        f"{''.join(fields)}"
        '              <div class="d-flex justify-content-end pt-2">\n'
        '                <button type="submit" class="btn btn-primary px-4">Run function</button>\n'
        "              </div>\n"
        "            </form>\n"
        '            <div class="mt-4">\n'
        '              <div class="d-flex align-items-center justify-content-between mb-2">\n'
        '                <h2 class="h6 mb-0">Response</h2>\n'
        '                <span class="badge text-bg-light border">JSON</span>\n'
        "              </div>\n"
        '              <pre id="result" class="result-box bg-body-tertiary border rounded-3 p-3 mb-0 small text-body-secondary">{}</pre>\n'
        "            </div>\n"
        "          </div>\n"
        "        </section>\n"
        "      </div>\n"
        "    </div>\n"
        "  </main>\n"
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
        '      if (kind === "bool") body.append(element.name, String(element.checked));\n'
        '      else if (kind === "path") { if (element.files[0]) body.append(element.name, element.files[0]); }\n'
        "      else body.append(element.name, element.value);\n"
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
        "  result.textContent = JSON.stringify(await response.json(), null, 2);\n"
        '  result.classList.remove("text-body-secondary");\n'
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
