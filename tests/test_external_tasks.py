import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.external_curated import REPAIRS
from scripts.external_task_contracts import codewars_examples, leetcode_examples
from scripts.repair_external_tasks import accepts_arity, curated_cases, curated_repair, source_slug
from task_shapes import public_task, resources_for_task
from runners.output_validators import validate_output


JS_REFERENCES = {
    "chunk-array": "function chunk(a,n){const r=[];for(let i=0;i<a.length;i+=n)r.push(a.slice(i,i+n));return r;}",
    "compact-object": "function compactObject(o){if(Array.isArray(o))return o.filter(Boolean).map(compactObject);if(o&&typeof o==='object')return Object.fromEntries(Object.entries(o).filter(([,v])=>Boolean(v)).map(([k,v])=>[k,compactObject(v)]));return o;}",
    "convert-object-to-json-string": "function jsonStringify(o){return JSON.stringify(o);}",
    "counter-ii": "function createCounter(init){let n=init;return {increment:()=>++n,decrement:()=>--n,reset:()=>n=init};}",
    "differences-between-two-objects": "function objDiff(a,b){if(Object.is(a,b))return {};if(a===null||b===null||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b))return [a,b];const out={};for(const k of Object.keys(a)){if(Object.hasOwn(b,k)){const d=objDiff(a[k],b[k]);if(Array.isArray(d)||Object.keys(d).length)out[k]=d;}}return out;}",
    "flatten-deeply-nested-array": "function flat(a,n){const out=[];for(const v of a){if(Array.isArray(v)&&n>0)out.push(...flat(v,n-1));else out.push(v);}return out;}",
    "is-object-empty": "function isEmpty(o){return Object.keys(o).length===0;}",
    "join-two-arrays-by-id": "function join(a,b){const m=new Map();for(const v of [...a,...b])m.set(v.id,{...m.get(v.id),...v});return [...m.values()].sort((x,y)=>x.id-y.id);}",
    "json-deep-equal": "function areDeeplyEqual(a,b){if(a===b)return true;if(a===null||b===null||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b))return false;const keys=Object.keys(a);return keys.length===Object.keys(b).length&&keys.every(k=>Object.hasOwn(b,k)&&areDeeplyEqual(a[k],b[k]));}",
    "return-length-of-arguments-passed": "function argumentsLength(...args){return args.length;}",
    "two-sum": "function twoSum(a,t){for(let i=0;i<a.length;i++)for(let j=i+1;j<a.length;j++)if(a[i]+a[j]===t)return [j,i];}",
}


def run_harness(language, source, cases):
    command = ([sys.executable, str(ROOT / "runners/python_harness.py")] if language == "python"
               else ["node", str(ROOT / "runners/js_harness.js")])
    result = subprocess.run(command, input=json.dumps({"code": source, "cases": cases}),
                            text=True, capture_output=True, timeout=20)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class ExternalTaskRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = [t for t in json.loads((ROOT / "tasks.json").read_text())["tasks"]
                     if t.get("source_platform") in {"leetcode", "codewars"}]
        cls.by_key = {(t["source_platform"], t["category"], source_slug(t)): t for t in cls.tasks}

    def test_all_source_links_are_specific_and_generic_videos_are_removed(self):
        self.assertEqual(len(self.tasks), 4352)
        for task in self.tasks:
            self.assertTrue(task["source_url"].startswith(("https://leetcode.com/problems/", "https://www.codewars.com/kata/", "https://github.com/")), task["id"])
            resources = resources_for_task(task)
            self.assertEqual(resources["docs"][0]["url"], task["source_url"])
            self.assertEqual(resources["videos"], [])

    def test_curated_contracts_have_saved_cases_and_russian_rules(self):
        count = 0
        for task in self.tasks:
            repair = curated_repair(task)
            if repair is None:
                continue
            count += 1
            self.assertIn(repair.contract, task["description"])
            logic = task["check_logic"]
            self.assertEqual(logic["cases"] + logic["hidden_cases"], curated_cases(task, repair))
            self.assertGreaterEqual(len(logic["hidden_cases"]), 3)
            public = public_task(task)
            self.assertNotIn("hidden_cases", json.dumps(public))
            self.assertNotIn("Краткая цель", task["description"])
        self.assertGreaterEqual(count, 88)

    def test_all_eleven_javascript_leetcode_contracts_in_actual_runner(self):
        for slug, source in JS_REFERENCES.items():
            task = self.by_key["leetcode", "javascript", slug]
            cases = task["check_logic"]["cases"] + task["check_logic"]["hidden_cases"]
            result = run_harness("javascript", source, cases)
            self.assertTrue(result["passed"], (slug, result))

    def test_old_counter_returning_internal_fields_is_rejected(self):
        task = self.by_key["leetcode", "javascript", "counter-ii"]
        logic = task["check_logic"]
        result = run_harness("javascript", "function createCounter(init){return {init,curr:init};}", logic["cases"] + logic["hidden_cases"])
        self.assertFalse(result["passed"])

    def test_shared_counter_state_is_rejected(self):
        task = self.by_key["leetcode", "javascript", "counter-ii"]
        result = run_harness("javascript", "let n;function createCounter(init){n=init;return {increment:()=>++n,decrement:()=>--n,reset:()=>n=init};}", task["check_logic"]["hidden_cases"])
        self.assertFalse(result["passed"])

    def test_bit_tests_are_inside_the_real_input_domain(self):
        task = self.by_key["leetcode", "python", "1-bit-and-2-bit-characters"]
        repair = curated_repair(task)
        for (bits,) in repair.samples:
            self.assertTrue(1 <= len(bits) <= 1000)
            self.assertEqual(bits[-1], 0)
            self.assertLessEqual(set(bits), {0, 1})
        result = run_harness("python", "def isOneBitCharacter(bits):\n i=0\n while i<len(bits)-1:i+=1+bits[i]\n return i==len(bits)-1", task["check_logic"]["cases"] + task["check_logic"]["hidden_cases"])
        self.assertTrue(result["passed"], result)

    def test_independent_golden_answers_for_edge_cases(self):
        golden = {
            ("leetcode", "3sum"): [([[-2, 0, 0, 2, 2]], [[-2, 0, 2]])],
            ("leetcode", "4sum-ii"): [([[0, 0], [0, 0], [0, 0], [0, 0]], 16)],
            ("leetcode", "2-keys-keyboard"): [([1000], 21)],
            ("leetcode", "compact-object"): [([{"a": [], "b": {}, "c": 0}], {"a": [], "b": {}})],
            ("leetcode", "differences-between-two-objects"): [([{"a": True}, {"a": 1}], {"a": [True, 1]}), ([[1, 2], [1, 3, 4]], {"1": [2, 3]})],
            ("leetcode", "json-deep-equal"): [([True, 1], False), ([{}, []], False), ([1, 1.0], True)],
            ("codewars", "human-readable-time"): [([359999], "99:59:59")],
            ("codewars", "rgb-to-hex-conversion"): [([-20, 275, 125], "00FF7D")],
            ("codewars", "growth-of-a-population"): [([99, 1, 1, 105], 4)],
            ("codewars", "tortoise-racing"): [([720, 850, 70], [0, 32, 18])],
            ("codewars", "2d-array-inner-join"): [([[[None], [1], [1]], [[None], [1]], 0, 0], [[1, 1], [1, 1]])],
        }
        for key, values in golden.items():
            repair = next(r for r in REPAIRS if r.platform == key[0] and key[1] in r.slugs)
            for args, expected in values:
                self.assertEqual(repair.reference()(*copy.deepcopy(args)), expected, (key, args))

    def test_argument_defaults_and_rest_parameters_are_honored(self):
        self.assertTrue(accepts_arity({"category": "python", "initial_code": "def f(a,b=2): pass"}, 1))
        self.assertFalse(accepts_arity({"category": "python", "initial_code": "def f(a,b=2): pass"}, 0))
        self.assertTrue(accepts_arity({"category": "javascript", "initial_code": "function f(...args) {}"}, 5))
        self.assertTrue(accepts_arity({"category": "javascript", "initial_code": "function f(a, b=[], c=1) {}"}, 1))

    def test_official_example_parser_keeps_booleans_and_quoted_literals(self):
        self.assertEqual(leetcode_examples('<pre><b>Input:</b> s = "false", nums = [0, 1]\n<b>Output:</b> true\n<b>Explanation:</b> ok</pre>'), [(["false", [0, 1]], True)])
        self.assertEqual(codewars_examples('f("true", false) => "false"', "f"), [(["true", False], "false")])
        self.assertEqual(codewars_examples("f(unknown) -> 2", "f"), [])

    def test_runner_comparisons_accept_equivalent_and_reject_wrong_answers(self):
        checks = [
            ("[[3],[2,1]]", [[1, 2], [3]], {"mode": "unordered_rows"}, True),
            ("[[3],[2,1]]", [[1, 2], [3]], {"mode": "unordered"}, False),
            ("[1,2]", [1, 1], {"mode": "unordered"}, False),
            ("0.333333", 1 / 3, {"mode": "json", "abs_tol": 1e-5}, True),
            ("0.3", 1 / 3, {"mode": "json", "abs_tol": 1e-5}, False),
            ("1", True, {"mode": "json"}, False),
        ]
        for language in ("python", "javascript"):
            cases = [{"code": expr, "expected": expected, "compare": compare} for expr, expected, compare, _ in checks]
            result = run_harness(language, "", cases)
            self.assertEqual([c["passed"] for c in result["cases"]], [v[3] for v in checks], language)

    def test_property_validators_accept_different_correct_answers(self):
        examples = [
            ("longest_palindrome", ["babad"], "bab", "aba", "bad"),
            ("reorganize_string", ["aab"], "aba", "aba", "aab"),
            ("largest_divisible_subset", [[1, 2, 3]], [1, 2], [1, 3], [2, 3]),
            ("shortest_common_supersequence", ["ab", "ba"], "aba", "bab", "ab"),
            ("shortest_superstring", [["ab", "ba"]], "aba", "bab", "abb"),
            ("unique_binary_string", [["01", "10"]], "11", "00", "01"),
            ("odd_count_string", [4], "pppz", "aaab", "aabb"),
            ("dice_observations", [[1, 5, 6], 3, 4], [2, 3, 2, 2], [1, 2, 3, 3], [1, 1, 1, 1]),
            ("no_zero_pair", [11], [2, 9], [3, 8], [1, 10]),
            ("fair_candy_swap", [[1, 2, 5], [1, 2, 3, 4]], [1, 2], [2, 3], [1, 1]),
            ("beautiful_arrangement", [3, 2], [1, 3, 2], [2, 3, 1], [1, 2, 3]),
            ("di_string_match", ["ID"], [0, 2, 1], [1, 2, 0], [0, 1, 2]),
            ("parity_positions", [[4, 2, 5, 7]], [4, 5, 2, 7], [2, 7, 4, 5], [5, 4, 7, 2]),
            ("gray_code", [2], [0, 1, 3, 2], [0, 2, 3, 1], [0, 1, 2, 3]),
            ("pancake_sort", [[3, 1, 2]], [1, 3, 2], [3, 2], [2, 3]),
            ("distinct_rows", [[1, 3, 4, 1, 2, 3, 1]], [[1, 3, 4, 2], [1, 3], [1]], [[1, 3], [1, 3, 2], [1, 4]], [[1, 1], [3, 3], [4, 2, 1]]),
            ("binary_matrix", [2, 1, [1, 1, 1]], [[1, 1, 0], [0, 0, 1]], [[0, 1, 1], [1, 0, 0]], [[1, 1, 1], [0, 0, 0]]),
            ("remove_parentheses", ["(a(b)c"], "a(b)c", "(ab)c", "a(bc"),
            ("highest_peak", [[[0, 1], [0, 0]]], [[1, 0], [2, 1]], [[1, 0], [2, 1]], [[1, 1], [2, 1]]),
            ("avoid_flood", [[1, 2, 0, 0, 2, 1]], [-1, -1, 2, 1, -1, -1], [-1, -1, 1, 2, -1, -1], [-1, -1, 1, 1, -1, -1]),
            ("longest_happy_string", [1, 1, 3], "ccabc", "ccbac", "cccab"),
            ("index_difference", [[5, 1, 4, 1], 2, 4], [0, 3], [3, 0], [0, 1]),
            ("recover_original_array", [[2, 10, 6, 4, 8, 12]], [3, 7, 11], [5, 7, 9], [2, 6, 10]),
            ("group_topological_order", [4, 2, [0, 0, 1, 1], [[], [], [], []]], [0, 1, 2, 3], [3, 2, 1, 0], [0, 2, 1, 3]),
            ("unequal_subsequence", [["a", "b", "c"], [0, 0, 1]], ["a", "c"], ["b", "c"], ["a", "b"]),
            ("parentheses_split", ["(())"], [0, 1, 1, 0], [1, 0, 0, 1], [0, 0, 0, 0]),
            ("nonoverlapping_substrings", ["adefaddaccc"], ["e", "f", "ccc"], ["ccc", "f", "e"], ["a", "f", "ccc"]),
            ("peak_index", [[1, 2, 1, 3, 1]], 1, 3, 2),
            ("peak_grid", [[[1, 4], [3, 2]]], [0, 1], [1, 0], [1, 1]),
            ("subset_sums", [2, [0, 1, -1, 0]], [1, -1], [-1, 1], [0, 0]),
        ]
        for kind, args, example, good, bad in examples:
            spec = {"kind": kind, "args": args, "example": example}
            self.assertTrue(validate_output(good, spec), (kind, good))
            self.assertFalse(validate_output(bad, spec), (kind, bad))

    def test_longest_palindrome_property_checker_against_brute_force(self):
        import itertools
        for n in range(1, 7):
            for letters in itertools.product("ab", repeat=n):
                text = "".join(letters)
                candidates = {text[i:j] for i in range(n) for j in range(i+1, n+1)}
                best = max((s for s in candidates if s == s[::-1]), key=len)
                spec = {"kind": "longest_palindrome", "args": [text], "example": best}
                for candidate in candidates:
                    self.assertEqual(validate_output(candidate, spec), candidate == candidate[::-1] and len(candidate) == len(best))

    def test_real_isolated_python_runner_uses_property_validation(self):
        case = {"code": "longestPalindrome('babad')", "expected": "bab",
                "validate": {"kind": "longest_palindrome", "args": ["babad"], "example": "bab"}}
        for answer, expected in (("aba", True), ("bad", False)):
            request = {"code": f"def longestPalindrome(s): return {answer!r}", "cases": [case]}
            result = subprocess.run([sys.executable, "-I", "-S", str(ROOT / "runners/python_harness.py")],
                                    input=json.dumps(request), text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["passed"], expected)

    def test_in_place_removal_checks_array_contents_and_allows_reordering(self):
        task = self.by_key["leetcode", "python", "remove-element"]
        cases = curated_cases(task, curated_repair(task))
        correct = "def removeElement(nums,val):\n kept=[v for v in nums if v!=val]\n nums[:]=kept[::-1]\n return len(kept)"
        wrong = "def removeElement(nums,val):\n return sum(v!=val for v in nums)"
        self.assertTrue(run_harness("python", correct, cases)["passed"])
        self.assertFalse(run_harness("python", wrong, cases)["passed"])
        for slug, limit in (("remove-duplicates-from-sorted-array", 1), ("remove-duplicates-from-sorted-array-ii", 2)):
            task = self.by_key["leetcode", "python", slug]
            cases = curated_cases(task, curated_repair(task))
            source = f"def removeDuplicates(nums):\n import collections\n kept=[v for v,c in sorted(collections.Counter(nums).items()) for _ in range(min(c,{limit}))]\n nums[:]=kept\n return len(kept)"
            self.assertTrue(run_harness("python", source, cases)["passed"], slug)


if __name__ == "__main__":
    unittest.main()
