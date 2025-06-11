#!/bin/bash
#
# Release Build Script for AIDocSynth
#
# This script creates a final, optimized build for distribution.
# - Smaller file size (UPX compression, stripped symbols)
# - Faster startup (lazy imports)
# - No console window
#
# Output directory: dist/release
#

echo "📦 Starting release build..."

# Run PyInstaller for a release build (PYI_MODE is not set)
# --jobs=auto uses all available CPU cores to speed up the build.
pyinstaller --noconfirm --distpath dist/release --workpath .build --jobs=auto AIDocSynth.spec

echo "🎉 Release build complete. You can find the app in the 'dist/release' folder."
