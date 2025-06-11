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

echo "🚀 Compiling Qt resources..."
pyside6-rcc resources.qrc -o aidocsynth/ui/qrc_resources.py

echo "🚀 Building (Dev)..."
PYI_MODE=dev pyinstaller --noconfirm --distpath dist --workpath build AIDocSynth.spec

echo "✅ Build complete in dist/"
