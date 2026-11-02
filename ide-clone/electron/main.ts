import path from "node:path";
import { fileURLToPath } from "node:url";
import { app, BrowserWindow, ipcMain } from "electron";

import { Channels, type AppInfo, type DirEntry } from "./ipc/channels.js";
import { FsService } from "./services/fs.js";

const __dirname2 = path.dirname(fileURLToPath(import.meta.url));

// WHY: single source of truth — every window is created from this factory so
// security options (contextIsolation, no nodeIntegration) are never missed.
const createWindow = (devUrl: string | null): void => {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 720,
    minHeight: 480,
    backgroundColor: "#1E1E1E", // VS Code dark, kills the white boot flash
    title: "MiniCode",
    webPreferences: {
      preload: path.join(__dirname2, "preload.js"), // CJS output path
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false, // preload needs require(); renderer never does
    },
  });

  if (devUrl) {
    void win.loadURL(devUrl);
  } else {
    void win.loadFile(path.join(__dirname2, "..", "..", "dist", "index.html"));
  }
};

const registerIpc = (fs: FsService): void => {
  const handleAppInfo = (): Promise<AppInfo> =>
    Promise.resolve(fs.appInfo(process.versions.electron, app.getVersion()));
  const handleListDir = (_evt: unknown, dir: string): Promise<DirEntry[]> => {
    if (typeof dir !== "string" || dir.length === 0) {
      return Promise.reject(new TypeError("listDir expects a path string"));
    }
    return fs.listDir(dir);
  };

  ipcMain.handle(Channels.appInfo, handleAppInfo);
  ipcMain.handle(Channels.homeDir, () => fs.homeDir());
  ipcMain.handle(Channels.appDataDir, () => fs.appDataDir());
  ipcMain.handle(Channels.listDir, handleListDir);
};

app.whenReady().then(() => {
  const fs = new FsService();
  registerIpc(fs);
  const devUrl = process.env.MINICODE_DEV_URL ?? null;
  createWindow(devUrl);

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow(devUrl);
    }
  });
});

app.on("window-all-closed", () => {
  // macOS convention: keep the app alive until Cmd+Q.
  if (process.platform !== "darwin") {
    app.quit();
  }
});
