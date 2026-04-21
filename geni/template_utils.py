from __future__ import annotations

from importlib.resources import files


def load_template(name: str) -> str:
    return files("geni.templates").joinpath(name).read_text(encoding="utf-8")


def render_template(name: str, values: dict[str, str]) -> str:
    template = load_template(name)
    for key, value in values.items():
        template = template.replace(f"__{key}__", value)
    return template
