import sys
from multiprocessing import freeze_support
from aidocsynth.app import main

if __name__ == "__main__":
    # Required for PyInstaller builds on Windows
    freeze_support()
    sys.exit(main())
