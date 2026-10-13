"""Load the local x64 probe DLL into a selected Windows process."""

import argparse
import ctypes as C
import os
import sys
from ctypes import wintypes as W
from pathlib import Path

if sys.platform != "win32" or C.sizeof(C.c_void_p) != 8:
    raise SystemExit("Run this with 64-bit Python on Windows.")

k32 = C.WinDLL("kernel32", use_last_error=True)
SIZE_T = C.c_size_t
LPVOID = C.c_void_p
HANDLE = W.HANDLE

def bind(name, result, *args):
    fn = getattr(k32, name)
    fn.restype = result
    fn.argtypes = args
    return fn

OpenProcess = bind("OpenProcess", HANDLE, W.DWORD, W.BOOL, W.DWORD)
CloseHandle = bind("CloseHandle", W.BOOL, HANDLE)
QueryFullProcessImageNameW = bind("QueryFullProcessImageNameW", W.BOOL, HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD))
VirtualAllocEx = bind("VirtualAllocEx", LPVOID, HANDLE, LPVOID, SIZE_T, W.DWORD, W.DWORD)
VirtualFreeEx = bind("VirtualFreeEx", W.BOOL, HANDLE, LPVOID, SIZE_T, W.DWORD)
WriteProcessMemory = bind("WriteProcessMemory", W.BOOL, HANDLE, LPVOID, LPVOID, SIZE_T, C.POINTER(SIZE_T))
GetModuleHandleW = bind("GetModuleHandleW", LPVOID, W.LPCWSTR)
GetProcAddress = bind("GetProcAddress", LPVOID, LPVOID, C.c_char_p)
CreateRemoteThread = bind("CreateRemoteThread", HANDLE, HANDLE, LPVOID, SIZE_T, LPVOID, LPVOID, W.DWORD, C.POINTER(W.DWORD))
WaitForSingleObject = bind("WaitForSingleObject", W.DWORD, HANDLE, W.DWORD)
GetExitCodeThread = bind("GetExitCodeThread", W.BOOL, HANDLE, C.POINTER(W.DWORD))

PROCESS_CREATE_THREAD = 0x0002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_WRITE = 0x0020
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04
WAIT_OBJECT_0 = 0

def check(value, operation):
    if not value:
        raise OSError(C.get_last_error(), operation)
    return value

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int, help="Target process ID")
    parser.add_argument("--dll", type=Path, default=Path(__file__).with_name("load_probe.dll"))
    parser.add_argument("--allow-test-process", action="store_true", help="Permit a non-Lirin process for a local test")
    args = parser.parse_args()
    dll = args.dll.resolve(strict=True)
    path_bytes = C.create_string_buffer(str(dll).encode("utf-16-le") + b"\0\0")

    access = PROCESS_CREATE_THREAD | PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_OPERATION | PROCESS_VM_WRITE
    process = check(OpenProcess(access, False, args.pid), "OpenProcess")
    address = None
    thread = None
    try:
        image = C.create_unicode_buffer(32768)
        image_size = W.DWORD(len(image))
        check(QueryFullProcessImageNameW(process, 0, image, C.byref(image_size)), "QueryFullProcessImageNameW")
        print("Target:", image.value)
        if not args.allow_test_process:
            expected = Path(r"C:\Program Files (x86)\Lirin\app\Lirin.exe")
            if os.path.normcase(os.path.abspath(image.value)) != os.path.normcase(os.path.abspath(expected)):
                raise ValueError("Target is not the Lirin game executable. Use --allow-test-process only for a local test.")

        address = check(VirtualAllocEx(process, None, len(path_bytes), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE), "VirtualAllocEx")
        written = SIZE_T()
        check(WriteProcessMemory(process, address, C.cast(path_bytes, LPVOID), len(path_bytes), C.byref(written)), "WriteProcessMemory")
        if written.value != len(path_bytes):
            raise RuntimeError("Incomplete DLL path write")

        kernel32 = check(GetModuleHandleW("kernel32.dll"), "GetModuleHandleW")
        load_library = check(GetProcAddress(kernel32, b"LoadLibraryW"), "GetProcAddress")
        thread = check(CreateRemoteThread(process, None, 0, load_library, address, 0, None), "CreateRemoteThread")
        if WaitForSingleObject(thread, 10000) != WAIT_OBJECT_0:
            raise TimeoutError("DLL load did not finish within 10 seconds")
        exit_code = W.DWORD()
        check(GetExitCodeThread(thread, C.byref(exit_code)), "GetExitCodeThread")
        if exit_code.value == 0:
            raise RuntimeError("LoadLibraryW failed in target process")
        print("LoadLibraryW returned a nonzero module handle (low 32 bits).")
        if dll.name.lower() == "load_probe.dll":
            print("Check", str(dll) + ".loaded.txt", "for the target PID.")
        elif dll.name.lower() == "python_loader.dll":
            print("Check", dll.with_name("python_loader.status.txt"), "and python_probe.loaded.txt.")
        elif dll.name.lower() == "python_window_loader.dll":
            print("Check", dll.with_name("python_window_loader.status.txt"), "and python_probe.loaded.txt.")
        elif dll.name.lower() == "python_window_loader_v2.dll":
            print("Check", dll.with_name("python_window_loader.status.txt"), "and python_probe_v2.loaded.txt.")
        elif dll.name.lower() == "python_window_loader_v3.dll":
            print("Check", dll.with_name("python_window_loader.status.txt"), "and python_modules_v3.tsv.")
        elif dll.name.lower() == "python_window_loader_v4.dll":
            print("Check", dll.with_name("python_window_loader.status.txt"), "and python_modules_v4.txt or python_probe_v4.error.txt.")
        elif dll.name.lower() == "python_window_loader_v5.dll":
            print("Check", dll.with_name("python_window_loader.status.txt"), "and python_symbols_v5.txt or python_probe_v5.error.txt.")
        elif dll.name.lower() == "python_window_loader_v6.dll":
            print("Check", dll.with_name("python_window_loader.status.txt"), "and python_ingame_v6.txt or python_probe_v6.error.txt.")
    finally:
        if thread:
            CloseHandle(thread)
        if address:
            VirtualFreeEx(process, address, 0, MEM_RELEASE)
        CloseHandle(process)

if __name__ == "__main__":
    main()
