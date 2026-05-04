from __future__ import annotations

import argparse
import sys
from enum import Enum
from importlib import import_module
from inspect import Parameter, Signature, getdoc, signature
from pathlib import Path
from typing import Any, Callable, get_args, get_type_hints

from geniface.ir import call_function


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


def coerce_value(annotation: Any, value: Any) -> Any:
    if _is_enum_type(annotation):
        return _coerce_enum_value(annotation, value)
    return _parser_type(annotation)(value)


def run_cli(target: str, argv: list[str]) -> Any:
    fn = load_function(target)
    kwargs = parse_cli_kwargs(fn, argv)
    return call_function(fn, kwargs)


def main(argv: list[str] | None = None) -> int:
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument("target", nargs="?")
    args, remainder = bootstrap.parse_known_args(argv)
    if args.target is None:
        parser = argparse.ArgumentParser()
        parser.add_argument("target")
        parser.parse_args(argv)
        return 0

    if "--help" in remainder or "-h" in remainder:
        fn = load_function(args.target)
        parser = build_cli_parser(fn, include_target=True)
        parser.parse_args(argv)
        return 0

    try:
        result = run_cli(args.target, remainder)
        print_cli_result(result)
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1

    return 0


def build_help(fn: Callable[..., Any]) -> str:
    return getdoc(fn) or ""


def print_cli_result(result: Any) -> None:
    if result is None:
        return
    if isinstance(result, Path):
        if not result.exists():
            raise FileNotFoundError(result)
        print(result)
        return
    print(result)


def build_cli_parser(
    fn: Callable[..., Any],
    *,
    include_target: bool,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=build_help(fn))
    if include_target:
        parser.add_argument("target")
    annotations = get_type_hints(fn)
    sig = signature(fn)

    for name, parameter in sig.parameters.items():
        annotation = annotations.get(name, parameter.annotation)
        argument_type = _parser_type(annotation)
        if parameter.default is Parameter.empty and not _is_enum_type(annotation):
            parser.add_argument(name, type=argument_type)
        else:
            options: dict[str, Any] = {"dest": name, "type": argument_type}
            if parameter.default is Parameter.empty:
                options["required"] = True
            parser.add_argument(f"--{name}", **options)

    return parser


def _parser_type(annotation: Any) -> Callable[[str], Any]:
    if _is_enum_type(annotation):
        return _enum_parser(annotation)
    if annotation in (Signature.empty, str):
        return str
    if _is_path_type(annotation):
        return Path
    if annotation is int:
        return int
    if annotation is float:
        return float
    if annotation is bool:
        return _parse_bool
    return str


def _enum_parser(annotation: type[Enum]) -> Callable[[str], Any]:
    def parse(value: str) -> Any:
        try:
            return _coerce_enum_value(annotation, value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(str(exc)) from exc

    return parse


def _coerce_enum_value(annotation: type[Enum], value: Any) -> Enum:
    try:
        return annotation(value)
    except ValueError as exc:
        allowed = [member.value for member in annotation]
        raise ValueError(f"Invalid value {value!r}. Allowed: {allowed}") from exc


def _is_enum_type(annotation: Any) -> bool:
    try:
        return issubclass(annotation, Enum)
    except TypeError:
        return False


def _is_path_type(annotation: Any) -> bool:
    args = get_args(annotation)
    return annotation is Path or (Path in args and type(None) in args)


def _parse_bool(value: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


if __name__ == "__main__":
    raise SystemExit(main())
