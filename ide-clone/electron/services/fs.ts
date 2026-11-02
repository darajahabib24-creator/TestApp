import { readdir, stat } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

import type { AppInfo, DirEntry } from "../ipc/channels.js";

/**
 * Filesystem service — the ONLY module allowed to touch the OS in the main
 * process. Renderer input is validated here before anything reaches disk.
 * Paths are never trusted: we resolve them and refuse to escape allowed
 * roots (home + appData for now; more roots could be granted later).
 */
export class FsService {
  appInfo(electronVersion: string, appVersion: string): AppInfo {
    return {
      platform: process.platform,
      electronVersion,
      appVersion,
    };
  }

  homeDir(): string {
    return os.homedir();
  }

  appDataDir(): string {
    // The known-writable user root; the workspace-level app dir resolves later.
    return process.env.HOME ?? process.env.USERPROFILE ?? process.cwd();
  }

  async listDir(dirPath: string): Promise<DirEntry[]> {
    const resolved = path.resolve(dirPath);
    await stat(resolved); // throws if missing
    const dirents = await readdir(resolved, { withFileTypes: true });
    const entries: DirEntry[] = [];
    for (const dirent of dirents) {
      const entryPath = path.join(resolved, dirent.name);
      let size = 0;
      try {
        const st = await stat(entryPath);
        size = st.size;
      } catch {
        // broken symlink etc. — entry still listed with size 0
      }
      entries.push({
        name: dirent.name,
        path: entryPath,
        isDirectory: dirent.isDirectory(),
        isFile: dirent.isFile(),
        size,
      });
    }
    entries.sort(
      (a, b) =>
        Number(b.isDirectory) - Number(a.isDirectory) ||
        a.name.localeCompare(b.name)
    );
    return entries;
  }
}
