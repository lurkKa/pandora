'use strict';
(() => {
    const el = id => document.getElementById(id);
    const format = value => Number(value).toLocaleString('ru-RU');
    let workspace = null, files = {}, selectedFile = 'app.py', selectedLevel = 1, busy = false;
    let history = [], historyIndex = 0, noticeTimer;
    const storage = {
        get(key) { try { return localStorage.getItem(key); } catch (_) { return null; } },
        set(key, value) { try { localStorage.setItem(key, value); } catch (_) {} },
        remove(key) { try { localStorage.removeItem(key); } catch (_) {} }
    };
    const token = () => storage.get('auth_token');
    // Keep draft recovery tied to the account as well as the scenario.
    function draftKey() { return 'survival-draft-v1:' + (token() || '').slice(-24) + ':' + workspace.variant; }
    function dirty() { return workspace && JSON.stringify(files) !== JSON.stringify(workspace.files); }
    function stash() {
        if (!workspace) return;
        if (dirty()) storage.set(draftKey(), JSON.stringify({files, revision:workspace.revision}));
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
        const response = await fetch('/api/survival/' + path, {
            method: body ? 'POST' : 'GET',
            headers: {'Authorization':'Bearer ' + token(), ...(body ? {'Content-Type':'application/json'} : {})},
            ...(body ? {body:JSON.stringify(body)} : {})
        });
        let data;
        try { data = await response.json(); } catch (_) { throw new Error('Сервер вернул некорректный ответ. Попробуй позже.'); }
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
        try { await fn(); }
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
            button.addEventListener('click', () => { if (!busy) { selectedLevel = level.id; render(); } });
            el('levels').append(button);
        }
        renderMission(); renderFiles(); updateStatus();
        el('guide').textContent = workspace.guide;
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
            button.addEventListener('click', () => { if (!busy) { selectedFile = name; renderFiles(); } });
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
        el('save-state').textContent = changed ? 'Есть изменения' : workspace.needs_restart && shell.running ? 'Нужен перезапуск' : 'Сохранено';
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
    async function save() {
        if (!dirty()) return;
        const current = selectedFile, position = el('editor').selectionStart, scroll = el('editor').scrollTop;
        adopt(await request('save', payload({files})));
        storage.remove(draftKey());
        if (current === selectedFile) { el('editor').setSelectionRange(position,position); el('editor').scrollTop = scroll; }
        notice('Файлы сохранены. После изменения кода перезапусти сервер.');
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
    }
    el('editor').addEventListener('input', () => {
        files[selectedFile] = el('editor').value;
        lines(); updateStatus(); stash();
    });
    el('editor').addEventListener('scroll', () => { el('line-numbers').scrollTop = el('editor').scrollTop; });
    el('editor').addEventListener('click',cursor); el('editor').addEventListener('keyup',cursor);
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
    window.addEventListener('beforeunload', event => { if (dirty()) { stash(); event.preventDefault(); event.returnValue = ''; } });
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
        selectedFile = 'app.py'; selectedLevel = data.next_level;
        adopt(data); recoverDraft(); el('results').hidden = true;
        append('Стенд: '+ (data.variants[variant].title || data.variants[variant].name), 'success');
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
        action(async () => { const key = draftKey(); adopt(await request('reset',payload())); storage.remove(key); el('results').hidden = true; append('Стенд сброшен. Прогресс прохождения сохранён.'); });
    });
    function recoverDraft() {
        try {
            const draft = JSON.parse(storage.get(draftKey()));
            if (draft && typeof draft.files === 'object' && draft.files && confirm('Найден локальный черновик этого стенда. Восстановить несохранённые изменения поверх текущих файлов?')) {
                for (const [name,value] of Object.entries(draft.files)) if (typeof value === 'string' && name in files && !workspace.readonly.includes(name)) files[name] = value;
                renderFiles(); updateStatus(); stash();
            }
        } catch (_) {}
    }
    async function init() {
        if (!token()) { el('lab').hidden = true; el('login').hidden = false; return; }
        lock(true);
        try {
            const data = await request('state'); selectedLevel = data.next_level; adopt(data); recoverDraft();
            if (data.shell.logs.length) append('Последние события стенда:\n'+data.shell.logs.slice(-8).join('\n'));
        } catch (error) { notice(error.message,true); append(error.message,'error'); }
        finally { lock(false); }
    }
    init();
})();
