/**
 * Shared IPC contract: the single source of truth for every channel.
 * The main process handles these; the preload exposes typed wrappers;
 * the renderer only ever calls the wrappers (never ipcRenderer directly).
 *
 * WHY contextIsolation + preload: the renderer must never touch Node APIs.
 * All OS access funnels through narrow, typed channels. A compromised web
 * page can only invoke what Main explicitly handles — not fs/process.
 */
export const Channels = {
  /** Ensure the window is ready; returns basic environment info. */
  appInfo: "app:info",
  /** Always-writable app-private workspace directory. */
  appDataDir: "fs:appDataDir",
  /** List a directory. Input is a path string, output is DirEntry[]. */
  listDir: "fs:list-dir",
  /** Home directory (startup workspace candidate). */
  homeDir: "fs:homeDir",
} as const;

export type ChannelName = (typeof Channels)[keyof typeof Channels];

export interface AppInfo {
  readonly platform: string;
  readonly electronVersion: string;
  readonly appVersion: string;
}

export interface DirEntry {
  readonly name: string;
  readonly path: string;
  readonly isDirectory: boolean;
  readonly isFile: boolean;
  /** Bytes (0 for directories). */
  readonly size: number;
}

export interface FsServiceAPI {
  appInfo(): Promise<AppInfo>;
  appDataDir(): Promise<string>;
  homeDir(): Promise<string>;
  listDir(path: string): Promise<DirEntry[]>;
}
