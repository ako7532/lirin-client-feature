#define WIN32_LEAN_AND_MEAN
#include <windows.h>

static DWORD WINAPI WriteLoadMarker(void* module) {
    wchar_t path[MAX_PATH] = {};
    const DWORD length = GetModuleFileNameW(static_cast<HMODULE>(module), path, MAX_PATH);
    if (length == 0 || length > MAX_PATH - 12) return 1;
    lstrcatW(path, L".loaded.txt");

    HANDLE file = CreateFileW(path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
                              nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return 2;
    char marker[96] = {};
    const int size = wsprintfA(marker, "load_probe.dll loaded in PID %lu\r\n", GetCurrentProcessId());
    DWORD written = 0;
    WriteFile(file, marker, static_cast<DWORD>(size), &written, nullptr);
    CloseHandle(file);
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, void*) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        HANDLE thread = CreateThread(nullptr, 0, WriteLoadMarker, module, 0, nullptr);
        if (thread) CloseHandle(thread);
    }
    return TRUE;
}
