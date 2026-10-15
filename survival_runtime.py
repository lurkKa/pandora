"""Bounded interpreter for the Python used in Backend Survival.

Student text is parsed, never passed to eval/exec/compile or a host shell.
Only explicit operations on JSON values and the in-memory lab database exist.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import json
import math
import operator
import sqlite3


class LabLimit(BaseException):
    pass


class LabCodeError(Exception):
    pass


class _Return(BaseException):
    def __init__(self, value):
        self.value = value


class _Break(BaseException):
    pass


class _Continue(BaseException):
    pass


@dataclass
class SafeCall:
    call: object


@dataclass
class Module:
    members: dict


@dataclass
class Function:
    node: object
    closure: dict


class Cursor:
    def __init__(self, cursor):
        self.rows = [dict(row) for row in cursor.fetchall()] if cursor.description else []
        self.lastrowid = cursor.lastrowid
        self.rowcount = cursor.rowcount

    def one(self):
        return self.rows.pop(0) if self.rows else None

    def all(self):
        result, self.rows = self.rows, []
        return result


class LabDatabase:
    def __init__(self, rows=(), ready=True):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("CREATE TABLE records(id TEXT PRIMARY KEY, amount INTEGER NOT NULL)")
        self.connection.executemany("INSERT INTO records VALUES (?,?)", [(r["id"], r["amount"]) for r in rows])
        self.ready = ready
        self.available = True
        self.calls = 0
        self.unsafe_queries = 0

    def execute(self, query, params=()):
        import re
        self.calls += 1
        if self.calls > 1500:
            raise LabLimit("Слишком много SQL-запросов")
        if not self.available or not self.ready:
            raise sqlite3.OperationalError("lab storage unavailable")
        if not isinstance(query, str) or len(query) > 1500 or not isinstance(params, (list, tuple)) or len(params) > 20:
            raise ValueError("SQL: запрос и параметры имеют неверный формат")
        if not re.match(r"^\s*(SELECT|INSERT|UPDATE|DELETE)\b", query, re.I):
            raise ValueError("В этой лаборатории доступны SELECT, INSERT, UPDATE, DELETE")
        if re.search(r";|--|/\*|\b(?:pragma|attach|detach|sqlite_|load_extension|randomblob|zeroblob)\b", query, re.I):
            raise ValueError("SQL-команда вне учебной базы")
        if any(not isinstance(v, (str, int, float, type(None))) or isinstance(v, str) and len(v) > 256 for v in params):
            raise ValueError("SQL: допустимы только короткие скалярные параметры")
        if not params and (re.match(r"\s*(INSERT|UPDATE|DELETE)\b", query, re.I) or re.search(r"\bWHERE\b", query, re.I)):
            self.unsafe_queries += 1
        # The authorizer confines all reads/writes to the one lab table.
        def authorize(action, arg1, arg2, db, source):
            if action in {sqlite3.SQLITE_READ, sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE} and arg1 != "records":
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_FUNCTION and str(arg2).lower() not in {"count", "sum", "min", "max", "coalesce", "length", "lower", "upper", "abs"}:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        self.connection.set_authorizer(authorize)
        ticks = [0]
        def progress():
            ticks[0] += 1
            return int(ticks[0] > 100)
        self.connection.set_progress_handler(progress, 100)
        try:
            self.connection.execute("SAVEPOINT lab_query")
            cursor = self.connection.execute(query, params)
            result = Cursor(cursor)
            self.connection.set_authorizer(None)
            rows = list(self.connection.execute("SELECT id, amount FROM records"))
            if len(rows) > 500 or any(not isinstance(r["id"], str) or len(r["id"]) > 128 or type(r["amount"]) is not int or abs(r["amount"]) > 1000000000 for r in rows):
                raise ValueError("records: id — короткая строка, amount — целое; максимум 500 записей")
            self.connection.execute("RELEASE lab_query")
        except BaseException:
            self.connection.set_authorizer(None)
            self.connection.set_progress_handler(None, 0)
            self.connection.execute("ROLLBACK TO lab_query")
            self.connection.execute("RELEASE lab_query")
            raise
        finally:
            self.connection.set_progress_handler(None, 0)
            self.connection.set_authorizer(None)
        return result

    def rows(self):
        return [dict(row) for row in self.connection.execute("SELECT id, amount FROM records ORDER BY id")]

    def close(self):
        self.connection.close()


def bounded(value, depth=0, seen=None, remaining=None):
    remaining = [10000] if remaining is None else remaining
    remaining[0] -= 1
    if remaining[0] < 0:
        raise LabLimit("Слишком большая структура данных")
    if depth > 16:
        raise LabLimit("Слишком глубокая структура данных")
    if isinstance(value, str) and len(value) > 32768 or isinstance(value, bytes) and len(value) > 65536:
        raise LabLimit("Слишком большая строка")
    if isinstance(value, int) and value.bit_length() > 256:
        raise LabLimit("Слишком большое число")
    if isinstance(value, float) and not math.isfinite(value):
        raise LabLimit("Число должно быть конечным")
    if isinstance(value, (dict, list, tuple, set)):
        if len(value) > 1000:
            raise LabLimit("Слишком много элементов")
        seen = set() if seen is None else seen
        if id(value) in seen:
            raise LabLimit("Циклические структуры недоступны")
        seen.add(id(value))
        for item in value.items() if isinstance(value, dict) else value:
            bounded(item, depth + 1, seen, remaining)
        seen.remove(id(value))
    return value


def printable(value):
    """Reject interpreter capabilities before a native repr can traverse closures."""
    bounded(value)
    def visit(item):
        if isinstance(item, (dict, list, tuple, set)):
            for child in item.items() if isinstance(item, dict) else item:
                visit(child)
        elif not isinstance(item, (str, bytes, int, float, bool, type(None))):
            raise LabCodeError("Для вывода используй обычные значения JSON")
    visit(value)
    # Bound textual expansion too (shared strings may have many references).
    def size(item):
        if isinstance(item, (dict, list, tuple, set)):
            return 2 + sum(size(child) + 2 for child in (item.items() if isinstance(item, dict) else item))
        return len(item) * 6 + 4 if isinstance(item, (str, bytes)) else 260
    if size(value) > 65536:
        raise LabLimit("Слишком большой вывод")
    return value


class PythonLab:
    TYPES = (int, float, str, bool, list, dict, tuple, set, range)
    ERRORS = (Exception, ValueError, TypeError, KeyError, IndexError, ZeroDivisionError,
              json.JSONDecodeError, sqlite3.DatabaseError, sqlite3.OperationalError, sqlite3.IntegrityError)
    ALLOWED = {
        "Module", "FunctionDef", "arguments", "arg", "Assign", "AnnAssign", "AugAssign", "Expr",
        "Return", "If", "For", "While", "Break", "Continue", "Pass", "Try", "ExceptHandler", "Raise",
        "Import", "ImportFrom", "alias", "Name", "Load", "Store", "Constant", "Dict", "List", "Tuple", "Set",
        "Subscript", "Slice", "Attribute", "Call", "keyword", "BinOp", "UnaryOp", "BoolOp", "Compare", "IfExp",
        "Lambda", "ListComp", "DictComp", "SetComp", "GeneratorExp", "comprehension", "JoinedStr", "FormattedValue",
        "Add", "Sub", "Mult", "Div", "FloorDiv", "Mod", "Pow", "USub", "UAdd", "Not", "And", "Or",
        "Eq", "NotEq", "Lt", "LtE", "Gt", "GtE", "In", "NotIn", "Is", "IsNot", "Del", "Delete",
    }

    def __init__(self, source, *, budget=450000):
        if not isinstance(source, str) or len(source.encode()) > 32768:
            raise LabCodeError("app.py: максимум 32 КБ")
        try:
            self.tree = ast.parse(source, filename="app.py")
        except (SyntaxError, RecursionError) as error:
            raise LabCodeError(f"app.py: {error}") from None
        nodes = list(ast.walk(self.tree))
        if len(nodes) > 4000:
            raise LabCodeError("app.py: слишком сложный модуль")
        for node in nodes:
            if type(node).__name__ not in self.ALLOWED:
                raise LabCodeError(f"Строка {getattr(node, 'lineno', '?')}: {type(node).__name__} пока не поддерживается учебным Python")
            if isinstance(node, (ast.Name, ast.Attribute)) and (getattr(node, "id", "").startswith("__") or getattr(node, "attr", "").startswith("_")):
                raise LabCodeError("Служебные атрибуты и имена недоступны")
            if isinstance(node, ast.FunctionDef) and (node.decorator_list or node.name.startswith("__")):
                raise LabCodeError("Декораторы и служебные функции недоступны")
            if isinstance(node, ast.FormattedValue) and (node.format_spec or node.conversion != -1):
                raise LabCodeError("В f-строках используй простую подстановку без спецификаторов")
        if any(not isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign, ast.AnnAssign, ast.Expr)) for node in self.tree.body):
            raise LabCodeError("В модуле объявляй функции и константы; обработку запросов помести в handle")
        self.budget = budget
        self.request_budget = 15000
        self.depth = 0
        self.logs = []
        self.sensitive_values = ()
        self.leaked = False
        self.modules = {
            "json": Module({"loads": SafeCall(self._loads), "dumps": SafeCall(self._dumps), "JSONDecodeError": json.JSONDecodeError}),
            "sqlite3": Module({"DatabaseError": sqlite3.DatabaseError, "OperationalError": sqlite3.OperationalError, "IntegrityError": sqlite3.IntegrityError}),
        }
        self.globals = {t.__name__: t for t in self.TYPES + self.ERRORS}
        self.globals.update({
            "len": SafeCall(len), "abs": SafeCall(abs), "min": SafeCall(min), "max": SafeCall(max),
            "sum": SafeCall(lambda xs, start=0: sum(self.iterate(xs), start)),
            "all": SafeCall(lambda xs: all(self.iterate(xs))), "any": SafeCall(lambda xs: any(self.iterate(xs))),
            "sorted": SafeCall(self._sorted), "enumerate": SafeCall(lambda xs, start=0: list(enumerate(self.iterate(xs), start))),
            "zip": SafeCall(lambda *xs: list(zip(*(self.iterate(x) for x in xs)))),
            "isinstance": SafeCall(self._isinstance), "print": SafeCall(self._print),
        })
        self.block(self.tree.body, self.globals)
        if not isinstance(self.globals.get("handle"), Function):
            raise LabCodeError("Определи функцию handle(request, state, env, db)")

    def step(self):
        self.budget -= 1
        self.request_budget -= 1
        if self.budget < 0 or self.request_budget < 0:
            raise LabLimit("Исчерпан лимит инструкций: проверь циклы и сложность обработчика")

    def iterate(self, value):
        if not isinstance(value, (list, tuple, dict, str, set, range)) and type(value).__name__ != "generator":
            raise TypeError("Ожидается последовательность")
        for i, item in enumerate(value):
            self.step()
            if i >= 1000:
                raise LabLimit("Не больше 1000 элементов за один проход")
            yield item

    def _isinstance(self, value, types):
        values = types if isinstance(types, tuple) else (types,)
        if any(t not in self.TYPES + (type(None),) for t in values):
            raise TypeError("Недоступный тип")
        return isinstance(value, types)

    def _loads(self, text):
        if not isinstance(text, (str, bytes)) or len(text) > 32768:
            raise ValueError("Некорректный JSON-ввод")
        return bounded(json.loads(text))

    def _dumps(self, value, **options):
        if set(options) - {"ensure_ascii", "sort_keys", "separators"}:
            raise ValueError("Недоступная опция JSON")
        return bounded(json.dumps(bounded(value), **options))

    def _print(self, *values, sep=" ", end="\n"):
        printable(values)
        line = bounded(str(printable(sep)).join(str(v) for v in values))
        self.leaked = self.leaked or any(secret in line for secret in self.sensitive_values)
        self.logs.append(line[:1000])
        self.logs[:] = self.logs[-100:]

    def _sorted(self, xs, key=None, reverse=False):
        values = list(self.iterate(xs))
        return sorted(values, key=(lambda item: self.call(key, [item], {})) if key is not None else None, reverse=bool(reverse))

    def call(self, function, args, kwargs):
        self.step()
        if isinstance(function, SafeCall):
            return bounded(function.call(*args, **kwargs))
        if function in self.TYPES or function in self.ERRORS:
            if function in (str, bytes) or function in self.ERRORS:
                printable(args)
            if function is range:
                result = range(*args)
                if len(result) > 1000:
                    raise LabLimit("range: не больше 1000 элементов")
                return result
            if function in (list, tuple, set):
                return bounded(function(self.iterate(args[0]) if args else ()))
            if function is dict and args:
                return bounded(dict(args[0], **kwargs) if isinstance(args[0], dict) else dict(self.iterate(args[0]), **kwargs))
            return bounded(function(*args, **kwargs))
        if not isinstance(function, Function):
            raise LabCodeError("Недоступный вызов функции")
        if self.depth >= 20:
            raise LabLimit("Слишком глубокая рекурсия")
        node = function.node
        names = [a.arg for a in node.args.posonlyargs + node.args.args]
        if len(args) > len(names) and not node.args.vararg:
            raise TypeError("Слишком много аргументов")
        local = dict(function.closure)
        defaults = {name: self.expression(value, function.closure) for name, value in zip(names[-len(node.args.defaults):], node.args.defaults)} if node.args.defaults else {}
        assigned = dict(zip(names, args))
        if set(assigned) & set(kwargs):
            raise TypeError("Аргумент передан дважды")
        assigned.update(kwargs)
        if set(assigned) - set(names):
            raise TypeError("Неизвестный аргумент")
        for name in names:
            if name not in assigned and name not in defaults:
                raise TypeError(f"Не передан аргумент {name}")
        local.update(defaults)
        local.update(assigned)
        if node.args.vararg:
            local[node.args.vararg.arg] = tuple(args[len(names):])
        self.depth += 1
        try:
            if isinstance(node, ast.Lambda):
                return self.expression(node.body, local)
            try:
                self.block(node.body, local)
            except _Return as result:
                return result.value
            return None
        finally:
            self.depth -= 1

    def attribute(self, value, name):
        if isinstance(value, Module):
            if name not in value.members:
                raise LabCodeError(f"Недоступный модульный атрибут: {name}")
            return value.members[name]
        if isinstance(value, LabDatabase) and name in {"execute", "commit"}:
            return SafeCall(value.execute if name == "execute" else lambda: None)
        if isinstance(value, Cursor):
            if name in {"fetchone", "fetchall"}:
                return SafeCall(value.one if name == "fetchone" else value.all)
            if name in {"lastrowid", "rowcount"}:
                return getattr(value, name)
        methods = {
            str: {"strip", "lstrip", "rstrip", "lower", "upper", "split", "rsplit", "startswith", "endswith", "replace", "isdigit", "isalnum", "isalpha", "count", "find"},
            dict: {"get", "keys", "values", "items", "pop", "setdefault", "update", "clear", "copy"},
            list: {"append", "extend", "pop", "remove", "count", "index", "clear", "copy", "reverse"},
            set: {"add", "discard", "remove", "clear", "copy"},
        }
        if isinstance(value, str) and name == "encode":
            def encode(encoding="utf-8"):
                if encoding not in {"utf-8", "utf8", "ascii"}:
                    raise ValueError("Доступны UTF-8 и ASCII")
                return bounded(value.encode(encoding))
            return SafeCall(encode)
        if isinstance(value, str) and name == "join":
            def join(xs):
                parts = list(self.iterate(xs))
                if sum(len(v) for v in parts) + len(value)*len(parts) > 32768:
                    raise LabLimit("Слишком большая строка")
                return value.join(parts)
            return SafeCall(join)
        for kind, allowed in methods.items():
            if isinstance(value, kind) and name in allowed:
                def method(*args, **kwargs):
                    if isinstance(value, str) and name == "replace" and len(args) >= 2 and isinstance(args[1], str) and len(value) * (len(args[1]) + 1) > 32768:
                        raise LabLimit("Слишком большая строка после replace")
                    if name in {"append", "extend", "add", "update", "setdefault"}:
                        bounded(args)
                    result = getattr(value, name)(*args, **kwargs)
                    bounded(value)
                    return list(result) if name in {"keys", "values", "items"} else result
                return SafeCall(method)
        raise LabCodeError(f"Атрибут {name} недоступен в учебном Python")

    def expression(self, node, env):
        self.step()
        if isinstance(node, ast.Constant):
            return bounded(node.value)
        if isinstance(node, ast.Name):
            if node.id not in env:
                raise NameError(node.id)
            return env[node.id]
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            result = [self.expression(n, env) for n in node.elts]
            return bounded(tuple(result) if isinstance(node, ast.Tuple) else set(result) if isinstance(node, ast.Set) else result)
        if isinstance(node, ast.Dict):
            if any(k is None for k in node.keys):
                raise LabCodeError("Распаковка словаря пока недоступна; используй update")
            return bounded({self.expression(k, env): self.expression(v, env) for k, v in zip(node.keys, node.values)})
        if isinstance(node, ast.Attribute):
            return self.attribute(self.expression(node.value, env), node.attr)
        if isinstance(node, ast.Subscript):
            return self.expression(node.value, env)[self.expression(node.slice, env)]
        if isinstance(node, ast.Slice):
            return slice(*(self.expression(n, env) if n else None for n in (node.lower, node.upper, node.step)))
        if isinstance(node, ast.Call):
            if any(k.arg is None for k in node.keywords):
                raise LabCodeError("Распаковка аргументов пока недоступна")
            return self.call(self.expression(node.func, env), [self.expression(n, env) for n in node.args], {k.arg: self.expression(k.value, env) for k in node.keywords})
        if isinstance(node, ast.BinOp):
            a, b = self.expression(node.left, env), self.expression(node.right, env)
            if isinstance(node.op, ast.Mod) and isinstance(a, (str, bytes)):
                raise LabCodeError("Для строк используй простые f-строки вместо %-форматирования")
            if isinstance(node.op, ast.Mult):
                seq, count = (a, b) if isinstance(a, (str, bytes, list, tuple)) else (b, a)
                if isinstance(seq, (str, bytes, list, tuple)) and isinstance(count, int) and len(seq)*max(count, 0) > (32768 if isinstance(seq, (str, bytes)) else 1000):
                    raise LabLimit("Слишком большая последовательность")
            if isinstance(node.op, ast.Pow) and (not isinstance(b, (int, float)) or abs(b) > 8):
                raise LabLimit("Слишком большая степень")
            operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
            return bounded(operations[type(node.op)](a, b))
        if isinstance(node, ast.UnaryOp):
            return {ast.Not: operator.not_, ast.USub: operator.neg, ast.UAdd: operator.pos}[type(node.op)](self.expression(node.operand, env))
        if isinstance(node, ast.BoolOp):
            result = None
            for value in node.values:
                result = self.expression(value, env)
                if isinstance(node.op, ast.And) and not result or isinstance(node.op, ast.Or) and result:
                    break
            return result
        if isinstance(node, ast.Compare):
            left = self.expression(node.left, env)
            checks = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge, ast.In: lambda a,b: a in b, ast.NotIn: lambda a,b: a not in b, ast.Is: operator.is_, ast.IsNot: operator.is_not}
            for op, right_node in zip(node.ops, node.comparators):
                right = self.expression(right_node, env)
                if not checks[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            return self.expression(node.body if self.expression(node.test, env) else node.orelse, env)
        if isinstance(node, ast.Lambda):
            return Function(node, dict(env))
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            def generate(index, local):
                if index == len(node.generators):
                    yield (self.expression(node.key, local), self.expression(node.value, local)) if isinstance(node, ast.DictComp) else self.expression(node.elt, local)
                    return
                comp = node.generators[index]
                if comp.is_async:
                    raise LabCodeError("async недоступен")
                for value in self.iterate(self.expression(comp.iter, local)):
                    next_env = dict(local)
                    self.assign(comp.target, value, next_env)
                    if all(self.expression(test, next_env) for test in comp.ifs):
                        yield from generate(index+1, next_env)
            result = generate(0, dict(env))
            if isinstance(node, ast.GeneratorExp):
                return result
            values = list(self.iterate(result))
            return bounded(dict(values) if isinstance(node, ast.DictComp) else set(values) if isinstance(node, ast.SetComp) else values)
        if isinstance(node, ast.JoinedStr):
            return bounded("".join(str(printable(self.expression(v.value, env))) if isinstance(v, ast.FormattedValue) else v.value for v in node.values))
        raise LabCodeError(f"Выражение {type(node).__name__} недоступно")

    def assign(self, target, value, env):
        bounded(value)
        if isinstance(target, ast.Name):
            env[target.id] = value
        elif isinstance(target, ast.Subscript):
            obj = self.expression(target.value, env)
            obj[self.expression(target.slice, env)] = value
            bounded(obj)
        elif isinstance(target, (ast.Tuple, ast.List)):
            values = list(self.iterate(value))
            if len(values) != len(target.elts):
                raise ValueError("Число значений не совпало")
            for item, val in zip(target.elts, values):
                self.assign(item, val, env)
        else:
            raise LabCodeError("Недоступное присваивание")

    def block(self, nodes, env):
        for node in nodes:
            self.step()
            try:
                if isinstance(node, ast.FunctionDef):
                    env[node.name] = Function(node, env)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name not in self.modules:
                                raise LabCodeError("Доступны только json и исключения sqlite3")
                            env[alias.asname or alias.name] = self.modules[alias.name]
                    else:
                        if node.level or node.module not in self.modules:
                            raise LabCodeError("Модуль недоступен")
                        for alias in node.names:
                            env[alias.asname or alias.name] = self.attribute(self.modules[node.module], alias.name)
                elif isinstance(node, ast.Assign):
                    value = self.expression(node.value, env)
                    for target in node.targets:
                        self.assign(target, value, env)
                elif isinstance(node, ast.AnnAssign):
                    if node.value:
                        self.assign(node.target, self.expression(node.value, env), env)
                elif isinstance(node, ast.AugAssign):
                    current = ast.Name(id=node.target.id) if isinstance(node.target, ast.Name) else node.target
                    self.assign(node.target, self.expression(ast.BinOp(left=current, op=node.op, right=node.value), env), env)
                elif isinstance(node, ast.Expr):
                    self.expression(node.value, env)
                elif isinstance(node, ast.Return):
                    raise _Return(self.expression(node.value, env) if node.value else None)
                elif isinstance(node, ast.If):
                    self.block(node.body if self.expression(node.test, env) else node.orelse, env)
                elif isinstance(node, (ast.For, ast.While)):
                    broke = False
                    values = self.iterate(self.expression(node.iter, env)) if isinstance(node, ast.For) else None
                    while True:
                        self.step()
                        if values is not None:
                            try:
                                self.assign(node.target, next(values), env)
                            except StopIteration:
                                break
                        elif not self.expression(node.test, env):
                            break
                        try:
                            self.block(node.body, env)
                        except _Continue:
                            continue
                        except _Break:
                            broke = True
                            break
                    if not broke:
                        self.block(node.orelse, env)
                elif isinstance(node, ast.Try):
                    try:
                        self.block(node.body, env)
                    except (LabLimit, _Return, _Break, _Continue):
                        raise
                    except Exception as error:
                        for handler in node.handlers:
                            match = self.expression(handler.type, env) if handler.type else Exception
                            kinds = match if isinstance(match, tuple) else (match,)
                            if any(kind not in self.ERRORS for kind in kinds):
                                raise LabCodeError("Недоступный тип исключения")
                            if isinstance(error, kinds):
                                if handler.name:
                                    env[handler.name] = str(error)
                                self.block(handler.body, env)
                                break
                        else:
                            raise
                    else:
                        self.block(node.orelse, env)
                    finally:
                        self.block(node.finalbody, env)
                elif isinstance(node, ast.Raise):
                    error = self.expression(node.exc, env) if node.exc else ValueError("Ошибка приложения")
                    if not isinstance(error, self.ERRORS):
                        raise LabCodeError("Недоступное исключение")
                    raise error
                elif isinstance(node, ast.Break):
                    raise _Break()
                elif isinstance(node, ast.Continue):
                    raise _Continue()
                elif isinstance(node, ast.Delete):
                    for target in node.targets:
                        if not isinstance(target, ast.Subscript):
                            raise LabCodeError("Можно удалять только элементы коллекции")
                        del self.expression(target.value, env)[self.expression(target.slice, env)]
                elif not isinstance(node, ast.Pass):
                    raise LabCodeError(f"Оператор {type(node).__name__} недоступен")
            except Exception as error:
                if not hasattr(error, "lab_line"):
                    error.lab_line = getattr(node, "lineno", "?")
                raise

    def handle(self, request, state, env, db):
        self.request_budget = 15000
        response = self.call(self.globals["handle"], [request, state, env, db], {})
        bounded(state)
        if not isinstance(response, dict) or type(response.get("status")) is not int or not 100 <= response["status"] <= 599 or "body" not in response:
            raise ValueError("Ответ: {'status': HTTP-код, 'body': JSON-значение}")
        json.dumps(response, allow_nan=False)
        return bounded(response)
