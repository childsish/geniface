from __future__ import annotations

import geni.run as run_module

from geni.run import build_help, parse_cli_kwargs, run_cli


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
