"""Starter code and test harness for Python submissions."""

from dailycommit.problems.schema import Signature, parse_type

_PY_TYPES = {"int": "int", "long": "int", "double": "float", "bool": "bool", "string": "str"}


def py_type(type_name: str) -> str:
    base, depth = parse_type(type_name)
    hint = _PY_TYPES[base]
    for _ in range(depth):
        hint = f"list[{hint}]"
    return hint


def starter_code(sig: Signature) -> str:
    params = ", ".join(f"{p.name}: {py_type(p.type)}" for p in sig.params)
    return (
        "class Solution:\n"
        f"    def {sig.function}(self, {params}) -> {py_type(sig.returns)}:\n"
        "        pass\n"
    )


# Runs inside the sandbox next to solution.py and inputs.json. Prints one marked JSON line per
# test on the real stdout; the user's prints are captured separately. It never sees expected
# outputs, so a forged line can at worst report a wrong answer.
_HARNESS = r"""
import io, json, os, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
MARK = sys.argv[1]
FUNCTION = __FUNCTION__
PARAMS = __PARAMS__
_out = os.fdopen(os.dup(1), "w")


def emit(obj):
    _out.write(MARK + json.dumps(obj) + "\n")
    _out.flush()


def user_trace(e):
    frames = [f for f in traceback.extract_tb(e.__traceback__) if f.filename.endswith("solution.py")]
    lines = traceback.format_list(frames[-5:]) + traceback.format_exception_only(e)
    return "".join(lines)[-2000:]


def main():
    with open(os.path.join(HERE, "inputs.json")) as f:
        cases = json.load(f)
    sys.path.insert(0, HERE)
    sys.setrecursionlimit(10000)
    captured = io.StringIO()
    sys.stdout = sys.stderr = captured
    try:
        import solution
    except SyntaxError as e:
        emit({"ce": "".join(traceback.format_exception_only(e))[-2000:]})
        return
    except BaseException as e:
        emit({"fatal": user_trace(e)})
        return
    try:
        fn = getattr(solution.Solution(), FUNCTION)
    except BaseException:
        emit({"fatal": "class Solution with method %s(...) was not found" % FUNCTION})
        return
    for i, case in enumerate(cases):
        args = [case[p] for p in PARAMS]
        captured.seek(0)
        captured.truncate()
        start = time.perf_counter()
        err = None
        result = None
        try:
            result = fn(*args)
        except BaseException as e:
            err = user_trace(e)
        ms = int((time.perf_counter() - start) * 1000)
        if err is None:
            try:
                json.dumps(result)
            except (TypeError, ValueError):
                err = "return value of type %s is not JSON-serializable" % type(result).__name__
                result = None
        emit({"i": i, "out": result, "ms": ms, "err": err, "stdout": captured.getvalue()[-1000:]})
    emit({"done": True})


main()
"""


def harness(sig: Signature) -> str:
    return _HARNESS.replace("__FUNCTION__", repr(sig.function)).replace(
        "__PARAMS__", repr([p.name for p in sig.params])
    )
