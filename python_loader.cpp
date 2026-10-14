#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

#ifdef USE_FEATURE_SCRIPT
#define SCRIPT_FILENAME L"client_feature.py"
#else
#define SCRIPT_FILENAME L"python_probe.py"
#endif

#ifdef USE_WINDOW_HOOK
static HMODULE g_module = nullptr;
static HHOOK g_hook = nullptr;
static volatile LONG g_invoked = 0;
static HWND g_game_window = nullptr;
static DWORD g_window_thread = 0;
#define STATUS_FILENAME L"python_window_loader.status.txt"
#ifdef USE_FEATURE_SCRIPT
static volatile LONG g_ready = 0;
static wchar_t g_snapshot_path[MAX_PATH] = {};
static wchar_t g_active_path[MAX_PATH] = {};
static wchar_t g_feature_status_path[MAX_PATH] = {};
static char g_feature_dll_name[MAX_PATH] = {};
static const char* g_snapshot_error = "snapshot not attempted";
static ULONGLONG g_last_snapshot_error = 0;
static constexpr ULONG_PTR RVA_CHARACTER_MANAGER = 0x07A6B450;
static constexpr ULONG_PTR RVA_PLAYER_SINGLETON = 0x07A6B6B0;
static constexpr ULONG_PTR RVA_METIN_QUEUE_ADD_METHOD = 0x072ECA18;
static constexpr ULONG_PTR RVA_METIN_QUEUE_ADD_BINDING = 0x003F6360;
static constexpr ULONG_PTR RVA_PARSE_TUPLE_INTEGER = 0x00897B40;
static constexpr ULONG_PTR RVA_ARGUMENT_ERROR = 0x00897E40;
static constexpr ULONG_PTR RVA_BUILD_VALUE = 0x00A6B650;
static constexpr ULONG_PTR RVA_INTEGER_FORMAT = 0x066E218C;
static constexpr ULONG_PTR RVA_GET_MAIN_ACTOR = 0x003D1DA0;
static constexpr ULONG_PTR RVA_ACTOR_CLICK = 0x003EBDD0;
static void AppendStatus(const wchar_t* status_path, const char* message);
static BYTE* g_game_base = nullptr;
static bool g_native_queue_wrapper_installed = false;

using ParseTupleInteger = char (*)(void*, int, int*);
using ArgumentError = void* (*)(int);
using BuildValue = void* (*)(const char*, ...);
using GetMainActor = void* (*)(void*);
using ActorClick = void (*)(void*, void*, int, char);

static void* NativeMetinQueueAdd(void*, void* args) {
    auto parse_integer = reinterpret_cast<ParseTupleInteger>(g_game_base + RVA_PARSE_TUPLE_INTEGER);
    auto argument_error = reinterpret_cast<ArgumentError>(g_game_base + RVA_ARGUMENT_ERROR);
    auto build_value = reinterpret_cast<BuildValue>(g_game_base + RVA_BUILD_VALUE);
    int vid = 0;
    if (!parse_integer(args, 0, &vid)) return argument_error(0);

    int added = 0;
    __try {
        BYTE* player = *reinterpret_cast<BYTE**>(g_game_base + RVA_PLAYER_SINGLETON);
        if (player) {
            auto get_main_actor = reinterpret_cast<GetMainActor>(g_game_base + RVA_GET_MAIN_ACTOR);
            void* main_actor = get_main_actor(player);
            if (main_actor) {
                auto begin = *reinterpret_cast<DWORD**>(player + 0x4588);
                auto end = *reinterpret_cast<DWORD**>(player + 0x4590);
                size_t before = 0;
                if (begin && end && end >= begin) before = static_cast<size_t>(end - begin);
                auto actor_click = reinterpret_cast<ActorClick>(g_game_base + RVA_ACTOR_CLICK);
                // Zero is the normal left-button actor-click path used by
                // CPythonPlayer::SetMouseState.
                actor_click(player, main_actor, vid, 0);
                begin = *reinterpret_cast<DWORD**>(player + 0x4588);
                end = *reinterpret_cast<DWORD**>(player + 0x4590);
                size_t after = 0;
                if (begin && end && end >= begin) after = static_cast<size_t>(end - begin);
                added = after > before;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        AppendStatus(g_feature_status_path, "native queue wrapper access fault");
        added = 0;
    }
    return build_value(reinterpret_cast<const char*>(g_game_base + RVA_INTEGER_FORMAT), added);
}

static bool InstallNativeMetinQueueWrapper(BYTE* base) {
    void** method = reinterpret_cast<void**>(base + RVA_METIN_QUEUE_ADD_METHOD);
    void* expected = base + RVA_METIN_QUEUE_ADD_BINDING;
    if (*method != expected) {
        AppendStatus(g_feature_status_path,
                     "native queue wrapper skipped: binding already changed");
        return false;
    }
    DWORD old_protection = 0;
    if (!VirtualProtect(method, sizeof(*method), PAGE_READWRITE, &old_protection)) {
        AppendStatus(g_feature_status_path,
                     "native queue wrapper skipped: method table is protected");
        return false;
    }
    *method = reinterpret_cast<void*>(&NativeMetinQueueAdd);
    DWORD ignored = 0;
    VirtualProtect(method, sizeof(*method), old_protection, &ignored);
    g_native_queue_wrapper_installed = true;
    AppendStatus(g_feature_status_path, "native manual queue wrapper installed");
    return true;
}

static void RestoreNativeMetinQueueWrapper() {
    if (!g_native_queue_wrapper_installed || !g_game_base) return;
    void** method = reinterpret_cast<void**>(g_game_base + RVA_METIN_QUEUE_ADD_METHOD);
    if (*method != reinterpret_cast<void*>(&NativeMetinQueueAdd)) return;
    DWORD old_protection = 0;
    if (!VirtualProtect(method, sizeof(*method), PAGE_READWRITE, &old_protection)) return;
    *method = g_game_base + RVA_METIN_QUEUE_ADD_BINDING;
    DWORD ignored = 0;
    VirtualProtect(method, sizeof(*method), old_protection, &ignored);
    g_native_queue_wrapper_installed = false;
}

struct CharacterNode {
    CharacterNode* left;
    CharacterNode* parent;
    CharacterNode* right;
    BYTE color;
    BYTE is_nil;
    BYTE padding[6];
    DWORD vid;
    DWORD padding2;
    void* actor;
};
static_assert(offsetof(CharacterNode, is_nil) == 0x19, "character node sentinel offset changed");
static_assert(offsetof(CharacterNode, vid) == 0x20, "character node VID offset changed");
static_assert(offsetof(CharacterNode, actor) == 0x28, "character node actor offset changed");

static bool IsCurrentFeatureDll() {
    HANDLE file = CreateFileW(g_active_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                              nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    char name[MAX_PATH] = {};
    DWORD count = 0;
    bool read = ReadFile(file, name, MAX_PATH - 1, &count, nullptr) != 0;
    CloseHandle(file);
    if (!read) return false;
    while (count && (name[count - 1] == '\r' || name[count - 1] == '\n')) name[--count] = 0;
    return lstrcmpiA(name, g_feature_dll_name) == 0;
}

static bool WriteVisibleVidsSnapshot() {
    BYTE* base = reinterpret_cast<BYTE*>(GetModuleHandleW(nullptr));
    if (!base) { g_snapshot_error = "snapshot: game base missing"; return false; }
    char output[65536] = {};
    int length = sprintf_s(output, "PID %lu\n", GetCurrentProcessId());
    if (length <= 0) { g_snapshot_error = "snapshot: header formatting failed"; return false; }
    bool valid = true;
    __try {
        BYTE* manager = *reinterpret_cast<BYTE**>(base + RVA_CHARACTER_MANAGER);
        CharacterNode* head = manager ? *reinterpret_cast<CharacterNode**>(manager + 0xf8) : nullptr;
        if (!head) { g_snapshot_error = "snapshot: character manager or tree missing"; valid = false; }
        else {
            CharacterNode* node = head->left;
            for (int count = 0; node && node != head && count < 4096; ++count) {
                if (node->is_nil) break;
                if (node->actor) {
                    int written = sprintf_s(output + length, sizeof(output) - length, "%lu\n", node->vid);
                    if (written <= 0) {
                        g_snapshot_error = "snapshot: output buffer full";
                        valid = false;
                        break;
                    }
                    length += written;
                }
                if (node->right && !node->right->is_nil) {
                    node = node->right;
                    int hops = 0;
                    while (node->left && !node->left->is_nil && hops++ < 4096) node = node->left;
                    if (hops >= 4096) {
                        g_snapshot_error = "snapshot: character tree cycle";
                        valid = false;
                        break;
                    }
                } else {
                    CharacterNode* parent = node->parent;
                    int hops = 0;
                    while (parent && !parent->is_nil && node == parent->right && hops++ < 4096) {
                        node = parent;
                        parent = parent->parent;
                    }
                    if (hops >= 4096) {
                        g_snapshot_error = "snapshot: character tree cycle";
                        valid = false;
                        break;
                    }
                    node = parent;
                }
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        g_snapshot_error = "snapshot: character tree access fault";
        valid = false;
    }
    if (!valid) return false;
    wchar_t temporary[MAX_PATH] = {};
    wcscpy_s(temporary, g_snapshot_path);
    wcscat_s(temporary, L".tmp");
    HANDLE file = CreateFileW(temporary, GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                              FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) { g_snapshot_error = "snapshot: temp file create failed"; return false; }
    DWORD written = 0;
    bool saved = WriteFile(file, output, static_cast<DWORD>(length), &written, nullptr) != 0 &&
                 written == static_cast<DWORD>(length);
    CloseHandle(file);
    if (!saved) { g_snapshot_error = "snapshot: temp file write failed"; return false; }
    if (!MoveFileExW(temporary, g_snapshot_path, MOVEFILE_REPLACE_EXISTING)) {
        g_snapshot_error = "snapshot: atomic replace failed";
        return false;
    }
    return true;
}
#endif
#else
#define STATUS_FILENAME L"python_loader.status.txt"
#endif

// RVAs from the analyzed Lirin game EXE (SHA-256 DBD69CAD...D3636D72F2).
static constexpr ULONG_PTR RVA_GIL_ENSURE = 0x00AB1520;
static constexpr ULONG_PTR RVA_GIL_RELEASE = 0x00AB15D0;
static constexpr ULONG_PTR RVA_IMPORT_ADD_MODULE = 0x00ABED90;
static constexpr ULONG_PTR RVA_MODULE_GET_DICT = 0x00AA9820;
static constexpr ULONG_PTR RVA_RUN_STRING_FLAGS = 0x00AB5E60;
static constexpr ULONG_PTR RVA_AUTO_INTERPRETER_STATE = 0x07B9AC88;
#ifdef USE_WINDOW_HOOK
static constexpr ULONG_PTR RVA_CURRENT_THREAD_STATE = 0x07B9AC70;
static constexpr ULONG_PTR RVA_AUTO_TLS_KEY = 0x07B9AC90;
static constexpr ULONG_PTR RVA_TLS_GET_VALUE = 0x00ACA170;
#endif
static constexpr DWORD EXPECTED_TIMESTAMP = 0x6ACA943D;
static constexpr DWORD EXPECTED_IMAGE_SIZE = 0x094C1000;

using GilEnsure = int (*)();
using GilRelease = void (*)(int);
using ImportAddModule = void* (*)(const char*);
using ModuleGetDict = void* (*)(void*);
using RunStringFlags = void* (*)(const char*, int, void*, void*, void*);

static void AppendStatus(const wchar_t* status_path, const char* message) {
    HANDLE file = CreateFileW(status_path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
                              nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return;
    char line[320] = {};
    int size = sprintf_s(line, "PID %lu: %s\r\n", GetCurrentProcessId(), message);
    if (size > 0) {
        DWORD written = 0;
        WriteFile(file, line, static_cast<DWORD>(size), &written, nullptr);
    }
    CloseHandle(file);
}

static DWORD WINAPI RunProbe(void* module_ptr) {
    wchar_t dll_path[MAX_PATH] = {};
    DWORD length = GetModuleFileNameW(static_cast<HMODULE>(module_ptr), dll_path, MAX_PATH);
    if (!length || length >= MAX_PATH - 32) return 1;
    wchar_t* slash = wcsrchr(dll_path, L'\\');
    if (!slash) return 2;
    *(slash + 1) = L'\0';

    wchar_t status_path[MAX_PATH] = {};
    wchar_t script_path[MAX_PATH] = {};
    wcscpy_s(status_path, dll_path);
    wcscat_s(status_path, STATUS_FILENAME);
    wcscpy_s(script_path, dll_path);
    wcscat_s(script_path, SCRIPT_FILENAME);
    AppendStatus(status_path, "DLL loaded");

    HMODULE game = GetModuleHandleW(nullptr);
    if (!game) { AppendStatus(status_path, "game module missing"); return 3; }
    auto dos = reinterpret_cast<IMAGE_DOS_HEADER*>(game);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) { AppendStatus(status_path, "invalid DOS header"); return 4; }
    auto nt = reinterpret_cast<IMAGE_NT_HEADERS64*>(reinterpret_cast<BYTE*>(game) + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE ||
        nt->FileHeader.TimeDateStamp != EXPECTED_TIMESTAMP ||
        nt->OptionalHeader.SizeOfImage != EXPECTED_IMAGE_SIZE) {
        AppendStatus(status_path, "EXE build mismatch; Python calls skipped");
        return 5;
    }
    AppendStatus(status_path, "EXE build matched");

    BYTE* base = reinterpret_cast<BYTE*>(game);
    auto auto_state = reinterpret_cast<void* volatile*>(base + RVA_AUTO_INTERPRETER_STATE);
    for (int i = 0; i < 100 && !*auto_state; ++i) Sleep(100);
    if (!*auto_state) { AppendStatus(status_path, "Python interpreter not initialized"); return 6; }

    DWORD attributes = GetFileAttributesW(script_path);
    if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & FILE_ATTRIBUTE_DIRECTORY)) {
        AppendStatus(status_path, "Python script missing beside DLL");
        return 7;
    }

    char script_path_utf8[MAX_PATH * 3] = {};
    if (!WideCharToMultiByte(CP_UTF8, 0, script_path, -1, script_path_utf8,
                             sizeof(script_path_utf8), nullptr, nullptr)) {
        AppendStatus(status_path, "script path conversion failed");
        return 8;
    }
    for (char* c = script_path_utf8; *c; ++c) {
        if (*c == '\\') *c = '/';
        if (*c == '\'') { AppendStatus(status_path, "quote in script path unsupported"); return 9; }
    }
    auto ensure = reinterpret_cast<GilEnsure>(base + RVA_GIL_ENSURE);
    auto release = reinterpret_cast<GilRelease>(base + RVA_GIL_RELEASE);
    auto add_module = reinterpret_cast<ImportAddModule>(base + RVA_IMPORT_ADD_MODULE);
    auto get_dict = reinterpret_cast<ModuleGetDict>(base + RVA_MODULE_GET_DICT);
    auto run_string = reinterpret_cast<RunStringFlags>(base + RVA_RUN_STRING_FLAGS);
#ifdef USE_WINDOW_HOOK
    auto tls_get = reinterpret_cast<void* (*)(ULONG_PTR)>(base + RVA_TLS_GET_VALUE);
    ULONG_PTR tls_key = *reinterpret_cast<DWORD*>(base + RVA_AUTO_TLS_KEY);
    void* this_state = tls_get(tls_key);
    void* current_state = *reinterpret_cast<void**>(base + RVA_CURRENT_THREAD_STATE);
    if (!this_state || this_state != current_state) {
        AppendStatus(status_path, "window thread does not own Python GIL; call skipped");
        return 12;
    }
    AppendStatus(status_path, "window thread owns Python GIL");
#endif
    AppendStatus(status_path, "waiting for Python GIL");
    int gil_state = ensure();
    AppendStatus(status_path, "Python GIL acquired");
#ifdef USE_FEATURE_SCRIPT
    g_game_base = base;
    InstallNativeMetinQueueWrapper(base);
    char source[MAX_PATH * 3 + 120] = {};
    if (sprintf_s(source,
                  "import __main__; __main__._lirin_native_queue_wrapper=%s; execfile(r'%s')",
                  g_native_queue_wrapper_installed ? "True" : "False", script_path_utf8) <= 0) {
        RestoreNativeMetinQueueWrapper();
        release(gil_state);
        AppendStatus(status_path, "Python source construction failed");
        return 10;
    }
#else
    char source[MAX_PATH * 3 + 32] = {};
    if (sprintf_s(source, "execfile(r'%s')", script_path_utf8) <= 0) {
        release(gil_state);
        AppendStatus(status_path, "Python source construction failed");
        return 10;
    }
#endif
    void* main_module = add_module("__main__");
    void* main_dict = main_module ? get_dict(main_module) : nullptr;
    void* result = main_dict ? run_string(source, 0x101, main_dict, main_dict, nullptr) : nullptr;
    AppendStatus(status_path, result ? "Python script returned successfully" : "Python call failed");
#ifdef USE_FEATURE_SCRIPT
    if (!result) RestoreNativeMetinQueueWrapper();
#endif
    // A single probe run leaves one result reference; avoid guessing a deallocator address.
    release(gil_state);
    AppendStatus(status_path, "Python GIL released");
    return result ? 0 : 11;
}

#ifdef USE_WINDOW_HOOK
static BOOL CALLBACK FindGameWindow(HWND window, LPARAM) {
    DWORD process_id = 0;
    DWORD thread_id = GetWindowThreadProcessId(window, &process_id);
    if (process_id != GetCurrentProcessId() || !IsWindowVisible(window)) return TRUE;
    wchar_t title[128] = {};
    GetWindowTextW(window, title, 128);
    if (lstrcmpiW(title, L"Lirin") == 0) {
        g_game_window = window;
        g_window_thread = thread_id;
        return FALSE;
    }
    return TRUE;
}

#ifdef USE_FEATURE_SCRIPT
static DWORD WINAPI FeatureWakeThread(void*) {
    AppendStatus(g_feature_status_path, "feature wake thread started");
    if (!g_ready) AppendStatus(g_feature_status_path, "feature wake skipped: script not ready");
    if (g_ready && !IsCurrentFeatureDll())
        AppendStatus(g_feature_status_path, "feature wake skipped: active DLL marker mismatch");
    while (g_ready && IsWindow(g_game_window) && IsCurrentFeatureDll()) {
        // WH_CALLWNDPROC may not receive another message after injection. Keep
        // the read-only entity snapshot independent of subsequent UI messages.
        if (!WriteVisibleVidsSnapshot() && GetTickCount64() - g_last_snapshot_error >= 5000) {
            g_last_snapshot_error = GetTickCount64();
            AppendStatus(g_feature_status_path, g_snapshot_error);
        }
        Sleep(1000);
    }
    return 0;
}
#endif

static LRESULT CALLBACK WindowHook(int code, WPARAM wparam, LPARAM lparam) {
    if (code >= 0 && InterlockedCompareExchange(&g_invoked, 1, 0) == 0) {
        DWORD probe_result = RunProbe(g_module);
#ifdef USE_FEATURE_SCRIPT
        if (probe_result != 0) {
            HHOOK hook = g_hook;
            g_hook = nullptr;
            LRESULT next = CallNextHookEx(hook, code, wparam, lparam);
            if (hook) UnhookWindowsHookEx(hook);
            return next;
        }
        InterlockedExchange(&g_ready, 1);
        // The feature snapshot has its own worker thread.  Keeping this hook
        // installed would make every later window message pass through the
        // injected DLL and synchronously re-read the marker file for no gain.
        HHOOK hook = g_hook;
        g_hook = nullptr;
        LRESULT next = CallNextHookEx(hook, code, wparam, lparam);
        if (hook) UnhookWindowsHookEx(hook);
        return next;
#else
        (void)probe_result;
        HHOOK hook = g_hook;
        g_hook = nullptr;
        LRESULT next = CallNextHookEx(hook, code, wparam, lparam);
        if (hook) UnhookWindowsHookEx(hook);
        return next;
#endif
    }
#ifdef USE_FEATURE_SCRIPT
    if (code >= 0 && g_ready) {
        if (!IsCurrentFeatureDll()) {
            HHOOK hook = g_hook;
            g_hook = nullptr;
            LRESULT next = CallNextHookEx(hook, code, wparam, lparam);
            if (hook) UnhookWindowsHookEx(hook);
            return next;
        }
    }
#endif
    return CallNextHookEx(g_hook, code, wparam, lparam);
}

static DWORD WINAPI InstallWindowHook(void* module_ptr) {
    wchar_t dll_path[MAX_PATH] = {};
    if (!GetModuleFileNameW(static_cast<HMODULE>(module_ptr), dll_path, MAX_PATH)) return 1;
    wchar_t* slash = wcsrchr(dll_path, L'\\');
    if (!slash || dll_path + MAX_PATH - slash < 34) return 2;
#ifdef USE_FEATURE_SCRIPT
    if (!WideCharToMultiByte(CP_ACP, 0, slash + 1, -1, g_feature_dll_name,
                             sizeof(g_feature_dll_name), nullptr, nullptr)) return 6;
#endif
    *(slash + 1) = L'\0';
#ifdef USE_FEATURE_SCRIPT
    wcscpy_s(g_snapshot_path, dll_path);
    wcscat_s(g_snapshot_path, L"client_feature_vids.txt");
    wcscpy_s(g_active_path, dll_path);
    wcscat_s(g_active_path, L"client_feature_active.txt");
    wcscpy_s(g_feature_status_path, dll_path);
    wcscat_s(g_feature_status_path, STATUS_FILENAME);
#endif
    wcscat_s(dll_path, STATUS_FILENAME);
    AppendStatus(dll_path, "window hook setup started");
    for (int i = 0; i < 50 && !g_game_window; ++i) {
        EnumWindows(FindGameWindow, 0);
        if (!g_game_window) Sleep(100);
    }
    if (!g_game_window) { AppendStatus(dll_path, "visible Lirin window not found"); return 3; }
    g_hook = SetWindowsHookExW(WH_CALLWNDPROC, WindowHook, static_cast<HMODULE>(module_ptr), g_window_thread);
    if (!g_hook) { AppendStatus(dll_path, "SetWindowsHookExW failed"); return 4; }
    AppendStatus(dll_path, "window hook installed; sending wake message");
    DWORD_PTR ignored = 0;
    if (!SendMessageTimeoutW(g_game_window, WM_NULL, 0, 0, SMTO_ABORTIFHUNG, 3000, &ignored)) {
        AppendStatus(dll_path, "SendMessageTimeoutW failed or timed out");
        return 5;
    }
#ifdef USE_FEATURE_SCRIPT
    HANDLE wake = CreateThread(nullptr, 0, FeatureWakeThread, nullptr, 0, nullptr);
    if (wake) CloseHandle(wake);
#endif
    return 0;
}
#endif

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, void*) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
#ifdef USE_WINDOW_HOOK
        g_module = module;
        HANDLE thread = CreateThread(nullptr, 0, InstallWindowHook, module, 0, nullptr);
#else
        HANDLE thread = CreateThread(nullptr, 0, RunProbe, module, 0, nullptr);
#endif
        if (thread) CloseHandle(thread);
    }
    return TRUE;
}
