# Calculator (Android APK)

A small Kivy calculator for Android. The expression engine is
[`calculator.py`](calculator.py) — a whitelist AST evaluator (no `eval`), so
arbitrary input can't run code. `main.py` is only the UI.

## Features

* `+ - * / ^ % ( )`, unary signs, decimals
* `sqrt`, `pi`, `e`
* live result preview while typing
* unclosed `(` is closed automatically (`sqrt(2` → `sqrt(2)`)
* backspace, clear, last-3 history
* hardware keyboard support (Enter = `=`, Backspace, digits, `+-*/^().`)
* one-shot CLI: `python3 main.py "2 + 3 * 4"`

## Build

```bash
ANDROID_DIST_NAME=Calculator \
ANDROID_APP_NAME=Calculator \
ANDROID_PACKAGE=com.minicode.calculator \
ANDROID_VERSION=1.0.0 \
ANDROID_ARCHS=arm64-v8a \
ANDROID_PERMISSIONS='' \
P4A_REQUIREMENTS='python3==3.11.5,kivy' \
./build.sh calculator_app
```

Output: `calculator_app/bin/Calculator-debug-1.0.0.apk` (debug-signed, so it
installs without a keystore; enable "unknown sources" on the device).

`ANDROID_PERMISSIONS=''` keeps the APK permission-free — the calculator touches
no storage and no network. Add `INTERNET` etc. there if you extend it.
