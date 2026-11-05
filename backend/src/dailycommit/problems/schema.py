"""The problem file format (problems/<slug>/) and its value-type system."""

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

BASE_TYPES = {"int", "long", "double", "bool", "string"}
_TYPE_RE = re.compile(r"^(int|long|double|bool|string)((?:\[\]){0,2})$")
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

INT_RANGE = (-(2**31), 2**31 - 1)
LONG_RANGE = (-(2**63), 2**63 - 1)


def parse_type(type_name: str) -> tuple[str, int]:
    """'int[][]' -> ('int', 2). Raises ValueError for unknown types."""
    m = _TYPE_RE.match(type_name)
    if not m:
        raise ValueError(f"unknown type {type_name!r}")
    return m.group(1), len(m.group(2)) // 2


def check_value(type_name: str, value: Any) -> bool:
    base, depth = parse_type(type_name)
    return _check(base, depth, value)


def _check(base: str, depth: int, value: Any) -> bool:
    if depth:
        return isinstance(value, list) and all(_check(base, depth - 1, v) for v in value)
    if base in ("int", "long"):
        lo, hi = INT_RANGE if base == "int" else LONG_RANGE
        return isinstance(value, int) and not isinstance(value, bool) and lo <= value <= hi
    if base == "double":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if base == "bool":
        return isinstance(value, bool)
    return isinstance(value, str)


class Param(BaseModel):
    name: str
    type: str

    @field_validator("name")
    @classmethod
    def _ident(cls, v: str) -> str:
        if not _IDENT_RE.match(v):
            raise ValueError(f"invalid parameter name {v!r}")
        return v

    @field_validator("type")
    @classmethod
    def _type(cls, v: str) -> str:
        parse_type(v)
        return v


class Signature(BaseModel):
    function: str
    params: list[Param]
    returns: str

    @field_validator("function")
    @classmethod
    def _ident(cls, v: str) -> str:
        if not _IDENT_RE.match(v):
            raise ValueError(f"invalid function name {v!r}")
        return v

    @field_validator("returns")
    @classmethod
    def _type(cls, v: str) -> str:
        parse_type(v)
        return v


class Limits(BaseModel):
    time_ms: int = Field(default=2000, ge=100, le=10_000)
    memory_mb: int = Field(default=256, ge=32, le=1024)


class FloatCompare(BaseModel):
    """`{float: 1e-6}` in problem.yaml"""

    tolerance: float = Field(alias="float", gt=0)


Compare = Literal["exact", "unordered"] | FloatCompare


class ProblemSpec(BaseModel):
    """problem.yaml"""

    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    title: str
    difficulty: Literal["easy", "medium", "hard"]
    topics: list[str] = Field(min_length=1)
    function: str
    params: list[Param]
    returns: str
    compare: Compare = "exact"
    limits: Limits = Limits()

    @property
    def signature(self) -> Signature:
        return Signature(function=self.function, params=self.params, returns=self.returns)


class TestSpec(BaseModel):
    """One entry of tests.json"""

    __test__ = False

    input: dict[str, Any]
    expected: Any
    sample: bool = False


def compare_json(compare: Compare) -> Any:
    """How `compare` is stored in the DB and passed to the runner."""
    return compare if isinstance(compare, str) else compare.model_dump(by_alias=True)
