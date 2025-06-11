#!/bin/bash
#
# Release Build Script for AIDocSynth
#
# This script creates a final, optimized build for distribution.
# - Smaller file size (UPX compression, stripped symbols)
# - Faster startup
# - No console window
#
set -e

echo "🚀 Compiling Qt resources..."
pyside6-rcc resources.qrc -o aidocsynth/ui/qrc_resources.py

echo "🚀 Building (Release)..."
# The spec file uses PYI_MODE to set dev=False
PYI_MODE=release pyinstaller --noconfirm --distpath dist --workpath build AIDocSynth.spec

echo "✅ Release build complete in dist/"

