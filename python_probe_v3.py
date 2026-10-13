"""Read-only inventory of modules already loaded in Lirin's Python runtime."""

import os
import sys


def clean(value):
    if isinstance(value, type(u"")):
        result = value
    elif isinstance(value, type(b"")):
        result = value.decode("utf-8", "replace")
    else:
        result = u"%s" % (value,)
    return result.replace(u"\t", u" ").replace(u"\r", u" ").replace(u"\n", u" ")


snapshot = sys.modules.copy()
lines = [u"module\tfile\tsymbol_count"]
for name in sorted(snapshot):
    module = snapshot[name]
    namespace = getattr(module, "__dict__", None)
    if isinstance(namespace, dict):
        origin = namespace.get("__file__", u"")
        symbol_count = len(namespace)
    else:
        origin = u""
        symbol_count = 0
    lines.append(u"%s\t%s\t%d" % (clean(name), clean(origin), symbol_count))

path = r"C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\python_modules_v3.tsv"
data = (u"\n".join(lines) + u"\n").encode("utf-8")
fd = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o644)
try:
    offset = 0
    while offset < len(data):
        written = os.write(fd, data[offset:])
        if written <= 0:
            raise IOError("module inventory write failed at byte %d" % offset)
        offset += written
finally:
    os.close(fd)
