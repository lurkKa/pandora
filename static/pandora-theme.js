/* Profile-owned theme preference. Local storage is only a first-paint cache. */
(() => {
    'use strict';
    const DEFAULT_THEME = 'modern';
    const validTheme = theme => theme === 'modern' || theme === 'classic';
    const storage = {
        get(key) { try { return localStorage.getItem(key); } catch (_) { return null; } },
        set(key, value) { try { localStorage.setItem(key, value); } catch (_) { /* Server still persists the preference. */ } }
    };
    const apiBase = () => /^https?:$/.test(location.protocol)
        ? location.origin
        : (storage.get('api_url') || 'http://127.0.0.1:8000').replace(/\/$/, '');
    const token = () => storage.get('auth_token') || '';
    const cacheKey = id => `pandora_ui_theme:${apiBase()}:${id}`;
    let profileId = null;
    let savedTheme = DEFAULT_THEME;
    let revision = 0;
    let pending = null;
    let statusText = '';

    function renderControl() {
        const select = document.getElementById('profile-ui-theme');
        if (select) {
            select.value = document.documentElement.dataset.uiTheme || DEFAULT_THEME;
            select.disabled = Boolean(pending);
        }
        const status = document.getElementById('profile-theme-status');
        if (status) status.textContent = statusText;
    }

    function apply(theme) {
        theme = validTheme(theme) ? theme : DEFAULT_THEME;
        document.documentElement.dataset.uiTheme = theme;
        const modernStyles = document.getElementById('pandora-modern-styles');
        if (modernStyles) modernStyles.disabled = theme === 'classic';
        renderControl();
    }

    function reset() {
        revision += 1;
        pending?.controller.abort();
        pending = null;
        profileId = null;
        savedTheme = DEFAULT_THEME;
        statusText = '';
        apply(DEFAULT_THEME);
    }

    function restoreCache() {
        reset();
        try {
            // The JWT subject locates a cache entry; it is never used for authorization.
            const encoded = token().split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
            const id = Number(JSON.parse(atob(encoded.padEnd(Math.ceil(encoded.length / 4) * 4, '='))).sub);
            if (!Number.isSafeInteger(id) || id <= 0) return;
            profileId = String(id);
            const cached = storage.get(cacheKey(profileId));
            savedTheme = validTheme(cached) ? cached : DEFAULT_THEME;
            apply(savedTheme);
        } catch (_) { /* No authenticated cache on a fresh sign-in screen. */ }
    }

    function acceptProfile(profile, expectedRevision = revision) {
        if (expectedRevision !== revision || !profile?.id || pending) return false;
        const id = String(profile.id);
        if (id !== profileId) {
            revision += 1;
            statusText = '';
        }
        profileId = id;
        savedTheme = validTheme(profile.ui_theme) ? profile.ui_theme : DEFAULT_THEME;
        storage.set(cacheKey(profileId), savedTheme);
        apply(savedTheme);
        return true;
    }

    async function syncAuthenticatedProfile() {
        const authToken = token();
        if (!authToken) { reset(); return; }
        const expectedRevision = revision;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch(`${apiBase()}/api/auth/me`, {
                headers: { Authorization: `Bearer ${authToken}` }, signal: controller.signal
            });
            if (token() !== authToken || revision !== expectedRevision) return;
            if (response.status === 401) { reset(); return; }
            if (!response.ok) return;
            const profile = await response.json();
            if (token() === authToken) acceptProfile(profile, expectedRevision);
        } catch (_) { /* Keep cached appearance while the connection is unavailable. */ }
        finally { clearTimeout(timeout); }
    }

    async function save(theme) {
        if (!validTheme(theme) || pending) return false;
        const authToken = token();
        if (!profileId || !authToken) {
            statusText = 'Войдите в профиль, чтобы сохранить тему.';
            renderControl();
            return false;
        }
        const expectedId = profileId;
        const expectedRevision = ++revision;
        const previous = savedTheme;
        const controller = new AbortController();
        pending = { controller };
        statusText = 'Сохраняем тему…';
        apply(theme);
        const timeout = setTimeout(() => controller.abort(), 10000);
        const isCurrent = () => profileId === expectedId && revision === expectedRevision && token() === authToken;
        try {
            const response = await fetch(`${apiBase()}/api/profile`, {
                method: 'PUT',
                headers: { Authorization: `Bearer ${authToken}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ ui_theme: theme }), signal: controller.signal
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            if (!isCurrent()) return false;
            savedTheme = theme;
            storage.set(cacheKey(expectedId), theme);
            statusText = 'Тема сохранена в профиле.';
            return true;
        } catch (_) {
            if (isCurrent()) {
                statusText = 'Не удалось сохранить тему. Проверьте соединение и попробуйте снова.';
                apply(previous);
            }
            return false;
        } finally {
            clearTimeout(timeout);
            if (isCurrent()) {
                pending = null;
                // Ignore profile reads that started while the save was in flight.
                revision += 1;
                renderControl();
            }
        }
    }

    window.PandoraTheme = {
        acceptProfile, syncAuthenticatedProfile, save, reset,
        get revision() { return revision; }
    };
    restoreCache();
    document.addEventListener('DOMContentLoaded', () => {
        document.getElementById('profile-ui-theme')?.addEventListener('change', event => save(event.target.value));
        renderControl();
    });
    window.addEventListener('storage', event => {
        if (event.key === 'auth_token' || event.key === null) {
            // The page also owns an authenticated user/editor snapshot. Reload
            // it together with the preference when another tab switches users.
            reset();
            location.reload();
        } else if (profileId && event.key === cacheKey(profileId) && validTheme(event.newValue) && !pending) {
            revision += 1;
            savedTheme = event.newValue;
            apply(savedTheme);
        }
    });
})();
