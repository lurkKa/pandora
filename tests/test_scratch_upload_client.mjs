import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../static/scratch-upload.js', import.meta.url), 'utf8');
const MB = 1024 * 1024;

function harness(fetch) {
    const hint = { textContent: '' };
    const context = vm.createContext({
        window: {}, document: { querySelectorAll: () => [hint] },
        fetch, AbortController, setTimeout, clearTimeout
    });
    vm.runInContext(source, context);
    return { api: context.window.PandoraScratchUpload, hint };
}

test('large projects are allowed, empty and oversized files are explained', () => {
    const { api } = harness();
    assert.equal(api.validate({ name: 'проект.SB3', size: 100 * MB }), null);
    assert.match(api.validate({ name: 'project.sb3', size: 100 * MB + 1 }), /100 МБ/);
    assert.match(api.validate({ name: 'project.sb3', size: 0 }), /пустой/);
    assert.match(api.validate({ name: 'project.zip', size: 100 }), /формат .sb3/);
    assert.match(api.validate(null), /выберите файл/);
});

test('server configuration controls validation and visible limit on both pages', async () => {
    const requests = [];
    const { api, hint } = harness(async url => {
        requests.push(url);
        return { ok: true, json: async () => ({ max_bytes: 150 * MB }) };
    });
    await Promise.all([api.load('https://example.test'), api.load('https://example.test')]);
    await api.load('https://example.test');
    assert.equal(requests.length, 1);
    assert.equal(requests[0], 'https://example.test/api/scratch/upload-config');
    assert.equal(api.validate({ name: 'project.sb3', size: 150 * MB }), null);
    assert.match(api.validate({ name: 'project.sb3', size: 150 * MB + 1 }), /150 МБ/);
    assert.match(hint.textContent, /150 МБ/);
    for (const page of ['index.html', 'exam.html']) {
        const html = readFileSync(new URL(`../${page}`, import.meta.url), 'utf8');
        assert.match(html, /src="static\/scratch-upload.js/);
        assert.match(html, /await PandoraScratchUpload.load\(API_URL\)/);
        assert.match(html, /return PandoraScratchUpload.validate\(file\)/);
    }
});

test('failed config can be retried and a stricter server limit is respected', async () => {
    let calls = 0;
    const { api } = harness(async () => {
        if (++calls === 1) throw new Error('offline');
        return { ok: true, json: async () => ({ max_bytes: 2 * MB }) };
    });
    await api.load('https://example.test');
    assert.equal(api.validate({ name: 'project.sb3', size: 11 * MB }), null);
    await api.load('https://example.test');
    assert.match(api.validate({ name: 'project.sb3', size: 11 * MB }), /2 МБ/);
});
