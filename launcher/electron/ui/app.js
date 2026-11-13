// The launcher's pages. Each page is drawn from the launcher's state; actions go through window.launcher.
const $ = (sel, el = document) => el.querySelector(sel);
const page = $('#page');
const L = window.launcher;
let current = 'play';
let game = { running: false };
let svc = null;                 // the install service's last state
let progress = null;            // its last step event
const logLines = [];            // the service's log, for the Install and Log pages

function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function msg(text, kind) { const m = $('#msg'); if (m) { m.textContent = text; m.className = 'msg' + (kind ? ' ' + kind : ''); } }

function show(name) {
    current = name;
    document.querySelectorAll('nav button').forEach(b => b.classList.toggle('on', b.dataset.page === name));
    ({ play: renderPlay, install: renderInstall, settings: renderSettings, textures: renderTextures, log: renderLog })[name]();
}
window.show = show;
document.querySelectorAll('nav button').forEach(b => b.addEventListener('click', () => show(b.dataset.page)));

// ---- Play
async function renderPlay() {
    const st = await L.call('state');
    const busy = svc && svc.busy;
    page.innerHTML = `
      <h2>MotorStorm: Pacific Rift</h2>
      <p class="lead">The PC build of your own copy of the game, made on this PC. Settings are read when it starts.</p>
      <div class="card">
        <h3>${st.installed ? 'Ready' : busy ? 'Installing...' : 'Not installed yet'}</h3>
        <p class="stat">${st.installed ? esc(st.dir) : 'Install it from your disc on the Install page.'}</p>
        <div class="btns">
          <button class="act" id="play" ${st.installed && !st.playing && !busy ? '' : 'disabled'}>Play</button>
          <button class="ghost" id="stop" ${st.playing ? '' : 'disabled'}>Stop the game</button>
          <button class="ghost" id="folder">Open the game folder</button>
          ${st.installed ? '' : '<button class="ghost" id="goinstall">Install...</button>'}
        </div>
        <div class="msg" id="msg"></div>
      </div>`;
    $('#play').onclick = async () => { const r = await L.call('game:play'); if (!r.ok) msg(r.message, 'bad'); };
    $('#stop').onclick = () => L.call('game:stop');
    $('#folder').onclick = () => L.call('open', 'folder');
    if ($('#goinstall')) $('#goinstall').onclick = () => show('install');
    game = { running: st.playing };
}
L.on('game', g => { game = g; if (current === 'play') renderPlay(); });

// ---- Install: the player's disc, the 1.03 update folder, their decrypted EBOOT.elf files, then the build
function statusOf(item, okText, emptyText) {
    if (!item || !item.path) return `<span class="status wait">${esc(emptyText)}</span>`;
    if (item.checking) return '<span class="status wait">Checking...</span>';
    if (item.ok) return `<span class="status ok">${esc(okText(item))}</span>`;
    return `<span class="status bad">${esc(item.error || 'Not usable')}</span>`;
}

async function renderInstall() {
    const st = await L.call('state');
    const s = svc || {};
    const busy = !!s.busy;
    const ready = s.disc && s.disc.ok && s.update && s.update.ok && s.elf100 && s.elf100.ok && s.elf103 && s.elf103.ok;
    const steps = (s.steps || []).map(x => `<li class="${x.done ? 'done' : x.id === s.stepId ? 'now' : ''}">${esc(x.title)}</li>`).join('');
    const elfRow = (which, label, item) => `
          <div class="fine">${label}</div>
          <div>${statusOf(item, () => 'Found, and it is the right file', 'Choose the decrypted EBOOT.elf')}</div>
          <div class="path">${esc(item && item.path)}</div>
          <div class="btns"><button class="ghost small" id="pick-elf${which}" ${busy ? 'disabled' : ''}>EBOOT.elf...</button></div>`;
    page.innerHTML = `
      <h2>Install</h2>
      <p class="lead">The game is built on this PC from your own disc and your own console's files: nothing of the game is
      downloaded or carried by this launcher. The launcher does not decrypt anything: you supply the decrypted program files
      (EBOOT.elf) of the disc and of the 1.03 update, made from your own console. It checks them by their hashes, translates
      them to PC code, downloads the build tools (each checked by its SHA-256) and builds. The first install takes 30 to 90 minutes.</p>
      <div class="grid">
        <div class="card">
          <h3><span class="num">01</span>Your game disc</h3>
          <div>${statusOf(s.disc, d => `${d.title || 'MotorStorm: Pacific Rift'} (${d.titleId}), ${d.release}`, 'Choose your disc image or its copied folder')}</div>
          <div class="path">${esc(s.disc && s.disc.path)}</div>
          <div class="btns">
            <button class="ghost small" id="pick-iso" ${busy ? 'disabled' : ''}>Disc image (.iso)...</button>
            <button class="ghost small" id="pick-folder" ${busy ? 'disabled' : ''}>Folder with PS3_GAME...</button>
          </div>
        </div>
        <div class="card">
          <h3><span class="num">02</span>The 1.03 update</h3>
          <div>${statusOf(s.update, u => `Update ${u.version || '1.03'} data found`, 'Choose the update folder (the one with USRDIR\\ms2patch.psarc)')}</div>
          <div class="path">${esc(s.update && s.update.path)}</div>
          <div class="btns"><button class="ghost small" id="pick-update" ${busy ? 'disabled' : ''}>Update folder...</button></div>
        </div>
        <div class="card">
          <h3><span class="num">03</span>Your decrypted EBOOT.elf files</h3>
          <p class="fine">Each is the program of one release, decrypted from your own console (the launcher does not do it).
          The file stays where it is: it is read at the build and by the game, never copied elsewhere or sent anywhere.</p>
          ${elfRow(100, 'The disc (1.00): also holds the job module the build needs', s.elf100)}
          ${elfRow(103, 'The 1.03 update: the program the game runs', s.elf103)}
        </div>
        <div class="card">
          <h3><span class="num">04</span>${s.built ? 'Installed' : 'Build'}</h3>
          <div class="fine">${esc(s.plan || '')}</div>
          <label class="check"><input type="checkbox" id="agree" ${s.agreed ? 'checked' : ''} ${busy ? 'disabled' : ''}>
            <span>I accept the license terms of Microsoft's C++ libraries and Windows SDK, which the build downloads from Microsoft
            (<a href="#" id="lic">read them</a>).</span></label>
          <div id="prog" ${busy || progress ? '' : 'hidden'}>
            <div id="step" class="status">${esc(progress && progress.step || '')}</div>
            <div class="bar ${progress && progress.fraction >= 0 ? '' : 'indet'}"><div id="fill" style="width:${progress && progress.fraction >= 0 ? Math.round(progress.fraction * 100) : 0}%"></div></div>
            <div id="detail" class="fine">${esc(progress && progress.detail || '')}</div>
          </div>
          <div class="msg" id="msg"></div>
          <div class="btns">
            <button class="act" id="install" ${busy || !ready || game.running ? 'disabled' : ''}>${s.built ? 'Build again' : 'Install'}</button>
            <button class="ghost" id="stop" ${busy ? '' : 'hidden'}>Stop</button>
            <button class="ghost" id="clean" ${busy ? 'disabled' : ''} title="Removes the build and the translated code. Keeps your EBOOT.elf files (they are not copied), the the build tools, the game files, your settings and HD textures.">Start over</button>
          </div>
        </div>
      </div>
      <div class="card"><h3>Steps</h3><ul class="steps">${steps}</ul></div>
      <pre class="log" id="log">${esc(logLines.slice(-300).join('\n'))}</pre>
      ${st.dev ? `<div class="card dev"><h3>Developer only</h3>
        <p class="fine">Copies a game already built elsewhere (it contains the translated game code: never for distribution).</p>
        <button class="ghost small" id="devinstall">Install from a built folder...</button></div>` : ''}`;
    const logEl = $('#log');
    logEl.scrollTop = logEl.scrollHeight;
    const pick = async (kind, key) => {
        const p = await L.call('pick', kind);
        if (p) L.command({ cmd: 'set', [key]: p });
    };
    $('#pick-iso').onclick = () => pick('iso', 'disc');
    $('#pick-folder').onclick = () => pick('folder', 'disc');
    $('#pick-update').onclick = () => pick('update', 'update');
    $('#pick-elf100').onclick = () => pick('elf', 'elf100');
    $('#pick-elf103').onclick = () => pick('elf', 'elf103');
    $('#lic').onclick = e => { e.preventDefault(); window.open('https://visualstudio.microsoft.com/license-terms/'); };
    $('#agree').onchange = e => L.command({ cmd: 'set', agreed: e.target.checked });
    $('#install').onclick = () => {
        if (!$('#agree').checked) { msg('Accept the license terms first: the build needs Microsoft\'s C++ libraries.', 'bad'); return; }
        progress = { step: 'Starting', fraction: -1 };
        L.command({ cmd: 'install', agreed: true });
    };
    $('#stop').onclick = () => L.command({ cmd: 'cancel' });
    $('#clean').onclick = () => { if (confirm('Remove the build and the translated code? The tools, your game files and your EBOOT.elf files stay.')) L.command({ cmd: 'clean', what: 'build' }); };
    if ($('#devinstall')) $('#devinstall').onclick = async () => {
        const r = await L.call('dev:install');
        msg(r.ok ? `Installed (${r.copied.length} files).` : r.message, r.ok ? 'good' : 'bad');
    };
    if (s.message) msg(s.message, s.ok === false ? 'bad' : 'good');
}

// ---- the service's events
let redraw = null;
L.on('svc', ev => {
    if (ev.ev === 'state') {
        svc = ev;
        if (!ev.busy && !ev.keepProgress) progress = null;
        if (current === 'install' || current === 'play') { clearTimeout(redraw); redraw = setTimeout(() => show(current), 50); }
        foot();
    } else if (ev.ev === 'step') {
        progress = ev;
        if (current === 'install' && $('#prog')) {
            $('#prog').hidden = false;
            $('#step').textContent = ev.step || '';
            $('#detail').textContent = ev.detail || '';
            const bar = $('#fill').parentElement;
            bar.classList.toggle('indet', !(ev.fraction >= 0));
            $('#fill').style.width = ev.fraction >= 0 ? Math.round(ev.fraction * 100) + '%' : '0';
        }
    } else if (ev.ev === 'log' || ev.ev === 'error' || ev.ev === 'done') {
        const line = ev.ev === 'log' ? ev.line : ev.message;
        if (line == null) return;
        logLines.push(line);
        if (logLines.length > 5000) logLines.splice(0, 1000);
        const el = $('#log');
        if (el && (current === 'install' || current === 'log')) {
            const atEnd = el.scrollTop + el.clientHeight >= el.scrollHeight - 30;
            el.textContent += (el.textContent ? '\n' : '') + line;
            if (atEnd) el.scrollTop = el.scrollHeight;
        }
        if (ev.ev !== 'log' && current === 'install') msg(ev.message, ev.ev === 'error' || ev.ok === false ? 'bad' : 'good');
    }
});
function foot() {
    const f = $('#nav-foot');
    if (!f || !svc) return;
    f.textContent = svc.busy ? (progress && progress.step) || 'Installing...' : svc.built ? 'Game installed' : '';
}

// ---- Settings
const NOTES = {
    resolution: 'The internal resolution the game is drawn at', dynres: 'Off keeps the resolution steady (the game\'s own drops are suppressed)',
    framerate: 'Variable: the game runs as fast as your PC allows', fsrmode: 'FSR 3.1 is sharper (temporal); FSR 1 is the safest',
    hdr: 'Needs an HDR display', aniso: 'Sharper textures at an angle', rtshadow: 'Needs a GPU with ray tracing (Vulkan ray queries)',
};
async function renderSettings() {
    const s = await L.call('settings:load');
    const v = s.values;
    const select = item => {
        const opts = item.choices.map(c => `<option value="${esc(c)}" ${v[item.key] === c ? 'selected' : ''}>${esc(c)}</option>`).join('');
        const miss = s.missing[item.key];
        const note = [NOTES[item.key], miss ? `Not on this PC yet: ${miss}` : ''].filter(Boolean).join('. ');
        return `<div class="row"><label>${esc(item.label)}<small>${esc(note)}</small></label><select data-key="${item.key}">${opts}</select></div>`;
    };
    const group = g => s.schema.filter(x => x.group === g).map(select).join('');
    const keyRow = ([a]) => `<div class="row"><label>${esc(a)}</label><input type="text" data-action="${a}" value="${esc(s.keys[a])}"></div>`;
    page.innerHTML = `
      <h2>Settings</h2>
      <p class="lead">Saved to settings.ini beside the game, the same file as the game's own Options &gt; PC Settings
      page${s.pcmenu ? '' : ' (that page appears once the install has made it)'}. The game must be closed to change them here.</p>
      <div class="grid">
        <div class="card"><h3>Display</h3>${group('Display')}</div>
        <div class="card"><h3>Upscaling</h3>${group('Upscaling')}</div>
      </div>
      <div class="card" style="margin-top:16px"><h3>Graphics</h3>${group('Graphics')}</div>
      <div class="card">
        <h3>Keyboard controls</h3>
        <p class="fine">Used when no controller is plugged in. One or two keys each, e.g. "W, 2": letters, digits, F1-F24, Num0-Num9,
        Space, Enter, Tab, Ctrl, Shift, arrows, PageUp ... (Esc, Alt and the mouse cannot be bound). The arrows also move in
        the menus. You can also change them in the game: Options &gt; PC Settings.</p>
        <div class="grid">${s.actions.map(keyRow).join('')}</div>
      </div>
      <div class="card">
        <h3>Game files</h3>
        <div class="row"><label>Disc files folder<small id="files-path">Set by the install. Change it only to read the game's files (PS3_GAME) from another folder.</small></label>
          <button class="ghost" id="pick">Choose</button><button class="ghost" id="reset">Use the install's</button></div>
        <button class="act" id="save" ${game.running ? 'disabled' : ''}>Save settings</button>
        <div class="msg" id="msg"></div>
      </div>`;
    let files = null, clearFiles = false;
    $('#save').onclick = async () => {
        const values = {}, keys = {};
        document.querySelectorAll('select[data-key]').forEach(el => { values[el.dataset.key] = el.value; });
        document.querySelectorAll('input[data-action]').forEach(el => { keys[el.dataset.action] = el.value; });
        const patch = { values, keys };
        if (files) patch.files = files;
        if (clearFiles) patch.clearFiles = true;
        const r = await L.call('settings:save', patch);
        msg(r.ok ? 'Saved. The game reads them next time it starts.' : r.message, r.ok ? 'good' : 'bad');
    };
    $('#pick').onclick = async () => {
        const dir = await L.call('pick', 'files');
        if (dir) { files = dir; clearFiles = false; $('#files-path').textContent = dir; }
    };
    $('#reset').onclick = () => { files = null; clearFiles = true; $('#files-path').textContent = "The install's game files"; };
}

// ---- HD textures
async function renderTextures() {
    const t = await L.call('textures:info');
    page.innerHTML = `
      <h2>HD textures</h2>
      <p class="lead">The game saves each texture it draws, then an upscaler makes sharper versions (Real-ESRGAN) with
      optional physically based maps. Needs Python with numpy and Pillow, once.</p>
      <div class="card">
        <h3>Collect</h3>
        <p class="stat" id="dumped">${t.dumped} textures saved so far</p>
        <button class="act" id="collect" ${t.playing || t.collecting ? 'disabled' : ''}>${t.collecting ? 'Collecting... (stop it below)' : 'Start collecting'}</button>
        <div class="msg" id="msg"></div>
      </div>
      <div class="card">
        <h3>Make the pack</h3>
        <p class="stat">${t.pack} HD textures in the pack now (${esc(t.folder)})</p>
        <div class="row"><label>Size<small>4x is sharper; 2x is faster and uses less memory</small></label>
          <select id="scale"><option value="4">4x</option><option value="2">2x</option></select></div>
        <div class="row"><label>Physically based maps<small>Adds normal and roughness maps (slower)</small></label>
          <select id="pbr"><option value="0">Off</option><option value="1">On</option></select></div>
        <div class="btns">
          <button class="act" id="pack" ${t.making ? 'disabled' : ''}>Make the HD pack</button>
          <button class="ghost" id="stop">Stop</button>
          <button class="ghost" id="tfolder">Open the folder</button>
        </div>
        <pre class="log" id="tlog"></pre>
      </div>
      <p class="fine">The pack is made from your copy of the game: keep it to yourself, do not share it.</p>`;
    $('#collect').onclick = async () => {
        const r = await L.call('textures:collect');
        if (!r.ok) msg(r.message, 'bad'); else renderTextures();
    };
    $('#pack').onclick = async () => {
        $('#tlog').textContent = '';
        const r = await L.call('textures:pack', { scale: Number($('#scale').value), pbr: $('#pbr').value === '1' });
        if (!r.ok) msg(r.message, 'bad');
    };
    $('#stop').onclick = () => L.call('textures:stop');
    $('#tfolder').onclick = () => L.call('open', 'textures');
}
L.on('pack', p => {
    const log = $('#tlog');
    if (p.line && log) { log.textContent += p.line + '\n'; log.scrollTop = log.scrollHeight; }
    if (p.done && current === 'textures') renderTextures();
});

// ---- Log
function renderLog() {
    page.innerHTML = `
      <h2>Log</h2>
      <div class="btns" style="margin-bottom:12px"><button class="ghost small" id="openlog">Open launcher.log</button>
        <button class="ghost small" id="openroot">Open the MotorStorm folder</button></div>
      <pre class="log tall" id="log">${esc(logLines.join('\n'))}</pre>`;
    $('#log').scrollTop = $('#log').scrollHeight;
    $('#openlog').onclick = () => L.call('open', 'log');
    $('#openroot').onclick = () => L.call('open', 'root');
}

L.command({ cmd: 'state' });
show('play');
