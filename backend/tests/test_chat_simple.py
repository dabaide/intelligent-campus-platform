#!/usr/bin/env python3
"""Compatibility wrapper for test scripts.

This file is kept so existing commands continue to work.
The actual script is located at backend/scripts/test_chat_simple.py
"""

import os
import runpy


if __name__ == "__main__":
    script_path = os.path.join(os.path.dirname(__file__), "scripts", "test_chat_simple.py")
    runpy.run_path(script_path, run_name="__main__")
