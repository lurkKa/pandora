/* Shared Scratch upload limits for quests and exams. */
(function () {
    let maxBytes = 100 * 1024 * 1024;
    let pending = null;
    let loadedApi = null;

    function updateHints() {
        document.querySelectorAll('[data-scratch-upload-limit]').forEach(element => {
            element.textContent = `Максимальный размер: ${maxBytes / (1024 * 1024)} МБ`;
        });
    }

    async function load(apiUrl) {
        if (loadedApi === apiUrl) return;
        if (pending) return pending;
        pending = (async () => {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 10000);
            try {
                const response = await fetch(`${apiUrl}/api/scratch/upload-config`, { signal: controller.signal });
                if (!response.ok) return;
                const config = await response.json();
                if (Number.isSafeInteger(config.max_bytes) && config.max_bytes > 0) {
                    maxBytes = config.max_bytes;
                    loadedApi = apiUrl;
                }
            } catch (_error) {
                // The server still enforces its limit if configuration is unavailable.
            } finally {
                clearTimeout(timer);
                updateHints();
            }
        })();
        try {
            await pending;
        } finally {
            pending = null;
        }
    }

    function validate(file) {
        if (!file) return 'Пожалуйста, выберите файл .sb3';
        if (!String(file.name || '').toLowerCase().endsWith('.sb3')) return 'Поддерживается только формат .sb3';
        if (!Number(file.size || 0)) return 'Файл пустой. Выберите сохранённый проект .sb3';
        if (file.size > maxBytes) return `Файл слишком большой (макс ${maxBytes / (1024 * 1024)} МБ)`;
        return null;
    }

    window.PandoraScratchUpload = { load, validate };
})();
