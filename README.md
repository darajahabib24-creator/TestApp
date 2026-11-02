# MiniCode — pocket code IDE for Android (Kivy + p4a)

A free, single-APK mini IDE in the spirit of VS Code for Android: create and
edit code, run Python, drive the Android shell, install pure-Python packages,
chat with a free AI assistant, and deploy (zip) your workspace.

## What the app does

| Tab      | Feature |
|----------|---------|
| Files    | Browse shared storage, create/open/delete files and folders |
| Editor   | Syntax-highlighted editor (pygments), open / save / save-as |
| Run      | Run the current file with bundled Python, or `!command` for the Android shell (`sh`) |
| Packages | Install pure-Python wheels directly from PyPI (no pip needed on device) |
| AI       | Free keyless AI chat (Pollinations API) + "explain my file" |
| Deploy   | Zip your workspace for backup / transfer |

Notes:
* On Android 11+ tap **Deploy > Open storage settings** and grant All files
  access so files live in `/storage/emulated/0/minicode`. Without it the app
  uses private storage.
* Only pure-Python packages install on-device (C-extension wheels can't be
  compiled on a phone).

## Build locally (Codespaces / Linux)

```bash
chmod +x build.sh
./build.sh .          # defaults to armeabi-v7a (armv7)
ANDROID_ARCHS=arm64-v8a ./build.sh .   # for 64-bit-only devices
```

The APK lands in `bin/`. First build downloads the Android SDK + NDK.

## Build on GitHub Actions + download link

1. Commit and push to `main`.
2. Open the **Actions** tab → run (or it auto-runs on push) **Build Android APK**.
3. When it finishes, the APK is published as a release:

```
https://github.com/<your-user>/TestApp/releases/tag/apk
```

Download the APK there (the workflow also uploads a `minicode-apk` artifact).
The CI build targets **armeabi-v7a (armv7)** by default.

## Customize

* App code: `main.py`
* App name / package / version: edit the `ANDROID_*` env vars in
  `.github/workflows/android.yml` or the defaults in `build.sh`
* Extra Python dependencies: add p4a-compatible names to `P4A_REQUIREMENTS`
  in `build.sh`
