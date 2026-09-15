"""Frozen entry point — the app's own main, nothing else."""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()          # PyInstaller: no re-exec of the parent process
    from orderflow_system.desktop.__main__ import main

    sys.exit(main())
