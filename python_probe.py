"""Read-only module snapshot after entering the game."""

import os
import sys


directory = r"C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test"


def save(filename, data):
    if not isinstance(data, bytes):
        data = data.encode("utf-8")
    fd = os.open(os.path.join(directory, filename), os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o644)
    try:
        offset = 0
        while offset < len(data):
            written = os.write(fd, data[offset:])
            if written <= 0:
                raise IOError("write failed at byte %d" % offset)
            offset += written
    finally:
        os.close(fd)


try:
    snapshot = sys.modules.copy()
    rows = [
        "Python version: %s" % sys.version.replace("\n", " "),
        "Loaded modules: %d" % len(snapshot),
        "game module present: %s" % ("game" in snapshot),
        "-- modules --",
    ]
    for name in sorted(snapshot.keys(), key=repr):
        rows.append(repr(name))
    save("python_ingame_v6.txt", "\n".join(rows) + "\n")
except:
    import traceback
    try:
        save("python_probe_v6.error.txt", traceback.format_exc())
    except:
        pass
    raise
