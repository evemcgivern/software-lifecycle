from __future__ import annotations

import os
import tempfile

from .errors import InputError


def write_text(path: str, text: str, input_path: str | None = None) -> None:
    """Write text atomically with owner-only permissions.

    Refuses to write over the input file or through a symlink.
    """
    if input_path is not None:
        if os.path.realpath(path) == os.path.realpath(input_path):
            raise InputError("refusing to overwrite the input file")
        try:
            if os.path.samefile(path, input_path):
                raise InputError("refusing to overwrite the input file")
        except OSError:
            pass  # output does not exist yet
    if os.path.islink(path):
        raise InputError("refusing to write through a symlink")
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".swlc-", suffix=".tmp")
    try:
        # mkstemp already makes the file owner-only where the system
        # supports it; os.fchmod is missing on Windows before Python 3.13.
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fd = -1
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if fd != -1:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
