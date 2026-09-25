"""
backend/tests/conftest.py

Adds the backend directory to sys.path so that the flat imports used by
the production modules (e.g. `from data_generator import ...`) resolve
correctly when pytest runs from any working directory.
"""

import sys
import os

# Insert the backend package directory at the front of sys.path so all
# production modules can be imported with their flat-import style.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
