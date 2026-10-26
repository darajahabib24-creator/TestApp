#!/usr/bin/env bash
set -Eeuo pipefail

# Build the directory containing main.py into an Android APK with p4a.
# Usage: ./build.sh [project-directory]

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${1:-$SCRIPT_DIR}" && pwd)"
if [[ ! -f "$PROJECT_DIR/main.py" ]]; then
  echo "ERROR: No main.py found in $PROJECT_DIR." >&2
  echo "Usage: $0 /path/to/project-containing-main.py" >&2
  exit 2
fi

as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

if ! command -v apt-get >/dev/null 2>&1; then
  echo "ERROR: This build script currently supports Debian/Ubuntu Linux (apt-get required)." >&2
  exit 1
fi
as_root apt-get update
as_root apt-get install -y curl unzip zip build-essential git pkg-config \
  autoconf automake cmake libtool libltdl-dev libffi-dev libssl-dev \
  libncurses5-dev libncursesw5-dev zlib1g-dev

# p4a's pinned Cython stack is not compatible with host Python 3.14.
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
UV="$(command -v uv || true)"
if [[ -z "$UV" ]]; then
  echo "ERROR: uv installation failed; install uv and rerun." >&2
  exit 1
fi

# Use a Python 3.11 build environment regardless of the system Python version.
P4A_VENV="${P4A_VENV:-$PROJECT_DIR/.venv-p4a}"
"$UV" python install 3.11
"$UV" venv --python 3.11 "$P4A_VENV"
P4A_PYTHON="$P4A_VENV/bin/python"
"$P4A_PYTHON" -m pip install --upgrade pip setuptools wheel
"$P4A_PYTHON" -m pip install 'Cython==0.29.36' 'python-for-android==2024.1.21'

# Prefer a configured Java 17, otherwise install it. Java 25 is too new for
# this pinned p4a toolchain.
find_java17() {
  local candidate
  local -a candidates=()
  [[ -n "${JAVA_HOME:-}" ]] && candidates+=("$JAVA_HOME")
  candidates+=(/usr/lib/jvm/* /opt/java/* /opt/jdk*)
  for candidate in "${candidates[@]}"; do
    [[ -x "$candidate/bin/java" ]] || continue
    if "$candidate/bin/java" -version 2>&1 | head -n 1 | grep -Eq 'version "17([.]|\\")'; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

if ! JAVA_HOME="$(find_java17)"; then
  as_root apt-get update
  as_root apt-get install -y openjdk-17-jdk
  JAVA_HOME="$(find_java17)" || {
    echo "ERROR: Could not find Java 17 after installing openjdk-17-jdk." >&2
    exit 1
  }
fi
export JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"
echo "Using Java: $(java -version 2>&1 | head -n 1)"

ANDROIDSDK="${ANDROIDSDK:-${ANDROID_HOME:-${RUNNER_TEMP:-$HOME}/android-sdk}}"
ANDROID_HOME="$ANDROIDSDK"
ANDROIDNDK="${ANDROIDNDK:-$ANDROIDSDK/ndk/25.2.9519653}"
export ANDROIDSDK ANDROID_HOME ANDROIDNDK
SDKMANAGER="$ANDROIDSDK/cmdline-tools/latest/bin/sdkmanager"

if [[ ! -x "$SDKMANAGER" ]]; then
  mkdir -p "$ANDROIDSDK/cmdline-tools"
  tools_zip="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/android-command-line-tools.zip"
  tools_unpack="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/android-cmdline-tools"
  curl -fsSL \
    https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip \
    -o "$tools_zip"
  rm -rf "$tools_unpack" "$ANDROIDSDK/cmdline-tools/latest"
  mkdir -p "$tools_unpack"
  unzip -q "$tools_zip" -d "$tools_unpack"
  mv "$tools_unpack/cmdline-tools" "$ANDROIDSDK/cmdline-tools/latest"
fi

export PATH="$ANDROIDSDK/cmdline-tools/latest/bin:$ANDROIDSDK/platform-tools:$PATH"
SDKMANAGER="$ANDROIDSDK/cmdline-tools/latest/bin/sdkmanager"

# Accept SDK licenses while preserving sdkmanager's exit status (yes may
# receive SIGPIPE after sdkmanager has accepted all licenses).
set +e
yes | "$SDKMANAGER" --sdk_root="$ANDROIDSDK" --licenses >/dev/null
license_status="${PIPESTATUS[1]}"
set -e
if [[ "$license_status" -ne 0 ]]; then
  echo "ERROR: sdkmanager could not accept Android SDK licenses." >&2
  exit "$license_status"
fi

"$SDKMANAGER" --sdk_root="$ANDROIDSDK" \
  'platform-tools' \
  'platforms;android-34' \
  'build-tools;34.0.0' \
  'ndk;25.2.9519653'

P4A_REQUIREMENTS="${P4A_REQUIREMENTS:-python3==3.11.5,kivy}"
ANDROID_ARCHS="${ANDROID_ARCHS:-arm64-v8a,armeabi-v7a}"
arch_args=()
IFS=',' read -r -a arch_list <<< "$ANDROID_ARCHS"
for arch in "${arch_list[@]}"; do
  [[ -n "$arch" ]] && arch_args+=(--arch "$arch")
done

permission_args=()
for permission in INTERNET READ_EXTERNAL_STORAGE WRITE_EXTERNAL_STORAGE MANAGE_EXTERNAL_STORAGE; do
  permission_args+=(--permission "$permission")
done

P4A_STORAGE_DIR="${P4A_STORAGE_DIR:-${RUNNER_TEMP:-$HOME}/p4a-storage}"
mkdir -p "$PROJECT_DIR/bin" "$P4A_STORAGE_DIR"
cd "$PROJECT_DIR"

# Give p4a a clean private source directory. Using the repository itself would
# also bundle .git, the host venv, build output, and other unrelated files.
PRIVATE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/kivy-p4a-private.XXXXXX")"
trap 'rm -rf -- "$PRIVATE_DIR"' EXIT
tar -C "$PROJECT_DIR" \
  --exclude='./.git' \
  --exclude='./.github' \
  --exclude='./.venv*' \
  --exclude='./bin' \
  --exclude='./build' \
  --exclude='./android-sdk' \
  --exclude='./p4a-storage' \
  -cf - . | tar -C "$PRIVATE_DIR" -xf -

"$P4A_VENV/bin/p4a" apk \
  --private "$PRIVATE_DIR" \
  --package "${ANDROID_PACKAGE:-org.stillframe.kivylauncher}" \
  --name "${ANDROID_APP_NAME:-Kivy Launcher}" \
  --version "${ANDROID_VERSION:-0.1.0}" \
  --bootstrap sdl2 \
  --requirements "$P4A_REQUIREMENTS" \
  "${arch_args[@]}" \
  --android-api 34 \
  --ndk-api 23 \
  --sdk-dir "$ANDROIDSDK" \
  --ndk-dir "$ANDROIDNDK" \
  --storage-dir "$P4A_STORAGE_DIR" \
  "${permission_args[@]}" \
  --orientation portrait

mapfile -d '' built_apks < <(
  find "$PROJECT_DIR" "$P4A_STORAGE_DIR" -type f -name '*.apk' -print0 2>/dev/null
)
if (( ${#built_apks[@]} == 0 )); then
  echo "ERROR: p4a finished without producing an APK." >&2
  exit 1
fi

for apk in "${built_apks[@]}"; do
  destination="$PROJECT_DIR/bin/$(basename "$apk")"
  [[ "$apk" -ef "$destination" ]] && continue
  cp -- "$apk" "$destination"
done

echo "APK output:"
find "$PROJECT_DIR/bin" -maxdepth 1 -type f -name '*.apk' -printf '%p (%k KB)\n'
