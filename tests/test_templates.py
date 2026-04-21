from __future__ import annotations

from pathlib import Path

import geni.adapters.fastapi as fastapi_module

from geni.run import load_function
from geni.template_utils import load_template


def test_load_template_reads_packaged_resource(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    template = load_template("fastapi_json.py.tmpl")

    assert "from __MODULE_NAME__ import __FUNCTION_NAME__" in template
    assert '@app.post("/__FUNCTION_NAME__")' in template


def test_fastapi_generate_does_not_depend_on_source_tree_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = tmp_path / "template_fixtures.py"
    module.write_text(
        "\n".join(
            [
                "def greet(name: str) -> str:",
                '    return f"hello {name}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(fastapi_module, "__file__", str(tmp_path / "missing-fastapi.py"))

    fn = load_function("template_fixtures:greet")
    output_path = tmp_path / "generated_from_templates.py"

    fastapi_module.generate(fn, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert output_path.exists()
    assert "from template_fixtures import greet" in content
    assert "UI_HTML =" in content
