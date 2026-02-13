# ERPlora Bridge — Buildozer spec for Android APK
#
# Build via Docker:
#   cd native
#   docker run --rm -v "$(pwd)":/home/user/hostcwd kivy/buildozer:latest \
#       android debug -c build/android/buildozer.spec
#
# Or use the build script:
#   ./native/build/android/build.sh

[app]

title = ERPlora Bridge
package.name = erplorabridge
package.domain = com.erplora

# Source — the build workspace contains main.py + erplora_bridge/
source.dir = .
source.include_exts = py,json
source.exclude_dirs = .buildozer,.git,__pycache__,bin
source.exclude_patterns = license,*.pyc

version = 0.1.0

# Minimal dependencies — websockets is pure Python (no C extensions)
# Removed FastAPI/uvicorn (too many C deps), using websockets server directly
requirements = python3,android,websockets,pyserial

# Android permissions for network + hardware access
android.permissions = INTERNET,BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_CONNECT,BLUETOOTH_SCAN,ACCESS_FINE_LOCATION,FOREGROUND_SERVICE

# Foreground service keeps bridge running when app is in background
services = Bridge:main.py:foreground

# Android API levels
android.api = 34
android.minapi = 26
android.ndk = 25b
android.sdk = 34

# Build only ARM64 (modern devices, smaller APK)
android.archs = arm64-v8a

# Accept SDK licenses automatically
android.accept_sdk_license = True

# App settings
orientation = portrait
fullscreen = 0

# Skip Python bytecode compilation (avoids hostpython path issues on macOS)
android.no-byte-compile-python = True

# Gradle
android.enable_androidx = True

[buildozer]
log_level = 2
warn_on_root = 0
