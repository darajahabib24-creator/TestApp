# Kivy p4a GitHub starter

This folder contains a Kivy entry point, a Bash python-for-android (p4a)
builder, and a GitHub Actions workflow. The script pins the host build tools to
Python 3.11 and Java 17 to avoid the Python 3.14 and Java 25 errors.

## Build in Codespaces or Linux

Run from this folder:

```bash
chmod +x build.sh
./build.sh .
```

Or pass the directory containing your app's `main.py`:

```bash
./build.sh /path/to/your/kivy-project
```

The APK is placed in `bin/`. First build downloads the Android SDK and NDK and
can take a while. Keep `main.py` and any assets the app needs in the project
folder so p4a can package them.

## GitHub Actions

Commit this folder to a repository and push to `main` or `master`, or run
**Build Android APK** from the Actions tab. Download the `kivy-launcher-apk`
artifact from the completed workflow run.

## Shared storage note

The sample `main.py` checks `/storage/emulated/0/kivy` and lists project folders
containing `main.py`. On Android 11 and newer, the app must be granted **All
files access** in Android Settings; the button in the sample opens that
settings page. Declaring `MANAGE_EXTERNAL_STORAGE` in the APK does not grant it
automatically. This is intended for a sideloaded personal launcher; Google Play
restricts that permission.

This starter only lists Python project folders. It does not dynamically execute
external `main.py` files or install each project's dependencies. p4a packages
the app's `main.py` and dependencies into the APK. To build your actual app,
replace the starter `main.py` with your app code, add assets to this project,
and add p4a-compatible Python dependencies to `P4A_REQUIREMENTS` in `build.sh`.
