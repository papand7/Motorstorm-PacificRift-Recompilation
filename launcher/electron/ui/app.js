// The launcher's pages. Each page is drawn from the launcher's state; actions go through window.launcher.
const $ = (sel, el = document) => el.querySelector(sel);
const page = $('#page');
const L = window.launcher;
let current = 'play';
let game = { running: false };
let svc = null;                 // the install service's last state
let progress = null;            // its last step event
const logLines = [];            // the service's log, for the Install and Log pages
// The log box is redrawn at most once a frame from the newest lines, never grown line by line: appending to its
// text made every line cost more than the last, and a build's flood of lines then stalled the install itself.
// an install that stopped part-way: a step past the quick checks is done, so Install carries on from there
const resumable = s => !s.built && (s.steps || []).some(x => x.done && !['game', 'elf', 'files'].includes(x.id));
let logPaint = 0;
function scheduleLogPaint() {
    if (logPaint) return;
    logPaint = requestAnimationFrame(() => {
        logPaint = 0;
        const el = $('#log');
        if (!el) return;
        const atEnd = el.scrollTop + el.clientHeight >= el.scrollHeight - 30;
        el.textContent = logLines.slice(current === 'log' ? -2000 : -300).join('\n');
        if (atEnd) el.scrollTop = el.scrollHeight;
    });
}

function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function msg(text, kind) { const m = $('#msg'); if (m) { m.textContent = text; m.className = 'msg' + (kind ? ' ' + kind : ''); } }

function show(name) {
    current = name;
    document.querySelectorAll('nav button').forEach(b => b.classList.toggle('on', b.dataset.page === name));
    ({ play: renderPlay, install: renderInstall, settings: renderSettings, textures: renderTextures, benchmark: renderBenchmark,
       cheats: renderCheats, log: renderLog })[name]();
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
          ${st.playing ? '<button class="ghost" id="stop">Stop the game</button>' : ''}
          <button class="ghost" id="folder">Open the game folder</button>
          ${st.installed ? '' : '<button class="ghost" id="goinstall">Install...</button>'}
        </div>
        <div class="msg" id="msg"></div>
      </div>
      <div class="card" id="saves"></div>`;
    $('#play').onclick = async () => { const r = await L.call('game:play', 'stable'); if (!r.ok) msg(r.message, 'bad'); };
    if ($('#stop')) $('#stop').onclick = () => L.call('game:stop');
    $('#folder').onclick = () => L.call('open', 'folder');
    if ($('#goinstall')) $('#goinstall').onclick = () => show('install');
    game = { running: st.playing };
    drawSaves(await L.call('saves:info'));
}
L.on('game', g => { game = g; if (current === 'play') renderPlay(); });

// ---- Saves (on the Play page): the game's save on this PC, Import save... (a PS3's save copied to USB, or RPCS3's),
// the backups an import or a restore keeps of the save it replaces
const KIND = { ps3: 'PS3 console', rpcs3: 'RPCS3', pc: 'PC' };
let saveMsg = null;   // { text, kind } shown under the card until the next action
function when(ms) { return ms ? new Date(ms).toLocaleString() : ''; }
function saveRow(s, extra) {
    const notes = [];
    if (s.region) notes.push(`${s.titleId}${s.suffix || ''} (${s.region})`);
    if (s.kind && s.titleId !== 'BLES00000') notes.push(KIND[s.kind] || s.kind);   // where it came from (not once it is the port's)
    if (s.profileVersion) notes.push(`profile ${s.profileVersion}${s.profileVersion === 'Beta 3' ? ' (updated game: converted for 1.00)' : ''}`);
    if (s.encrypted) notes.push(`encrypted: ${s.protected.join(', ')}`);
    return `<div class="row save">
      ${s.icon ? `<img class="saveicon" src="${esc(s.icon)}" alt="">` : '<div class="saveicon"></div>'}
      <label>${esc(s.title || s.dirName)}<small>${esc([s.subtitle, when(s.date)].filter(Boolean).join(' - '))}</small>
        <small>${esc(notes.join(' - '))}</small>
        ${s.problems && s.problems.length ? `<small class="status bad">${esc(s.problems.join('; '))}</small>` : ''}</label>
      ${extra || ''}</div>`;
}
function drawSaves(info) {
    const box = $('#saves');
    if (!box || !info) return;
    const busy = info.playing;
    const main = info.current.filter(s => !s.suffix);
    box.innerHTML = `
      <h3>Saves</h3>
      <p class="fine">Bring your progress from a PS3 (the save copied to a USB stick: PS3\\SAVEDATA) or from RPCS3
      (dev_hdd0\\home\\00000001\\savedata). Choose the save's folder or a folder above it; saves of other games are skipped.
      Any region's save works with your disc. The save you replace is kept as a backup.</p>
      ${main.length ? main.map(s => saveRow(s)).join('') : '<p class="stat">No save on this PC yet: the game makes one when you first play.</p>'}
      <div class="btns">
        <button class="act" id="save-import" ${busy ? 'disabled' : ''}>Import save...</button>
        <button class="ghost" id="save-folder">Open the saves folder</button>
        ${info.found.some(s => s.encrypted) ? `<button class="ghost" id="save-keys" ${busy ? 'disabled' : ''}>${info.keys ? 'Save tool folder chosen' : 'Choose your save tool folder...'}</button>` : ''}
      </div>
      ${info.found.length ? `<h3 style="margin-top:16px">Found</h3>${info.found.map((s, i) => saveRow(s,
          `<button class="ghost small" data-import="${i}" ${busy || (s.problems && s.problems.length) || (s.encrypted && !info.keys) ? 'disabled' : ''}>Import</button>`)).join('')}
          ${info.found.some(s => s.encrypted) ? `<p class="fine">A PS3 console's save is encrypted. The launcher carries no PS3 keys: choose the folder
          of your own save tool (pfdtool or Bruteforce Save Data, with its global.conf and games.conf) and it is decrypted
          while it is copied. The keys are only read, for this session.</p>` : ''}` : ''}
      ${info.backups.length ? `<details><summary>Backups (${info.backups.length})</summary>${info.backups.map(b => saveRow(b.save || { title: b.dir },
          `<span class="fine">${esc(b.reason)} ${esc(new Date(b.at).toLocaleString())}</span>
           <button class="ghost small" data-restore="${esc(b.name)}" ${busy ? 'disabled' : ''}>Restore</button>`)).join('')}</details>` : ''}
      <div class="msg${saveMsg ? ' ' + saveMsg.kind : ''}" id="save-msg">${esc(saveMsg ? saveMsg.text : '')}</div>`;
    saveMsg = null;
    const after = (r, okText) => {
        if (!r.ok) { if (r.message) saveMsg = { text: r.message, kind: 'bad' }; L.call('saves:info').then(drawSaves); return; }
        if (okText) saveMsg = { text: okText(r), kind: 'good' };
        drawSaves(r);
    };
    $('#save-import').onclick = async () => after(await L.call('saves:scan'),
        r => r.found.length ? `Found ${r.found.length} MotorStorm: Pacific Rift save${r.found.length > 1 ? 's' : ''}.`
                            : 'No MotorStorm: Pacific Rift save in that folder.');
    $('#save-folder').onclick = () => L.call('open', 'saves');
    if ($('#save-keys')) $('#save-keys').onclick = async () => after(await L.call('saves:keys'), () => 'Save tool folder read: encrypted saves can be imported now.');
    box.querySelectorAll('[data-import]').forEach(b => b.onclick = async () => {
        const s = info.found[Number(b.dataset.import)];
        const has = info.current.some(c => c.dirName === s.target);
        if (has && !confirm(`Replace the game's save on this PC with this one (${s.titleId}${s.suffix || ''}, ${when(s.date)})?\n\n` +
                            'The save it replaces is kept as a backup (Backups, Restore).')) return;
        after(await L.call('saves:import', Number(b.dataset.import)),
              r => `Imported as ${r.result.dir}${r.result.converted.length ? ` (${r.result.converted.join('; ')})` : ''}.` +
                   `${r.result.backup ? ' The save it replaced is in Backups.' : ''} Press Play: the game loads it when it starts.`);
    });
    box.querySelectorAll('[data-restore]').forEach(b => b.onclick = async () => {
        if (!confirm('Put this backup back? The save it replaces is kept as a backup too.')) return;
        after(await L.call('saves:restore', b.dataset.restore), r => `Restored ${r.result.dir}.`);
    });
}

// ---- Install: the player's disc, their decrypted EBOOT.elf files, then the build
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
    const ready = s.disc && s.disc.ok && s.elf100 && s.elf100.ok;
    const steps = (s.steps || []).map(x => `<li class="${x.done ? 'done' : x.id === s.stepId ? 'now' : ''}">${esc(x.title)}</li>`).join('');
    const elfRow = (which, label, item) => `
          <div class="fine">${label}</div>
          <div>${statusOf(item, () => 'Found, and it is the right file', 'Choose the decrypted EBOOT.elf')}</div>
          <div class="path">${esc(item && item.path)}</div>
          <div class="btns"><button class="ghost small" id="pick-elf${which}" ${busy ? 'disabled' : ''}>EBOOT.elf...</button>
            <button class="ghost small" id="auto-elf${which}" ${busy || !(s.disc && s.disc.ok) ? 'disabled' : ''}
              title="${s.disc && s.disc.ok ? 'Downloads RPCS3, decrypts the EBOOT.BIN of your disc with it, then deletes RPCS3 again' : 'Choose your game disc (step 01) first'}">Decrypt automatically...</button></div>`;
    page.innerHTML = `
      <h2>Install</h2>
      <p class="lead">The game is built on this PC from your own disc and your own console's files: nothing of the game is
      downloaded or carried by this launcher. You supply the decrypted program file (EBOOT.elf) of the disc, made from your
      own console, or let the launcher make it from your disc with RPCS3 (Decrypt automatically). It checks it by its hash, translates it to PC code,
      downloads the build tools (each checked by its SHA-256) and builds. The first install takes 30 to 90 minutes.</p>
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
          <h3><span class="num">02</span>Your decrypted EBOOT.elf files</h3>
          <p class="fine">The program of the disc, decrypted from your own console; or choose Decrypt automatically to have
          RPCS3 make it from your disc's EBOOT.BIN (it is downloaded for this and deleted afterwards). The file stays where
          it is: it is read at the build and by the game, never sent anywhere.</p>
          ${elfRow(100, 'The disc\'s program (1.00); also holds the job module the build needs. Required.', s.elf100)}
        </div>
        <div class="card">
          <h3><span class="num">03</span>${s.built ? 'Installed' : 'Build'}</h3>
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
            <button class="act" id="install" ${busy || !ready || game.running ? 'disabled' : ''}>${s.built ? 'Build again' : resumable(s) ? 'Resume install' : 'Install'}</button>
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
    $('#pick-elf100').onclick = () => pick('elf', 'elf100');
    $('#auto-elf100').onclick = () => {
        // nothing is downloaded before the player says yes here (the service also refuses without confirmed: true)
        if (!confirm('Decrypt automatically?\n\nThis downloads RPCS3, a third-party open-source PS3 emulator (GPL-2.0), ' +
                     'from its official source (github.com/RPCS3/rpcs3-binaries-win, about 40 MB). It is used only to decrypt ' +
                     'the EBOOT.BIN of your own disc (a copy; your disc files are not changed), and it is deleted afterwards ' +
                     'with everything it created. The result is checked by its SHA-256 and kept only if it is the right file.')) return;
        progress = { step: 'Starting', fraction: -1 };
        L.command({ cmd: 'autodecrypt', which: 100, confirmed: true });
    };
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
            // (painted from logLines, once a frame)
            scheduleLogPaint();

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
    framerate: '30 FPS is the original speed and the default; above 30 is experimental (camera, shadow and vehicle glitches)', lighting: 'Fidelity. Original is the game’s own look; Enhanced (experimental) adds new lighting, world-fixed shadows, AO and tone mapping', vsync: 'Off is tear-free and keeps 60 FPS steady', fsrmode: 'FSR 3.1 is sharper (temporal); FSR 1 is the safest',
    shadows: 'Off skips the game’s own shadows for slower machines. Reflections are not changed. Shown with Fidelity Original only',
    hdr: 'Needs an HDR display', framegen: 'Twice the frames shown (30 to 60); the real frame shows about 17 ms later at 30 FPS. Needs Upscaler FSR 3.1 with a quality on and HDR off. Light is cheap with more ghosting; On is AMD FSR 3.1 frame generation. Best with V-Sync Off on a VRR display; with V-Sync On keep twice the frame rate within the refresh rate', aniso: 'Sharper textures at an angle',
    prompts: 'Keys or controller buttons in the game’s prompts; Auto shows keys unless a gamepad or wheel is connected',
    wheelmode: 'Auto uses Thrustmaster and Logitech wheels; a gamepad keeps working', wheelrange: 'Wheel rotation, lock to lock, that gives full steering',
    wheelpedals: 'Combined: throttle and brake share one axis', wheelpedaldir: 'Auto reads the released pedals at start',
    wheelffb: 'Off by default. Centering spring and the game\'s rumble only; takes the wheel exclusively',
    lod: 'Lowest and Low draw scenery and trees a shorter way out (more pop-in), faster on small GPUs and CPUs',
    shadowq: 'Size and softness of the sun shadow map. Low: hard edges and no stored layer (288 MB less video memory)',
    texq: 'Half or Quarter: blurrier game textures and much less video memory. The HD texture pack is not changed',
    fxdensity: 'Fewer of the game\'s own particles (smoke, dust, spray). Minimal: no dust or mud from the wheels',
    oppdetail: 'Simpler models for the other cars and wrecks sooner (the game\'s own split-screen values)',
    drsfloor: 'How low the game\'s dynamic resolution may go when the frame rate falls. Only with Dynamic resolution On',
    debris: 'Off: no loose parts fly off wrecks, less physics work. Changes the gameplay feel (no debris to hit)',
    boostblur: 'The game\'s radial blur while boosting (motion blur is the Graphics setting)',
};
// The Low-end button (Performance card): fills the page for a handheld or integrated GPU (GPD with Ryzen AI 9 HX 370 /
// Radeon 890M class); nothing is saved until Save. Measured in generated/analysis/lowend_opts/RESULTS.md.
const LOW_END = {
    shadowq: 'Low', texq: 'Half', fxdensity: 'Low', oppdetail: 'Low', debris: 'Off', boostblur: 'Off',
    dynres: 'On', drsfloor: '40%', lod: 'Lowest', fxquality: 'Minimal', particles: 'Off', volfog: 'Off',
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
    // "Shadows" is a row only with Fidelity Original (the game's page hides it the same way,
    // pc_settings.h pcs_row_hidden). Not rendered otherwise, so a save does not post it and its stored value stays.
    const SHADOWS = s.schema.find(x => x.key === 'shadows');
    const shadowsRow = () => select(SHADOWS).replace('<div class="row">', '<div class="row" data-shadows>');
    const gfx = s.schema.filter(x => x.group === 'Graphics' && x.key !== 'shadows').map(item =>
        select(item) + (item.key === 'lighting' && v.lighting === 'Original' ? shadowsRow() : '')).join('');
    const keyRow = ([a]) => `<div class="row"><label>${esc(a)}</label><input type="text" data-action="${a}" value="${esc(s.keys[a])}"></div>`;
    page.innerHTML = `
      <h2>Settings</h2>
      <p class="lead">Saved to settings.ini beside the game, the same file as the game's own Options &gt; PC Settings
      page${s.pcmenu ? '' : ' (that page appears once the install has made it)'}. The game must be closed to change them here.</p>
      <div class="grid">
        <div class="card"><h3>Display</h3>${group('Display')}</div>
        <div class="card"><h3>Upscaling</h3>${group('Upscaling')}</div>
      </div>
      <div class="card" style="margin-top:16px"><h3>Graphics</h3>${gfx}</div>
      <div class="card"><h3>Performance</h3>
        <p class="fine">Lower quality for slower PCs, handhelds and integrated graphics. Every setting here is off (today's look)
        until you change it. Read when the game starts.</p>
        ${group('Performance')}
        <div class="btns"><button class="ghost small" id="lowend">Low-end preset</button></div>
        <p class="fine">The Low-end preset fills this page and a few Graphics and Display settings for a handheld or integrated
        GPU (Radeon 890M class): it turns Wreck debris off (a gameplay-feel change) and Dynamic resolution on. Nothing is saved
        until you press Save settings.</p></div>
      <div class="card"><h3>Racing wheel</h3>${group('Wheel')}
        <p class="fine">Thrustmaster T300RS and Logitech G25/G27/G29/DFGT are read through DirectInput, beside a gamepad. Axes, pedal calibration and
        button mapping are wheel.* lines in settings.ini: run wheel_probe (--calibrate) to get them. Not tested on real hardware yet.</p></div>
      <div class="card">
        <h3>Multiplayer</h3>
        <div class="row"><label>Player name<small>The name other players see in LAN play (on the PS3 it was your PSN online ID).
          3 to 16 letters, digits, - or _, starting with a letter. Empty: the game's default name.</small></label>
          <input type="text" id="player-name" maxlength="16" spellcheck="false" placeholder="PS3Player" value="${esc(s.playerName || '')}"></div>
        <div class="msg ${s.playerNameError ? 'bad' : ''}" id="player-msg">${esc(s.playerNameError || '')}</div>
        <p class="fine">Saved to settings.ini and read when the game starts. The game's own PC Settings page does not show it.</p>
      </div>
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
      </div>
      <div class="card" id="updates"></div>`;
    // Fidelity changed on the page: the shadows row appears with Original and goes with Enhanced; its unsaved pick is kept
    const lightingSel = document.querySelector('select[data-key="lighting"]');
    lightingSel.onchange = () => {
        const row = document.querySelector('[data-shadows]');
        if (row) v.shadows = row.querySelector('select').value;
        if (lightingSel.value === 'Original' && !row) lightingSel.closest('.row').insertAdjacentHTML('afterend', shadowsRow());
        else if (lightingSel.value !== 'Original' && row) row.remove();
    };
    // Low-end preset: only fills the selects (Save writes them); the Shadows row is not touched (Fidelity is left as it is)
    $('#lowend').onclick = () => {
        for (const [k, val] of Object.entries(LOW_END)) {
            const sel = document.querySelector(`select[data-key="${k}"]`);
            if (sel && [...sel.options].some(o => o.value === val)) sel.value = val;
        }
        msg('Low-end preset filled in. Press Save settings to keep it.', 'good');
    };
    // Player name: the same rules as settings.js checkPlayerName (it decides on save); told as it is typed
    const nameMsg = () => {
        const n = $('#player-name').value.trim(), m = $('#player-msg');
        const bad = n && !/^[A-Za-z][A-Za-z0-9_-]{2,15}$/.test(n);
        m.className = 'msg' + (bad ? ' bad' : '');
        m.textContent = bad ? '3 to 16 letters, digits, - or _, starting with a letter (no spaces or accents).' : '';
        return !bad;
    };
    $('#player-name').oninput = nameMsg;
    let files = null, clearFiles = false;
    $('#save').onclick = async () => {
        const values = {}, keys = {};
        document.querySelectorAll('select[data-key]').forEach(el => { values[el.dataset.key] = el.value; });
        document.querySelectorAll('input[data-action]').forEach(el => { keys[el.dataset.action] = el.value; });
        const patch = { values, keys, playerName: $('#player-name').value };
        if (!nameMsg()) { msg('Not saved: the player name is not valid (see Multiplayer).', 'bad'); return; }
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
    drawUpdates(await L.call('update:info'));
}

// ---- Launcher updates (on the Settings page; its own controls, not part of Save settings). The channel: Public
// (default; checked only on request) or Private (papand7/motorstorm-private-builds, pre-releases included, with the
// player's GitHub access token; also checked at start). The token goes from its field straight to the launcher,
// which keeps it encrypted by Windows; the page is only ever told whether one is stored, and the field is cleared.
let updateShown = null;   // the last check's result, for this card and the nav note
function updateText(r) { return r && r.status && r.status !== 'off' ? r.message || '' : ''; }
function noteUpdate(r) {
    updateShown = r;
    const n = $('#nav-update');
    if (!n) return;
    n.textContent = r && r.status === 'available' ? `Update ${r.update.version}` : r && r.status === 'bad-token' ? 'Update check: token problem' : r && r.status === 'no-token' ? 'Update check: no token' : '';
    n.onclick = () => show('settings');
}
function drawUpdates(info) {
    const el = $('#updates');
    if (!el) return;
    const priv = info.channel === 'private';
    const repoOf = id => (info.channels.find(c => c.id === id) || {}).repo || '';
    const last = updateShown || info.last;
    const lastKind = last && last.status === 'available' ? 'good' : last && ['bad-token', 'no-token', 'error'].includes(last.status) ? 'bad' : '';
    el.innerHTML = `
        <h3>Launcher updates</h3>
        <div class="row"><label>Update channel<small>Public: the public releases (${esc(repoOf('public'))}), checked when you press
          Check for updates. Private: the private builds (${esc(repoOf('private'))}), pre-releases included, checked at start
          too; needs a GitHub access token with read access to that repository.</small></label>
          <select id="upd-channel">${info.channels.map(c => `<option value="${esc(c.id)}" ${c.id === info.channel ? 'selected' : ''}>${esc(c.label)}</option>`).join('')}</select></div>
        ${priv ? `<div class="row"><label>GitHub access token<small>${info.hasToken ? 'A token is stored, encrypted by Windows for this account. Enter a new one to replace it.'
            : 'None stored. A fine-grained token with Contents: read on the private repository (or a classic token with repo).'}
          ${info.encryption ? '' : ' Windows cannot encrypt it here, so it cannot be stored.'}</small></label>
          <input type="password" id="upd-token" autocomplete="off" spellcheck="false" placeholder="${info.hasToken ? 'stored' : 'github_pat_...'}"></div>
        <div class="btns"><button class="ghost small" id="upd-save">Store token</button>
          ${info.hasToken ? '<button class="ghost small" id="upd-forget">Remove token</button>' : ''}</div>` : ''}
        <div class="btns"><button class="ghost" id="upd-check">Check for updates</button>
          ${last && last.status === 'available' ? '<button class="act" id="upd-open">Open the release page</button>' : ''}</div>
        <p class="fine">This launcher: ${esc(info.version)}. An update opens on GitHub in your browser; nothing is downloaded or replaced here.</p>
        <div class="msg ${lastKind}" id="upd-msg">${esc(updateText(last))}</div>`;
    const umsg = (text, kind) => { const m = $('#upd-msg'); m.textContent = text; m.className = 'msg' + (kind ? ' ' + kind : ''); };
    $('#upd-channel').onchange = async () => { noteUpdate(null); drawUpdates(await L.call('update:channel', $('#upd-channel').value)); };
    if ($('#upd-save')) $('#upd-save').onclick = async () => {
        const field = $('#upd-token'), token = field.value.trim();
        field.value = '';
        if (!token) { umsg('Enter the token first.', 'bad'); return; }
        const r = await L.call('update:token', token);
        noteUpdate(null);
        drawUpdates(r);
        umsg(r.ok ? 'Token stored (encrypted by Windows). Press Check for updates to try it.' : r.message, r.ok ? 'good' : 'bad');
    };
    if ($('#upd-forget')) $('#upd-forget').onclick = async () => { noteUpdate(null); drawUpdates(await L.call('update:forget')); umsg('Token removed.', 'good'); };
    $('#upd-check').onclick = async () => {
        umsg('Checking...');
        $('#upd-check').disabled = true;
        const r = await L.call('update:check', false);
        noteUpdate(r);
        if (current === 'settings') drawUpdates(await L.call('update:info'));
    };
    if ($('#upd-open')) $('#upd-open').onclick = async () => { const r = await L.call('update:open'); if (!r.ok) umsg(r.message, 'bad'); };
}

// ---- Cheats: switches saved to settings.ini like the Settings page (the game must be closed; it reads them at start)
const CHEAT_NOTES = {
    unlockvehicles: 'Every vehicle class and ticket counts as unlocked.',
    unlocktracks: 'Every track appears in the Free Play track list. The Festival and Time Trial lists are not covered yet.',
};
async function renderCheats() {
    const s = await L.call('settings:load');
    game = { running: (await L.call('state')).playing };   // fresh: a stale flag kept Save greyed out after the game closed
    const rows = s.schema.filter(x => x.group === 'Cheats');
    const sw = item => `
        <label class="check"><input type="checkbox" data-cheat="${item.key}" ${s.values[item.key] === 'On' ? 'checked' : ''}>
          <span><b>${esc(item.label)}</b><br>${esc(CHEAT_NOTES[item.key] || '')}</span></label>`;
    page.innerHTML = `
      <h2>Cheats</h2>
      <p class="lead">Changes what this copy of the game treats as unlocked. Off is the normal game. These switches never
      change your progress or your saves: while one is on, the game's unlock checks answer "unlocked"; turn it off and the
      next start is the normal game again.</p>
      <div class="card">
        ${rows.map(sw).join('')}
        <p class="fine">Takes effect when the game next starts. Not tested in the game yet.</p>
        <button class="act" id="save-cheats" ${game.running ? 'disabled' : ''}>Save</button>
        ${game.running ? '<p class="fine">The game is running: close it to change these.</p>' : ''}
        <div class="msg" id="msg"></div>
      </div>`;
    $('#save-cheats').onclick = async () => {
        const values = {};
        document.querySelectorAll('input[data-cheat]').forEach(el => { values[el.dataset.cheat] = el.checked ? 'On' : 'Off'; });
        const r = await L.call('settings:save', { values, keys: {} });
        msg(r.ok ? 'Saved. The game reads it next time it starts.' : r.message, r.ok ? 'good' : 'bad');
    };
}

// ---- HD textures
async function renderTextures() {
    const t = await L.call('textures:info');
    if (t.packOpts) packChoice = { ...t.packOpts };   // the running (or last) job's choice, so a redraw keeps it
    page.innerHTML = `
      <h2>HD textures</h2>
      <p class="lead">The game saves each texture it draws, then an upscaler makes sharper versions (Real-ESRGAN) with
      optional physically based maps. The first time, the launcher downloads what this needs into its own tools folder
      (numpy, Pillow and Real-ESRGAN, about 65 MB, more if Python is not there yet); after that it works offline.</p>
      <div class="card">
        <h3>Collect all textures</h3>
        <p class="stat" id="dumped">${t.dumped} textures saved so far</p>
        <p class="fine">Saves every texture of the game from your own game archive, without playing a race (about a minute;
        the game is not started). The files stay on this PC, in ${esc(t.folder.replace(/pack$/, 'dump'))}.</p>
        <button class="act" id="collectall" ${t.playing || t.collecting || t.collectingAll ? 'disabled' : ''}>${t.collectingAll ? 'Collecting...' : 'Collect all textures'}</button>
        <div class="msg" id="msg"></div>
      </div>
      <div class="card">
        <h3>Collect while playing</h3>
        <p class="fine">The fallback for the few textures the game builds while it runs: play with this on and each one is saved the first time it is drawn.</p>
        <button class="ghost" id="collect" ${t.playing || t.collecting ? 'disabled' : ''}>${t.collecting ? 'Collecting... (stop it below)' : 'Start collecting'}</button>
      </div>
      <div class="card">
        <h3>Make the pack</h3>
        <p class="stat">${t.pack} HD textures in the pack now (${esc(t.folder)})</p>
        <p class="fine">The full set (about ${t.dumped || 6000} textures) takes many hours to upscale: about 9 seconds per texture at 2x on the test PC.
        You can stop and run it again; finished textures are kept.</p>
        <div class="row"><label>Size<small>2x is the default: faster and uses less memory. 4x is sharper but slower: use it only for a smaller set</small></label>
          <select id="scale"><option value="2"${packChoice.scale === 4 ? '' : ' selected'}>2x</option><option value="4"${packChoice.scale === 4 ? ' selected' : ''}>4x (a smaller set)</option></select></div>
        <div class="row"><label>Physically based maps<small>Adds normal and roughness maps (slower)</small></label>
          <select id="pbr"><option value="0">Off</option><option value="1"${packChoice.pbr ? ' selected' : ''}>On</option></select></div>
        <div class="btns">
          <button class="act" id="pack" ${t.making ? 'disabled' : ''}>${t.making ? 'Making the pack...' : 'Make the HD pack'}</button>
          <button class="ghost" id="stop">Stop</button>
          <button class="ghost" id="tfolder">Open the folder</button>
        </div>
        <div class="stat" id="tprog">${t.making ? esc(tprog || 'Starting: reading the dumped textures...') : ''}</div>
        <progress id="tbar" max="100" value="${tpct}" style="width:100%;${t.making ? '' : 'display:none'}"></progress>
        <pre class="log" id="tlog">${esc(tlogLines.join('\n'))}</pre>
      </div>
      <p class="fine">The pack is made from your copy of the game: keep it to yourself, do not share it.</p>`;
    $('#collectall').onclick = async () => {
        tlogLines.length = 0;
        const r = await L.call('textures:collectall');
        if (!r.ok) msg(r.message, 'bad'); else renderTextures();
    };
    $('#collect').onclick = async () => {
        const r = await L.call('textures:collect');
        if (!r.ok) msg(r.message, 'bad'); else renderTextures();
    };
    $('#scale').onchange = () => { packChoice.scale = Number($('#scale').value); };
    $('#pbr').onchange = () => { packChoice.pbr = $('#pbr').value === '1'; };
    $('#pack').onclick = async () => {
        tlogLines.length = 0;
        $('#tlog').textContent = '';
        packChoice = { scale: Number($('#scale').value), pbr: $('#pbr').value === '1' };
        const r = await L.call('textures:pack', packChoice);
        if (!r.ok) msg(r.message, 'bad'); else renderTextures();
    };
    $('#stop').onclick = () => L.call('textures:stop');
    $('#tfolder').onclick = () => L.call('open', 'textures');
}
let packChoice = { scale: 2, pbr: false };   // the pack's Size / PBR choice: the page redraws when a job starts or ends
const tlogLines = [];   // the texture jobs' output, kept so the totals stay on screen after the page redraws
let tprog = '', tpct = 0;   // the HD pack's progress line and percent (texpack.py prints "PROGRESS n/total ...")
L.on('pack', p => {
    const m = p.line && /^PROGRESS (\d+)\/(\d+)\s*(.*)$/.exec(p.line);
    if (m) {
        tpct = m[2] > 0 ? Math.round(100 * m[1] / m[2]) : 0;
        tprog = `${m[1]} of ${m[2]} textures (${tpct}%) ${m[3]}`;
        if ($('#tprog')) $('#tprog').textContent = tprog;
        if ($('#tbar')) { $('#tbar').value = tpct; $('#tbar').style.display = ''; }
        return;
    }
    if (p.done) { tprog = ''; tpct = 0; }
    if (p.line) { tlogLines.push(p.line); if (tlogLines.length > 400) tlogLines.splice(0, 100); }
    const log = $('#tlog');
    if (p.line && log) { log.textContent += p.line + '\n'; log.scrollTop = log.scrollHeight; }
    if (p.done && current === 'textures') renderTextures();
});

// ---- Benchmark: the game runs it with the player's settings, measures it itself, quits, and this page shows its result
const BENCH_ABOUT = {
    fly: 'The game\'s own benchmark on two maps, one after the other: a camera flight over Happy Jungle, then one over the lava ' +
         'track Wildfire, no cars. The game starts once for each map. Only the flights are measured; the still views the game ' +
         'shows after them are not. A few minutes in all.',
    race: 'A 16-car race on Kanaloa Bay. The game\'s own AI drives every car, yours included. 90 seconds of racing are measured, ' +
          'from about 20 seconds after the start. About two and a half minutes in all. Crashes differ from run to run, so its ' +
          'results vary a little more than the fly-through\'s.',
};
let benchShown = null;   // the benchmark whose result is on screen (the one that just ended, else the last picked)
const fmt = (x, d = 0) => (typeof x === 'number' && isFinite(x) ? x.toFixed(d) : '-');
function gb(bytes) { return bytes > 0 ? `${(bytes / 1024 ** 3).toFixed(bytes >= 10 * 1024 ** 3 ? 0 : 1)} GB` : '-'; }
function benchResultCard(mode, r, info) {
    const title = info.modes[mode].title;
    const when = r.at ? new Date(r.at).toLocaleString() : '';
    // GPU, CPU and RAM as the game reported them (the GPU it rendered on); the launcher's view only if the game named none
    const sys = [['GPU', r.gpu || 'not reported by the game'], ['CPU', r.cpu || info.host.cpu || '-'],
                 ['Total RAM', gb(r.ram_bytes || info.host.ram_bytes)]];
    const sysRows = sys.map(([k, v]) => `<div class="kv"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('');
    const maps = Array.isArray(r.maps) ? r.maps : null;   // fly: each map's own result, then the combined one
    const tile = (label, v, d) => `<div class="tile"><div class="v">${fmt(v, d)}</div><div class="l">${esc(label)}</div></div>`;
    const numbers = (x, lows) => `
        <div class="tiles">${tile('Min FPS', x.fps.min)}${tile('Max FPS', x.fps.max)}${tile('Average FPS', x.fps.avg, 1)}</div>
        ${lows ? `<div class="kv"><span>1 % low</span><b>${fmt(x.fps.low1, 1)} FPS</b></div>
        <div class="kv"><span>0.1 % low</span><b>${fmt(x.fps.low01, 1)} FPS</b></div>` : ''}
        <div class="kv"><span>Measured</span><b>${fmt(x.seconds, 1)} s, ${esc(x.frames)} frames</b></div>`;
    if (!r.ok && !(maps && maps.some(m => m.ok))) return `
      <div class="card result bad">
        <h3>${esc(title)}: no result <span class="when">${esc(when)}</span></h3>
        ${sysRows}
        ${maps ? maps.map(m => `<p class="msg bad">${esc(m.map_name || m.map)}: ${esc(m.error || 'no result')}</p>`).join('')
               : `<p class="msg bad">${esc(r.error || 'The benchmark did not finish.')}</p>`}
      </div>`;
    const set = (r.settings || []).map(x => `<div class="kv${x.applied === false ? ' off' : ''}"><span>${esc(x.name)}</span>` +
        `<b>${esc(x.value)}${x.applied === false ? ' (not used with this Fidelity)' : ''}</b></div>`).join('');
    const body = !maps ? numbers(r, true) : maps.map((m, i) => `
        <h4 class="benchmap">Map ${i + 1}/${maps.length}: ${esc(m.map_name || m.map)}</h4>
        ${m.ok ? numbers(m, true) : `<p class="msg bad">No result: ${esc(m.error || 'the run did not finish.')}</p>`}`).join('') + `
        <h4 class="benchmap">Combined: ${esc(maps.map(m => m.map_name || m.map).join(' + '))}</h4>
        ${r.ok ? numbers(r, false) + `<p class="fine">Average: all measured frames of both maps over their measured time. Min: the
        lower of the maps' Min, Max: the higher of their Max.</p>`
               : '<p class="msg bad">No combined result: a map has no result.</p>'}`;
    return `
      <div class="card result${r.ok ? '' : ' bad'}">
        <h3>${esc(title)}: ${r.ok ? 'result' : 'partial result'} <span class="when">${esc(when)}</span></h3>
        ${sysRows}
        ${body}
        <div class="kv"><span>Benchmark</span><b>${esc(title)}</b></div>
        ${r.pipelines_built > 0 ? `<p class="msg bad">The game built ${esc(r.pipelines_built)} shader pipelines while it was measured
        (${fmt((r.pipelines_ms || 0) / 1000, 1)} s): the first run of a benchmark on this PC compiles them, and the stutter
        lowers Min and the lows. The game keeps them, so run it again for a steady result.</p>` : ''}
        <p class="fine">Frames are the game's own finished frames. Min and max: the slowest and the fastest whole second of the
        measured part. 1 % low: the average of the slowest 1 % of frames, as frames per second.</p>
        <details open><summary>Settings used</summary><div class="settings-used">${set || '<p class="fine">Not reported.</p>'}</div></details>
      </div>`;
}
async function renderBenchmark() {
    const info = await L.call('bench:info');
    const busy = info.playing || !info.installed;
    const card = mode => `
        <div class="card">
          <h3>${esc(info.modes[mode].title)}</h3>
          <p class="fine">${esc(BENCH_ABOUT[mode])}</p>
          <div class="btns">
            <button class="act" data-bench="${mode}" ${busy ? 'disabled' : ''}>${info.running === mode ? 'Running...' : 'Run'}</button>
            ${info.results[mode] ? `<button class="ghost small" data-showbench="${mode}">Last result</button>` : ''}
          </div>
        </div>`;
    if (!benchShown || !info.results[benchShown]) benchShown = Object.keys(info.results).find(m => info.results[m]) || null;
    page.innerHTML = `
      <h2>Benchmark</h2>
      <p class="lead">Runs the game with your current settings (the Settings page, settings.ini), measures it and closes it
      by itself, then shows the result here. Nothing is changed in your settings. Leave the game window in front and the PC
      alone while it runs.</p>
      ${info.running ? `<div class="card"><h3>Running: ${esc(info.modes[info.running].title)}${info.step && info.step.count > 1
          ? `, map ${esc(info.step.index + 1)}/${esc(info.step.count)}: ${esc(info.step.map || '')}` : ''}</h3>
        ${info.step && info.step.retry ? '<p class="fine">The game stopped at start-up; started once more.</p>' : ''}
        <p class="fine">The game closes by itself when the measurement is done${info.step && info.step.count > 1
          ? ', then starts again for the next map. Stop ends all maps' : ''}.</p>
        <button class="ghost" id="benchstop">Stop</button></div>` : ''}
      <div class="grid">${card('fly')}${card('race')}</div>
      ${!info.installed ? '<p class="fine" style="margin-top:12px">Install the game first (Install page).</p>' : ''}
      <div id="benchresult" style="margin-top:16px">${benchShown && !info.running ? benchResultCard(benchShown, info.results[benchShown], info) : ''}</div>
      <div class="msg" id="msg"></div>`;
    document.querySelectorAll('[data-bench]').forEach(b => b.onclick = async () => {
        const r = await L.call('bench:run', b.dataset.bench);
        if (!r.ok) msg(r.message, 'bad'); else renderBenchmark();
    });
    document.querySelectorAll('[data-showbench]').forEach(b => b.onclick = () => { benchShown = b.dataset.showbench; renderBenchmark(); });
    if ($('#benchstop')) $('#benchstop').onclick = () => L.call('game:stop');
}
L.on('bench', ev => {
    if (ev.result) benchShown = ev.mode;   // the run just ended: its result on screen
    if (ev.result && current !== 'benchmark') show('benchmark');
    else if (current === 'benchmark') renderBenchmark();
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
L.call('update:check', true).then(r => { if (r && r.status !== 'off') noteUpdate(r); }).catch(() => {});
