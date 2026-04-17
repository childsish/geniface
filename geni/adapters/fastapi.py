from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Any, Callable


def generate(fn: Callable[..., Any], output_path: Path) -> None:
    module_name = fn.__module__
    function_name = fn.__name__
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        dedent(
            f"""\
            from fastapi import FastAPI

            from {module_name} import {function_name}

            app = FastAPI()


            @app.post("/{function_name}")
            def route(payload: dict):
                result = {function_name}(**payload)
                return {{"result": result}}
            """
        ),
        encoding="utf-8",
    )
