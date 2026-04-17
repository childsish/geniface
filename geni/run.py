from __future__ import annotations

import argparse
from importlib import import_module
from inspect import Parameter, Signature, getdoc, signature
from typing import Any, Callable, get_type_hints

from geni.ir import call_function


def load_function(target: str) -> Callable[..., Any]:
    module_name, separator, function_name = target.partition(":")
    if not separator:
        raise ValueError(f"Invalid function target: {target}")
    module = import_module(module_name)
    return getattr(module, function_name)


def parse_cli_kwargs(fn: Callable[..., Any], argv: list[str]) -> dict[str, Any]:
    parser = build_cli_parser(fn, include_target=False)
    namespace = parser.parse_args(argv)
    return {name: value for name, value in vars(namespace).items() if value is not None}


def main(argv: list[str] | None = None) -> int:
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument("target", nargs="?")
    args, _ = bootstrap.parse_known_args(argv)
    if args.target is None:
        parser = argparse.ArgumentParser()
        parser.add_argument("target")
        parser.parse_args(argv)
        return 0

    fn = load_function(args.target)
    parser = build_cli_parser(fn, include_target=True)
    namespace = parser.parse_args(argv)
    kwargs = {
        name: value
        for name, value in vars(namespace).items()
        if name != "target" and value is not None
    }
    result = call_function(fn, kwargs)
    print(result)
    return 0


def build_cli_parser(
    fn: Callable[..., Any],
    *,
    include_target: bool,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=getdoc(fn))
    if include_target:
        parser.add_argument("target")
    annotations = get_type_hints(fn)
    sig = signature(fn)

    for name, parameter in sig.parameters.items():
        argument_type = _parser_type(annotations.get(name, parameter.annotation))
        if parameter.default is Parameter.empty:
            parser.add_argument(name, type=argument_type)
        else:
            parser.add_argument(f"--{name}", dest=name, type=argument_type)

    return parser


def _parser_type(annotation: Any) -> Callable[[str], Any]:
    if annotation in (Signature.empty, str):
        return str
    if annotation is int:
        return int
    if annotation is float:
        return float
    if annotation is bool:
        return _parse_bool
    return str


def _parse_bool(value: str) -> bool:
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


if __name__ == "__main__":
    raise SystemExit(main())
