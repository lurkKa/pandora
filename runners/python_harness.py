#!/usr/bin/env python3
"""
PANDORA Python Verification Harness (Sandbox Target)

This script is designed to run inside a constrained environment (preferably Docker)
and MUST treat input code as untrusted.

Input (stdin): JSON
{
  "code": "python source code",
  "cases": [
    {"type": "variable_value", "name": "x", "expected": 1},
    {"code": "add(2, 3)", "expected": 5}
  ],
  "max_stdout": 4000
}

Output (stdout): JSON
{
  "passed": true|false,
  "exec_error": {"type": "...", "message": "...", "trace": "..."} | null,
  "stdout": "...",
  "cases": [
    {"label": "...", "passed": true|false, "expected": ..., "actual": ..., "error": "..."}
  ]
}
"""

from __future__ import annotations

import io
import json
import math
import random
import resource
import signal
import sys
import traceback
from pathlib import Path
from contextlib import contextmanager, redirect_stderr, redirect_stdout

# ── Resource limits (protection when running without Docker) ──
# Memory: 256 MB virtual address space
_MEM_LIMIT_BYTES = 256 * 1024 * 1024
try:
    resource.setrlimit(resource.RLIMIT_AS, (_MEM_LIMIT_BYTES, _MEM_LIMIT_BYTES))
except (ValueError, OSError):
    pass  # Not supported on this platform

# CPU time: soft 8s, hard 10s (SIGKILL fallback for infinite loops)
try:
    resource.setrlimit(resource.RLIMIT_CPU, (8, 10))
except (ValueError, OSError):
    pass
from typing import Any

# -I excludes the script directory from sys.path in Docker. Load only the
# bundled, trusted validator module; submitted code still runs in its own env.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from output_validators import validate_output


def _matches(actual: Any, expected: Any, comparison: Any = None) -> bool:
    if not comparison:
        return actual == expected
    mode = comparison.get("mode", "json")
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        if len(actual) != len(expected):
            return False
        child = dict(comparison, mode="json")
        if mode in {"unordered", "unordered_rows"}:
            remaining = list(expected)
            for value in actual:
                row_comparison = dict(child, mode="unordered") if mode == "unordered_rows" else child
                for i, target in enumerate(remaining):
                    if _matches(value, target, row_comparison):
                        remaining.pop(i)
                        break
                else:
                    return False
            return True
        return all(_matches(a, b, child) for a, b in zip(actual, expected))
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _matches(actual[key], expected[key], dict(comparison, mode="json")) for key in expected
        )
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    if isinstance(actual, int) and isinstance(expected, int):
        return actual == expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        if not math.isfinite(actual) or not math.isfinite(expected):
            return False
        return math.isclose(actual, expected,
                            rel_tol=float(comparison.get("rel_tol", 0)),
                            abs_tol=float(comparison.get("abs_tol", 0)))
    return type(actual) is type(expected) and actual == expected


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)


@contextmanager
def _time_limit(timeout_s: float):
    """Best-effort wall-clock timeout guard for exec/eval blocks."""
    if timeout_s <= 0 or not hasattr(signal, "setitimer"):
        yield
        return

    def _raise_timeout(signum, frame):  # noqa: ANN001, ANN202
        raise TimeoutError("Verification timed out")

    old_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, timeout_s)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


def main() -> int:
    raw = sys.stdin.read()
    try:
        req = json.loads(raw or "{}")
    except json.JSONDecodeError:
        sys.stdout.write(json.dumps({"passed": False, "exec_error": {"type": "JSONDecodeError", "message": "Invalid JSON", "trace": ""}, "stdout": "", "cases": []}))
        return 0

    code = req.get("code") or ""
    cases = req.get("cases") or []
    max_stdout = int(req.get("max_stdout") or 4000)
    exec_timeout_s = max(0.1, float(req.get("exec_timeout_ms") or 2500) / 1000.0)
    case_timeout_s = max(0.1, float(req.get("case_timeout_ms") or 1200) / 1000.0)

    random.seed(0)
    env: dict[str, Any] = {"__name__": "__pandora__"}

    stdout_buf = io.StringIO()
    exec_error = None

    try:
        compiled = compile(code, "<pandora_user_code>", "exec")
        with redirect_stdout(stdout_buf), redirect_stderr(stdout_buf):
            with _time_limit(exec_timeout_s):
                exec(compiled, env, env)
    except Exception as e:  # noqa: BLE001 - intentional sandbox boundary
        exec_error = {
            "type": type(e).__name__,
            "message": str(e),
            "trace": traceback.format_exc(limit=10),
        }

    results = []
    all_passed = exec_error is None

    if exec_error is None:
        for case in cases:
            case_type = (case or {}).get("type")
            label = (case or {}).get("code") or (case or {}).get("name") or "case"
            expected = (case or {}).get("expected")

            passed = False
            actual = None
            error = None

            try:
                if case_type == "variable_value":
                    name = (case or {}).get("name")
                    if not name:
                        raise ValueError("Missing 'name' for variable_value case")
                    if name not in env:
                        raise NameError(f"Variable '{name}' is not defined")
                    actual = env.get(name)
                    passed = validate_output(actual, case["validate"]) is True if case.get("validate") else _matches(actual, expected, case.get("compare"))
                else:
                    expr = (case or {}).get("code")
                    if not expr:
                        raise ValueError("Missing 'code' expression for case")
                    with _time_limit(case_timeout_s):
                        actual = eval(expr, env, env)  # noqa: S307 - trusted expressions from tasks.json
                    with _time_limit(case_timeout_s):
                        passed = validate_output(actual, case["validate"]) is True if case.get("validate") else _matches(actual, expected, case.get("compare"))
            except Exception as e:  # noqa: BLE001 - intentional
                error = f"{type(e).__name__}: {e}"
                passed = False

            if not passed:
                all_passed = False

            results.append(
                {
                    "label": str(label),
                    "passed": bool(passed),
                    "expected": _json_safe(expected),
                    "actual": _json_safe(actual),
                    "error": error,
                }
            )

    out = {
        "passed": bool(all_passed),
        "exec_error": exec_error,
        "stdout": (stdout_buf.getvalue() or "")[:max_stdout],
        "cases": results,
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
