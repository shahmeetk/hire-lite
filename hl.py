#!/usr/bin/env python3
"""Run the Hire Lite CLI without installing: ``python3 hl.py <command>``."""
from hire_lite.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
