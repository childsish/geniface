from __future__ import annotations

from pathlib import Path

from geni.run import load_function
from geni.serve import bind_function_args, parse_serve_argv


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
