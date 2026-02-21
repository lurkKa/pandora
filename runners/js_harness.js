#!/usr/bin/env node
/**
 * PANDORA JavaScript Verification Harness (Sandbox Target)
 *
 * Designed to run inside a constrained environment (preferably Docker).
 * Reads JSON from stdin and writes JSON to stdout.
 *
 * Input:
 * {
 *   "code": "js source",
 *   "cases": [
 *     {"code": "add(2, 3)", "expected": 5},
 *     {"type": "variable_value", "name": "x", "expected": 1}
 *   ],
 *   "timeout_ms": 750
 * }
 */

const vm = require('node:vm');

function safeJson(value) {
  try {
    return JSON.parse(JSON.stringify(value));
  } catch {
    try {
      return String(value);
    } catch {
      return '[unserializable]';
    }
  }
}

function deepEqual(a, b) {
  if (Object.is(a, b)) return true;
  if (typeof a !== typeof b) return false;
  if (a === null || b === null) return a === b;
  if (typeof a !== 'object') return a === b;

  // Arrays
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b)) return false;
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
      if (!deepEqual(a[i], b[i])) return false;
    }
    return true;
  }

  const aKeys = Object.keys(a).sort();
  const bKeys = Object.keys(b).sort();
  if (aKeys.length !== bKeys.length) return false;
  for (let i = 0; i < aKeys.length; i++) {
    if (aKeys[i] !== bKeys[i]) return false;
  }
  for (const k of aKeys) {
    if (!deepEqual(a[k], b[k])) return false;
  }
  return true;
}

function readStdin() {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => (data += chunk));
    process.stdin.on('end', () => resolve(data));
  });
}

async function main() {
  const raw = await readStdin();
  let req;
  try {
    req = JSON.parse(raw || '{}');
  } catch {
    process.stdout.write(
      JSON.stringify({
        passed: false,
        exec_error: { type: 'JSONParseError', message: 'Invalid JSON', trace: '' },
        stdout: '',
        cases: [],
      })
    );
    return;
  }

  const code = req.code || '';
  const cases = req.cases || [];
  const timeoutMs = Math.max(250, Number(req.timeout_ms || 1500));

  const logs = [];
  const sandbox = {
    console: {
      log: (...args) => logs.push(args.map(String).join(' ')),
      error: (...args) => logs.push(args.map(String).join(' ')),
    },
    Math,
    Date,
    // Remove common escape hatches
    require: undefined,
    process: undefined,
    Function: undefined,
    eval: undefined,
    fetch: undefined,
    setTimeout: undefined,
    setInterval: undefined,
  };

  vm.createContext(sandbox);

  let execError = null;
  try {
    vm.runInContext(code, sandbox, { timeout: timeoutMs });
  } catch (e) {
    execError = {
      type: e?.name || 'Error',
      message: String(e?.message || e),
      trace: String(e?.stack || ''),
    };
  }

  const results = [];
  let allPassed = execError === null;

  if (!execError) {
    for (const c of cases) {
      const label = c?.code || c?.name || 'case';
      const expected = c?.expected;
      let passed = false;
      let actual;
      let error = null;

      try {
        if (c?.type === 'variable_value') {
          const name = c?.name;
          if (!name) throw new Error("Missing 'name' for variable_value case");
          actual = sandbox[name];
          if (typeof actual === 'undefined') throw new Error(`Variable '${name}' is not defined`);
          passed = deepEqual(actual, expected);
        } else {
          const expr = c?.code;
          if (!expr) throw new Error("Missing 'code' expression for case");
          actual = vm.runInContext(expr, sandbox, { timeout: timeoutMs });
          passed = deepEqual(actual, expected);
        }
      } catch (e) {
        passed = false;
        error = `${e?.name || 'Error'}: ${String(e?.message || e)}`;
      }

      if (!passed) allPassed = false;

      results.push({
        label: String(label),
        passed: Boolean(passed),
        expected: safeJson(expected),
        actual: safeJson(actual),
        error,
      });
    }
  }

  process.stdout.write(
    JSON.stringify({
      passed: Boolean(allPassed),
      exec_error: execError,
      stdout: logs.join('\n').slice(0, 4000),
      cases: results,
    })
  );
}

main().catch((e) => {
  process.stdout.write(
    JSON.stringify({
      passed: false,
      exec_error: { type: e?.name || 'Error', message: String(e?.message || e), trace: String(e?.stack || '') },
      stdout: '',
      cases: [],
    })
  );
});
