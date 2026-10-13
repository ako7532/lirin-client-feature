"""Request a normal close of windows owned by one process ID."""

import ctypes as C
import sys
from ctypes import wintypes as W

pid = int(sys.argv[1])
user32 = C.WinDLL("user32", use_last_error=True)
EnumWindows = user32.EnumWindows
EnumWindows.argtypes = [C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM), W.LPARAM]
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
PostMessageW = user32.PostMessageW
PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
WM_CLOSE = 0x0010

@C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
def callback(hwnd, unused):
    owner = W.DWORD()
    GetWindowThreadProcessId(hwnd, C.byref(owner))
    if owner.value == pid:
        result = PostMessageW(hwnd, WM_CLOSE, 0, 0)
        print("WM_CLOSE", hwnd, "sent" if result else "failed")
    return True

EnumWindows(callback, 0)
