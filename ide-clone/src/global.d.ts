import type { AppInfo, DirEntry, FsServiceAPI } from "../electron/ipc/channels";

declare global {
  interface Window {
    readonly minicode: FsServiceAPI;
  }
}

export type { AppInfo, DirEntry };
