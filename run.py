import sys
import argparse
from multiprocessing import freeze_support
from aidocsynth.app import main

if __name__ == "__main__":
    # Important: call freeze_support() BEFORE parsing CLI args.
    # In PyInstaller-frozen apps, multiprocessing spawns child processes
    # by re-invoking the executable with special flags such as
    # --multiprocessing-fork or Python interpreter flags (-B -S -I -c ...).
    # freeze_support() handles these cases. We also use parse_known_args()
    # to ignore any unknown flags that are intended for the MP bootstrap.
    freeze_support()

    parser = argparse.ArgumentParser(description="AIDocSynth")
    parser.add_argument(
        "--loglevel",
        type=str.upper,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level (default: INFO)",
    )
    args, _unknown = parser.parse_known_args()

    sys.exit(main(loglevel=args.loglevel))
