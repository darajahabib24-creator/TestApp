# MiniCode IDE — VS Code-style workbench (Electron + TypeScript)

Desktop: Electron (main process = Node backend, renderer = workbench UI, preload = typed IPC bridge).
Android: same workbench wrapped with Capacitor (planned).

## Layout (Phase 1)
```
ide-clone/
├── package.json
├── tsconfig.json          # renderer (browser) config
├── tsconfig.node.json     # main + preload (CJS, Node) config
├── vite.config.ts         # renderer bundler
├── index.html
├── electron/              # MAIN PROCESS (Node: fs, node-pty…)
│   ├── main.ts            # app lifecycle + BrowserWindow
│   ├── preload.ts         # contextBridge: typed window.minicode API
│   └── services/fs.ts     # filesystem backend service
└── src/                   # RENDERER
    ├── main.ts            # workbench shell entry
    └── global.d.ts        # typed window.minicode
```

## Run
```bash
cd ide-clone
npm install
npm run dev        # starts vite + electron
npm run typecheck  # strict TS check (main + renderer)
```
