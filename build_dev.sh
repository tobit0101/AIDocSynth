#!/bin/bash
#
# Development Build Script for AIDocSynth
#
# This script creates a non-optimized, debug-friendly build.
# - Faster build time
# - Console window is visible
# - Not compressed with UPX
# - No lazy imports
#
# Output directory: dist/dev
#

echo "🚀 Starting development build..."

pyside6-rcc resources.qrc -o aidocsynth/ui/qrc_resources.py

# Set environment variable for the spec file and run PyInstaller
PYI_MODE=dev pyinstaller --noconfirm --distpath dist/dev --workpath .build AIDocSynth.spec

echo "✅ Development build complete. You can find the app in the 'dist/dev' folder."
