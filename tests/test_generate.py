from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from geniface.adapters.fastapi import generate as fastapi_generate
from geniface.run import load_function


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


def test_fastapi_adapter_generate_creates_valid_file(tmp_path: Path, monkeypatch) -> None:
    module = tmp_path / "adapter_fixtures.py"
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

    fn = load_function("adapter_fixtures:greet")
    output_path = tmp_path / "generated_fastapi.py"

    fastapi_generate(fn, output_path)

    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "from fastapi import FastAPI" in content
    assert "from fastapi.responses import FileResponse, HTMLResponse" in content
    assert "from adapter_fixtures import greet" in content
    assert '@app.post("/greet")' in content
    assert '@app.get("/ui", response_class=HTMLResponse)' in content
    assert "return FileResponse(" in content


def test_generated_fastapi_file_can_be_imported_and_called(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = tmp_path / "generated_fixtures.py"
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

    fn = load_function("generated_fixtures:greet")
    output_path = tmp_path / "generated_app.py"
    fastapi_generate(fn, output_path)

    spec = importlib.util.spec_from_file_location("generated_app", output_path)
    assert spec is not None
    assert spec.loader is not None
    generated_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generated_module)

    client = TestClient(generated_module.app)
    ui_response = client.get("/ui")
    assert ui_response.status_code == 200
    assert "text/html" in ui_response.headers["content-type"]
    assert '<form id="form">' in ui_response.text
    assert 'name="name"' in ui_response.text
    assert 'name="excited"' in ui_response.text
    response = client.post("/greet", json={"name": "Ada", "excited": True})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"result": "hello Ada!"}


def test_generated_fastapi_file_supports_path_return(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = tmp_path / "download_fixtures.py"
    module.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "",
                "def export(name: str) -> Path:",
                "    output = Path(__file__).with_name('download.txt')",
                "    output.write_text(f'hello {name}', encoding='utf-8')",
                "    return output",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    fn = load_function("download_fixtures:export")
    output_path = tmp_path / "generated_download_app.py"
    fastapi_generate(fn, output_path)

    spec = importlib.util.spec_from_file_location("generated_download_app", output_path)
    assert spec is not None
    assert spec.loader is not None
    generated_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generated_module)

    client = TestClient(generated_module.app)
    response = client.post("/export", json={"name": "Ada"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert "attachment" in response.headers["content-disposition"]
    assert "download.txt" in response.headers["content-disposition"]
    assert response.content == b"hello Ada"


def test_generated_fastapi_file_supports_path_upload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = tmp_path / "upload_fixtures.py"
    module.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "",
                "def ingest(upload: Path, name: str, count: int, enabled: bool = False) -> str:",
                "    content = upload.read_text(encoding='utf-8')",
                '    return f"{name}:{count}:{enabled}:{content}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    fn = load_function("upload_fixtures:ingest")
    output_path = tmp_path / "generated_upload_app.py"
    fastapi_generate(fn, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "UploadFile = File(...)" in content
    assert "name: str = Form(...)" in content
    assert "count: int = Form(...)" in content
    assert "enabled: bool = Form(False)" in content

    spec = importlib.util.spec_from_file_location("generated_upload_app", output_path)
    assert spec is not None
    assert spec.loader is not None
    generated_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generated_module)

    client = TestClient(generated_module.app)
    ui_response = client.get("/ui")
    assert ui_response.status_code == 200
    assert 'name="upload"' in ui_response.text
    assert 'type="file"' in ui_response.text
    assert 'name="name"' in ui_response.text
    assert 'name="count"' in ui_response.text
    response = client.post(
        "/ingest",
        data={"name": "Ada", "count": "3", "enabled": "true"},
        files={"upload": ("sample.txt", b"hello file", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json() == {"result": "Ada:3:True:hello file"}


def test_generate_cli_via_subprocess(tmp_path: Path) -> None:
    module = tmp_path / "cli_generate_fixtures.py"
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

    project_root = Path(__file__).resolve().parents[1]
    output_path = tmp_path / "generated_cli_app.py"
    env = _build_subprocess_env(tmp_path, project_root)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "geniface.generate",
            "cli_generate_fixtures:greet",
            "--target",
            "fastapi",
            "--output",
            str(output_path),
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert output_path.exists()
