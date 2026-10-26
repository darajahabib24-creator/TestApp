"""Small Kivy starter screen for the p4a Android build.

The app inspects /storage/emulated/0/kivy and lists project folders that contain
main.py. Android 11+ requires the user to grant All files access in Settings.
This starter only lists projects; it does not execute Python code from shared
storage. p4a packages this file as the app's entry point.
"""

from pathlib import Path

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView


PROJECTS_DIR = Path("/storage/emulated/0/kivy")


class LauncherScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(18), spacing=dp(12), **kwargs)

        self.add_widget(
            Label(
                text="Kivy Project Browser",
                font_size="24sp",
                size_hint_y=None,
                height=dp(48),
            )
        )
        self.status = Label(text="", halign="left", valign="middle", size_hint_y=None)
        self.status.bind(width=lambda label, width: setattr(label, "text_size", (width, None)))
        self.add_widget(self.status)

        self.add_widget(
            Button(
                text="Open Android storage settings",
                size_hint_y=None,
                height=dp(48),
                on_release=lambda *_: self.open_storage_settings(),
            )
        )
        self.add_widget(
            Button(
                text="Refresh project list",
                size_hint_y=None,
                height=dp(48),
                on_release=lambda *_: self.refresh(),
            )
        )

        self.projects = Label(text="", halign="left", valign="top", size_hint_y=None)
        self.projects.bind(
            width=lambda label, width: setattr(label, "text_size", (width, None)),
            texture_size=lambda label, size: setattr(label, "height", size[1]),
        )
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.projects)
        self.add_widget(scroll)

        self.refresh()

    def refresh(self):
        if not PROJECTS_DIR.exists():
            self.status.text = (
                f"Folder not found or storage access is not granted:\n{PROJECTS_DIR}\n\n"
                "Create the folder in shared storage, grant access in Android Settings, "
                "then tap Refresh."
            )
            self.projects.text = ""
            return

        try:
            folders = sorted(path for path in PROJECTS_DIR.iterdir() if path.is_dir())
        except OSError as exc:
            self.status.text = f"Cannot read {PROJECTS_DIR}: {exc}"
            self.projects.text = ""
            return

        self.status.text = f"Projects folder: {PROJECTS_DIR}\nFound {len(folders)} folder(s)."
        entries = []
        for folder in folders:
            entry = folder / "main.py"
            marker = "main.py found" if entry.is_file() else "main.py missing"
            entries.append(f"{folder.name}  —  {marker}")
        self.projects.text = "\n\n".join(entries) if entries else "No project folders yet."

    def open_storage_settings(self):
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Settings = autoclass("android.provider.Settings")
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")

            activity = PythonActivity.mActivity
            intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
            intent.setData(Uri.parse("package:" + str(activity.getPackageName())))
            activity.startActivity(intent)
        except Exception as exc:
            self.status.text = (
                "Could not open the Android storage settings automatically. "
                f"Enable All files access for this app in Settings.\n{exc}"
            )


class KivyProjectBrowser(App):
    title = "Kivy Project Browser"

    def build(self):
        return LauncherScreen()


if __name__ == "__main__":
    KivyProjectBrowser().run()
