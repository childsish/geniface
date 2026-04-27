from geniface import call_function, inspect_function


def test_inspect_function_with_required_argument() -> None:
    def greet(name: str) -> str:
        return f"hello {name}"

    spec = inspect_function(greet)

    assert spec.name == "greet"
    assert len(spec.inputs) == 1
    assert spec.inputs[0].name == "name"
    assert spec.inputs[0].type == "string"
    assert spec.inputs[0].required is True
    assert spec.inputs[0].default is None


def test_inspect_function_with_default_argument() -> None:
    def scale(count: int = 3) -> int:
        return count

    spec = inspect_function(scale)

    assert len(spec.inputs) == 1
    assert spec.inputs[0].name == "count"
    assert spec.inputs[0].type == "integer"
    assert spec.inputs[0].required is False
    assert spec.inputs[0].default == 3


def test_inspect_function_with_return_type() -> None:
    def enabled() -> bool:
        return True

    spec = inspect_function(enabled)

    assert spec.output.name == "result"
    assert spec.output.type == "boolean"
    assert spec.output.required is True
    assert spec.output.default is None
    assert spec.fn is enabled


def test_call_function_with_simple_keyword_arguments() -> None:
    def greet(name: str) -> str:
        return f"hello {name}"

    result = call_function(greet, {"name": "Ada"})

    assert result == "hello Ada"


def test_call_function_with_default_argument() -> None:
    def scale(count: int = 3) -> int:
        return count * 2

    result = call_function(scale, {})

    assert result == 6


def test_call_function_returns_value() -> None:
    def add(left: int, right: int) -> int:
        return left + right

    result = call_function(add, {"left": 2, "right": 5})

    assert result == 7
