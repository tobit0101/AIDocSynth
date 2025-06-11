#!/usr/bin/env bash
set -e
echo "[rcc] compiling resources.qrc"
pyside6-rcc resources.qrc -o aidocsynth/ui/qrc_resources.py
