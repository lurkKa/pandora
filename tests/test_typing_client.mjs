import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const index = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const alex = readFileSync(new URL('../alextype.html', import.meta.url), 'utf8');
function section(source, start, end) {
  const first = source.indexOf(start);
  const last = source.indexOf(end, first + start.length);
  assert.ok(first >= 0 && last > first, `Missing client section: ${start}`);
  return source.slice(first, last);
}

// Run the actual collectors with a tiny DOM adapter. Browser trust is supplied
// explicitly so both trusted keyboard events and synthetic-event paths are tested.
function collector(scope) {
  const records = [];
  const handlers = new Map();
  let now = 1000;
  const inputEl = {
    value: '',
    addEventListener(type, fn) { handlers.set(type, fn); },
  };
  const context = vm.createContext({
    records, inputEl, window: {}, record: (...args) => records.push(args),
    Date: { now: () => now }, performance: { now: () => now },
    setTimeout: () => 1, setInterval: () => 1, clearInterval() {},
    setStatus() {}, renderSample() {}, setStats() {}, claimXP() {},
    scheduleFrontendPreview() {},
  });
  const run = code => vm.runInContext(code, context);
  if (scope === 'task') {
    run(`
      let taskTypingTelemetry = { record };
      let taskTypingLastValue = '', taskTypingBeforeInput = null;
      let taskTypingLastKeydownAt = 0, taskTypingLastKeydownTrusted = false;
      let taskTypingLastKeydownRepeat = false, editorTabNavigation = false;
    `);
    run(section(index, '        function taskEditorChangedChars(', '        function reconcileTaskEditorTelemetry('));
    run(section(index, '        function handleEditorKeydown(', '        // Add shake animation'));
    run(section(index, '        function captureTaskEditorBeforeInput(', '        const codeEditorEl ='));
    handlers.set('keydown', context.handleEditorKeydown);
    handlers.set('beforeinput', context.captureTaskEditorBeforeInput);
    handlers.set('input', context.captureTaskEditorInput);
  } else {
    run(`
      let typingTelemetry = { record };
      let _lastInputValue = '', _pendingInputMeta = null;
      let startedAt = 0, timer = null, targetText = 'fixture that is never completed';
    `);
    run(section(alex, '    // ===== ANTI-CHEAT v3:', '    document.getElementById("newText")'));
  }
  function dispatch(type, values = {}) {
    const event = {
      key: 'a', isTrusted: true, repeat: false, inputType: 'insertText', data: 'a',
      target: inputEl, currentTarget: inputEl,
      preventDefault() { this.defaultPrevented = true; }, stopPropagation() {},
      ...values,
    };
    handlers.get(type)?.(event);
    return event;
  }
  function change(value, opts = {}) {
    now += opts.delay ?? 80;
    if (opts.keydown !== false) dispatch('keydown', opts);
    const before = dispatch('beforeinput', opts);
    assert.ok(!before.defaultPrevented, 'Fixture input must be accepted');
    inputEl.value = value;
    dispatch('input', opts);
    return records.at(-1);
  }
  return { records, change, dispatch, inputEl, run };
}

for (const scope of ['task', 'alextype']) {
  test(`${scope}: physical key repeat is excluded from bot rhythm`, () => {
    const c = collector(scope);
    assert.deepEqual(c.change('a'), ['insert', 1, true]);
    assert.deepEqual(c.change('aa', { repeat: true }), ['auto', 1, true]);
    assert.deepEqual(c.change('aaa', { repeat: true, isTrusted: false }), ['insert', 1, false]);
  });
  test(`${scope}: native undo and redo are restoration, synthetic undo remains untrusted`, () => {
    const c = collector(scope);
    c.change('a');
    assert.deepEqual(c.change('', { inputType: 'historyUndo', data: null }), ['restore', 1, true]);
    assert.deepEqual(c.change('a', { inputType: 'historyRedo', data: null }), ['restore', 1, true]);
    assert.deepEqual(c.change('b', { inputType: 'historyUndo', data: null, isTrusted: false }), ['programmatic', 1, false]);
  });
  test(`${scope}: IME updates count growth once, not the whole composition buffer`, () => {
    const c = collector(scope);
    c.dispatch('compositionstart');
    const composition = { inputType: 'insertCompositionText', isComposing: true, keydown: false };
    assert.deepEqual(c.change('n', { ...composition, data: 'n' }), ['composition', 1, true]);
    assert.deepEqual(c.change('ni', { ...composition, data: 'ni' }), ['composition', 1, true]);
    assert.deepEqual(c.change('你', { ...composition, data: '你' }), ['delete', 1, true]);
    assert.deepEqual(c.change('好', { ...composition, data: '好' }), ['composition', 0, true]);
    const inserts = c.records.filter(r => r[0] === 'composition').reduce((sum, r) => sum + r[1], 0);
    assert.equal(inserts, 2);
  });
  test(`${scope}: forged IME does not bypass source checks`, () => {
    const c = collector(scope);
    c.dispatch('compositionstart', { isTrusted: false });
    assert.deepEqual(c.change('synthetic', {
      inputType: 'insertCompositionText', isComposing: true, data: 'synthetic', isTrusted: false,
    }), ['composition', 9, false]);
  });
  test(`${scope}: unreported same-length text replacement is recorded`, () => {
    const c = collector(scope);
    c.change('a');
    c.inputEl.value = 'b';
    c.dispatch('input', { isTrusted: false });
    assert.deepEqual(c.records.at(-1), ['programmatic', 1, false]);
  });
}
