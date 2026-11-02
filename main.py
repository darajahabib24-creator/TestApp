"""MiniCode — a pocket code editor for Android (Kivy + p4a).

Features
--------
* Files     : browse shared storage, create files & folders, open in editor
* Editor    : syntax-highlighted code editor (pygments), open / save / save-as
* Terminal  : run the current file with the bundled Python, or drive the
              Android shell (/system/bin/sh) with any command
* Packages  : install pure-Python wheels straight from PyPI into a private
              site-packages (no pip needed, works offline-free afterwards)
* AI        : free keyless AI chat via the Pollinations text API
* Deploy    : zip the workspace so it can be backed up or copied to a PC

Full VS Code cannot run on Android; this is a compact mobile IDE in the same
spirit, packaged as a single free APK.
"""

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import traceback
import urllib.parse
import urllib.request
import zipfile

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.codeinput import CodeInput
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

Window.softinput_mode = "below_target"

DARK = (0.11, 0.11, 0.13, 1)
PANEL = (0.15, 0.15, 0.17, 1)
ACCENT = (0.26, 0.52, 0.96, 1)
TXT = (0.90, 0.90, 0.93, 1)

AI_URL = "https://text.pollinations.ai/"
PYPI_URL = "https://pypi.org/pypi/{pkg}/json"

# Shared storage root; falls back to app-internal storage when the user has
# not granted "All files access".
SHARED = "/storage/emulated/0"


def workspace_root():
    shared_ws = os.path.join(SHARED, "minicode")
    try:
        os.makedirs(shared_ws, exist_ok=True)
        probe = os.path.join(shared_ws, ".probe")
        with open(probe, "w") as fh:
            fh.write("1")
        os.remove(probe)
        return shared_ws
    except OSError:
        internal = os.path.join(os.path.expanduser("~"), "workspace")
        os.makedirs(internal, exist_ok=True)
        return internal


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0


def ui_label(text="", **kw):
    kw.setdefault("color", TXT)
    kw.setdefault("halign", "left")
    kw.setdefault("valign", "middle")
    label = Label(text=text, **kw)
    label.bind(size=lambda w, s: setattr(w, "text_size", s))
    return label


def ui_button(text, callback, height=dp(44), **kw):
    btn = Button(text=text, size_hint_y=None, height=height,
                 background_normal="", background_color=ACCENT, **kw)
    btn.bind(on_release=callback)
    return btn


def prompt_popup(title, initial, on_ok):
    box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
    field = TextInput(text=initial, multiline=False, size_hint_y=None, height=dp(44),
                      focus=True)
    box.add_widget(field)

    def submit(_=None):
        popup.dismiss()
        on_ok(field.text.strip())

    row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
    row.add_widget(ui_button("OK", submit))
    row.add_widget(ui_button("Cancel", lambda *_: popup.dismiss(),
                             background_color=(0.3, 0.3, 0.32, 1)))
    box.add_widget(row)
    field.bind(on_text_validate=submit)
    popup = Popup(title=title, content=box, size_hint=(0.9, 0.4))
    popup.open()


def confirm_popup(text, on_ok):
    box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
    box.add_widget(ui_label(text))
    row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
    row.add_widget(ui_button("Yes", lambda *_: (popup.dismiss(), on_ok())))
    row.add_widget(ui_button("No", lambda *_: popup.dismiss(),
                             background_color=(0.3, 0.3, 0.32, 1)))
    box.add_widget(row)
    popup = Popup(title="Confirm", content=box, size_hint=(0.9, 0.4))
    popup.open()


class FilesScreen(Screen):
    """Browse, create, delete and open files/folders."""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.cwd = app.workspace
        self.selected = None

        root = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(6))
        bar = GridLayout(cols=4, size_hint_y=None, height=dp(44), spacing=dp(4))
        bar.add_widget(ui_button("New file", lambda *_: self.new_file()))
        bar.add_widget(ui_button("New folder", lambda *_: self.new_folder()))
        bar.add_widget(ui_button("Delete", lambda *_: self.delete_selected()))
        bar.add_widget(ui_button("Refresh", lambda *_: self.refresh()))
        root.add_widget(bar)
        self.path_label = ui_label("", size_hint_y=None, height=dp(26),
                                   font_size="12sp")
        root.add_widget(self.path_label)

        self.grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(2))
        self.grid.bind(minimum_height=self.grid.setter("height"))
        scroll = ScrollView(bar_width=dp(4))
        scroll.add_widget(self.grid)
        root.add_widget(scroll)
        root.add_widget(ui_label(self.app.home_note, size_hint_y=None,
                                 height=dp(34), font_size="11sp"))
        self.add_widget(root)

    def on_enter(self):
        self.refresh()

    def refresh(self):
        self.grid.clear_widgets()
        self.path_label.text = self.cwd
        entries = []
        try:
            for name in sorted(os.listdir(self.cwd)):
                full = os.path.join(self.cwd, name)
                if os.path.isdir(full):
                    entries.append((name, True))
                else:
                    entries.append((f"{name}  ({human_size(os.path.getsize(full))})", False))
        except OSError as exc:
            self.app.flash(f"Cannot list {self.cwd}: {exc}")
        if self.cwd != "/":
            entries.insert(0, ("..", "up"))
        for name, kind in entries:
            text = f"[{kind.upper()}] {name}" if kind in (True, "up") else name
            self.grid.add_widget(
                ui_button(text, lambda *_a, n=name, k=kind: self.open_entry(n, k),
                          background_color=PANEL,
                          background_normal="",
                          halign="left"))

    def open_entry(self, name, kind):
        if kind == "up":
            self.cwd = os.path.dirname(self.cwd.rstrip("/")) or "/"
        elif kind is True:
            self.cwd = os.path.join(self.cwd, name)
        else:
            path = os.path.join(self.cwd, name.split("  (")[0])
            self.selected = path
            self.app.open_in_editor(path)
            self.app.show_tab("editor")
        self.refresh()

    def new_file(self):
        prompt_popup("New file name", "untitled.py",
                     lambda name: self._create(name, folder=False))

    def new_folder(self):
        prompt_popup("New folder name", "project",
                     lambda name: self._create(name, folder=True))

    def _create(self, name, folder):
        if not name:
            return
        path = os.path.join(self.cwd, name)
        try:
            if folder:
                os.makedirs(path, exist_ok=True)
            else:
                if not os.path.exists(path):
                    with open(path, "w", encoding="utf-8"):
                        pass
                self.selected = path
                self.app.open_in_editor(path)
                self.app.show_tab("editor")
        except OSError as exc:
            self.app.flash(f"Create failed: {exc}")
        self.refresh()

    def delete_selected(self):
        if not self.selected:
            self.app.flash("Tap a file first to select it, then Delete.")
            return
        path = self.selected

        def do_delete():
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                self.selected = None
                self.app.flash(f"Deleted {path}")
            except OSError as exc:
                self.app.flash(f"Delete failed: {exc}")
            self.refresh()

        confirm_popup(f"Delete {path}?", do_delete)


class EditorScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.path = None
        root = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(6))
        bar = GridLayout(cols=4, size_hint_y=None, height=dp(44), spacing=dp(4))
        bar.add_widget(ui_button("Open selected", lambda *_: self.open_selected()))
        bar.add_widget(ui_button("Save", lambda *_: self.save()))
        bar.add_widget(ui_button("Save as", lambda *_: self.save_as()))
        bar.add_widget(ui_button("Run", lambda *_: self.run()))
        root.add_widget(bar)
        self.title_label = ui_label("no file", size_hint_y=None, height=dp(24),
                                    font_size="12sp")
        root.add_widget(self.title_label)
        self.editor = CodeInput(font_size="13sp", background_color=DARK,
                                foreground_color=TXT, autoforce_down=True)
        root.add_widget(self.editor)
        self.add_widget(root)

    def open_selected(self):
        files = self.app.screen("files")
        if files.selected and os.path.isfile(files.selected):
            self.open_path(files.selected)
        else:
            self.app.flash("Select a file in the Files tab first.")

    def open_path(self, path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                self.editor.text = fh.read()
        except (OSError, UnicodeError) as exc:
            self.app.flash(f"Open failed: {exc}")
            return
        self.path = path
        self.title_label.text = path
        self.editor.lexer = self.app.lexer_for(path)

    def save(self):
        if not self.path:
            self.save_as()
            return
        self._write(self.path)

    def save_as(self):
        prompt_popup("Save as (name in workspace)", "script.py",
                     lambda name: self._write(os.path.join(self.app.workspace, name)))

    def _write(self, path):
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.editor.text)
            self.path = path
            self.title_label.text = path
            self.app.flash(f"Saved {path}")
        except OSError as exc:
            self.app.flash(f"Save failed: {exc}")

    def run(self):
        self.save()
        if self.path:
            self.app.screen("terminal").run_file(self.path)


class TerminalScreen(Screen):
    """Runs the current file in-process, or drives the Android shell."""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.session_ns = {"__name__": "__console__"}
        self.results = queue.Queue()
        root = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(6))
        bar = GridLayout(cols=3, size_hint_y=None, height=dp(44), spacing=dp(4))
        bar.add_widget(ui_button("Run current file", lambda *_: self.run_open_file()))
        bar.add_widget(ui_button("Clear", self._clear))
        bar.add_widget(ui_button("Interrupt hint", lambda *_: self._hint()))
        root.add_widget(bar)
        self.output = ui_label("", font_size="12sp")
        scroll = ScrollView(bar_width=dp(4))
        scroll.add_widget(self.output)
        scroll.bind(scroll_y=lambda *_: None)
        root.add_widget(scroll)
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        self.input = TextInput(multiline=False, font_size="13sp", hint_text="python code or !ls")
        self.input.bind(on_text_validate=lambda *_: self.submit())
        row.add_widget(self.input)
        row.add_widget(ui_button("Send", lambda *_: self.submit(), width=dp(90),
                                 size_hint_x=None))
        root.add_widget(row)
        self.add_widget(root)
        Clock.schedule_interval(self._drain, 0.2)

    def _clear(self, *_):
        self.output.text = ""

    def _hint(self, *_):
        self._emit("Long-running loops cannot be interrupted on mobile; "
                   "keep scripts short or use !sh commands.")

    def _emit(self, text):
        self.results.put(("info", text))

    def run_file(self, path):
        threading.Thread(target=self._run_file_bg, args=(path,), daemon=True).start()
        self.app.show_tab("terminal")

    def _run_file_bg(self, path):
        self._emit(f"--- running {path} ---")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                self._exec(fh.read(), path)
        except OSError as exc:
            self._emit(f"open failed: {exc}")

    def run_open_file(self):
        editor = self.app.screen("editor")
        if editor.path:
            editor.save()
            self.run_file(editor.path)
        else:
            self.app.flash("Open a file in the Editor tab first.")

    def submit(self):
        line = self.input.text.strip()
        self.input.text = ""
        if not line:
            return
        if line.startswith("!"):
            threading.Thread(target=self._shell_bg, args=(line[1:],),
                             daemon=True).start()
            self._emit(f"$ {line[1:]}")
        else:
            threading.Thread(target=self._python_bg, args=(line,),
                             daemon=True).start()
            self._emit(f">>> {line}")

    def _python_bg(self, code):
        self._exec(code, "<console>")
        self._emit("")

    def _shell_bg(self, command):
        try:
            proc = subprocess.run(["/system/bin/sh", "-c", command],
                                  capture_output=True, text=True, timeout=15)
            out = (proc.stdout or "") + (proc.stderr or "")
            self._emit(out.strip()[:4000] or "(no output)")
        except FileNotFoundError:
            self._emit("Shell not available on this device.")
        except subprocess.TimeoutExpired:
            self._emit("Command timed out (15 s limit).")
        self._emit("")

    def _exec(self, code, filename):
        buffer_out = _OutBuffer(self.results)
        old = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = buffer_out
        try:
            exec(compile(code, filename, "exec"), self.session_ns)
        except BaseException:
            self._emit(traceback.format_exc(limit=8))
        finally:
            sys.stdout, sys.stderr = old
            buffer_out.flush()

    def _drain(self, dt):
        dropped = False
        while not self.results.empty():
            try:
                tag, text = self.results.get_nowait()
            except queue.Empty:
                break
            text = text.rstrip()
            if text:
                self.output.text = (self.output.text + "\n" + text)[-8000:]
            dropped = True
        if dropped:
            scroll_parent = self.output.parent
            if scroll_parent:
                scroll_parent.scroll_y = 0


class _OutBuffer:
    def __init__(self, results):
        self.results = results
        self.chunks = []

    def write(self, text):
        if text and text.strip():
            self.chunks.append(text)

    def flush(self):
        if self.chunks:
            self.results.put(("out", "".join(self.chunks)[:4000]))
            self.chunks = []

    def isatty(self):
        return False


class PackagesScreen(Screen):
    """Install pure-Python packages from PyPI without pip."""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(6))
        bar = GridLayout(cols=2, size_hint_y=None, height=dp(48), spacing=dp(4))
        self.field = TextInput(multiline=False, font_size="13sp",
                               hint_text="package name, e.g. requests")
        self.field.bind(on_text_validate=lambda *_: self.install())
        bar.add_widget(self.field)
        bar.add_widget(ui_button("Install", lambda *_: self.install()))
        root.add_widget(bar)
        self.info = ui_label(
            "Installs pure-Python wheels from PyPI into a private\n"
            "site-packages folder and makes them importable right away.\n"
            "Packages with C extensions cannot be compiled on-device.\n\n"
            "Installed packages:", font_size="12sp", size_hint_y=None,
            height=dp(110))
        self.info.bind(width=lambda w, s: setattr(w, "text_size", s))
        root.add_widget(self.info)
        self.grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(2))
        self.grid.bind(minimum_height=self.grid.setter("height"))
        scroll = ScrollView(bar_width=dp(4))
        scroll.add_widget(self.grid)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_enter(self):
        self.grid.clear_widgets()
        target = self.app.site_dir
        if not os.path.isdir(target):
            return
        for name in sorted(os.listdir(target)):
            if os.path.isdir(os.path.join(target, name)):
                self.grid.add_widget(ui_button(name, lambda *_: None,
                                               background_color=PANEL,
                                               background_normal="",
                                               halign="left"))

    def install(self):
        pkg = self.field.text.strip()
        if not pkg:
            return
        self.field.text = ""
        self.app.flash(f"Fetching {pkg} from PyPI...")
        threading.Thread(target=self._install_bg, args=(pkg,), daemon=True).start()

    def _install_bg(self, pkg):
        try:
            with urllib.request.urlopen(PYPI_URL.format(pkg=urllib.parse.quote(pkg)),
                                        timeout=20) as resp:
                data = json.loads(resp.read().decode())
            wheel = self._pick_wheel(data.get("urls", []))
            if not wheel:
                self.app.flash(f"'{pkg}' has no pure-Python wheel; "
                               "source/C builds are not supported on-device.")
                return
            dest = os.path.join(self.app.site_dir, pkg.replace("-", "_"))
            os.makedirs(dest, exist_ok=True)
            tmp = os.path.join(dest, "wheel.zip")
            urllib.request.urlretrieve(wheel["url"], tmp)
            with zipfile.ZipFile(tmp) as zf:
                zf.extractall(self.app.site_dir)
            os.remove(tmp)
            self._ensure_path()
            self.app.flash(f"Installed {wheel['filename']} — import it!")
        except Exception as exc:  # noqa: BLE001 — network errors must never crash the UI
            self.app.flash(f"Install failed: {exc}")

    @staticmethod
    def _pick_wheel(urls):
        preferred, fallback = None, None
        for item in urls:
            fn = item.get("filename", "")
            if not fn.endswith(".whl"):
                continue
            pure = ("py3-none-any" in fn or "py2.py3-none-any" in fn
                    or fn.endswith("-none-any.whl"))
            if pure:
                preferred = item
                break
            fallback = fallback or item
        return preferred

    def _ensure_path(self):
        if self.app.site_dir not in sys.path:
            sys.path.insert(0, self.app.site_dir)


class AIScreen(Screen):
    """Free keyless AI assistant (Pollinations text API)."""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.history = []
        root = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(6))
        bar = GridLayout(cols=2, size_hint_y=None, height=dp(44), spacing=dp(4))
        bar.add_widget(ui_button("New chat", lambda *_: self.clear()))
        bar.add_widget(ui_button("Explain my file", lambda *_: self.explain_file()))
        root.add_widget(bar)
        self.chat = ui_label(
            "Free AI assistant (no API key needed).\n"
            "Ask about Python, debugging, your project...\n"
            "Requires internet.", font_size="12sp")
        scroll = ScrollView(bar_width=dp(4))
        scroll.add_widget(self.chat)
        root.add_widget(scroll)
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        self.input = TextInput(multiline=False, font_size="13sp",
                               hint_text="Ask the AI anything")
        self.input.bind(on_text_validate=lambda *_: self.send())
        row.add_widget(self.input)
        row.add_widget(ui_button("Send", lambda *_: self.send(), width=dp(90),
                                 size_hint_x=None))
        root.add_widget(row)
        self.add_widget(root)

    def clear(self):
        self.history = []
        self.chat.text = "New chat. Ask anything."

    def explain_file(self):
        editor = self.app.screen("editor")
        if editor.path and editor.editor.text.strip():
            src = editor.editor.text[:3000]
            self.send(f"Explain this file ({os.path.basename(editor.path)}):\n{src}")
        else:
            self.app.flash("Open a file in the Editor tab first.")

    def send(self, text=None):
        prompt = (text or self.input.text).strip()
        if not prompt:
            return
        if text is None:
            self.input.text = ""
        self.chat.text += f"\n\nYou: {prompt[:500]}"
        self.history = (self.history + [{"role": "user", "content": prompt}])[-8:]
        self.app.flash("Asking AI...")
        threading.Thread(target=self._ask_bg, daemon=True).start()

    def _ask_bg(self):
        try:
            payload = json.dumps({
                "model": "openai",
                "messages": ([{"role": "system", "content":
                               "You are MiniCode's concise coding assistant."}]
                             + self.history),
            }).encode()
            req = urllib.request.Request(AI_URL, data=payload,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                answer = resp.read().decode(errors="replace").strip()
            self.history.append({"role": "assistant", "content": answer})
            Clock.schedule_once(lambda *_: self._show(answer))
        except Exception as exc:  # noqa: BLE001
            Clock.schedule_once(lambda *_: self._show(
                f"AI request failed ({exc}).\nCheck internet and try again."))

    def _show(self, answer):
        self.chat.text = (self.chat.text + f"\n\nAI: {answer[:6000]}")[-12000:]
        self.chat.parent.scroll_y = 0
        self.app.flash("AI reply ready.")


class DeployScreen(Screen):
    """Zip the workspace for backup / transfer."""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        root = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        root.add_widget(ui_button("Zip my workspace", lambda *_: self.zip_workspace()))
        root.add_widget(ui_button("Open storage settings",
                                  lambda *_: self.storage_settings()))
        self.info = ui_label("", font_size="13sp", size_hint_y=None, height=dp(220))
        self.info.bind(width=lambda w, s: setattr(w, "text_size", s))
        root.add_widget(self.info)
        self.add_widget(root)

    def on_enter(self):
        self.info.text = (
            f"Workspace: {self.app.workspace}\n\n"
            "Zip it here, then copy the archive with a file manager,\n"
            "or grab it over USB.\n\nTip: 'Storage settings' grants All-files\n"
            "access so your work survives app uninstalls.")

    def zip_workspace(self):
        src = self.app.workspace
        target = os.path.join(src if os.access(src, os.W_OK) else os.path.expanduser("~"),
                              "minicode_project.zip")
        try:
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
                for base, _dirs, files in os.walk(src):
                    for name in files:
                        if name.endswith(".zip"):
                            continue
                        full = os.path.join(base, name)
                        zf.write(full, os.path.relpath(full, src))
            self.info.text = self.info.text + f"\n\nCreated: {target}"
            self.app.flash(f"Created {target}")
        except (OSError, zipfile.BadZipFile) as exc:
            self.app.flash(f"Zip failed: {exc}")

    def storage_settings(self):
        try:
            from jnius import autoclass

            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            Settings = autoclass("android.provider.Settings")
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
            intent.setData(Uri.parse("package:" + str(activity.getPackageName())))
            activity.startActivity(intent)
        except Exception as exc:  # noqa: BLE001
            self.app.flash(f"Open Android Settings > Apps > MiniCode > Files manually. ({exc})")


class MiniCode(App):
    title = "MiniCode"

    def build(self):
        self.workspace = workspace_root()
        self.site_dir = os.path.join(os.path.expanduser("~"), "site-packages")
        self._ensure_path()
        self.home_note = (
            f"Workspace: {self.workspace}" +
            ("" if self.workspace.startswith("/storage") else
             "\nGrant All files access (Deploy tab) for shared storage."))

        self.sm = ScreenManager()
        self.sm.add_widget(FilesScreen(self, name="files"))
        self.sm.add_widget(EditorScreen(self, name="editor"))
        self.sm.add_widget(TerminalScreen(self, name="terminal"))
        self.sm.add_widget(PackagesScreen(self, name="packages"))
        self.sm.add_widget(AIScreen(self, name="ai"))
        self.sm.add_widget(DeployScreen(self, name="deploy"))

        root = BoxLayout(orientation="vertical", spacing=dp(2))
        tabs = GridLayout(cols=6, size_hint_y=None, height=dp(40), spacing=dp(2),
                          padding=[dp(4), dp(4), dp(4), 0])
        for name, label in (("files", "Files"), ("editor", "Editor"),
                            ("terminal", "Run"), ("packages", "Packages"),
                            ("ai", "AI"), ("deploy", "Deploy")):
            tabs.add_widget(ui_button(label, lambda *_a, n=name: self.show_tab(n),
                                      font_size="12sp"))
        self.status = ui_label("", size_hint_y=None, height=dp(24), font_size="11sp")
        root.add_widget(tabs)
        root.add_widget(self.sm)
        root.add_widget(self.status)
        self.show_tab("files")
        return root

    def _ensure_path(self):
        if os.path.isdir(self.site_dir) and self.site_dir not in sys.path:
            sys.path.insert(0, self.site_dir)

    def screen(self, name):
        return self.sm.get_screen(name)

    def show_tab(self, name):
        self.sm.current = name

    def flash(self, text):
        self.status.text = text

    def open_in_editor(self, path):
        self.screen("editor").open_path(path)

    def lexer_for(self, path):
        from pygments import lexers

        try:
            return lexers.guess_lexer_for_filename(path, "")
        except Exception:  # noqa: BLE001 — unknown extension: plain text
            return lexers.TextLexer()


if __name__ == "__main__":
    MiniCode().run()
