import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const controllerSource = readFileSync(new URL('../static/pandora-theme.js', import.meta.url), 'utf8');
const origin = 'https://pandora.example';
const keyFor = (id, api = origin) => `pandora_ui_theme:${api}:${id}`;
const tokenFor = id => `header.${Buffer.from(JSON.stringify({ sub: String(id) })).toString('base64url')}.signature`;
const response = (data = {}, status = 200) => ({
    ok: status >= 200 && status < 300, status, json: async () => data
});

function harness(entries = {}) {
    const stored = new Map(Object.entries(entries));
    const requests = [];
    let reloads = 0;
    const windowEvents = new Map();
    const documentEvents = new Map();
    const elements = new Map([
        ['profile-ui-theme', { value: '', disabled: false, addEventListener() {} }],
        ['profile-theme-status', { textContent: '' }],
        ['pandora-modern-styles', { disabled: false }]
    ]);
    const document = {
        documentElement: { dataset: {} },
        getElementById: id => elements.get(id) || null,
        addEventListener: (name, callback) => documentEvents.set(name, callback)
    };
    const window = { addEventListener: (name, callback) => windowEvents.set(name, callback) };
    const context = vm.createContext({
        window, document, location: { protocol: 'https:', origin, reload() { reloads++; } },
        localStorage: {
            getItem: key => stored.get(key) ?? null,
            setItem: (key, value) => stored.set(key, String(value))
        },
        atob, AbortController, setTimeout, clearTimeout,
        fetch: (url, options) => new Promise((resolve, reject) => {
            requests.push({ url, options, resolve, reject });
        })
    });
    vm.runInContext(controllerSource, context, { filename: 'pandora-theme.js' });
    documentEvents.get('DOMContentLoaded')?.();
    return {
        api: window.PandoraTheme, document, stored, requests,
        select: elements.get('profile-ui-theme'),
        status: elements.get('profile-theme-status'),
        styles: elements.get('pandora-modern-styles'),
        get theme() { return document.documentElement.dataset.uiTheme; },
        get reloads() { return reloads; },
        changeStorage(key, value) {
            if (key === null) stored.clear();
            else if (value === null) stored.delete(key);
            else stored.set(key, value);
            windowEvents.get('storage')?.({ key, newValue: value });
        }
    };
}

test('saved themes have separate account and server caches', async () => {
    const browser = harness({
        auth_token: tokenFor(1),
        [keyFor(1)]: 'classic',
        [keyFor(2)]: 'classic',
        [keyFor(1, 'https://another-school.example')]: 'classic'
    });
    assert.equal(browser.theme, 'classic');
    const save = browser.api.save('modern');
    browser.requests[0].resolve(response());
    assert.equal(await save, true);
    assert.equal(browser.stored.get(keyFor(1)), 'modern');
    assert.equal(browser.stored.get(keyFor(2)), 'classic');
    assert.equal(browser.stored.get(keyFor(1, 'https://another-school.example')), 'classic');

    // Reload both auth and appearance when another tab changes the account.
    browser.changeStorage('auth_token', tokenFor(2));
    assert.equal(browser.reloads, 1);
    assert.equal(await browser.api.save('modern'), false);
    assert.equal(browser.stored.get(keyFor(1)), 'modern');
    assert.equal(browser.requests.length, 1);
    const reloaded = harness(Object.fromEntries(browser.stored));
    assert.equal(reloaded.theme, 'classic');
});

test('another tab signing out or clearing storage aborts pending saves and reloads auth', async () => {
    for (const key of ['auth_token', null]) {
        const browser = harness({ auth_token: tokenFor(1), [keyFor(1)]: 'classic' });
        const save = browser.api.save('modern');
        browser.changeStorage(key, null);
        assert.equal(browser.reloads, 1);
        assert.equal(browser.requests[0].options.signal.aborted, true);
        browser.requests[0].resolve(response());
        assert.equal(await save, false);
        assert.equal(await browser.api.save('classic'), false);
        assert.equal(browser.requests.length, 1);
    }
});

test('another tab changing only the theme updates appearance without reloading work', () => {
    const browser = harness({ auth_token: tokenFor(1) });
    browser.changeStorage(keyFor(1), 'classic');
    assert.equal(browser.theme, 'classic');
    assert.equal(browser.reloads, 0);
    browser.changeStorage(keyFor(2), 'modern');
    assert.equal(browser.theme, 'classic');
});

test('authenticated server preference restores on a fresh device', async () => {
    const browser = harness({ auth_token: tokenFor(17) });
    assert.equal(browser.theme, 'modern');
    const sync = browser.api.syncAuthenticatedProfile();
    const request = browser.requests[0];
    assert.equal(request.url, `${origin}/api/auth/me`);
    assert.equal(request.options.headers.Authorization, `Bearer ${tokenFor(17)}`);
    request.resolve(response({ id: 17, ui_theme: 'classic' }));
    await sync;
    assert.equal(browser.theme, 'classic');
    assert.equal(browser.styles.disabled, true);
    assert.equal(browser.select.value, 'classic');
    assert.equal(browser.stored.get(keyFor(17)), 'classic');
});

test('failed save rolls back appearance/cache and re-enables the setting', async t => {
    for (const failure of ['network', 'http']) {
        await t.test(failure, async () => {
            const browser = harness({ auth_token: tokenFor(1), [keyFor(1)]: 'modern' });
            const save = browser.api.save('classic');
            assert.equal(browser.theme, 'classic');
            assert.equal(browser.styles.disabled, true);
            assert.equal(browser.select.disabled, true);
            assert.equal(browser.stored.get(keyFor(1)), 'modern');
            const request = browser.requests[0];
            assert.equal(request.options.method, 'PUT');
            assert.deepEqual(JSON.parse(request.options.body), { ui_theme: 'classic' });
            if (failure === 'network') request.reject(new Error('Connection lost'));
            else request.resolve(response({}, 503));
            assert.equal(await save, false);
            assert.equal(browser.theme, 'modern');
            assert.equal(browser.styles.disabled, false);
            assert.equal(browser.select.disabled, false);
            assert.equal(browser.stored.get(keyFor(1)), 'modern');
            assert.match(browser.status.textContent, /Не удалось сохранить/);

            const retry = browser.api.save('classic');
            browser.requests[1].resolve(response());
            assert.equal(await retry, true);
            assert.equal(browser.theme, 'classic');
            assert.equal(browser.select.disabled, false);
            assert.equal(browser.stored.get(keyFor(1)), 'classic');
        });
    }
});

test('GET begun before a save cannot overwrite the selected theme', async () => {
    const browser = harness({ auth_token: tokenFor(1) });
    const sync = browser.api.syncAuthenticatedProfile();
    const save = browser.api.save('classic');
    browser.requests[0].resolve(response({ id: 1, ui_theme: 'modern' }));
    await sync;
    assert.equal(browser.theme, 'classic');
    assert.equal(browser.select.disabled, true);
    browser.requests[1].resolve(response());
    assert.equal(await save, true);
    assert.equal(browser.theme, 'classic');
    assert.equal(browser.select.disabled, false);
});

test('GET begun during a save is stale even when it arrives after the save', async () => {
    const browser = harness({ auth_token: tokenFor(1) });
    const save = browser.api.save('classic');
    const readRevision = browser.api.revision;
    const sync = browser.api.syncAuthenticatedProfile();
    browser.requests[0].resolve(response());
    assert.equal(await save, true);
    assert.notEqual(browser.api.revision, readRevision);
    browser.requests[1].resolve(response({ id: 1, ui_theme: 'modern' }));
    await sync;
    assert.equal(browser.theme, 'classic');
    assert.equal(browser.stored.get(keyFor(1)), 'classic');
    // The index page's independent /api/profile reads use this same snapshot.
    assert.equal(browser.api.acceptProfile({ id: 1, ui_theme: 'modern' }, readRevision), false);
    assert.equal(browser.theme, 'classic');
});

test('reset during save isolates the new account from a late old-account response', async () => {
    const browser = harness({ auth_token: tokenFor(1), [keyFor(1)]: 'classic' });
    const oldSave = browser.api.save('modern');
    const oldRequest = browser.requests[0];
    // Same-tab sign-out must call reset: storage events fire only in other tabs.
    browser.api.reset();
    browser.stored.set('auth_token', tokenFor(2));
    assert.equal(browser.api.acceptProfile({ id: 2, ui_theme: 'classic' }), true);
    assert.equal(oldRequest.options.signal.aborted, true);
    assert.equal(browser.select.disabled, false);
    oldRequest.resolve(response());
    assert.equal(await oldSave, false);
    assert.equal(browser.theme, 'classic');
    assert.equal(browser.stored.get(keyFor(1)), 'classic');
    assert.equal(browser.stored.get(keyFor(2)), 'classic');
    const newSave = browser.api.save('modern');
    browser.requests[1].resolve(response());
    assert.equal(await newSave, true);
    assert.equal(browser.stored.get(keyFor(1)), 'classic');
    assert.equal(browser.stored.get(keyFor(2)), 'modern');
});

test('anonymous and expired sessions cannot keep an authenticated appearance', async () => {
    const anonymous = harness({ [keyFor(1)]: 'classic' });
    assert.equal(anonymous.theme, 'modern');
    assert.equal(await anonymous.api.save('classic'), false);
    assert.equal(anonymous.requests.length, 0);
    assert.equal(anonymous.select.disabled, false);
    const expired = harness({ auth_token: tokenFor(1), [keyFor(1)]: 'classic' });
    const sync = expired.api.syncAuthenticatedProfile();
    expired.requests[0].resolve(response({}, 401));
    await sync;
    assert.equal(expired.theme, 'modern');
    assert.equal(await expired.api.save('classic'), false);
    assert.equal(expired.requests.length, 1);
});
