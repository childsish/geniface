from __future__ import annotations

import argparse
import json
from functools import partial, update_wrapper
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable

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
    class FunctionHandler(BaseHTTPRequestHandler):
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


def run_http_server(
    fn: Callable[..., Any],
    host: str,
    port: int,
) -> None:
    server = HTTPServer((host, port), build_handler(fn))
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