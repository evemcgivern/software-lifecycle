from __future__ import annotations


class InputError(Exception):
    """Bad input file or arguments. Maps to exit code 3."""


class DataError(Exception):
    """A data check failed. Maps to exit code 4."""
