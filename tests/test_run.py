from __future__ import annotations

from pathlib import Path

import geniface.run as run_module

from geniface.run import build_help, parse_cli_kwargs, run_cli


def test_parse_cli_kwargs_uses_positional_required_and_optional_flags() -> None:
    def sample(name: str, count: int = 3, enabled: bool = False, ratio: float = 1.5) -> None:
        return None

    kwargs = parse_cli_kwargs(
        sample,
        ["Ada", "--count", "4", "--enabled", "true", "--ratio", "2.5"],
    )

    assert kwargs == {
        "name": "Ada",
        "count": 4,
        "enabled": True,
        "ratio": 2.5,
    }


def test_run_cli_direct_call(monkeypatch) -> None:
    def greet(name: str, excited: bool = False) -> str:
        return f"hello {name}!" if excited else f"hello {name}"

    monkeypatch.setattr(run_module, "load_function", lambda target: greet)

    result = run_cli("fixtures:greet", ["Ada", "--excited", "true"])

    assert result == "hello Ada!"


def test_parse_cli_kwargs_omits_optional_arguments_when_not_provided() -> None:
    def sample(name: str, excited: bool = False) -> None:
        return None

    kwargs = parse_cli_kwargs(sample, ["Ada"])

    assert kwargs == {"name": "Ada"}


def test_parse_cli_kwargs_supports_path_type(tmp_path: Path) -> None:
    def sample(path: Path) -> None:
        return None

    file_path = tmp_path / "input.txt"
    kwargs = parse_cli_kwargs(sample, [str(file_path)])

    assert kwargs == {"path": file_path}


def test_build_help_uses_docstring() -> None:
    def greet(name: str, excited: bool = False) -> str:
        """Greet one person from the CLI."""

        return f"hello {name}!" if excited else f"hello {name}"

    assert "Greet one person from the CLI." in build_help(greet)


def test_main_prints_run_cli_result(monkeypatch, capsys) -> None:
    def greet(name: str, excited: bool = False) -> str:
        return f"hello {name}!" if excited else f"hello {name}"

    monkeypatch.setattr(run_module, "load_function", lambda target: greet)

    exit_code = run_module.main(["fixtures:greet", "Ada", "--excited", "true"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == "hello Ada!"


def test_main_prints_returned_path(monkeypatch, capsys, tmp_path: Path) -> None:
    output_path = tmp_path / "result.txt"
    output_path.write_text("done", encoding="utf-8")

    def build_file() -> Path:
        return output_path

    monkeypatch.setattr(run_module, "load_function", lambda target: build_file)

    exit_code = run_module.main(["fixtures:build_file"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == str(output_path)
    assert captured.err == ""


def test_main_errors_for_nonexistent_returned_path(monkeypatch, capsys, tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.txt"

    def build_file() -> Path:
        return missing_path

    monkeypatch.setattr(run_module, "load_function", lambda target: build_file)

    exit_code = run_module.main(["fixtures:build_file"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert str(missing_path) in captured.err


def test_main_prints_nothing_for_none_result(monkeypatch, capsys) -> None:
    def do_nothing() -> None:
        return None

    monkeypatch.setattr(run_module, "load_function", lambda target: do_nothing)

    exit_code = run_module.main(["fixtures:do_nothing"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == ""
    assert captured.err == ""
