from __future__ import annotations

from dataclasses import dataclass
from inspect import Parameter, Signature, signature
from typing import Any, Callable


@dataclass
class FieldSpec:
    name: str
    type: str
    required: bool
    default: Any | None


@dataclass
class FunctionSpec:
    name: str
    inputs: list[FieldSpec]
    output: FieldSpec
    fn: Callable[..., Any]


def inspect_function(fn: Callable[..., Any]) -> FunctionSpec:
    sig = signature(fn)
    inputs = [
        FieldSpec(
            name=parameter.name,
            type=_map_type(parameter.annotation),
            required=parameter.default is Parameter.empty,
            default=None if parameter.default is Parameter.empty else parameter.default,
        )
        for parameter in sig.parameters.values()
    ]
    output = FieldSpec(
        name="result",
        type=_map_type(sig.return_annotation),
        required=True,
        default=None,
    )
    return FunctionSpec(name=fn.__name__, inputs=inputs, output=output, fn=fn)


def _map_type(annotation: Any) -> str:
    if annotation is Signature.empty:
        return "object"
    if annotation is str:
        return "string"
    if annotation is int:
        return "integer"
    if annotation is float:
        return "number"
    if annotation is bool:
        return "boolean"
    return "object"
