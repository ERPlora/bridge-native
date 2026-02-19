#!/bin/bash
# Build ERPlora Bridge APK using Docker + Buildozer
#
# Usage: ./native/build/android/build.sh
#
# Prerequisites: Docker installed and running
# Note: On Apple Silicon Macs, Docker uses x86_64 emulation (Rosetta/QEMU)
#       which is slower but required since Android build-tools are x86_64-only.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NATIVE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$NATIVE_DIR/buildozer_workspace"

echo "=== ERPlora Bridge APK Builder ==="
echo "Native dir: $NATIVE_DIR"
echo "Build dir:  $BUILD_DIR"
echo ""

# 1. Prepare build workspace
echo ">> Preparing build workspace..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Copy main.py entry point
cp "$SCRIPT_DIR/main.py" "$BUILD_DIR/main.py"

# Copy the erplora_bridge package
cp -r "$NATIVE_DIR/erplora_bridge" "$BUILD_DIR/erplora_bridge"

# Copy buildozer.spec
cp "$SCRIPT_DIR/buildozer.spec" "$BUILD_DIR/buildozer.spec"

echo ">> Build workspace ready."
echo ""

# 2. Run Buildozer via Docker
echo ">> Starting Docker build (this takes 10-30 minutes on first run)..."
echo ">> The Docker image will download Android SDK/NDK automatically."
echo ""

# Force linux/amd64 platform — Android build-tools (aidl) are x86_64-only binaries
# On Apple Silicon this uses Rosetta/QEMU emulation (slower but works)
docker run --rm \
    --platform linux/amd64 \
    --entrypoint bash \
    -v "$BUILD_DIR":/home/user/hostcwd \
    -w /home/user/hostcwd \
    kivy/buildozer:latest \
    -c 'cd /home/user/hostcwd && buildozer android debug'

# 3. Copy APK to output
echo ""
echo ">> Build complete!"

APK_PATH=$(find "$BUILD_DIR/bin" -name "*.apk" -type f 2>/dev/null | head -1)

if [ -n "$APK_PATH" ]; then
    mkdir -p "$NATIVE_DIR/dist"
    cp "$APK_PATH" "$NATIVE_DIR/dist/"
    APK_NAME=$(basename "$APK_PATH")
    echo ">> APK copied to: native/dist/$APK_NAME"
    echo ""
    echo "To install on Android device:"
    echo "  adb install native/dist/$APK_NAME"
    echo ""
    echo "Or transfer the file to your phone and install manually."
else
    echo ">> ERROR: APK not found in build output."
    echo ">> Check Docker logs above for errors."
    exit 1
fi
