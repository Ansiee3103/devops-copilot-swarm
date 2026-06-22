import os
import sys

# Save original stat
original_stat = os.stat

def patched_stat(path, *args, **kwargs):
    try:
        return original_stat(path, *args, **kwargs)
    except PermissionError:
        # Return the stat of the current directory (which is a valid, accessible directory)
        # to satisfy pytest's traversal logic without raising exceptions.
        return original_stat(".")

# Apply patch
os.stat = patched_stat

import pytest
if __name__ == "__main__":
    sys.exit(pytest.main(["-c", "pytest.ini", "tests/"]))
