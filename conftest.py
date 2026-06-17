"""
Placing conftest.py in the project root tells pytest to add this directory to
the import path, so tests in tests/ can do `from tools import ...` and
`from utils.data_loader import ...` without any extra setup.
"""
