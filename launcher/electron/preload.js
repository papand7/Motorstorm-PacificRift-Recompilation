// The page's only way to the launcher: named calls to main.js, commands to the install service, and named events
// back. Nothing else of Node is exposed.
const { contextBridge, ipcRenderer } = require('electron');

const CHANNELS = ['state', 'dev:install', 'settings:load', 'settings:save', 'textures:info', 'textures:collect', 'textures:collectall',
                  'textures:pack', 'textures:stop', 'game:play', 'game:stop', 'pick', 'open', 'bench:info', 'bench:run'];
const EVENTS = ['game', 'pack', 'svc', 'bench'];

contextBridge.exposeInMainWorld('launcher', {
    call: (channel, ...args) => {
        if (!CHANNELS.includes(channel)) throw new Error('unknown call ' + channel);
        return ipcRenderer.invoke(channel, ...args);
    },
    command: cmd => ipcRenderer.send('svc', cmd),
    on: (channel, fn) => {
        if (!EVENTS.includes(channel)) throw new Error('unknown event ' + channel);
        ipcRenderer.on(channel, (_, data) => fn(data));
    },
});
