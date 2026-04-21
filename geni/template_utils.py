from __future__ import annotations

from importlib.resources import files


def load_template(name: str) -> str:
    return files("geni.templates").joinpath(name).read_text(encoding="utf-8")
