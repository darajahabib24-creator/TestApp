import type { DirEntry } from "./global";

/**
 * Phase 1 renderer: minimal workbench mount + IPC smoke test.
 * Phase 2 replaces this markup with the real 5-part layout components.
 */
interface WorkbenchRefs {
  readonly sidebar: HTMLElement;
  readonly status: HTMLElement;
  readonly editorArea: HTMLElement;
}

function mount(): WorkbenchRefs {
  const root = document.getElementById("root");
  if (!root) throw new Error("#root missing from index.html");

  root.innerHTML = `
    <div data-test="workbench" style="display:flex; height:100vh; flex-direction:column">
      <div style="display:flex; flex:1; min-height:0">
        <div data-test="activity" style="width:48px; background:#333333"></div>
        <div data-test="sidebar" style="width:240px; background:#252526; padding:8px; overflow:auto"></div>
        <div data-test="editor" style="flex:1; background:#1e1e1e; padding:16px"></div>
      </div>
      <div data-test="status" style="height:24px; background:#007acc; font-size:12px; padding:0 12px; line-height:24px"></div>
    </div>`;

  const refs: WorkbenchRefs = {
    sidebar: root.querySelector('[data-test="sidebar"]') as HTMLElement,
    status: root.querySelector('[data-test="status"]') as HTMLElement,
    editorArea: root.querySelector('[data-test="editor"]') as HTMLElement,
  };
  refs.editorArea.textContent = "MiniCode — IPC alive if the sidebar fills below";
  return refs;
}

function render(entries: DirEntry[]): string {
  return entries
    .map(
      (e) =>
        `<div style="padding:2px 4px; font-family:monospace">` +
        `${e.isDirectory ? "[DIR]" : "     "} ${e.name}</div>`
    )
    .join("");
}

async function bootstrap(): Promise<void> {
  const refs = mount();

  const info = await window.minicode.appInfo();
  refs.status.textContent =
    `${info.appVersion} · Electron ${info.electronVersion} · ${info.platform}`;

  const home = await window.minicode.homeDir();
  const entries = await window.minicode.listDir(home);
  refs.sidebar.innerHTML =
    `<strong style="font-size:12px">/ ${home}</strong>` + render(entries);
}

void bootstrap();
