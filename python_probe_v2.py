"""Python 2.7 compatible in-client probe using explicit low-level file I/O."""

import os
import sys

path = r"C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\python_probe_v2.loaded.txt"
data = "Python version: %s\nLoaded modules: %d\n" % (sys.version, len(sys.modules))
fd = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o644)
try:
    count = os.write(fd, data)
    if count != len(data):
        raise IOError("short probe write: %d of %d bytes" % (count, len(data)))
finally:
    os.close(fd)
