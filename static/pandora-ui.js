/* Keyboard and focus behavior shared by Pandora dialogs and side panels. */
(() => {
    'use strict';
    const layerSelector = '.modal-overlay, .profile-modal-overlay, .leaderboard-sidebar, .profile-panel, .guild-sidebar, #my-code-modal';
    const focusSelector = 'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), iframe, summary, [tabindex]:not([tabindex="-1"])';
    const layers = new Map();
    const inertState = new Map();
    let topLayer = null;
    let frame = 0;
    let order = 0;
    let titleSequence = 0;

    const isVisible = element => element.getClientRects().length > 0 && getComputedStyle(element).visibility !== 'hidden';
    const isOpen = element => element.isConnected && (element.classList.contains('active') || element.classList.contains('open') || (element.id === 'my-code-modal' && element.style.display !== 'none'));
    const focusables = layer => [...layer.querySelectorAll(focusSelector)].filter(element => isVisible(element) && !element.closest('[inert]') && element.tabIndex >= 0);
    const schedule = () => { if (!frame) frame = requestAnimationFrame(sync); };

    function registerLayers() {
        document.querySelectorAll(layerSelector).forEach(layer => {
            if (layers.has(layer)) return;
            const observer = new MutationObserver(schedule);
            observer.observe(layer, { attributes: true, attributeFilter: ['class', 'style'] });
            layers.set(layer, { observer, open: false, order: 0, trigger: null });
            layer.setAttribute('role', 'dialog');
            layer.setAttribute('aria-modal', 'true');
            if (!layer.hasAttribute('aria-labelledby') && !layer.hasAttribute('aria-label')) {
                const heading = layer.querySelector('h2, h3');
                if (heading) {
                    if (!heading.id) heading.id = `ui-dialog-title-${++titleSequence}`;
                    layer.setAttribute('aria-labelledby', heading.id);
                } else {
                    layer.setAttribute('aria-label', 'Пандора');
                }
            }
        });
        schedule();
    }

    function focusStart(layer) {
        const heading = layer.querySelector('h2, h3');
        const target = heading || focusables(layer)[0] || layer;
        if ((target === heading || target === layer) && !target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
        target.focus({ preventScroll: true });
    }

    function sync() {
        frame = 0;
        const previous = topLayer;
        const previousTrigger = layers.get(previous)?.trigger;
        const openLayers = [];
        layers.forEach((state, layer) => {
            const open = isOpen(layer);
            if (open && !state.open) {
                state.trigger = document.activeElement;
                state.order = ++order;
                layer.style.setProperty('--ui-layer-order', state.order);
            }
            state.open = open;
            if (open) openLayers.push(layer);
            if (!layer.isConnected) {
                state.observer.disconnect();
                layers.delete(layer);
            }
        });
        openLayers.sort((a, b) => layers.get(a).order - layers.get(b).order);
        topLayer = openLayers.at(-1) || null;

        inertState.forEach((value, element) => { element.inert = value; });
        inertState.clear();
        if (topLayer) {
            [...document.body.children].forEach(element => {
                if (element === topLayer || element.contains(topLayer) || element.id === 'panel-overlay' || ['SCRIPT', 'STYLE', 'LINK'].includes(element.tagName)) return;
                inertState.set(element, element.inert);
                element.inert = true;
            });
        }
        document.body.classList.toggle('ui-dialog-open', Boolean(topLayer));
        if (topLayer !== previous) {
            if (previousTrigger?.isConnected && isVisible(previousTrigger) && !previousTrigger.closest('[inert]') && (!topLayer || topLayer.contains(previousTrigger))) {
                previousTrigger.focus({ preventScroll: true });
            } else if (topLayer) {
                focusStart(topLayer);
            } else if (previous) {
                const fallback = [...document.querySelectorAll('.app-brand, #login-user')].find(isVisible);
                fallback?.focus({ preventScroll: true });
            }
        }
    }

    function closeTop() {
        const close = {
            'quest-modal': () => closeModal(),
            'paste-modal': () => cancelPaste(),
            'achievements-modal': () => closeAchievementsModal(),
            'guild-create-modal': () => closeGuildCreateModal(),
            'public-profile-modal': () => closePublicProfile(),
            'my-code-modal': () => closeMyCodeModal()
        }[topLayer?.id];
        if (close) close();
        else if (topLayer?.matches('.leaderboard-sidebar, .profile-panel, .guild-sidebar')) closePanels();
        else topLayer?.querySelector('.guild-close-btn, .btn-close, [aria-label="Закрыть"]')?.click();
    }

    document.addEventListener('keydown', event => {
        if (!topLayer) return;
        if (event.key === 'Escape') {
            // The editor uses Escape followed by Tab to leave indentation mode.
            if (event.target.id === 'code-editor') return;
            event.preventDefault();
            event.stopPropagation();
            closeTop();
        } else if (event.key === 'Tab') {
            const items = focusables(topLayer);
            if (!items.length) {
                event.preventDefault();
                focusStart(topLayer);
                return;
            }
            const index = items.indexOf(document.activeElement);
            if (event.shiftKey && index <= 0) {
                event.preventDefault();
                items.at(-1).focus();
            } else if (!event.shiftKey && (index === items.length - 1 || index < 0)) {
                event.preventDefault();
                items[0].focus();
            }
        }
    }, true);

    document.addEventListener('focusin', event => {
        if (topLayer && isOpen(topLayer) && !topLayer.contains(event.target)) focusStart(topLayer);
    });
    document.getElementById('code-editor')?.addEventListener('blur', () => { editorTabNavigation = false; });
    const updateSkipLink = () => {
        const loggedIn = isVisible(document.getElementById('app'));
        const link = document.getElementById('skip-to-content');
        link.href = loggedIn ? '#main-content' : '#login-user';
        link.textContent = loggedIn ? 'Перейти к заданиям' : 'Перейти к входу';
    };
    new MutationObserver(updateSkipLink).observe(document.getElementById('app'), { attributes: true, attributeFilter: ['class', 'style'] });
    updateSkipLink();
    const bodyObserver = new MutationObserver(registerLayers);
    bodyObserver.observe(document.body, { childList: true });
    registerLayers();
})();
