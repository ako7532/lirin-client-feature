"""Read-only module inventory with a separate Python error report."""

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
    rows = ["module\tfile\tsymbol_count"]
    for name in sorted(snapshot.keys(), key=repr):
        module = snapshot[name]
        namespace = getattr(module, "__dict__", None)
        if isinstance(namespace, dict):
            origin = namespace.get("__file__", "")
            symbol_count = len(namespace)
        else:
            origin = ""
            symbol_count = 0
        rows.append("%s\t%s\t%d" % (repr(name), repr(origin), symbol_count))
    save("python_modules_v4.txt", "\n".join(rows) + "\n")
except:
    import traceback
    try:
        save("python_probe_v4.error.txt", traceback.format_exc())
    except:
        pass
    raise
