from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from geni.run import parse_cli_kwargs


def _build_subprocess_env(tmp_path: Path, project_root: Path) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("DEBUGPY_") and not key.startswith("PYDEVD_")
    }
    python_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{tmp_path}{os.pathsep}{project_root}"
        if not python_path
        else f"{tmp_path}{os.pathsep}{project_root}{os.pathsep}{python_path}"
    )
    return env


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


def test_cli_invocation_uses_subprocess(tmp_path: Path) -> None:
    module = tmp_path / "cli_fixtures.py"
    module.write_text(
        "\n".join(
            [
                "def greet(name: str, excited: bool = False) -> str:",
                '    """Greet one person from the CLI."""',
                '    return f"hello {name}!" if excited else f"hello {name}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    project_root = Path(__file__).resolve().parents[1]
    env = _build_subprocess_env(tmp_path, project_root)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "geni.run",
            "cli_fixtures:greet",
            "Ada",
            "--excited",
            "true",
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "hello Ada!"


def test_parse_cli_kwargs_omits_optional_arguments_when_not_provided() -> None:
    def sample(name: str, excited: bool = False) -> None:
        return None

    kwargs = parse_cli_kwargs(sample, ["Ada"])

    assert kwargs == {"name": "Ada"}


def test_cli_help_uses_function_docstring(tmp_path: Path) -> None:
    module = tmp_path / "cli_fixtures.py"
    module.write_text(
        "\n".join(
            [
                "def greet(name: str, excited: bool = False) -> str:",
                '    """Greet one person from the CLI."""',
                '    return f"hello {name}!" if excited else f"hello {name}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    project_root = Path(__file__).resolve().parents[1]
    env = _build_subprocess_env(tmp_path, project_root)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "geni.run",
            "cli_fixtures:greet",
            "--help",
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    print(result.stderr)

    assert result.returncode == 0
    assert "Greet one person from the CLI." in result.stdout
