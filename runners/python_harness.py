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
import random
import signal
import sys
import traceback
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from typing import Any


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
                    passed = actual == expected
                else:
                    expr = (case or {}).get("code")
                    if not expr:
                        raise ValueError("Missing 'code' expression for case")
                    with _time_limit(case_timeout_s):
                        actual = eval(expr, env, env)  # noqa: S307 - trusted expressions from tasks.json
                    passed = actual == expected
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
