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
static constexpr ULONG_PTR RVA_CHARACTER_MANAGER = 0x07CCAB10;
static constexpr ULONG_PTR RVA_PLAYER_SINGLETON = 0x07CCAF00;
static constexpr ULONG_PTR RVA_METIN_QUEUE_ADD_METHOD = 0x07525778;
static constexpr ULONG_PTR RVA_METIN_QUEUE_ADD_BINDING = 0x004011C0;
static constexpr ULONG_PTR RVA_PARSE_TUPLE_INTEGER = 0x008C7020;
static constexpr ULONG_PTR RVA_ARGUMENT_ERROR = 0x008C7320;
static constexpr ULONG_PTR RVA_INPUT_RECORDER = 0x07CCB198;
static constexpr ULONG_PTR RVA_APP_GLOBAL = 0x07CD3168;
static void AppendStatus(const wchar_t* status_path, const char* message);
static BYTE* g_game_base = nullptr;

// The character-manager red-black tree node (std::set), the same tree the
// entity snapshot and chr.GetProjectPosition walk.  Fields verified against
// the loader's own snapshot walk.
struct CharacterNode {
    CharacterNode* left;   // +0x00
    CharacterNode* parent; // +0x08
    CharacterNode* right;  // +0x10
    BYTE color;            // +0x18
    BYTE is_nil;           // +0x19
    BYTE padding[6];       // +0x1A..+0x1F
    DWORD vid;             // +0x20
    DWORD padding2;        // +0x24
    void* actor;           // +0x28
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

// RVAs from the analyzed Lirin game EXE (SHA-256 8B6F5EA9...A75A0, build 2026-10-16).
static constexpr ULONG_PTR RVA_GIL_ENSURE = 0x00AF2750;
static constexpr ULONG_PTR RVA_GIL_RELEASE = 0x00AF2800;
static constexpr ULONG_PTR RVA_IMPORT_ADD_MODULE = 0x00B0D5D0;
static constexpr ULONG_PTR RVA_MODULE_GET_DICT = 0x00B07000;
static constexpr ULONG_PTR RVA_RUN_STRING_FLAGS = 0x00AF7090;
static constexpr ULONG_PTR RVA_AUTO_INTERPRETER_STATE = 0x07DFB058;
#ifdef USE_WINDOW_HOOK
static constexpr ULONG_PTR RVA_CURRENT_THREAD_STATE = 0x07DFB040;
static constexpr ULONG_PTR RVA_AUTO_TLS_KEY = 0x07DFB060;
static constexpr ULONG_PTR RVA_TLS_GET_VALUE = 0x00B069C0;
#endif
static constexpr DWORD EXPECTED_TIMESTAMP = 0x6AD21E5A;
static constexpr DWORD EXPECTED_IMAGE_SIZE = 0x09735000;

using GilEnsure = int (*)();
using GilRelease = void (*)(int);
using ImportAddModule = void* (*)(const char*);
using ModuleGetDict = void* (*)(void*);
using RunStringFlags = void* (*)(const char*, int, void*, void*, void*);

// ---------------------------------------------------------------------------
// Native Hunter observer (read-only private module `_lirin_hunter_native`).
// Every RVA below is verified in handovers/HUNTER_NATIVE_API_CONTRACT.md and
// is used only as `g_game_base + RVA`.
// ---------------------------------------------------------------------------
#ifdef USE_FEATURE_SCRIPT

static constexpr ULONG_PTR RVA_GET_ACTOR_BY_VID = 0x05353B0;   // FUN_1405353b0 (manager, vid)
static constexpr ULONG_PTR RVA_QUEUE_ELIGIBILITY = 0x003ED370; // FUN_1403ed370 (player, actor)

static constexpr ULONG_PTR RVA_INIT_MODULE4 = 0x00AA5ED0;
static constexpr ULONG_PTR RVA_DICT_NEW = 0x00AE8AE0;
static constexpr ULONG_PTR RVA_DICT_SET_ITEM_STRING = 0x00AE8D30;
static constexpr ULONG_PTR RVA_TUPLE_NEW = 0x00AE0F10;
static constexpr ULONG_PTR RVA_INT_FROM_LONG = 0x00ACE140;
static constexpr ULONG_PTR RVA_LONG_FROM_ULONGLONG = 0x00AD2390;
static constexpr ULONG_PTR RVA_STRING_FROM_STRING = 0x00ADB610;
static constexpr ULONG_PTR RVA_PY_NONE = 0x075437D8;

static constexpr ptrdiff_t PLAYER_QUEUE_BEGIN_OFFSET = 0x4588;
static constexpr ptrdiff_t PLAYER_QUEUE_END_OFFSET = 0x4590;
static constexpr ptrdiff_t PLAYER_QUEUE_CAP_OFFSET = 0x4598;
static constexpr ptrdiff_t PLAYER_QUEUE_ENABLED_OFFSET = 0x457C;

static constexpr size_t HUNTER_QUEUE_GUARD = 1024;
static constexpr int HUNTER_OBSERVER_API_VERSION = 1;

struct PyMethodDefNative {
    const char* ml_name;
    void* ml_meth;
    int ml_flags;
    const char* ml_doc;
};
#define METH_VARARGS 0x0001
#define METH_NOARGS  0x0004

using InitModule4Fn = void* (*)(const char*, void*, const char*, void*, int);
using DictNewFn = void* (*)();
using DictSetItemStringFn = int (*)(void*, const char*, void*);
using TupleNewFn = void* (*)(long long);
using IntFromLongFn = void* (*)(long);
using LongFromULongLongFn = void* (*)(unsigned long long);
using StringFromStringFn = void* (*)(const char*);
using ParseTupleIntegerFn = char (*)(void*, int, int*);
using ArgumentErrorFn = void* (*)(int);
using GetActorByVidFn = void* (*)(void*, unsigned int);
using EligibilityFn = int (*)(void*, void*);

// Verified CPython 2.7 object header: ob_refcnt @0, ob_type @8; tp_dealloc at
// ob_type + 0x30 (the same layout every decompiled DECREF site uses).
struct PyObjectHeader { long long refcnt; void* type; };

static void ObserverIncref(void* op) {
    if (op) ++reinterpret_cast<PyObjectHeader*>(op)->refcnt;
}

static void ObserverDecref(void* op) {
    if (!op) return;
    PyObjectHeader* h = reinterpret_cast<PyObjectHeader*>(op);
    if (--h->refcnt == 0) {
        void* type = h->type;
        void (*dealloc)(void*) = *reinterpret_cast<void(**)(void*)>(
            reinterpret_cast<char*>(type) + 0x30);
        dealloc(op);
    }
}

// Copy the authoritative queue VIDs into a bounded buffer.  Returns the element
// count, or -1 when the state is unreadable/invalid (never "empty").  The only
// accepted empty state is begin == end == capacity == nullptr.  Enforces
// 4-byte alignment, begin <= end <= capacity, and rechecks begin/end/capacity
// after the copy.
static long long ReadQueueVids(BYTE* player, unsigned int* out, size_t cap) {
    __try {
        DWORD* begin = *reinterpret_cast<DWORD**>(player + PLAYER_QUEUE_BEGIN_OFFSET);
        DWORD* end = *reinterpret_cast<DWORD**>(player + PLAYER_QUEUE_END_OFFSET);
        DWORD* capacity = *reinterpret_cast<DWORD**>(player + PLAYER_QUEUE_CAP_OFFSET);
        // Reject any pointer that is not 4-byte aligned.
        if ((reinterpret_cast<uintptr_t>(begin) % sizeof(DWORD)) != 0 ||
            (reinterpret_cast<uintptr_t>(end) % sizeof(DWORD)) != 0 ||
            (reinterpret_cast<uintptr_t>(capacity) % sizeof(DWORD)) != 0) return -1;
        // Only the all-null triple is a valid empty vector.
        if (begin == nullptr || end == nullptr || capacity == nullptr) {
            if (begin == nullptr && end == nullptr && capacity == nullptr) return 0;
            return -1;
        }
        if (end < begin || capacity < end) return -1;
        size_t length = reinterpret_cast<size_t>(end) - reinterpret_cast<size_t>(begin);
        size_t capacity_len = reinterpret_cast<size_t>(capacity) - reinterpret_cast<size_t>(begin);
        if (length % sizeof(DWORD) != 0 || capacity_len % sizeof(DWORD) != 0) return -1;
        length /= sizeof(DWORD);
        capacity_len /= sizeof(DWORD);
        if (length > HUNTER_QUEUE_GUARD || capacity_len > HUNTER_QUEUE_GUARD) return -1;
        if (length > cap) return -1;
        for (size_t i = 0; i < length; ++i) out[i] = static_cast<unsigned int>(begin[i]);
        // Recheck metadata for a concurrent change.
        if (*reinterpret_cast<DWORD**>(player + PLAYER_QUEUE_BEGIN_OFFSET) != begin ||
            *reinterpret_cast<DWORD**>(player + PLAYER_QUEUE_END_OFFSET) != end ||
            *reinterpret_cast<DWORD**>(player + PLAYER_QUEUE_CAP_OFFSET) != capacity) return -1;
        return static_cast<long long>(length);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return -1;
    }
}

// Set the standard dict keys for a valid/error result.  Values are borrowed
// (the caller keeps ownership) except where noted; this helper does not steal.
static void FillResultStatus(void* dict, bool valid, const char* error) {
    auto dict_set = reinterpret_cast<DictSetItemStringFn>(g_game_base + RVA_DICT_SET_ITEM_STRING);
    auto int_from_long = reinterpret_cast<IntFromLongFn>(g_game_base + RVA_INT_FROM_LONG);
    void* valid_obj = int_from_long(valid ? 1 : 0);
    dict_set(dict, "valid", valid_obj);
    ObserverDecref(valid_obj);
    if (error == nullptr) {
        void* none = reinterpret_cast<void*>(g_game_base + RVA_PY_NONE);
        ObserverIncref(none);
        dict_set(dict, "error", none);
        ObserverDecref(none);
    } else {
        auto str_from_string = reinterpret_cast<StringFromStringFn>(g_game_base + RVA_STRING_FROM_STRING);
        void* err_obj = str_from_string(error);
        dict_set(dict, "error", err_obj);
        ObserverDecref(err_obj);
    }
}

static void* ObserverNowMs(void*, void*) {
    auto long_from_ulonglong = reinterpret_cast<LongFromULongLongFn>(g_game_base + RVA_LONG_FROM_ULONGLONG);
    return long_from_ulonglong(static_cast<unsigned long long>(GetTickCount64()));
}

// Convert the native player address to an opaque Python integer token.  The raw
// C++ pointer is NEVER inserted into a Python container as a PyObject* (that
// would let refcounting write into the player object).  A null cookie yields
// None.
static void SetPlayerCookie(void* dict, void* cookie) {
    auto dict_set = reinterpret_cast<DictSetItemStringFn>(g_game_base + RVA_DICT_SET_ITEM_STRING);
    auto long_from_ulonglong = reinterpret_cast<LongFromULongLongFn>(g_game_base + RVA_LONG_FROM_ULONGLONG);
    void* token = nullptr;
    if (cookie != nullptr) {
        token = long_from_ulonglong(static_cast<unsigned long long>(
            reinterpret_cast<uintptr_t>(cookie)));
    } else {
        token = reinterpret_cast<void*>(g_game_base + RVA_PY_NONE);
        ObserverIncref(token);
    }
    dict_set(dict, "player_cookie", token);
    ObserverDecref(token);
}

static void* ObserverSnapshot(void*, void*) {
    auto dict_new = reinterpret_cast<DictNewFn>(g_game_base + RVA_DICT_NEW);
    auto dict_set = reinterpret_cast<DictSetItemStringFn>(g_game_base + RVA_DICT_SET_ITEM_STRING);
    auto tuple_new = reinterpret_cast<TupleNewFn>(g_game_base + RVA_TUPLE_NEW);
    auto int_from_long = reinterpret_cast<IntFromLongFn>(g_game_base + RVA_INT_FROM_LONG);
    auto long_from_ulonglong = reinterpret_cast<LongFromULongLongFn>(g_game_base + RVA_LONG_FROM_ULONGLONG);

    void* dict = dict_new();
    if (dict == nullptr) return nullptr;

    unsigned int vids[HUNTER_QUEUE_GUARD];
    long long length = -1;
    int enabled = 0;
    int max_size = 0;
    int binding_ok = 0;
    bool valid = false;
    const char* error = "unreadable";
    void* cookie = nullptr;

    __try {
        BYTE* player = *reinterpret_cast<BYTE**>(g_game_base + RVA_PLAYER_SINGLETON);
        if (player == nullptr) {
            error = "player singleton missing";
        } else {
            cookie = player;
            void* method = *reinterpret_cast<void**>(g_game_base + RVA_METIN_QUEUE_ADD_METHOD);
            binding_ok = (method == reinterpret_cast<void*>(g_game_base + RVA_METIN_QUEUE_ADD_BINDING)) ? 1 : 0;
            enabled = (*reinterpret_cast<char*>(player + PLAYER_QUEUE_ENABLED_OFFSET) != 0) ? 1 : 0;
            length = ReadQueueVids(player, vids, HUNTER_QUEUE_GUARD);
            if (length < 0) {
                error = "queue vector unreadable";
            } else {
                // max_size is not derived here; the gateway sources it from the
                // stock player.MetinQueueGetMaxSize() binding (the verified
                // stock query).  max_size stays 0 in the raw snapshot.
                valid = true;
                error = nullptr;
            }
            // Recheck the singleton did not change during the copy.
            if (valid && *reinterpret_cast<BYTE**>(g_game_base + RVA_PLAYER_SINGLETON) != player) {
                valid = false;
                length = -1;
                error = "player singleton changed";
                cookie = nullptr;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        valid = false;
        length = -1;
        error = "access fault";
        cookie = nullptr;
    }

    // build the vids tuple (empty when invalid/unreadable)
    void* tup = tuple_new(length > 0 ? length : 0);
    if (tup == nullptr) { ObserverDecref(dict); return nullptr; }
    if (length > 0) {
        for (long long i = 0; i < length; ++i) {
            void* vid_obj = int_from_long(static_cast<long>(vids[i]));
            if (vid_obj == nullptr) { ObserverDecref(tup); ObserverDecref(dict); return nullptr; }
            // PyTuple_SET_ITEM semantics: steal the new reference.
            reinterpret_cast<void**>(tup)[3 + i] = vid_obj;
        }
    }

    void* api_obj = int_from_long(HUNTER_OBSERVER_API_VERSION);
    dict_set(dict, "api_version", api_obj);
    ObserverDecref(api_obj);

    FillResultStatus(dict, valid, error);

    SetPlayerCookie(dict, cookie);
    dict_set(dict, "vids", tup);
    ObserverDecref(tup);

    void* enabled_obj = int_from_long(enabled);
    dict_set(dict, "enabled", enabled_obj);
    ObserverDecref(enabled_obj);

    void* max_obj = int_from_long(max_size);
    dict_set(dict, "max_size", max_obj);
    ObserverDecref(max_obj);

    void* tick_obj = long_from_ulonglong(static_cast<unsigned long long>(GetTickCount64()));
    dict_set(dict, "observed_tick_ms", tick_obj);
    ObserverDecref(tick_obj);

    void* binding_obj = int_from_long(binding_ok);
    dict_set(dict, "stock_binding_ok", binding_obj);
    ObserverDecref(binding_obj);

    return dict;
}

static void* ObserverAdmission(void*, void* args) {
    auto parse_integer = reinterpret_cast<ParseTupleIntegerFn>(g_game_base + RVA_PARSE_TUPLE_INTEGER);
    auto argument_error = reinterpret_cast<ArgumentErrorFn>(g_game_base + RVA_ARGUMENT_ERROR);
    auto dict_new = reinterpret_cast<DictNewFn>(g_game_base + RVA_DICT_NEW);
    auto dict_set = reinterpret_cast<DictSetItemStringFn>(g_game_base + RVA_DICT_SET_ITEM_STRING);
    auto int_from_long = reinterpret_cast<IntFromLongFn>(g_game_base + RVA_INT_FROM_LONG);
    auto get_actor = reinterpret_cast<GetActorByVidFn>(g_game_base + RVA_GET_ACTOR_BY_VID);
    auto eligibility = reinterpret_cast<EligibilityFn>(g_game_base + RVA_QUEUE_ELIGIBILITY);

    int vid = 0;
    if (!parse_integer(args, 0, &vid)) return argument_error(0);

    void* dict = dict_new();
    if (dict == nullptr) return nullptr;

    bool valid = false;
    int eligible = 0;
    const char* reason = "unreadable";
    void* cookie = nullptr;

    __try {
        if (vid <= 0) {
            valid = true;
            eligible = 0;
            reason = "zero or negative VID";
        } else {
            BYTE* player = *reinterpret_cast<BYTE**>(g_game_base + RVA_PLAYER_SINGLETON);
            BYTE* manager = *reinterpret_cast<BYTE**>(g_game_base + RVA_CHARACTER_MANAGER);
            if (player == nullptr || manager == nullptr) {
                reason = "singleton missing";
            } else {
                cookie = player;
                void* actor = get_actor(manager, static_cast<unsigned int>(vid));
                if (actor == nullptr) {
                    valid = true;
                    eligible = 0;
                    reason = "actor unresolved";
                } else {
                    valid = true;
                    eligible = eligibility(player, actor) != 0 ? 1 : 0;
                    reason = eligible ? nullptr : "native predicate rejected";
                }
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        valid = false;
        eligible = 0;
        reason = "access fault";
        cookie = nullptr;
    }

    FillResultStatus(dict, valid, reason);

    void* eligible_obj = int_from_long(eligible);
    dict_set(dict, "eligible", eligible_obj);
    ObserverDecref(eligible_obj);

    SetPlayerCookie(dict, cookie);

    return dict;
}

static void* ObserverAuditStatus(void*, void*) {
    auto dict_new = reinterpret_cast<DictNewFn>(g_game_base + RVA_DICT_NEW);
    auto dict_set = reinterpret_cast<DictSetItemStringFn>(g_game_base + RVA_DICT_SET_ITEM_STRING);
    auto int_from_long = reinterpret_cast<IntFromLongFn>(g_game_base + RVA_INT_FROM_LONG);
    auto long_from_ulonglong = reinterpret_cast<LongFromULongLongFn>(g_game_base + RVA_LONG_FROM_ULONGLONG);

    void* dict = dict_new();
    if (dict == nullptr) return nullptr;

    bool valid = false;
    const char* error = "unreadable";
    int recorder_enabled = 0;
    int sample_ms = 0;
    int flush_ms = 0;
    int app_active = 0;

    __try {
        BYTE* recorder = *reinterpret_cast<BYTE**>(g_game_base + RVA_INPUT_RECORDER);
        BYTE* app = *reinterpret_cast<BYTE**>(g_game_base + RVA_APP_GLOBAL);
        if (recorder == nullptr || app == nullptr) {
            error = "recorder or app singleton missing";
        } else {
            recorder_enabled = (recorder[8] != 0) ? 1 : 0;
            sample_ms = static_cast<int>(*reinterpret_cast<WORD*>(recorder + 10));
            flush_ms = static_cast<int>(*reinterpret_cast<WORD*>(recorder + 12));
            app_active = static_cast<int>(app[0x20]);
            valid = true;
            error = nullptr;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        valid = false;
        error = "access fault";
    }

    FillResultStatus(dict, valid, error);

    void* tick_obj = long_from_ulonglong(static_cast<unsigned long long>(GetTickCount64()));
    dict_set(dict, "observed_tick_ms", tick_obj);
    ObserverDecref(tick_obj);

    void* rec_obj = int_from_long(recorder_enabled);
    dict_set(dict, "recorder_enabled", rec_obj);
    ObserverDecref(rec_obj);

    void* sample_obj = int_from_long(sample_ms);
    dict_set(dict, "sample_ms", sample_obj);
    ObserverDecref(sample_obj);

    void* flush_obj = int_from_long(flush_ms);
    dict_set(dict, "flush_ms", flush_obj);
    ObserverDecref(flush_obj);

    void* active_obj = int_from_long(app_active);
    dict_set(dict, "app_active", active_obj);
    ObserverDecref(active_obj);

    return dict;
}

static PyMethodDefNative g_hunter_methods[] = {
    {"now_ms",       reinterpret_cast<void*>(&ObserverNowMs),      METH_NOARGS,  "monotonic milliseconds (GetTickCount64)"},
    {"snapshot",     reinterpret_cast<void*>(&ObserverSnapshot),   METH_NOARGS,  "authoritative queue snapshot (read-only)"},
    {"admission",    reinterpret_cast<void*>(&ObserverAdmission),  METH_VARARGS, "full native queue eligibility for a VID"},
    {"audit_status", reinterpret_cast<void*>(&ObserverAuditStatus), METH_NOARGS, "effective recorder/app-active status (read-only)"},
    {nullptr, nullptr, 0, nullptr},
};

static bool RegisterHunterNativeObserver() {
    auto init_module4 = reinterpret_cast<InitModule4Fn>(g_game_base + RVA_INIT_MODULE4);
    void* module = init_module4("_lirin_hunter_native", g_hunter_methods,
                                "Read-only Hunter queue observation (API v1)",
                                nullptr, 0x3f5);
    return module != nullptr;
}

// Explicit experiment, separate from the read-only observer and stock binding.
// Calls the native event producer only; no UI/button/picker/configuration writes.
static constexpr ULONG_PTR RVA_RECORDER_EXPLICIT_EVENT = 0x00497840;
static constexpr ULONG_PTR RVA_GAME_UI_GLOBAL = 0x07CCAB50;
static constexpr ULONG_PTR RVA_GAME_STREAM_GLOBAL = 0x07CCAA18;
using RecorderExplicitEventFn = void (*)(void*, unsigned char, int, int);

struct RecorderPairContext {
    BYTE* recorder;
    BYTE* player;
    BYTE* app;
    BYTE* game;
    BYTE* stream;
    void* transport;
    WORD sample_ms;
    WORD flush_ms;
    DWORD sample_due;
    DWORD flush_due;
    int width;
    int height;
    int x;
    int y;
    int active;
    int requested_vid;
};
static RecorderPairContext g_recorder_pair = {};
static bool g_recorder_pair_pending = false;
static bool g_recorder_pair_failed = false;
static DWORD g_recorder_pair_thread = 0;

static void LogRecorderPair(const char* phase, int status,
                            const RecorderPairContext& context) {
    char line[256] = {};
    if (status == 0) {
        sprintf_s(line, "recorder_pair %s status=0 requested_vid=%d; "
                  "recorder disabled, no event produced", phase, context.requested_vid);
        AppendStatus(g_feature_status_path, line);
        return;
    }
    sprintf_s(line,
        "recorder_pair %s status=%d requested_vid=%d context_x=%d context_y=%d app_active=%d; "
        "producer return is not delivery or manual-click equivalence",
        phase, status, context.requested_vid, context.x, context.y, context.active);
    AppendStatus(g_feature_status_path, line);
}

// 1=enabled context, 0=disabled (no producer call), negative=reject.
static int ReadRecorderPairContext(RecorderPairContext* context, int vid) {
    if (g_game_base == nullptr || GetCurrentThreadId() != g_recorder_pair_thread ||
        !IsCurrentFeatureDll()) return -1;
    __try {
        // Exact-build producer prefix, verified from 140497840.json/.asm.
        static const BYTE expected[] = {
            0x40, 0x53, 0x48, 0x81, 0xec, 0x90, 0x00, 0x00, 0x00,
            0x48, 0x8b, 0x05, 0xf0, 0x77, 0x81, 0x07
        };
        if (memcmp(g_game_base + RVA_RECORDER_EXPLICIT_EVENT,
                   expected, sizeof(expected)) != 0) return -1;
        context->requested_vid = vid;
        context->recorder = *reinterpret_cast<BYTE**>(g_game_base + RVA_INPUT_RECORDER);
        context->player = *reinterpret_cast<BYTE**>(g_game_base + RVA_PLAYER_SINGLETON);
        context->app = *reinterpret_cast<BYTE**>(g_game_base + RVA_APP_GLOBAL);
        context->game = *reinterpret_cast<BYTE**>(g_game_base + RVA_GAME_UI_GLOBAL);
        context->stream = *reinterpret_cast<BYTE**>(g_game_base + RVA_GAME_STREAM_GLOBAL);
        if (!context->recorder || !context->player || !context->app ||
            !context->game || !context->stream) return -1;
        context->transport = *reinterpret_cast<void**>(context->stream + 0x58);
        if (context->stream[0x199] != 5 || context->transport == nullptr ||
            *reinterpret_cast<void**>(g_game_base + RVA_METIN_QUEUE_ADD_METHOD) !=
                reinterpret_cast<void*>(g_game_base + RVA_METIN_QUEUE_ADD_BINDING)) return -1;
        if (context->recorder[8] == 0) return 0;
        context->sample_ms = *reinterpret_cast<WORD*>(context->recorder + 0x0a);
        context->flush_ms = *reinterpret_cast<WORD*>(context->recorder + 0x0c);
        context->sample_due = *reinterpret_cast<DWORD*>(context->recorder + 0x10);
        context->flush_due = *reinterpret_cast<DWORD*>(context->recorder + 0x14);
        context->width = *reinterpret_cast<int*>(context->game + 8);
        context->height = *reinterpret_cast<int*>(context->game + 12);
        context->active = context->app[0x20];
        // Same sources as the native periodic sampler, no projected/forged coords.
        BYTE* coordinates = context->active ? context->game + 0x20
                                            : context->recorder + 0x9c;
        context->x = *reinterpret_cast<int*>(coordinates);
        context->y = *reinterpret_cast<int*>(coordinates + 4);
        // Reject unsupported dimensions/overflowing normalization inputs.
        if (context->width <= 0 || context->width > 65535 ||
            context->height <= 0 || context->height > 65535 ||
            context->x < -214748 || context->x > 214748 ||
            context->y < -214748 || context->y > 214748) return -1;
        return 1;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return -1;
    }
}

static int BeginRecorderPair(int vid) {
    RecorderPairContext context = {};
    context.requested_vid = vid;
    if (g_recorder_pair_failed || g_recorder_pair_pending) return -1;
    int status = ReadRecorderPairContext(&context, vid);
    if (status == 1) {
        // Mark before the call: a fault may occur after an append or cap flush.
        g_recorder_pair = context;
        g_recorder_pair_pending = true;
        __try {
            auto produce = reinterpret_cast<RecorderExplicitEventFn>(
                g_game_base + RVA_RECORDER_EXPLICIT_EVENT);
            produce(context.recorder, 1, context.x, context.y);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            status = -2; // Uncertain side effect; never retry.
            g_recorder_pair_pending = false;
        }
    }
    if (status < 0) g_recorder_pair_failed = true;
    LogRecorderPair("down", status, context);
    return status;
}

static int EndRecorderPair(int vid) {
    // Keep the original context local, then consume it before any attempted up.
    RecorderPairContext original = g_recorder_pair;
    RecorderPairContext current = {};
    if (!g_recorder_pair_pending || g_recorder_pair_failed ||
        GetCurrentThreadId() != g_recorder_pair_thread) return -1;
    g_recorder_pair_pending = false;
    int status = ReadRecorderPairContext(&current, vid);
    if (status != 1 || vid != original.requested_vid ||
        current.recorder != original.recorder || current.player != original.player ||
        current.app != original.app || current.game != original.game ||
        current.stream != original.stream || current.transport != original.transport ||
        current.sample_ms != original.sample_ms || current.flush_ms != original.flush_ms ||
        current.sample_due != original.sample_due || current.flush_due != original.flush_due ||
        current.width != original.width || current.height != original.height ||
        current.active != original.active) {
        status = -3; // Context/config changed: do not append into a new session.
    } else {
        __try {
            auto produce = reinterpret_cast<RecorderExplicitEventFn>(
                g_game_base + RVA_RECORDER_EXPLICIT_EVENT);
            produce(original.recorder, 2, original.x, original.y);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            status = -2;
        }
    }
    if (status < 0) g_recorder_pair_failed = true;
    LogRecorderPair("up", status, original);
    return status;
}

static void* RecorderPairBegin(void*, void* args) {
    int vid = 0;
    auto parse = reinterpret_cast<ParseTupleIntegerFn>(g_game_base + RVA_PARSE_TUPLE_INTEGER);
    if (!parse(args, 0, &vid) || vid <= 0) {
        auto error = reinterpret_cast<ArgumentErrorFn>(g_game_base + RVA_ARGUMENT_ERROR);
        return error(0);
    }
    auto make = reinterpret_cast<IntFromLongFn>(g_game_base + RVA_INT_FROM_LONG);
    return make(BeginRecorderPair(vid));
}

static void* RecorderPairEnd(void*, void* args) {
    int vid = 0;
    auto parse = reinterpret_cast<ParseTupleIntegerFn>(g_game_base + RVA_PARSE_TUPLE_INTEGER);
    if (!parse(args, 0, &vid) || vid <= 0) {
        auto error = reinterpret_cast<ArgumentErrorFn>(g_game_base + RVA_ARGUMENT_ERROR);
        return error(0);
    }
    auto make = reinterpret_cast<IntFromLongFn>(g_game_base + RVA_INT_FROM_LONG);
    return make(EndRecorderPair(vid));
}

static PyMethodDefNative g_recorder_pair_methods[] = {
    {"begin_queue_add", reinterpret_cast<void*>(&RecorderPairBegin), METH_VARARGS,
     "TEST ONLY: native down snapshot, no queue/button-state mutation"},
    {"end_queue_add", reinterpret_cast<void*>(&RecorderPairEnd), METH_VARARGS,
     "TEST ONLY: native up snapshot for the same guarded context"},
    {nullptr, nullptr, 0, nullptr},
};

static bool RegisterRecorderPairExperiment() {
    g_recorder_pair_thread = GetCurrentThreadId();
    auto init = reinterpret_cast<InitModule4Fn>(g_game_base + RVA_INIT_MODULE4);
    return init("_lirin_recorder_pair_experiment", g_recorder_pair_methods,
                "Opt-in recorder snapshots; NOT physical-click equivalence",
                nullptr, 0x3f5) != nullptr;
}

#endif  // USE_FEATURE_SCRIPT

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
    if (!RegisterHunterNativeObserver()) {
        AppendStatus(status_path, "Hunter observer module registration failed");
    } else {
        AppendStatus(status_path, "Hunter observer module registered");
    }
    if (!RegisterRecorderPairExperiment()) {
        AppendStatus(status_path, "Recorder-pair experiment module registration failed");
    } else {
        AppendStatus(status_path, "Recorder-pair experiment module registered (opt-in only)");
    }
    char source[MAX_PATH * 3 + 32] = {};
    if (sprintf_s(source, "execfile(r'%s')", script_path_utf8) <= 0) {
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
