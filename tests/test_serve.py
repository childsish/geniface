from __future__ import annotations

import http.client
import json
from http.server import HTTPServer
from pathlib import Path
from threading import Thread

import geni.serve as serve_module
from geni.run import load_function
from geni.serve import bind_function_args, build_handler, parse_serve_argv


def test_parse_serve_argv_reads_server_args() -> None:
    server_args, target, function_argv = parse_serve_argv(
        [
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
            "fixtures:greet",
            "Ada",
            "--excited",
            "true",
        ]
    )

    assert server_args.host == "0.0.0.0"
    assert server_args.port == 9000
    assert target == "fixtures:greet"
    assert function_argv == ["Ada", "--excited", "true"]


def test_load_function_resolves_function_path(tmp_path: Path, monkeypatch) -> None:
    module = tmp_path / "serve_fixtures.py"
    module.write_text(
        "\n".join(
            [
                "def greet(name: str, excited: bool = False) -> str:",
                '    return f"hello {name}!" if excited else f"hello {name}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    fn = load_function("serve_fixtures:greet")

    assert fn.__name__ == "greet"
    assert fn("Ada") == "hello Ada"


def test_bind_function_args_separates_function_arguments() -> None:
    def greet(name: str, excited: bool = False) -> str:
        return f"hello {name}!" if excited else f"hello {name}"

    fn = bind_function_args(greet, ["Ada", "--excited", "true"])

    assert fn.__name__ == "greet"
    assert fn() == "hello Ada!"


def test_bind_function_args_allows_no_startup_function_args() -> None:
    def greet(name: str) -> str:
        return f"hello {name}"

    fn = bind_function_args(greet, [])

    assert fn is greet


def test_ui_returns_html_with_function_name() -> None:
    def greet(name: str, upload: Path, excited: bool = False) -> str:
        return f"hello {name}!" if excited else f"hello {name}"

    server, thread = _start_server(greet)

    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1])
        connection.request("GET", "/ui")
        response = connection.getresponse()
        body = response.read().decode("utf-8")

        assert response.status == 200
        assert "text/html" in response.getheader("Content-Type", "")
        assert "greet" in body
        assert "<form" in body
        assert "bootstrap@5.3.8" in body
        assert "form-control" in body
        assert 'type="file"' in body
    finally:
        server.shutdown()
        thread.join()


def test_ui_api_submission_returns_expected_result() -> None:
    def compute(name: str, count: int, ratio: float, enabled: bool) -> str:
        return f"{name}:{count}:{ratio}:{enabled}"

    server, thread = _start_server(compute)

    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1])
        connection.request(
            "POST",
            "/compute",
            body=json.dumps(
                {
                    "name": "Ada",
                    "count": 3,
                    "ratio": 1.5,
                    "enabled": True,
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        body = json.loads(response.read())

        assert response.status == 200
        assert body == {"result": "Ada:3:1.5:True"}
    finally:
        server.shutdown()
        thread.join()


def test_multipart_upload_maps_file_to_path() -> None:
    def read_upload(upload: Path, note: str) -> str:
        return f"{upload.exists()}:{upload.read_text(encoding='utf-8')}:{note}"

    server, thread = _start_server(read_upload)

    try:
        boundary = "test-boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="note"\r\n\r\n'
            "memo\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="upload"; filename="sample.txt"\r\n'
            "Content-Type: text/plain\r\n\r\n"
            "hello file\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")
        connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1])
        connection.request(
            "POST",
            "/read_upload",
            body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        response = connection.getresponse()
        payload = json.loads(response.read())

        assert response.status == 200
        assert payload == {"result": "True:hello file:memo"}
    finally:
        server.shutdown()
        thread.join()


def test_run_http_server_prints_ready_message(monkeypatch, capsys) -> None:
    state: dict[str, bool] = {"served": False, "closed": False}

    class FakeServer:
        def __init__(self, address, handler) -> None:
            self.server_address = ("127.0.0.1", 4321)

        def serve_forever(self) -> None:
            state["served"] = True

        def server_close(self) -> None:
            state["closed"] = True

    monkeypatch.setattr(serve_module, "HTTPServer", FakeServer)

    def greet(name: str) -> str:
        return f"hello {name}"

    serve_module.run_http_server(greet, "127.0.0.1", 0)

    captured = capsys.readouterr()

    assert "Serving on http://127.0.0.1:4321" in captured.out
    assert state == {"served": True, "closed": True}


def _start_server(fn):
    server = HTTPServer(("127.0.0.1", 0), build_handler(fn))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
