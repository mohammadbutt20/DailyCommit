"""Comparing a test's actual output with the expected output. Runs in the worker, never in
the sandbox."""

import json
from typing import Any


def outputs_match(actual: Any, expected: Any, mode: Any) -> bool:
    """mode: "exact" | "unordered" | "unordered_nested" | {"float": tolerance}

    unordered: the top-level list's order doesn't matter.
    unordered_nested: neither does the order inside each element list (one level down), e.g.
    3sum's triplets or group-anagrams' groups."""
    if mode == "unordered_nested":
        if not (isinstance(actual, list) and isinstance(expected, list)):
            return False
        inner = [_canonical_sort(v) if isinstance(v, list) else v for v in actual]
        want = [_canonical_sort(v) if isinstance(v, list) else v for v in expected]
        return outputs_match(inner, want, "unordered")
    if mode == "unordered":
        if not (isinstance(actual, list) and isinstance(expected, list)):
            return False
        if len(actual) != len(expected):
            return False
        return all(
            _equal(a, e, None)
            for a, e in zip(_canonical_sort(actual), _canonical_sort(expected), strict=True)
        )
    if isinstance(mode, dict) and "float" in mode:
        return _equal(actual, expected, float(mode["float"]))
    return _equal(actual, expected, None)


def _canonical_sort(values: list[Any]) -> list[Any]:
    return sorted(values, key=lambda v: json.dumps(v, sort_keys=True))


def _equal(a: Any, b: Any, tol: float | None) -> bool:
    # bool is an int subclass in Python; true must not equal 1.
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, int | float) and isinstance(b, int | float):
        if tol is None:
            return a == b
        return abs(a - b) <= tol * max(1.0, abs(b))
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_equal(x, y, tol) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_equal(a[k], b[k], tol) for k in a)
    return type(a) is type(b) and a == b
