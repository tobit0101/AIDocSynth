import sys
import argparse
from multiprocessing import freeze_support
from aidocsynth.app import main

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AIDocSynth")
    parser.add_argument(
        "--loglevel",
        type=str.upper,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level (default: INFO)",
    )
    args = parser.parse_args()

    # Required for PyInstaller builds on Windows
    freeze_support()
    sys.exit(main(loglevel=args.loglevel))
