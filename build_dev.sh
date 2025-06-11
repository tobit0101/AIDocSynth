#!/bin/bash
#
# Development Build Script for AIDocSynth
#
# This script creates a non-optimized, debug-friendly build.
# - Faster build time
# - Console window is visible
# - Not compressed with UPX
#
set -e

# --- Environment for macOS ARM64 Build ---
export ARCHFLAGS="-arch arm64"
export QT_MAC_WANTS_LAYER=1 # Recommended for PySide6 on Apple Silicon

echo "🚀 Compiling Qt resources..."
pyside6-rcc resources.qrc -o aidocsynth/ui/qrc_resources.py

echo "🚀 Building for macOS ARM64 (Dev)..."
PYI_MODE=dev pyinstaller --noconfirm --distpath dist --workpath build AIDocSynth.spec

echo "✅ Build complete. Opening application..."
open dist/AIDocSynth.app

# Output directory: dist/dev
#

echo "🚀 Starting development build..."

pyside6-rcc resources.qrc -o aidocsynth/ui/qrc_resources.py

# Set environment variable for the spec file and run PyInstaller
PYI_MODE=dev pyinstaller --noconfirm --distpath dist --workpath .build AIDocSynth.spec

echo "✅ Development build complete. You can find the app in the 'dist' folder."
