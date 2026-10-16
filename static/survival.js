'use strict';
(() => {
    const el = id => document.getElementById(id);
    const format = value => Number(value).toLocaleString('ru-RU');
    let workspace = null, files = {}, selectedFile = 'app.py', selectedLevel = 1, busy = false;
    let history = [], historyIndex = 0, noticeTimer, autosaveTimer, saveFlight = null, saveExpectedRevision = null, savingFiles = null, persistenceError = false;
    const storage = {
        get(key) { try { return localStorage.getItem(key); } catch (_) { return null; } },
        set(key, value) { try { localStorage.setItem(key, value); } catch (_) {} },
        remove(key) { try { localStorage.removeItem(key); } catch (_) {} }
    };
    const token = () => storage.get('auth_token');
    const sessionToken = token();
    // Keep draft recovery tied to the account as well as the scenario.
    function draftKey() { return 'survival-draft-v2:' + workspace.owner_id + ':' + workspace.variant; }
    function viewKey() { return 'survival-view-v1:' + workspace.owner_id + ':' + workspace.variant; }
    function uiSnapshot() {
        let remaining = 30000;
        const terminal = [...el('terminal-output').querySelectorAll('.terminal-entry')].slice(-80).reverse().map(row => {
            const text = row.textContent.slice(0, Math.min(4000, remaining)); remaining -= text.length;
            return {text, kind:['command','error','success'].find(kind => row.classList.contains(kind)) || ''};
        }).filter(row => row.text).reverse();
        const ui = {selected_file:selectedFile, selected_level:selectedLevel, cursor:el('editor').selectionStart,
            scroll:Math.round(el('editor').scrollTop), terminal, history:history.slice(-50),
            command:el('command').value, guide_open:el('guide-details').open,
            previous_open:el('previous-contracts').closest('details').open};
        while (new Blob([JSON.stringify(ui)]).size > 90000) {
            if (ui.terminal.length) ui.terminal.shift();
            else if (ui.history.length) ui.history.shift();
            else break;
        }
        return ui;
    }
    function rememberView() {
        if (workspace) storage.set(viewKey(),JSON.stringify(uiSnapshot()));
    }
    function scheduleSave() {
        if (!workspace) return;
        rememberView(); clearTimeout(autosaveTimer);
        autosaveTimer = setTimeout(async () => {
            if (busy) { scheduleSave(); return; }
            try { await save({quiet:true}); }
            catch (error) { persistenceError = true; updateStatus(); notice(error.message + ' Локальный черновик сохранён.',true); }
        },800);
    }
    function dirty() { return workspace && JSON.stringify(files) !== JSON.stringify(workspace.files); }
    function stash() {
        if (!workspace) return;
        if (dirty()) storage.set(draftKey(), JSON.stringify({files, revision:workspace.revision, base_files:workspace.files, pending_files:savingFiles, ui:uiSnapshot()}));
        else storage.remove(draftKey());
    }
    function notice(message, error = false) {
        clearTimeout(noticeTimer);
        el('notice').textContent = message;
        el('notice').classList.toggle('error', error);
        el('notice').hidden = false;
        noticeTimer = setTimeout(() => { el('notice').hidden = true; }, error ? 15000 : 6500);
    }
    async function request(path, body) {
        if (token() !== sessionToken) throw new Error('Аккаунт изменился. Обнови страницу стенда.');
        const encoded = body ? JSON.stringify(body) : null;
        const response = await fetch('/api/survival/' + path, {
            method: body ? 'POST' : 'GET',
            headers: {'Authorization':'Bearer ' + token(), ...(body ? {'Content-Type':'application/json'} : {})},
            ...(body ? {body:encoded} : {}),
            ...(['save','session'].includes(path) && new Blob([encoded]).size < 60000 ? {keepalive:true} : {})
        });
        let data;
        try { data = await response.json(); } catch (_) { throw new Error('Сервер вернул некорректный ответ. Попробуй позже.'); }
        if (token() !== sessionToken) throw new Error('Аккаунт изменился. Обнови страницу стенда.');
        if (!response.ok) {
            if (response.status === 401) { el('login').hidden = false; el('lab').hidden = true; }
            const detail = Array.isArray(data.detail) ? 'Проверь формат файлов и команды.' : data.detail;
            throw new Error(detail || 'Не удалось выполнить запрос (' + response.status + ')');
        }
        return data;
    }
    function payload(extra = {}) { return {variant:workspace.variant, revision:workspace.revision, ...extra}; }
    function lock(value) {
        busy = value;
        el('lab').setAttribute('aria-busy', String(value));
        for (const id of ['variant','save','run','grade','export','reset','command']) el(id).disabled = value || !workspace;
        el('editor').disabled = value || !workspace;
        for (const button of document.querySelectorAll('.level,.file-button')) button.disabled = value;
        updateStatus();
    }
    async function action(fn) {
        if (busy) return;
        lock(true);
        try { if (saveFlight) await saveFlight; await fn(); }
        catch (error) { notice(error.message, true); append(error.message, 'error'); }
        finally { if (workspace) el('variant').value = workspace.variant; lock(false); }
    }
    function adopt(data, replaceFiles = true) {
        workspace = data;
        if (replaceFiles) files = {...data.files};
        render();
    }
    function render() {
        const selector = el('variant');
        selector.replaceChildren();
        for (const [key, variant] of Object.entries(workspace.variants)) {
            const option = document.createElement('option');
            option.value = key; option.textContent = variant.title || variant.name;
            selector.append(option);
        }
        selector.value = workspace.variant;
        el('profile-xp').textContent = format(workspace.xp) + ' XP';
        const complete = workspace.levels.filter(level => level.completed).length;
        el('campaign-count').textContent = complete + ' / ' + workspace.levels.length + ' ЭТАПОВ';
        el('progress-fill').style.width = 100 * complete / workspace.levels.length + '%';
        el('levels').replaceChildren();
        for (const level of workspace.levels) {
            const button = document.createElement('button');
            button.className = 'level' + (level.completed ? ' completed' : '') + (!level.unlocked ? ' locked' : '') + (level.id === selectedLevel ? ' selected' : '');
            button.setAttribute('aria-current', level.id === selectedLevel ? 'step' : 'false');
            button.title = level.unlocked ? level.title : 'Условия можно изучить; для сдачи пройди предыдущие этапы';
            const number = document.createElement('span'); number.className = 'level-number';
            number.textContent = level.completed ? '✓' : String(level.id).padStart(2,'0');
            const copy = document.createElement('span'); copy.className = 'level-copy';
            const title = document.createElement('strong'); title.textContent = level.title;
            const reward = document.createElement('small'); reward.textContent = (level.completed ? 'ЗАКРЫТО · ' : '') + format(level.xp) + ' XP';
            copy.append(title,reward); button.append(number,copy);
            button.addEventListener('click', () => { if (!busy) { selectedLevel = level.id; renderMissionSelection(); scheduleSave(); } });
            el('levels').append(button);
        }
        renderMission(); renderFiles(); updateStatus();
        el('guide').textContent = workspace.guide;
    }
    function renderMissionSelection() {
        [...el('levels').children].forEach((button,index) => {
            button.classList.toggle('selected',workspace.levels[index].id === selectedLevel);
            button.setAttribute('aria-current',workspace.levels[index].id === selectedLevel ? 'step' : 'false');
        });
        renderMission(); updateStatus();
    }
    function renderMission() {
        const level = workspace.levels.find(item => item.id === selectedLevel);
        const variant = workspace.variants[workspace.variant];
        el('mission-number').textContent = 'ИСПЫТАНИЕ / ' + String(level.id).padStart(2, '0') + (level.completed ? ' · ВЫПОЛНЕНО' : !level.unlocked ? ' · ПОКА ЗАКРЫТО' : '');
        el('mission-title').textContent = level.title;
        el('mission-xp').textContent = format(level.xp);
        el('mission-contract').textContent = level.contract;
        el('variant-contract').textContent = variant.path + '  →  ' + variant.id + ': строка, ' + variant.value + ': целое ' + variant.minimum + '…' + variant.maximum;
        el('previous-contracts').replaceChildren();
        for (const item of workspace.levels.filter(item => item.id < selectedLevel)) {
            const p = document.createElement('p'); p.textContent = item.id + '. ' + item.title + '. ' + item.contract;
            el('previous-contracts').append(p);
        }
        if (selectedLevel === 1) el('previous-contracts').textContent = 'Это первый этап. Начни с healthcheck и настройки окружения.';
        el('grade').textContent = level.completed ? 'Проверить снова →' : 'Проверить этап →';
    }
    function renderFiles() {
        if (!(selectedFile in files)) selectedFile = 'app.py';
        el('files').replaceChildren();
        const names = Object.keys(files).sort((a,b) => (a === 'app.py' ? -1 : b === 'app.py' ? 1 : a.localeCompare(b)));
        for (const name of names) {
            const button = document.createElement('button');
            const readonly = workspace.readonly.includes(name);
            button.className = 'file-button' + (name === selectedFile ? ' active' : '') + (readonly ? ' readonly' : '');
            const icon = document.createElement('span'); icon.className = 'file-icon'; icon.textContent = readonly ? '◇' : name.endsWith('.py') ? 'Py' : '·';
            const label = document.createElement('span'); label.textContent = name;
            button.append(icon,label); button.setAttribute('aria-pressed', String(name === selectedFile));
            button.addEventListener('click', () => { if (!busy) { selectedFile = name; renderFiles(); scheduleSave(); } });
            el('files').append(button);
        }
        el('editor').value = files[selectedFile];
        el('editor').readOnly = workspace.readonly.includes(selectedFile);
        el('editor').setAttribute('aria-label', 'Содержимое файла ' + selectedFile);
        el('file-name').textContent = selectedFile;
        el('file-mode').textContent = workspace.readonly.includes(selectedFile) ? 'ТОЛЬКО ЧТЕНИЕ' : selectedFile.endsWith('.py') ? 'PYTHON' : 'TEXT';
        lines();
    }
    function lines() {
        el('line-numbers').textContent = Array.from({length:el('editor').value.split('\n').length}, (_,i) => i+1).join('\n');
        el('line-numbers').scrollTop = el('editor').scrollTop;
        cursor();
    }
    function cursor() {
        const before = el('editor').value.slice(0,el('editor').selectionStart).split('\n');
        el('cursor-position').textContent = 'Строка ' + before.length + ', столбец ' + (before.at(-1).length+1);
    }
    function updateStatus() {
        if (!workspace) return;
        const shell = workspace.shell, changed = dirty();
        el('save-state').textContent = saveFlight ? 'Сохраняем…' : persistenceError ? 'Черновик · нет синхронизации' : changed ? 'Есть изменения · автосохранение' : workspace.needs_restart && shell.running ? 'Сохранено · нужен перезапуск' : 'Сохранено';
        el('process-state').textContent = shell.running ? 'RUNNING' : 'OFFLINE';
        el('process-dot').className = 'signal-dot' + (!shell.running ? ' offline' : workspace.needs_restart || changed ? ' stale' : '');
        el('connection-state').textContent = shell.connected ? 'SSH CONNECTED' : 'SSH DISCONNECTED';
        el('prompt').textContent = (shell.active ? '(.venv) ' : '') + (shell.connected ? 'trainee@lab:~/app$' : 'guest@local:~$');
        el('grade').disabled = busy || !workspace.levels.find(item => item.id === selectedLevel).unlocked;
        el('run').textContent = shell.running ? '↻ Перезапустить' : '▷ Запустить';
    }
    function append(text, kind = '') {
        const row = document.createElement('div'); row.className = 'terminal-entry' + (kind ? ' '+kind : ''); row.textContent = text;
        el('terminal-output').append(row);
        while (el('terminal-output').children.length > 150) el('terminal-output').firstChild.remove();
        el('terminal-output').scrollTop = el('terminal-output').scrollHeight;
    }
    async function save({quiet = false} = {}) {
        clearTimeout(autosaveTimer);
        if (saveFlight) await saveFlight;
        const changed = dirty(), ui = uiSnapshot();
        if (!changed && JSON.stringify(ui) === JSON.stringify(workspace.ui)) return;
        const snapshot = {...files};
        saveExpectedRevision = workspace.revision + (changed ? 1 : 0);
        savingFiles = changed ? snapshot : null;
        saveFlight = (async () => {
            const data = await request(changed ? 'save' : 'session',payload(changed ? {files:snapshot,ui} : {ui}));
            // Typing can continue while autosave is in flight. Never replace the editor with an older snapshot.
            if (changed) workspace = data;
            else workspace.ui = ui;
            persistenceError = false; stash(); rememberView();
            if (!quiet && changed) notice('Файлы сохранены. После изменения кода перезапусти сервер.');
        })();
        updateStatus();
        try { await saveFlight; }
        finally { saveFlight = null; saveExpectedRevision = null; savingFiles = null; updateStatus(); }
        if (dirty() || JSON.stringify(uiSnapshot()) !== JSON.stringify(workspace.ui)) scheduleSave();
    }
    async function command(text) {
        await save();
        append(el('prompt').textContent + ' ' + text, 'command');
        const result = await request('command',payload({command:text}));
        adopt(result.workspace);
        if (result.output) append(result.output, result.output.startsWith('ERROR:') ? 'error' : '');
        if (result.action?.type === 'clear') el('terminal-output').replaceChildren();
        if (result.action?.type === 'open') { selectedFile = result.action.file; renderFiles(); }
        if (result.action?.type === 'grade') await check();
        scheduleSave();
    }
    async function check() {
        await save();
        el('grade').textContent = 'Проверяем…';
        const level = selectedLevel;
        const result = await request('grade',payload({level}));
        adopt(result.workspace);
        el('results').hidden = false;
        el('result-summary').textContent = result.passed ? 'ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ' : 'ЕСТЬ ОШИБКИ';
        el('result-summary').className = result.passed ? 'result-pass' : 'result-fail';
        el('result-stats').replaceChildren();
        for (const [value,label] of [[result.score+'%','проверок'],[result.requests,'запросов'],[result.crashes,'падений'],['+'+format(result.awarded),'XP начислено']]) {
            const cell = document.createElement('div'), strong = document.createElement('strong'), span = document.createElement('span');
            strong.textContent = value; span.textContent = label; cell.append(strong,span); el('result-stats').append(cell);
        }
        el('checks').replaceChildren();
        for (const item of result.checks) {
            const row = document.createElement('div'); row.className = 'check-row' + (item.passed ? '' : ' failed');
            const icon = document.createElement('span'), title = document.createElement('span'), detail = document.createElement('small');
            icon.className = 'check-icon'; icon.textContent = item.passed ? '✓' : '×'; title.textContent = item.name; detail.textContent = item.detail;
            row.append(icon,title,detail); el('checks').append(row);
        }
        const message = result.passed ? result.already_completed ? 'Этап пройден повторно. Награда уже получена.' : 'Этап пройден! Начислено '+format(result.awarded)+' XP.' : 'Сервер не прошёл все проверки. Подробности под консолью.';
        append(message,result.passed ? 'success' : 'error'); notice(message,!result.passed);
        if (result.passed && !result.already_completed) {
            const next = workspace.levels.find(item => item.id === level+1);
            if (next) { selectedLevel = next.id; render(); }
        }
        scheduleSave();
    }
    el('editor').addEventListener('input', () => {
        files[selectedFile] = el('editor').value;
        lines(); updateStatus(); stash(); scheduleSave();
    });
    el('editor').addEventListener('scroll', () => { el('line-numbers').scrollTop = el('editor').scrollTop; scheduleSave(); });
    for (const event of ['click','keyup']) el('editor').addEventListener(event, () => { cursor(); scheduleSave(); });
    el('command').addEventListener('input',scheduleSave);
    for (const element of [el('guide-details'),el('previous-contracts').closest('details')]) element.addEventListener('toggle',scheduleSave);
    el('editor').addEventListener('keydown', event => {
        if (event.key === 'Tab' && !el('editor').readOnly) {
            event.preventDefault();
            el('editor').setRangeText('    ',el('editor').selectionStart,el('editor').selectionEnd,'end');
            el('editor').dispatchEvent(new Event('input'));
        }
    });
    document.addEventListener('keydown', event => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
            event.preventDefault(); if (workspace) action(save);
        }
    });
    window.addEventListener('beforeunload', event => { rememberView(); if (dirty()) { stash(); event.preventDefault(); event.returnValue = ''; } });
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden' && workspace) { stash(); scheduleSave(); } });
    window.addEventListener('pagehide', () => {
        if (!workspace || token() !== sessionToken) return;
        stash(); rememberView(); clearTimeout(autosaveTimer);
        if (busy) return;
        const changed = dirty(), ui = uiSnapshot();
        // A save can have committed while its response is still travelling.
        // Queue the last snapshot against that revision; the local draft also survives a lost connection.
        const revision = saveExpectedRevision ?? workspace.revision;
        const body = JSON.stringify(payload(changed ? {files,ui,revision} : {ui,revision}));
        if (new Blob([body]).size >= 60000) return;
        fetch('/api/survival/' + (changed ? 'save' : 'session'), {
            method:'POST', headers:{Authorization:'Bearer '+token(),'Content-Type':'application/json'}, body,keepalive:true
        }).catch(() => {});
    });
    window.addEventListener('pageshow', event => { if (event.persisted) location.reload(); });
    window.addEventListener('storage', event => {
        if (event.key === 'auth_token' || event.key === null) {
            clearTimeout(autosaveTimer); stash(); workspace = null; location.reload();
        }
    });
    el('save').addEventListener('click', () => action(save));
    el('run').addEventListener('click', () => action(() => command('restart')));
    el('grade').addEventListener('click', () => action(check));
    el('terminal-form').addEventListener('submit', event => {
        event.preventDefault(); if (!workspace || busy) return;
        const text = el('command').value.trim(); if (!text) return;
        history.push(text); historyIndex = history.length; el('command').value = '';
        action(async () => { await command(text); }).finally(() => el('command').focus());
    });
    el('command').addEventListener('keydown', event => {
        if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
            event.preventDefault(); historyIndex = Math.max(0,Math.min(history.length,historyIndex+(event.key === 'ArrowUp' ? -1 : 1)));
            el('command').value = history[historyIndex] || '';
        }
    });
    el('variant').addEventListener('change', () => action(async () => {
        const variant = el('variant').value;
        await save();
        const data = await request('state?variant='+encodeURIComponent(variant));
        adoptRestored(data); el('results').hidden = true;
        el('terminal-output').replaceChildren(); restoreTerminal(data.ui);
        append('Стенд: '+ (data.variants[variant].title || data.variants[variant].name), 'success');
        scheduleSave();
    }));
    for (const [id,key] of [['schema-example','schema_example'],['unit-example','unit_example']]) {
        el(id).addEventListener('click', () => { if (workspace) { el('example').textContent = workspace[key]; el('example').hidden = false; } });
    }
    el('export').addEventListener('click', () => action(async () => {
        await save();
        const response = await fetch('/api/survival/export?variant='+encodeURIComponent(workspace.variant),{headers:{Authorization:'Bearer '+token()}});
        if (!response.ok) throw new Error('Не удалось скачать проект. Проверь вход в аккаунт.');
        const url = URL.createObjectURL(await response.blob()), link = document.createElement('a');
        link.href = url; link.download = 'survival-'+workspace.variant+'.zip'; document.body.append(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url),1000);
    }));
    el('reset').addEventListener('click', () => {
        if (!workspace || busy || !confirm('Сбросить файлы, консоль и учебную БД этого варианта? Пройденные этапы и полученный XP сохранятся.')) return;
        action(async () => { const key = draftKey(), view = viewKey(); clearTimeout(autosaveTimer); const data = await request('reset',payload()); storage.remove(key); storage.remove(view); el('terminal-output').replaceChildren(); adoptRestored(data); el('results').hidden = true; append('Стенд сброшен. Прогресс прохождения сохранён.'); scheduleSave(); });
    });
    function recoverDraft() {
        try {
            const oldKey = 'survival-draft-v1:' + (token() || '').slice(-24) + ':' + workspace.variant;
            const draft = JSON.parse(storage.get(draftKey()) || storage.get(oldKey));
            if (draft && JSON.stringify(draft.files) === JSON.stringify(files)) { storage.remove(draftKey()); storage.remove(oldKey); return; }
            const baseMatches = draft && [draft.base_files,draft.pending_files].some(base => base && JSON.stringify(base) === JSON.stringify(files));
            if (draft && typeof draft.files === 'object' && draft.files && (draft.revision === workspace.revision || baseMatches || confirm('Локальный черновик отличается от сохранённого стенда. Восстановить его поверх текущих файлов?'))) {
                for (const [name,value] of Object.entries(draft.files)) if (typeof value === 'string' && name in files && !workspace.readonly.includes(name)) files[name] = value;
                renderFiles(); updateStatus(); stash(); storage.remove(oldKey);
            }
        } catch (_) {}
    }
    function restoreTerminal(ui) {
        for (const row of ui?.terminal || []) append(row.text,row.kind);
    }
    function adoptRestored(data) {
        workspace = data;
        let ui = data.ui || {};
        if (!Object.keys(ui).length) { try { ui = JSON.parse(storage.get(viewKey())) || {}; } catch (_) {} }
        selectedFile = ui.selected_file in data.files ? ui.selected_file : 'app.py';
        selectedLevel = data.levels.some(item => item.id === ui.selected_level) ? ui.selected_level : data.next_level;
        history = Array.isArray(ui.history) ? ui.history.filter(text => typeof text === 'string').slice(-50) : [];
        historyIndex = history.length;
        adopt(data); recoverDraft();
        el('editor').setSelectionRange(ui.cursor || 0,ui.cursor || 0);
        el('editor').scrollTop = ui.scroll || 0;
        el('command').value = ui.command || '';
        el('guide-details').open = Boolean(ui.guide_open);
        el('previous-contracts').closest('details').open = Boolean(ui.previous_open);
        return ui;
    }
    async function init() {
        if (!token()) { el('lab').hidden = true; el('login').hidden = false; return; }
        lock(true);
        try {
            const data = await request('state'); const ui = adoptRestored(data); restoreTerminal(ui);
            if (!ui.terminal?.length && data.shell.logs.length) append('Последние события стенда:\n'+data.shell.logs.slice(-8).join('\n'));
            scheduleSave();
        } catch (error) { notice(error.message,true); append(error.message,'error'); }
        finally { lock(false); }
    }
    init();
})();
