"""Deterministic parsing of official examples; never guesses expected answers."""
from __future__ import annotations

import ast
from html import unescape
from html.parser import HTMLParser
import json
import re


def literal_value(text):
    tree = ast.parse(text, mode="eval")
    class Names(ast.NodeTransformer):
        def visit_Name(self, node):
            values = {"true": True, "false": False, "null": None}
            if node.id in values:
                return ast.copy_location(ast.Constant(values[node.id]), node)
            return node
    return ast.literal_eval(Names().visit(tree))


class HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1
        if tag in {"p", "pre", "li", "br", "div", "h1", "h2", "h3"}:
            self.parts.append("\n")
        if tag == "sup":
            self.parts.append("^")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip -= 1
        if tag in {"p", "pre", "li", "div", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_text(content):
    parser = HTMLText()
    parser.feed(content or "")
    return unescape("".join(parser.parts)).replace("\xa0", " ")


def literal_prefix(text):
    """Read exactly one JSON/Python literal, retaining its consumed length."""
    text = text.lstrip()
    try:
        value, end = json.JSONDecoder().raw_decode(text)
        return value, end
    except ValueError:
        pass
    # Python examples sometimes use single-quoted strings or booleans.
    for end in range(len(text), 0, -1):
        try:
            return literal_value(text[:end]), end
        except (ValueError, SyntaxError):
            continue
    raise ValueError("Expected a literal")


def parse_arguments(text):
    """Parse `nums = [1, 2], target = 3` without splitting inside arrays."""
    rest = text.strip()
    args = []
    while rest:
        rest = re.sub(r"^[A-Za-z_]\w*\s*=\s*", "", rest)
        value, end = literal_prefix(rest)
        args.append(value)
        rest = rest[end:].lstrip()
        if not rest:
            break
        if rest[0] != ",":
            raise ValueError("Unexpected input separator")
        rest = rest[1:].lstrip()
    return args


def leetcode_examples(content):
    text = html_text(content)
    examples = []
    for match in re.finditer(
        r"Input:\s*(.*?)\s*Output:\s*(.*?)(?=\s*Explanation:|\s*Example\s*\d|\s*Constraints:|\s*Follow.up:|\Z)",
        text, re.S | re.I,
    ):
        try:
            args = parse_arguments(match[1])
            expected, _ = literal_prefix(match[2])
        except ValueError:
            continue
        examples.append((args, expected))
    return examples


def function_name(task):
    starter = task.get("initial_code", "")
    match = re.search(r"(?:def|function)\s+([A-Za-z_$][\w$]*)\s*\(", starter)
    if not match:
        raise ValueError("Unsupported starter signature")
    return match[1]


def call_expression(task, args):
    if task["category"] == "python":
        values = ", ".join(repr(a) for a in args)
    else:
        values = ", ".join(json.dumps(a, ensure_ascii=False, separators=(",", ":")) for a in args)
    return function_name(task) + "(" + values + ")"


def unique_examples(examples):
    seen = set()
    out = []
    for args, expected in examples:
        key = json.dumps([args, expected], sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            out.append((args, expected))
    return out


def codewars_examples(description, name):
    """Recover literal calls from prose/code and their explicit expected values.

    Handles Python, JavaScript and pseudocode arrows, but deliberately skips
    expressions needing execution, undefined globals, and ambiguous outputs.
    """
    text = description.replace("\r", "")
    examples = []
    names = {name, "solution", re.sub(r"_([a-z])", lambda m: m[1].upper(), name)}
    names.add(re.sub(r"([A-Z])", lambda m: "_" + m[1].lower(), name))
    for fname in names:
        for m in re.finditer(r"\b" + re.escape(fname) + r"\s*\(", text, re.I):
            start = m.end()
            depth = 1
            quote = None
            escaped = False
            end = start
            for end in range(start, len(text)):
                ch = text[end]
                if quote:
                    if escaped:
                        escaped = False
                    elif ch == "\\":
                        escaped = True
                    elif ch == quote:
                        quote = None
                elif ch in "\"'":
                    quote = ch
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        break
            if depth != 0:
                continue
            raw_args = text[start:end]
            tail = text[end + 1:]
            marker = re.match(r"\s*;?\s*(?://\s*|#\s*|=>\s*|->\s*|==\s*|=\s*|returns?\s+|should\s+(?:return|be)\s+)", tail, re.I)
            if not marker:
                continue
            try:
                args = literal_value("[" + raw_args + "]")
                output = tail[marker.end():]
                expected, _ = literal_prefix(output)
                json.dumps([args, expected], allow_nan=False)
            except (ValueError, SyntaxError, TypeError):
                continue
            examples.append((args, expected))
    return unique_examples(examples)
