"""Original first in-client probe retained for comparison."""

import sys

path = r"C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\python_probe.loaded.txt"
with open(path, "w") as output:
    output.write("Python version: %s\n" % sys.version)
    output.write("Loaded modules: %d\n" % len(sys.modules))
