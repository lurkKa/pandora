"""Checks for tasks whose answer is not unique.

These functions validate the mathematical contract, never compare with one
arbitrarily chosen arrangement/string from an example.
"""
from collections import Counter


def ints(values):
    return isinstance(values, (list, tuple)) and all(type(v) is int for v in values)


def subsequence(small, large):
    it = iter(large)
    return all(value in it for value in small)


def parentheses_depth(text):
    balance = highest = 0
    for char in text:
        if char == "(":
            balance += 1
            highest = max(highest, balance)
        elif char == ")":
            balance -= 1
            if balance < 0:
                return None
    return highest if balance == 0 else None


def validate_output(answer, spec):
    kind, args, example = spec["kind"], spec["args"], spec["example"]
    if kind in {"remove_duplicates", "remove_duplicates_twice", "remove_element"}:
        if not isinstance(answer, (list, tuple)) or len(answer) != 2 or type(answer[0]) is not int or not ints(answer[1]):
            return False
        k, values = answer
        nums = args[0]
        if kind == "remove_element":
            required = [v for v in nums if v != args[1]]
            return k == example == len(required) and len(values) >= k and Counter(values[:k]) == Counter(required)
        limit = 1 if kind == "remove_duplicates" else 2
        required = [v for v, count in sorted(Counter(nums).items()) for _ in range(min(count, limit))]
        return k == example == len(required) and len(values) >= k and list(values[:k]) == required
    if kind == "longest_palindrome":
        return isinstance(answer, str) and len(answer) == len(example) and answer in args[0] and answer == answer[::-1]
    if kind == "reorganize_string":
        if example == "":
            return answer == ""
        return isinstance(answer, str) and Counter(answer) == Counter(args[0]) and all(a != b for a, b in zip(answer, answer[1:]))
    if kind == "largest_divisible_subset":
        return ints(answer) and len(answer) == len(example) and all(v > 0 for v in answer) and not (Counter(answer) - Counter(args[0])) and all(a % b == 0 or b % a == 0 for a in answer for b in answer)
    if kind == "shortest_common_supersequence":
        return isinstance(answer, str) and len(answer) == len(example) and all(subsequence(s, answer) for s in args)
    if kind == "shortest_superstring":
        return isinstance(answer, str) and len(answer) == len(example) and all(word in answer for word in args[0])
    if kind == "unique_binary_string":
        return isinstance(answer, str) and len(answer) == len(args[0]) and set(answer) <= {"0", "1"} and answer not in args[0]
    if kind == "odd_count_string":
        return isinstance(answer, str) and len(answer) == args[0] and set(answer) <= set("abcdefghijklmnopqrstuvwxyz") and all(n % 2 for n in Counter(answer).values())
    if kind == "dice_observations":
        rolls, mean, n = args
        total = (len(rolls) + n) * mean - sum(rolls)
        if not n <= total <= 6 * n:
            return answer == []
        return ints(answer) and len(answer) == n and all(1 <= v <= 6 for v in answer) and sum(answer) == total
    if kind == "no_zero_pair":
        return ints(answer) and len(answer) == 2 and all(v > 0 and "0" not in str(v) for v in answer) and sum(answer) == args[0]
    if kind == "fair_candy_swap":
        a, b = args
        return ints(answer) and len(answer) == 2 and answer[0] in a and answer[1] in b and sum(a) - answer[0] + answer[1] == sum(b) - answer[1] + answer[0]
    if kind == "beautiful_arrangement":
        n, k = args
        return ints(answer) and sorted(answer) == list(range(1, n + 1)) and len({abs(a-b) for a, b in zip(answer, answer[1:])}) == k
    if kind == "di_string_match":
        s, = args
        return ints(answer) and sorted(answer) == list(range(len(s) + 1)) and all((answer[i] < answer[i+1]) == (ch == "I") for i, ch in enumerate(s))
    if kind == "parity_positions":
        return ints(answer) and Counter(answer) == Counter(args[0]) and all(v % 2 == i % 2 for i, v in enumerate(answer))
    if kind == "gray_code":
        n, = args
        if not ints(answer) or len(answer) != 2 ** n or answer[0] != 0 or set(answer) != set(range(2 ** n)):
            return False
        return all((a ^ b) != 0 and ((a ^ b) & ((a ^ b)-1)) == 0 for a, b in zip(answer, answer[1:] + answer[:1]))
    if kind == "pancake_sort":
        arr = list(args[0])
        if not ints(answer) or len(answer) > 10 * len(arr) or not all(1 <= k <= len(arr) for k in answer):
            return False
        for k in answer:
            arr[:k] = arr[:k][::-1]
        return arr == sorted(arr)
    if kind == "distinct_rows":
        nums, = args
        return isinstance(answer, (list, tuple)) and len(answer) == max(Counter(nums).values()) and all(ints(row) and row and len(row) == len(set(row)) for row in answer) and Counter(v for row in answer for v in row) == Counter(nums)
    if kind == "binary_matrix":
        upper, lower, cols = args
        if example == []:
            return answer == []
        return isinstance(answer, (list, tuple)) and len(answer) == 2 and all(ints(row) and len(row) == len(cols) and set(row) <= {0, 1} for row in answer) and sum(answer[0]) == upper and sum(answer[1]) == lower and all(a+b == c for a, b, c in zip(answer[0], answer[1], cols))
    if kind == "remove_parentheses":
        s, = args
        return isinstance(answer, str) and len(answer) == len(example) and subsequence(answer, s) and "".join(c for c in answer if c not in "()") == "".join(c for c in s if c not in "()") and parentheses_depth(answer) is not None
    if kind == "highest_peak":
        water, = args
        m, n = len(water), len(water[0])
        if not isinstance(answer, (list, tuple)) or len(answer) != m or not all(ints(row) and len(row) == n and min(row) >= 0 for row in answer):
            return False
        if max(map(max, answer)) != max(map(max, example)):
            return False
        return all((not water[i][j] or answer[i][j] == 0) and (i == 0 or abs(answer[i][j] - answer[i-1][j]) <= 1) and (j == 0 or abs(answer[i][j] - answer[i][j-1]) <= 1) for i in range(m) for j in range(n))
    if kind == "avoid_flood":
        rains, = args
        if example == []:
            return answer == []
        if not ints(answer) or len(answer) != len(rains):
            return False
        full = set()
        for lake, dry in zip(rains, answer):
            if lake:
                if dry != -1 or lake in full:
                    return False
                full.add(lake)
            else:
                if dry <= 0:
                    return False
                full.discard(dry)
        return True
    if kind == "longest_happy_string":
        return isinstance(answer, str) and len(answer) == len(example) and set(answer) <= set("abc") and all(answer.count(ch) <= limit and ch*3 not in answer for ch, limit in zip("abc", args))
    if kind == "index_difference":
        nums, index_diff, value_diff = args
        if example == [-1, -1]:
            return answer == [-1, -1]
        return ints(answer) and len(answer) == 2 and all(0 <= i < len(nums) for i in answer) and abs(answer[0] - answer[1]) >= index_diff and abs(nums[answer[0]] - nums[answer[1]]) >= value_diff
    if kind == "recover_original_array":
        nums, = args
        if not ints(answer) or not answer or len(answer) * 2 != len(nums):
            return False
        k = min(answer) - min(nums)
        return k > 0 and Counter(v for x in answer for v in (x-k, x+k)) == Counter(nums)
    if kind == "group_topological_order":
        n, m, groups, before = args
        if example == []:
            return answer == []
        if not ints(answer) or sorted(answer) != list(range(n)):
            return False
        positions = {item: i for i, item in enumerate(answer)}
        if any(positions[parent] >= positions[item] for item, parents in enumerate(before) for parent in parents):
            return False
        blocks = {}
        for item, group in enumerate(groups):
            if group >= 0:
                blocks.setdefault(group, []).append(positions[item])
        return all(max(block)-min(block)+1 == len(block) for block in blocks.values())
    if kind == "unequal_subsequence":
        n, words, groups = args if len(args) == 3 else (len(args[0]), *args)
        if not isinstance(answer, (list, tuple)) or len(answer) != len(example) or not all(isinstance(v, str) and v in words for v in answer):
            return False
        indices = [words.index(word) for word in answer]
        return all(a < b and groups[a] != groups[b] for a, b in zip(indices, indices[1:]))
    if kind == "parentheses_split":
        s, = args
        if not ints(answer) or len(answer) != len(s) or not set(answer) <= {0, 1}:
            return False
        depths = [parentheses_depth("".join(c for c, g in zip(s, answer) if g == group)) for group in (0, 1)]
        return None not in depths and max(depths) == (parentheses_depth(s)+1)//2
    if kind == "nonoverlapping_substrings":
        s, = args
        if not isinstance(answer, (list, tuple)) or len(answer) != len(example) or not all(isinstance(v, str) and v and v in s for v in answer) or sum(map(len, answer)) != sum(map(len, example)):
            return False
        intervals = sorted((s.find(word), s.find(word)+len(word)) for word in answer)
        return all(b <= c for (a, b), (c, d) in zip(intervals, intervals[1:])) and all(s.find(ch) >= left and s.rfind(ch) < right for left, right in intervals for ch in set(s[left:right]))
    if kind == "peak_index":
        nums, = args
        return type(answer) is int and 0 <= answer < len(nums) and (answer == 0 or nums[answer] > nums[answer-1]) and (answer == len(nums)-1 or nums[answer] > nums[answer+1])
    if kind == "peak_grid":
        grid, = args
        if not ints(answer) or len(answer) != 2:
            return False
        i, j = answer
        if not (0 <= i < len(grid) and 0 <= j < len(grid[0])):
            return False
        return all(not (0 <= x < len(grid) and 0 <= y < len(grid[0])) or grid[i][j] > grid[x][y] for x, y in ((i-1,j), (i+1,j), (i,j-1), (i,j+1)))
    if kind == "subset_sums":
        n, sums = args
        if not ints(answer) or len(answer) != n:
            return False
        generated = [0]
        for value in answer:
            generated += [s+value for s in generated]
        return Counter(generated) == Counter(sums)
    raise ValueError(f"Unknown output validator: {kind}")
