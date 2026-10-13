"""Verify the probe and injector using a disposable local Python process."""

import subprocess
import sys
import time
from pathlib import Path

here = Path(__file__).resolve().parent
dll = here / "load_probe.dll"
marker = Path(str(dll) + ".loaded.txt")
if marker.exists():
    marker.unlink()

target = subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep(30)"],
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
)
try:
    result = subprocess.run(
        [sys.executable, str(here / "inject.py"), str(target.pid), "--allow-test-process"],
        capture_output=True, text=True, timeout=15,
    )
    print(result.stdout, end="")
    if result.returncode:
        print(result.stderr, file=sys.stderr, end="")
        raise SystemExit(result.returncode)
    for _ in range(30):
        if marker.exists() and str(target.pid) in marker.read_text():
            print("PASS: DLL load marker matches disposable target PID", target.pid)
            break
        time.sleep(0.1)
    else:
        raise SystemExit("FAIL: expected DLL load marker was not written")
finally:
    target.terminate()
    target.wait(timeout=5)
