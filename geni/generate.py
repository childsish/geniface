from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from geni.adapters.fastapi import generate as fastapi_generate
from geni.run import load_function

ADAPTERS: dict[str, Callable[..., Any]] = {
    "fastapi": fastapi_generate,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("function_target")
    parser.add_argument("--target", choices=sorted(ADAPTERS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    fn = load_function(args.function_target)
    ADAPTERS[args.target](fn, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
