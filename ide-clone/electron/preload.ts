import { contextBridge, ipcRenderer } from "electron";

import {
  Channels,
  type AppInfo,
  type DirEntry,
} from "./ipc/channels.js";

/**
 * The only bridge between renderer and OS. It implements exactly the API the
 * renderer is allowed to see — nothing structural leaks (no ipcRenderer, no
 * fs). Everything is async and typed, so renderer code stays strict-TS.
 */
const api = {
  appInfo: (): Promise<AppInfo> => ipcRenderer.invoke(Channels.appInfo),
  appDataDir: (): Promise<string> => ipcRenderer.invoke(Channels.appDataDir),
  homeDir: (): Promise<string> => ipcRenderer.invoke(Channels.homeDir),
  listDir: (dirPath: string): Promise<DirEntry[]> =>
    ipcRenderer.invoke(Channels.listDir, dirPath),
};

contextBridge.exposeInMainWorld("minicode", api);
