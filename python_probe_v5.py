"""Read-only symbol inventory for selected loaded client modules."""

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
    names = (
        "__main__", "ServerStateChecker", "newlogin", "newloginwindow",
        "networkmodule", "system", "rootlib", "pack", "loginutils",
        "serverinfo", "app", "net", "player", "ui",
    )
    snapshot = sys.modules.copy()
    rows = ["module\tsymbol\ttype"]
    for name in names:
        module = snapshot.get(name)
        namespace = getattr(module, "__dict__", None)
        if isinstance(namespace, dict):
            for symbol in sorted(namespace.keys(), key=repr):
                rows.append("%s\t%s\t%s" % (name, repr(symbol), type(namespace[symbol]).__name__))
    save("python_symbols_v5.txt", "\n".join(rows) + "\n")
except:
    import traceback
    try:
        save("python_probe_v5.error.txt", traceback.format_exc())
    except:
        pass
    raise
