#!/usr/bin/env python3
"""Recover external exercise contracts from public, authoritative metadata.

Downloads are cached outside the repository. No accounts or API keys are used.
The audit never treats an arbitrary successful reference call as a valid test.
"""
from __future__ import annotations

import argparse
import ast
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.external_curated import REPAIRS, PROPERTY_CONTRACTS
from scripts.external_task_contracts import (
    call_expression, codewars_examples, function_name, html_text, leetcode_examples,
    unique_examples,
)
from runners.output_validators import validate_output

ROOT = Path(__file__).resolve().parents[1]
HARNESS_FINGERPRINT = hashlib.sha256(b"".join((ROOT / "runners" / name).read_bytes() for name in ("python_harness.py", "js_harness.js", "output_validators.py"))).hexdigest()
LOCAL = threading.local()
QUESTION_QUERY = """query { question(titleSlug: %s) {
 questionId questionFrontendId title titleSlug content exampleTestcases sampleTestCase
 codeSnippets { langSlug code }
} }"""

LEETCODE_ALIASES = {
    "play-with-chips": "minimum-cost-to-move-chips-to-the-same-position",
    "bulb-switcher-iv": "minimum-suffix-flips",
    "implement-strstr": "find-the-index-of-the-first-occurrence-in-a-string",
    "minimum-deletion-cost-to-avoid-repeating-letters": "minimum-time-to-make-rope-colorful",
    "max-sum-of-sub-matrix-no-larger-than-k": "max-sum-of-rectangle-no-larger-than-k",
    "minimum-number-of-buckets-required-to-collect-rainwater-from-houses": "minimum-number-of-food-buckets-to-feed-the-hamsters",
    "increasing-subsequences": "non-decreasing-subsequences",
    "coin-change-2": "coin-change-ii",
    "longest-arithmetic-sequence": "longest-arithmetic-subsequence",
    "type-of-triangle-ii": "type-of-triangle",
    "array-partition-i": "array-partition",
}

MUTATES_FIRST = {"move-zeroes", "reverse-string", "sort-colors", "next-permutation", "rotate-image"}
UNORDERED_ROWS = {"3sum", "4sum", "permutations", "permutations-ii", "subsets", "subsets-ii", "combination-sum", "combination-sum-ii", "combination-sum-iii", "group-anagrams"}
UNORDERED = {"two-sum", "intersection-of-two-arrays", "intersection-of-two-arrays-ii"}
# These need property-based checkers, not equality with one arbitrary example.
MULTIPLE_VALID = {
    "sort-items-by-groups-respecting-dependencies", "largest-divisible-subset",
    "shortest-common-supersequence", "recover-the-original-array", "map-of-highest-peak",
    "convert-integer-to-the-sum-of-two-no-zero-integers", "gray-code", "fair-candy-swap",
    "find-missing-observations", "find-unique-binary-string", "beautiful-arrangement-ii",
    "find-the-shortest-superstring", "minimum-remove-to-make-valid-parentheses",
    "reconstruct-a-2-row-binary-matrix", "pancake-sorting",
    "convert-an-array-into-a-2d-array-with-conditions",
    "maximum-nesting-depth-of-two-valid-parentheses-strings",
    "generate-a-string-with-characters-that-have-odd-counts",
    "longest-unequal-adjacent-groups-subsequence-i", "maximum-number-of-non-overlapping-substrings",
    "longest-happy-string", "avoid-flood-in-the-city", "di-string-match",
    "sort-array-by-parity-ii", "find-array-given-subset-sums",
    "find-indices-with-index-and-value-difference-i", "find-indices-with-index-and-value-difference-ii",
    "remove-element", "remove-duplicates-from-sorted-array", "remove-duplicates-from-sorted-array-ii",
    "merge-sorted-array", "find-peak-element", "find-a-peak-element-ii", "peak-index-in-a-mountain-array",
    "reorganize-string", "wiggle-sort-ii", "longest-palindromic-substring", "peak-element",
}

PROPERTY_VALIDATORS = {
    "remove-duplicates-from-sorted-array": "remove_duplicates",
    "remove-duplicates-from-sorted-array-ii": "remove_duplicates_twice",
    "remove-element": "remove_element",
    "longest-palindromic-substring": "longest_palindrome",
    "reorganize-string": "reorganize_string",
    "largest-divisible-subset": "largest_divisible_subset",
    "shortest-common-supersequence": "shortest_common_supersequence",
    "find-the-shortest-superstring": "shortest_superstring",
    "find-unique-binary-string": "unique_binary_string",
    "generate-a-string-with-characters-that-have-odd-counts": "odd_count_string",
    "find-missing-observations": "dice_observations",
    "convert-integer-to-the-sum-of-two-no-zero-integers": "no_zero_pair",
    "fair-candy-swap": "fair_candy_swap",
    "beautiful-arrangement-ii": "beautiful_arrangement",
    "di-string-match": "di_string_match",
    "sort-array-by-parity-ii": "parity_positions",
    "gray-code": "gray_code",
    "pancake-sorting": "pancake_sort",
    "convert-an-array-into-a-2d-array-with-conditions": "distinct_rows",
    "reconstruct-a-2-row-binary-matrix": "binary_matrix",
    "minimum-remove-to-make-valid-parentheses": "remove_parentheses",
    "map-of-highest-peak": "highest_peak",
    "avoid-flood-in-the-city": "avoid_flood",
    "longest-happy-string": "longest_happy_string",
    "find-indices-with-index-and-value-difference-i": "index_difference",
    "find-indices-with-index-and-value-difference-ii": "index_difference",
    "recover-the-original-array": "recover_original_array",
    "sort-items-by-groups-respecting-dependencies": "group_topological_order",
    "longest-unequal-adjacent-groups-subsequence-i": "unequal_subsequence",
    "maximum-nesting-depth-of-two-valid-parentheses-strings": "parentheses_split",
    "maximum-number-of-non-overlapping-substrings": "nonoverlapping_substrings",
    "find-peak-element": "peak_index",
    "find-a-peak-element-ii": "peak_grid",
    "find-array-given-subset-sums": "subset_sums",
}


def official_question(task, cache):
    slug = source_slug(task)
    for suffix in (".canonical.json", ".json"):
        path = cache / "leetcode" / (slug + suffix)
        if path.exists():
            question = (json.loads(path.read_text()).get("data") or {}).get("question")
            if question and question.get("content"):
                return question
    return None


def source_link(task, cache):
    if task["source_platform"] == "leetcode":
        question = official_question(task, cache)
        if question:
            return f"https://leetcode.com/problems/{question['titleSlug']}/", "Условие на LeetCode"
        repository = "kamyu104/LeetCode-Solutions"
    else:
        path = cache / "codewars" / (source_slug(task) + ".json")
        if path.exists():
            metadata = json.loads(path.read_text())
            normalize = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
            if metadata.get("id") and normalize(metadata.get("name", "")) == normalize(task.get("source_title", "")):
                return "https://www.codewars.com/kata/" + metadata["id"], "Условие на Codewars"
        repository = "AKleriX/codewars-tasks"
    path = task["source_path"].split("/", 1)[1]
    if task["source_platform"] == "codewars":
        path = str(Path(path).parent / "task-description.txt")
    return "https://github.com/" + repository + "/blob/master/" + quote(path, safe="/"), "Исходное условие в архиве" if task["source_platform"] == "codewars" else "Исходный файл задачи"


def curated_repair(task):
    slug = source_slug(task)
    return next((r for r in REPAIRS if r.platform == task["source_platform"] and slug in r.slugs), None)


def restore_starter_signature(task, cache):
    if task["source_platform"] != "codewars":
        return False
    source = reference_source(task, cache)
    if not source:
        return False
    name = function_name(task)
    if task["category"] == "python":
        try:
            function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
            # Defaults are part of the public interface. Never copy the body.
            for default in function.args.defaults:
                ast.literal_eval(default)
            for arg in function.args.posonlyargs + function.args.args + function.args.kwonlyargs:
                arg.annotation = None
            function.returns = None
            function.body = [ast.Pass()]
            function.decorator_list = []
            starter = ast.unparse(function) + "\n"
        except (SyntaxError, StopIteration, ValueError):
            return False
    else:
        fname = re.escape(name)
        patterns = [rf"function\s+{fname}\s*\((.*?)\)\s*\{{",
                    rf"\b{fname}\s*=\s*(?:async\s*)?\((.*?)\)\s*=>",
                    rf"\b{fname}\s*=\s*function\s*\((.*?)\)\s*\{{"]
        match = next((m for p in patterns if (m := re.search(p, source, re.S))), None)
        if not match:
            return False
        params = match[1].strip()
        # Do not copy a function body mistaken for a signature by a regex.
        if len(params) > 200 or "\n" in params or ";" in params or "{" in params:
            return False
        starter = f"function {name}({params}) {{\n  // Реализуй функцию по условию.\n}}\n"
    # Preserve familiar starters when their signature was already complete.
    old = task["initial_code"].splitlines()[0].strip()
    new = starter.splitlines()[0].strip()
    if old == new:
        return False
    task["initial_code"] = starter
    return True


def accepts_arity(task, count):
    if task["category"] == "python":
        args = ast.parse(task["initial_code"]).body[0].args
        maximum = len(args.posonlyargs) + len(args.args)
        minimum = maximum - len(args.defaults)
        return count >= minimum and (args.vararg is not None or count <= maximum)
    # JavaScript permits omitted and extra arguments even without explicit
    # defaults/rest syntax. The reference execution verifies each actual call.
    return count >= 0


def case_for(task, args, expected, comparison=None):
    slug = source_slug(task)
    code = call_expression(task, args)
    display_code = None
    if slug in {"remove-duplicates-from-sorted-array", "remove-duplicates-from-sorted-array-ii", "remove-element"} and task["source_platform"] == "leetcode":
        display_code = code
        tail = "".join(", " + repr(v) for v in args[1:])
        code = f"(lambda a: (lambda k: [k, a])({function_name(task)}(a{tail})))({repr(args[0])})"
    if slug in MUTATES_FIRST and task["source_platform"] == "leetcode":
        if task["category"] == "python":
            code = f"(lambda a: ({function_name(task)}(a), a)[1])({repr(args[0])})"
        else:
            code = f"(() => {{ const a = {json.dumps(args[0])}; {function_name(task)}(a); return a; }})()"
    if slug == "counter-ii" and task["category"] == "javascript":
        code = "(() => { const c = createCounter(" + json.dumps(args[0]) + "); return " + json.dumps(args[1]) + ".map(op => c[op]()); })()"
    case = {"code": code, "expected": expected, "compare": comparison or {"mode": "json"}}
    if display_code:
        case["example_call"] = display_code
    if task["category"] == "python" and task["source_platform"] == "leetcode" and slug in PROPERTY_VALIDATORS:
        case["validate"] = {"kind": PROPERTY_VALIDATORS[slug], "args": args, "example": expected}
    def fractional(value):
        if isinstance(value, float):
            return True
        if isinstance(value, list):
            return any(fractional(v) for v in value)
        if isinstance(value, dict):
            return any(fractional(v) for v in value.values())
        return False
    if fractional(expected):
        tolerance = 1e-5 if task["source_platform"] == "leetcode" else 1e-9
        case["compare"] = dict(case["compare"])
        case["compare"].setdefault("rel_tol", tolerance)
        case["compare"].setdefault("abs_tol", tolerance)
    return case


def curated_cases(task, repair):
    reference = repair.reference()
    cases = []
    for args in repair.samples:
        expected = reference(*copy.deepcopy(args))
        # Mutation exercises' reference produces the final array, not None.
        json.dumps(expected, allow_nan=False)
        cases.append(case_for(task, args, expected, {"mode": repair.compare}))
    if source_slug(task) == "counter-ii":
        cases.append({"code": "(() => { const a = createCounter(0), b = createCounter(10); return [a.increment(), b.decrement(), a.increment(), b.reset(), a.reset()]; })()", "expected": [1, 9, 2, 10, 0], "compare": {"mode": "json"}})
    return cases


def curated_description(task, repair, cases):
    name = function_name(task)
    signature = task["initial_code"].splitlines()[0].strip()
    language = task["category"]
    examples = []
    for i, case in enumerate(cases[:3], 1):
        label = "Один из допустимых ответов" if case.get("validate") else "Результат"
        examples.append(f"### Пример {i}\n\n```{language}\n{case.get('example_call', case['code'])}\n```\n{label}:\n```json\n{json.dumps(case['expected'], ensure_ascii=False)}\n```")
    return (
        "## Условие\n\n" + (repair if isinstance(repair, str) else repair.contract) + "\n\n### Функция\n\n"
        + f"Используй имя `{name}` и параметры из стартового кода:\n\n```{language}\n{signature}\n```\n\n"
        + "\n\n".join(examples)
        + "\n\n### Проверка\n\nВсе данные передаются через параметры; ввод с клавиатуры и печать ответа не нужны. "
        + "Данные тестов соответствуют области входных значений задачи. Если условие допускает несколько ответов, подходит любой из них."
    )


def reference_source(task, cache):
    if task["source_platform"] == "codewars":
        path = cache / "cw-source" / task["source_path"].split("/", 1)[1]
        return path.read_text() if path.exists() else None
    if task["category"] != "python":
        return None
    path = cache / "references" / (task["id"] + ".py")
    if not path.exists():
        return None
    source = path.read_text()
    # Keep the actual Solution implementation and helpers. No downloaded code
    # executes in this maintenance process; all calls go through the sandbox.
    source = source.replace(".iteritems()", ".items()").replace(".itervalues()", ".values()").replace(".iterkeys()", ".keys()")
    source = source.replace("itertools.izip", "zip").replace("itertools.imap", "map").replace("itertools.ifilter", "filter")
    source = re.sub(r"^from __future__ import .*\n", "", source, flags=re.M)
    source = source.replace("from fractions import gcd", "from math import gcd")
    prefix = "from __future__ import annotations\nfrom typing import *\nimport math, collections, functools, itertools, heapq, bisect\nxrange=range\nlong=int\nunicode=str\nreduce=functools.reduce\n_builtin_map=map\n_builtin_filter=filter\n_builtin_zip=zip\nmap=lambda *a: list(_builtin_map(*a))\nfilter=lambda *a: list(_builtin_filter(*a))\nzip=lambda *a: list(_builtin_zip(*a))\n"
    return prefix + source + f"\ndef {function_name(task)}(*args):\n    return Solution().{function_name(task)}(*args)\n"


def check_reference(task, cases, cache):
    source = reference_source(task, cache)
    if not source:
        return False, "reference_unavailable"
    key = hashlib.sha256((HARNESS_FINGERPRINT + source + json.dumps(cases, sort_keys=True)).encode()).hexdigest()
    result_file = cache / "verification" / (task["id"] + ".json")
    if result_file.exists():
        saved = json.loads(result_file.read_text())
        if saved.get("key") == key:
            return saved["passed"], saved["reason"]
    python = task["category"] == "python"
    command = [sys.executable, str(ROOT / "runners/python_harness.py")] if python else ["node", "--max-old-space-size=128", str(ROOT / "runners/js_harness.js")]
    try:
        result = subprocess.run(command, input=json.dumps({"code": source, "cases": cases}), text=True, capture_output=True, timeout=20)
        data = json.loads(result.stdout)
        passed = bool(data.get("passed"))
        reason = str((data.get("exec_error") or {}).get("message") or "reference_disagrees")
        result_file.parent.mkdir(parents=True, exist_ok=True)
        result_file.write_text(json.dumps({"key": key, "passed": passed, "reason": reason}))
        return passed, reason
    except (subprocess.TimeoutExpired, ValueError):
        return False, "reference_error"


def candidate_official_cases(task, cache):
    slug = source_slug(task)
    if task["source_platform"] == "leetcode":
        if slug in MULTIPLE_VALID and slug not in PROPERTY_VALIDATORS:
            return [], "needs_property_checker"
        question = official_question(task, cache)
        if not question:
            return [], "statement_unavailable"
        examples = unique_examples(leetcode_examples(question["content"]))
        if slug == "longest-unequal-adjacent-groups-subsequence-i":
            examples = [([len(a[0]), *a], expected) if len(a) == 2 and accepts_arity(task, 3) else (a, expected) for a, expected in examples]
        text = html_text(question["content"]).lower()
        comparison = {"mode": "unordered_rows" if slug in UNORDERED_ROWS else "unordered" if slug in UNORDERED or "in any order" in text else "json"}
        precision = re.search(r"(?:within|error|accuracy|precision).{0,120}?10\s*\^\s*\{?\s*-\s*(\d+)", text, re.S)
        if precision:
            tolerance = 10 ** -int(precision[1])
            comparison.update(rel_tol=tolerance, abs_tol=tolerance)
    else:
        path = cache / "cw-source" / Path(task["source_path"].split("/", 1)[1]).parent / "task-description.txt"
        if not path.exists():
            return [], "statement_unavailable"
        text = path.read_text()
        examples = codewars_examples(text, function_name(task))
        comparison = {"mode": "unordered" if re.search(r"(?:any order|order .* (?:not|unimportant))", text, re.I) else "json"}
    if not examples:
        return [], "examples_not_machine_readable"
    try:
        # An adaptation may have a different signature from the original task.
        if any(not accepts_arity(task, len(args)) for args, _ in examples):
            return [], "signature_mismatch"
        cases = [case_for(task, args, expected, comparison) for args, expected in examples]
        json.dumps(cases, allow_nan=False)
    except (ValueError, SyntaxError, TypeError):
        return [], "unsupported_example_format"
    if all(case.get("validate") for case in cases):
        try:
            if all(validate_output(case["expected"], case["validate"]) is True for case in cases):
                return cases, "property_checked_examples"
        except (ValueError, TypeError, IndexError, ZeroDivisionError):
            pass
        return [], "property_checker_needs_review"
    ok, reason = check_reference(task, cases, cache)
    return (cases, "official_examples_verified") if ok else ([], reason)


def refresh_examples(task, cases):
    """Remove generated, invalid parameter examples from old descriptions.

    This intentionally does not claim that the remaining Russian prose has
    been reviewed; that is tracked separately in the audit.
    """
    description = task.get("description", "")
    signature = task["initial_code"].splitlines()[0].strip()
    params = f"### Параметры\n\nПараметры передаются в порядке из стартового кода:\n\n```{task['category']}\n{signature}\n```\n\n"
    description = re.sub(r"### Параметры\n.*?(?=### Возвращаемое значение)", lambda _: params, description, flags=re.S)
    examples = []
    for i, case in enumerate(cases, 1):
        examples.append(f"**Пример {i}**\n\nВызов:\n```{task['category']}\n{case['code']}\n```\nРезультат проверки:\n```json\n{json.dumps(case['expected'], ensure_ascii=False)}\n```")
    description = re.sub(r"### Примеры\n.*?(?=### Важно|\Z)", lambda _: "### Примеры\n\n" + "\n\n".join(examples) + "\n\n", description, flags=re.S)
    description = re.sub(r"Переходить на внешнюю платформу не нужно:.*?находятся в этом описании\.", "Оригинальные правила доступны по ссылке в материалах задания.", description)
    description = description.replace("скрытые тесты используют другие входные данные тех же типов", "проверка использует допустимые примеры исходного условия")
    task["description"] = description


def repair_bundle(bundle, cache, workers=4, verify_examples=True):
    tasks = [t for t in bundle["tasks"] if t.get("source_platform") in {"leetcode", "codewars"}]
    audit = []
    pending = []
    for task in tasks:
        url, label = source_link(task, cache)
        task["source_url"] = url
        task["resources"] = {"docs": [{"title": label, "url": url}], "videos": []}
        signature_changed = restore_starter_signature(task, cache)
        if signature_changed:
            task["external_signature_revision"] = "2026-10-15"
        repair = curated_repair(task)
        entry = {"id": task["id"], "platform": task["source_platform"], "language": task["category"], "source_url": url,
                 "russian_statement_reviewed": bool(repair), "test_status": "awaiting_review", "signature_restored": bool(task.get("external_signature_revision"))}
        audit.append(entry)
        if repair:
            if source_slug(task) == "return-length-of-arguments-passed":
                task["initial_code"] = "function argumentsLength(...args) {\n  // Верни число переданных аргументов.\n}\n"
                task["external_signature_revision"] = "2026-10-15"
                entry["signature_restored"] = True
            cases = curated_cases(task, repair)
            task["description"] = curated_description(task, repair, cases)
            task["check_logic"] = {"engine": "pyodide" if task["category"] == "python" else "javascript", "cases": cases[:3], "hidden_cases": cases[3:]}
            entry["test_status"] = "curated"
            entry["case_count"] = len(cases)
            task["external_content_revision"] = "2026-10-15-curated"
        elif verify_examples:
            pending.append((task, entry))
    def verify(item):
        task, entry = item
        cases, status = candidate_official_cases(task, cache)
        entry["test_status"] = status
        if cases:
            task["check_logic"] = {"engine": "pyodide" if task["category"] == "python" else "javascript", "cases": cases, "hidden_cases": []}
            contract = PROPERTY_CONTRACTS.get(source_slug(task)) if task["source_platform"] == "leetcode" else None
            if contract:
                task["description"] = curated_description(task, contract, cases)
                entry["russian_statement_reviewed"] = True
            else:
                refresh_examples(task, cases)
            task["external_content_revision"] = "2026-10-15-official-examples"
            entry["case_count"] = len(cases)
        return bool(cases)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, _ in enumerate(pool.map(verify, pending), 1):
            if i % 100 == 0 or i == len(pending):
                print(f"Example verification: {i}/{len(pending)}", flush=True)
    return audit


def write_summary(audit):
    verified = {"curated", "official_examples_verified", "property_checked_examples"}
    statements = sum(row["russian_statement_reviewed"] for row in audit)
    checked = sum(row["test_status"] in verified for row in audit)
    curated = sum(row["test_status"] == "curated" for row in audit)
    signatures = sum(row["signature_restored"] for row in audit)
    lines = [
        "# Исправление импортированных задач — 15 октября 2026\n",
        f"В пакете **{len(audit)} задачи**. Работа над всем пакетом ещё не завершена.\n",
        f"- Ссылки на конкретный первоисточник установлены у всех {len(audit)} задач.",
        f"- Полные русские условия проверены и переписаны у **{statements} задач**.",
        f"- Проверки заменены подтверждёнными примерами или наборами тестов у **{checked} задач**.",
        f"- Из них **{curated}** получили дополнительные граничные и скрытые тесты.",
        f"- Восстановлены **{signatures}** сигнатуры с потерянными параметрами по умолчанию/переменным числом аргументов.",
        f"- **{len(audit)-statements} русских условий** ещё требуют ручной сверки.",
        f"- У **{len(audit)-checked} задач** старые тесты пока сохранены: новых достоверных проверок для них ещё нет.\n",
        "## Что исправлено\n",
        "В новых наборах проверяются допустимые входные данные: например, битовый массив состоит из 0 и 1 и заканчивается нулём, а размер части в Chunk Array положителен. Counter II проверяется через вызовы методов, включая независимость двух экземпляров. У операций удаления элементов проверяется изменение исходного списка, а не только возвращённое число.\n",
        "Для задач с несколькими ответами проверяются свойства результата: длина и палиндромность, условия перестановки, корректность кода Грея, допустимость плана осушения и другие требования. Порядок элементов игнорируется только там, где это разрешено. Для дробных ответов учитывается численный допуск.\n",
        "Примеры, подтверждённые по оригинальному решению, сами по себе не являются полным набором скрытых тестов. Это отдельный статус в отчёте.\n",
        "## Источники и воспроизведение\n",
        "Использованы [данные LeetCode](https://leetcode.com/problems/), [публичный API Codewars](https://dev.codewars.com/) и [исходный архив Codewars](https://github.com/AKleriX/codewars-tasks). Когда ссылка на конкретную ката не подтверждена, указан существующий файл условия в исходном архиве, а не угаданный адрес.\n",
        "Подробный статус каждой задачи — в [external_tasks_audit.json](external_tasks_audit.json). `russian_statement_reviewed` относится к полному тексту условия, `test_status` — к проверкам. Идентификаторы, XP и прогресс пользователей сохранены.\n",
        "```bash",
        "venv/bin/python scripts/repair_external_tasks.py --fetch --workers 2",
        "venv/bin/python scripts/repair_external_tasks.py --references --workers 4",
        "venv/bin/python scripts/repair_external_tasks.py --codewars-sources --workers 4",
        "venv/bin/python scripts/repair_external_tasks.py --apply --workers 4",
        "venv/bin/python task_store.py --build",
        "```\n",
        "Загрузки кэшируются в `/tmp/pandora-external-repair` (можно указать `--cache`). При HTTP 429 загрузчик останавливается; повторный запуск использует сохранённые ответы. Оригинальные решения запускаются только в ограниченном раннере и не включаются в публичные данные задач.\n",
        "## Оставшиеся статусы\n",
        "| Статус | Число задач |",
        "| --- | ---: |",
    ]
    for status, count in Counter(row["test_status"] for row in audit if row["test_status"] not in verified).most_common():
        lines.append(f"| {status} | {count} |")
    (ROOT / "docs/external_tasks_repair.md").write_text("\n".join(lines) + "\n")


def session():
    if not hasattr(LOCAL, "session"):
        LOCAL.session = requests.Session()
        LOCAL.session.headers["User-Agent"] = "PANDORA exercise repair/1.0"
    return LOCAL.session


def cached_get(url, path, *, json_data=True):
    if path.exists():
        return json.loads(path.read_text()) if json_data else path.read_text()
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            response = session().get(url, timeout=25)
            if response.status_code == 429:
                # Respect the service limit; keep the cache and resume later.
                raise RuntimeError("Source rate limit (429); stop and resume after the indicated cooldown")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            result = response.json() if json_data else response.text
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(result, ensure_ascii=False) if json_data else result)
            tmp.replace(path)
            return result
        except (requests.RequestException, ValueError):
            if attempt == 2:
                raise
            time.sleep(1 + attempt)


def source_slug(task):
    path = Path(task["source_path"])
    if task["source_platform"] == "leetcode":
        return path.stem
    title = path.parent.name
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def fetch_task(task, cache):
    slug = source_slug(task)
    platform = task["source_platform"]
    if platform == "leetcode":
        canonical = LEETCODE_ALIASES.get(slug, slug)
        query = QUESTION_QUERY % json.dumps(canonical)
        url = "https://leetcode.com/graphql?query=" + quote(query)
    else:
        url = "https://www.codewars.com/api/v1/code-challenges/" + quote(slug)
    filename = slug + (".canonical" if platform == "leetcode" and slug in LEETCODE_ALIASES else "") + ".json"
    data = cached_get(url, cache / platform / filename)
    if platform == "leetcode":
        data = ((data or {}).get("data") or {}).get("question")
    return bool(data and (data.get("content") or data.get("description")))


def fetch_all(tasks, cache, workers):
    unique = {(t["source_platform"], source_slug(t)): t for t in tasks}
    good = bad = 0
    failed = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_task, t, cache): t for t in unique.values()}
        for i, future in enumerate(as_completed(futures), 1):
            task = futures[future]
            try:
                ok = future.result()
            except RuntimeError:
                for pending in futures:
                    pending.cancel()
                raise
            except Exception as e:
                ok = False
                failed.append({"id": task["id"], "error": str(e)})
            if ok:
                good += 1
            else:
                bad += 1
                failed.append({"id": task["id"], "slug": source_slug(task)})
            if i % 50 == 0 or i == len(futures):
                print(f"Contracts: {i}/{len(futures)}; available={good}; unresolved={bad}", flush=True)
    (cache / "fetch_report.json").write_text(json.dumps(failed, ensure_ascii=False, indent=2))


def fetch_references(tasks, cache, workers):
    tasks = [t for t in tasks if t["source_platform"] == "leetcode" and t["category"] == "python"]
    def fetch(task):
        path = task["source_path"].split("/", 1)[1]
        url = "https://raw.githubusercontent.com/kamyu104/LeetCode-Solutions/master/" + quote(path)
        return cached_get(url, cache / "references" / (task["id"] + ".py"), json_data=False) is not None
    good = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, result in enumerate(pool.map(fetch, tasks), 1):
            good += result
            if i % 100 == 0 or i == len(tasks):
                print(f"References: {i}/{len(tasks)}; available={good}", flush=True)


def fetch_codewars_sources(tasks, cache, workers):
    wanted = {}
    for task in tasks:
        if task["source_platform"] != "codewars":
            continue
        rel = task["source_path"].split("/", 1)[1]
        wanted[rel] = cache / "cw-source" / rel
        desc = str(Path(rel).parent / "task-description.txt")
        wanted[desc] = cache / "cw-source" / desc
    def fetch(item):
        rel, target = item
        url = "https://raw.githubusercontent.com/AKleriX/codewars-tasks/master/" + quote(rel)
        try:
            return cached_get(url, target, json_data=False) is not None
        except Exception:
            return False
    good = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, result in enumerate(pool.map(fetch, wanted.items()), 1):
            good += result
            if i % 100 == 0 or i == len(wanted):
                print(f"Codewars source files: {i}/{len(wanted)}; available={good}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("/tmp/pandora-external-repair"))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--references", action="store_true")
    parser.add_argument("--codewars-sources", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    tasks = [t for t in json.loads((ROOT / "tasks.json").read_text())["tasks"]
             if t.get("source_platform") in {"leetcode", "codewars"}]
    if args.fetch:
        fetch_all(tasks, args.cache, args.workers)
    if args.references:
        fetch_references(tasks, args.cache, args.workers)
    if args.codewars_sources:
        fetch_codewars_sources(tasks, args.cache, args.workers)
    if args.apply or args.audit:
        bundle = json.loads((ROOT / "tasks.json").read_text())
        audit = repair_bundle(bundle, args.cache, args.workers)
        report = {"revision": "2026-10-15", "tasks": audit}
        report_path = ROOT / "docs/external_tasks_audit.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        write_summary(audit)
        if args.apply:
            target = ROOT / "tasks.json"
            tmp = target.with_suffix(".repair.tmp")
            tmp.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n")
            tmp.replace(target)


if __name__ == "__main__":
    main()
