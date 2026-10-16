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
static constexpr ULONG_PTR RVA_BUILD_VALUE = 0x00AA5EA0;
static constexpr ULONG_PTR RVA_INTEGER_FORMAT = 0x068FB3CC;
static constexpr ULONG_PTR RVA_GET_ACTOR_BY_VID = 0x003EE6D0;
static constexpr ULONG_PTR RVA_SET_MOUSE_STATE = 0x003E5940; // STALE (dead code since v35; no longer referenced)
static constexpr ULONG_PTR RVA_RECORD_INPUT = 0x00497840;
static constexpr ULONG_PTR RVA_INPUT_RECORDER = 0x07CCB198;
static constexpr ULONG_PTR RVA_GET_CURSOR_POSITION = 0x00824180;
static constexpr ULONG_PTR RVA_GAME_INSTANCE = 0x07CCAB50;
static constexpr ULONG_PTR RVA_GAME_DOWN_DISPATCH = 0x00826C30;
static constexpr ULONG_PTR RVA_GAME_UP_DISPATCH = 0x00826D90;
static constexpr ULONG_PTR RVA_APP_GLOBAL = 0x07CD3168;
// World->screen projection (the forward projection used by the pick path).
// FUN_1404a2ec0 reads an actor's world position; FUN_14061ca10 sets up the
// projection matrix (camera 2) that FUN_14061e430 consumes; DAT_147a6b678 is
// the camera/graphics context, and DAT_1466e6050 is the position-Y obfuscation
// key applied before projection.
static constexpr ULONG_PTR RVA_GET_ACTOR_POSITION = 0x004D2E40;
static constexpr ULONG_PTR RVA_PROJECTION_SETUP = 0x0065B530;
static constexpr ULONG_PTR RVA_PROJECT = 0x0065CEF0;
static constexpr ULONG_PTR RVA_CAMERA = 0x07CCAB48;
static constexpr ULONG_PTR RVA_POS_Y_OBF = 0x068FCCF0;
static constexpr ptrdiff_t CHARACTER_MANAGER_PICKED_ACTOR_OFFSET = 0xE0;
static constexpr ptrdiff_t PLAYER_MOUSE_DOWN_OFFSET = 0xFF;
static void AppendStatus(const wchar_t* status_path, const char* message);
static BYTE* g_game_base = nullptr;
static bool g_native_queue_wrapper_installed = false;
static volatile LONG g_wrapper_owner = 0;

// Return codes reported to Python through the wrapped MetinQueueAdd binding.
// 0 = not added (invalid input, missing state, or the client rejected it);
// 1 = requested VID newly present in the authoritative queue;
// 2 = requested VID already present (no click dispatched);
// 3 = outcome unknown (dispatch ran but queue membership did not change).
static constexpr int ADD_NOT_ADDED = 0;
static constexpr int ADD_ADDED = 1;
static constexpr int ADD_ALREADY_PRESENT = 2;
static constexpr int ADD_UNKNOWN = 3;

static constexpr ptrdiff_t PLAYER_QUEUE_BEGIN_OFFSET = 0x4588;
static constexpr ptrdiff_t PLAYER_QUEUE_END_OFFSET = 0x4590;

// The authoritative Metin queue is a std::vector<int> at player+0x4588..0x4590.
static bool QueueVectorValid(BYTE* player) {
    __try {
        DWORD* begin = *reinterpret_cast<DWORD**>(player + PLAYER_QUEUE_BEGIN_OFFSET);
        DWORD* end = *reinterpret_cast<DWORD**>(player + PLAYER_QUEUE_END_OFFSET);
        // An empty std::vector has begin == end (both null when capacity is 0);
        // that is valid, not a fault.  Only reject an inconsistent pair, a
        // reversed range, or a misaligned element count.
        if ((begin == nullptr) != (end == nullptr)) return false;
        if (begin && end && end < begin) return false;
        size_t bytes = reinterpret_cast<size_t>(end) - reinterpret_cast<size_t>(begin);
        if (bytes % sizeof(DWORD) != 0) return false;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return true;
}

static bool QueueContainsVid(BYTE* player, int vid) {
    __try {
        DWORD* begin = *reinterpret_cast<DWORD**>(player + PLAYER_QUEUE_BEGIN_OFFSET);
        DWORD* end = *reinterpret_cast<DWORD**>(player + PLAYER_QUEUE_END_OFFSET);
        if (!begin || !end || end < begin) return false;
        for (DWORD* it = begin; it < end; ++it) {
            if (static_cast<int>(*it) == vid) return true;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return false;
}

using ParseTupleInteger = char (*)(void*, int, int*);
using ArgumentError = void* (*)(int);
using BuildValue = void* (*)(const char*, ...);
using GetActorByVid = void* (*)(void*, int);
using SetMouseState = void (*)(void*, int, char);
using RecordInput = void (*)(void*, char, int, int);
using GetCursorPosition = void (*)(void*, int*, int*);
using GameDownDispatch = bool (*)(void*, int, int);
using GameUpDispatch = bool (*)(void*, int, int);
using GetActorPosition = void (*)(void*, float*);
using ProjectionSetup = void (*)();
using Project = void (*)(void*, float, float, float, float*, float*, int*);

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

// Observe only. Do not generate input records or alter recorder settings.
static void LogQueueInputState(int vid) {
    char line[256] = {};
    __try {
        BYTE* recorder = *reinterpret_cast<BYTE**>(g_game_base + RVA_INPUT_RECORDER);
        if (!recorder) {
            sprintf_s(line, "queue input diagnostic: tick=%llu vid=%d recorder=missing",
                      GetTickCount64(), vid);
        } else {
            unsigned bg = 0;
            unsigned mouse_down = 0;
            __try {
                BYTE* app = *reinterpret_cast<BYTE**>(g_game_base + RVA_APP_GLOBAL);
                if (app) {
                    bg = static_cast<unsigned>(app[0x20]);
                }
                BYTE* player = *reinterpret_cast<BYTE**>(g_game_base + RVA_PLAYER_SINGLETON);
                if (player) {
                    mouse_down = static_cast<unsigned>(player[PLAYER_MOUSE_DOWN_OFFSET]);
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
            sprintf_s(line,
                      "queue input diagnostic: tick=%llu vid=%d recorder_enabled=%u sample_ms=%u flush_ms=%u bg=%u mouse_down=%u",
                      GetTickCount64(), vid, static_cast<unsigned>(recorder[8]),
                      static_cast<unsigned>(*reinterpret_cast<WORD*>(recorder + 10)),
                      static_cast<unsigned>(*reinterpret_cast<WORD*>(recorder + 12)),
                      bg, mouse_down);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        strcpy_s(line, "queue input diagnostic: recorder read unavailable");
    }
    AppendStatus(g_feature_status_path, line);
}

// Fill the client's own cursor position (client coordinates).  This is the
// same source the input recorder logs for its movement samples, so a synthetic
// click stays on the recorded movement path even while the window is unfocused
// (the OS cursor would instead report wherever the physical pointer is).
static void GetGameCursorPosition(int* out_x, int* out_y) {
    *out_x = 0;
    *out_y = 0;
    void* game_instance = *reinterpret_cast<void**>(
        g_game_base + RVA_GAME_INSTANCE);
    if (!game_instance) return;
    auto get_cursor_position = reinterpret_cast<GetCursorPosition>(
        g_game_base + RVA_GET_CURSOR_POSITION);
    __try {
        get_cursor_position(game_instance, out_x, out_y);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        *out_x = 0;
        *out_y = 0;
    }
}

// Emit a bare synthetic left-click (down code 1, up code 2) into the client
// input recorder.  FUN_140471b10 is a no-op while the recorder is disabled.
// Used for UI automations (reaction game, channel dialog) that a human would
// click but that never pass through the Windows mouse handler.
//
// Returns true only when both the down and up records were actually emitted
// into an enabled recorder.  The whole path (recorder dereference, cursor
// getter, and record calls) is fault-guarded.  This is a deprecated
// compatibility path; it must not introduce a second recorder event alongside
// real dispatch.
static bool EmitSyntheticClick() {
    bool emitted = false;
    __try {
        BYTE* recorder = *reinterpret_cast<BYTE**>(g_game_base + RVA_INPUT_RECORDER);
        if (recorder && recorder[8] != 0) {
            int cursor_x = 0;
            int cursor_y = 0;
            GetGameCursorPosition(&cursor_x, &cursor_y);
            auto record_input = reinterpret_cast<RecordInput>(
                g_game_base + RVA_RECORD_INPUT);
            record_input(recorder, 1, cursor_x, cursor_y);
            record_input(recorder, 2, cursor_x, cursor_y);
            emitted = true;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        emitted = false;
    }
    return emitted;
}

// Reproduce the WndProc mouse-down/up sequence at explicit client-pixel
// coordinates: record down (code 1) -> game down dispatch -> record up
// (code 2) -> game up dispatch.  No picker override; the client's own
// hit-testing picks whatever is under those coordinates.
//
// The down/up dispatch results are captured and logged (route diagnostics),
// and an access fault after the down dispatch triggers a best-effort release
// so the player is never left in a pressed state.  Returns false when the game
// instance is missing, the down dispatch faulted, or the down dispatch
// reported that nothing was handled.
// Log the viewport bounds and the player's post-down pick state so a failed
// queue add can be classified as off-screen, ground-click, or wrong-actor.
// player+0xec pick code: 0=cleared/unknown, 1=ground move, 2=item, 5=actor
// (picked VID stored at player+0x58).  game+0x1c/0x18 are the viewport
// width/height, game+0x30/0x34 the client offsets, game+0x20/0x24 the
// normalized cursor written by the down dispatch.
static void LogClickPickState(int vid, int x, int y) {
    char line[352] = {};
    __try {
        void* game_instance = *reinterpret_cast<void**>(g_game_base + RVA_GAME_INSTANCE);
        BYTE* player = *reinterpret_cast<BYTE**>(g_game_base + RVA_PLAYER_SINGLETON);
        int view_w = 0, view_h = 0, x_off = 0, y_off = 0, cur_x = 0, cur_y = 0;
        unsigned pick_code = 0, picked_vid = 0, mouse_down = 0;
        if (game_instance) {
            view_w = *reinterpret_cast<int*>(reinterpret_cast<BYTE*>(game_instance) + 0x1c);
            view_h = *reinterpret_cast<int*>(reinterpret_cast<BYTE*>(game_instance) + 0x18);
            x_off = *reinterpret_cast<int*>(reinterpret_cast<BYTE*>(game_instance) + 0x30);
            y_off = *reinterpret_cast<int*>(reinterpret_cast<BYTE*>(game_instance) + 0x34);
            cur_x = *reinterpret_cast<int*>(reinterpret_cast<BYTE*>(game_instance) + 0x20);
            cur_y = *reinterpret_cast<int*>(reinterpret_cast<BYTE*>(game_instance) + 0x24);
        }
        if (player) {
            pick_code = *reinterpret_cast<unsigned*>(player + 0xec);
            picked_vid = *reinterpret_cast<unsigned*>(player + 0x58);
            mouse_down = static_cast<unsigned>(player[PLAYER_MOUSE_DOWN_OFFSET]);
        }
        sprintf_s(line,
                  "native click pick: vid=%d x=%d y=%d viewport=%dx%d off=%d,%d cursor=%d,%d pick_code=%u picked_vid=%u mouse_down=%u",
                  vid, x, y, view_w, view_h, x_off, y_off, cur_x, cur_y,
                  pick_code, picked_vid, mouse_down);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        sprintf_s(line, "native click pick: vid=%d x=%d y=%d unavailable", vid, x, y);
    }
    AppendStatus(g_feature_status_path, line);
}

static bool DispatchClickAt(int vid, int x, int y) {
    void* game_instance = *reinterpret_cast<void**>(g_game_base + RVA_GAME_INSTANCE);
    if (!game_instance) return false;
    auto record_input = reinterpret_cast<RecordInput>(g_game_base + RVA_RECORD_INPUT);
    BYTE* recorder = *reinterpret_cast<BYTE**>(g_game_base + RVA_INPUT_RECORDER);
    auto game_down = reinterpret_cast<GameDownDispatch>(g_game_base + RVA_GAME_DOWN_DISPATCH);
    auto game_up = reinterpret_cast<GameUpDispatch>(g_game_base + RVA_GAME_UP_DISPATCH);

    bool down_dispatched = false;
    bool up_dispatched = false;
    bool fault = false;
    __try {
        if (recorder) record_input(recorder, 1, x, y);
        down_dispatched = game_down(game_instance, x, y);
        LogClickPickState(vid, x, y);
        if (recorder) record_input(recorder, 2, x, y);
        up_dispatched = game_up(game_instance, x, y);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        fault = true;
    }

    // If the down dispatch ran but the up dispatch faulted (or vice versa)
    // before release, attempt a release once so player +0xFF is not stuck.
    if (fault && down_dispatched) {
        __try {
            game_up(game_instance, x, y);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }

    {
        char line[192] = {};
        sprintf_s(line,
                  "native click dispatch: x=%d y=%d down=%d up=%d fault=%d",
                  x, y, down_dispatched ? 1 : 0, up_dispatched ? 1 : 0,
                  fault ? 1 : 0);
        AppendStatus(g_feature_status_path, line);
    }

    if (fault) {
        AppendStatus(g_feature_status_path, "native queue wrapper click dispatch fault");
        return false;
    }
    return down_dispatched;
}

// Performs the actual click dispatch for a positive VID, assuming the
// re-entrancy guard is held.  Returns an ADD_* code.  The acknowledgement is
// derived from the requested VID's membership in the authoritative queue, not
// from a raw size delta (a click can remove-then-add, keeping the size equal).
static constexpr int PROJECT_CLICK_HEIGHT = 100;

// Linear scan of the character-manager tree for the actor matching a VID.
// Mirrors chr.GetProjectPosition's resolution (the same tree the entity
// snapshot walks) so the projected position matches what the pick uses.
static void* FindActorByVid(BYTE* manager, int vid) {
    __try {
        CharacterNode* head = manager ? *reinterpret_cast<CharacterNode**>(manager + 0xf8) : nullptr;
        if (!head) return nullptr;
        CharacterNode* node = head->left;
        for (int count = 0; node && node != head && count < 4096; ++count) {
            if (node->is_nil) break;
            if (node->actor && static_cast<int>(node->vid) == vid) {
                return node->actor;
            }
            if (node->right && !node->right->is_nil) {
                node = node->right;
                int hops = 0;
                while (node->left && !node->left->is_nil && hops++ < 4096) node = node->left;
                if (hops >= 4096) return nullptr;
            } else {
                CharacterNode* parent = node->parent;
                int hops = 0;
                while (parent && !parent->is_nil && node == parent->right && hops++ < 4096) {
                    node = parent;
                    parent = parent->parent;
                }
                if (hops >= 4096) return nullptr;
                node = parent;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return nullptr;
}

// Project an actor VID to client-pixel screen coordinates.  Unlike the Python
// chr.GetProjectPosition binding, this refreshes the projection matrix first
// (FUN_14061ca10, which player.GetProjectPosition also calls but
// chr.GetProjectPosition skips), so the result aligns with the rendered screen
// rect the pick uses.  Returns false when the actor is unresolvable or the
// projection reports the point is behind the camera.
static bool ProjectActorToScreen(int vid, int height, int* out_x, int* out_y) {
    *out_x = -100;
    *out_y = -100;
    __try {
        BYTE* manager = *reinterpret_cast<BYTE**>(g_game_base + RVA_CHARACTER_MANAGER);
        void* actor = FindActorByVid(manager, vid);
        if (!actor) return false;

        float pos[3] = { 0.0f, 0.0f, 0.0f };
        auto get_position = reinterpret_cast<GetActorPosition>(g_game_base + RVA_GET_ACTOR_POSITION);
        get_position(actor, pos);

        auto setup = reinterpret_cast<ProjectionSetup>(g_game_base + RVA_PROJECTION_SETUP);
        setup();

        void* camera = *reinterpret_cast<void**>(g_game_base + RVA_CAMERA);
        if (!camera) return false;

        float x = pos[0];
        unsigned y_bits = *reinterpret_cast<unsigned*>(&pos[1]) ^
                          *reinterpret_cast<unsigned*>(g_game_base + RVA_POS_Y_OBF);
        float y = *reinterpret_cast<float*>(&y_bits);
        float z = static_cast<float>(height) + pos[2];

        auto project = reinterpret_cast<Project>(g_game_base + RVA_PROJECT);
        float screen_x = 0.0f;
        float screen_y = 0.0f;
        int behind = 0;
        project(camera, x, y, z, &screen_x, &screen_y, &behind);
        if (behind == 1) return false;

        *out_x = static_cast<int>(screen_x);
        *out_y = static_cast<int>(screen_y);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

static int NativeMetinQueueAddInner(int vid, int click_x, int click_y) {
    LogQueueInputState(vid);

    BYTE* player = *reinterpret_cast<BYTE**>(g_game_base + RVA_PLAYER_SINGLETON);
    BYTE* manager = *reinterpret_cast<BYTE**>(g_game_base + RVA_CHARACTER_MANAGER);
    if (!player || !manager) {
        AppendStatus(g_feature_status_path, "native queue wrapper skipped: singleton missing");
        return ADD_NOT_ADDED;
    }
    if (!QueueVectorValid(player)) {
        AppendStatus(g_feature_status_path, "native queue wrapper skipped: queue vector invalid");
        return ADD_NOT_ADDED;
    }

    // Check membership before any click.  The native click path can remove an
    // already-queued actor under its duplicate gate, so a click on an
    // already-present VID must not be dispatched.
    if (QueueContainsVid(player, vid)) {
        AppendStatus(g_feature_status_path, "native queue wrapper: VID already present; no click");
        return ADD_ALREADY_PRESENT;
    }

    if (player[PLAYER_MOUSE_DOWN_OFFSET] != 0) {
        AppendStatus(g_feature_status_path, "native queue wrapper skipped: mouse already down");
        return ADD_NOT_ADDED;
    }

    auto get_actor = reinterpret_cast<GetActorByVid>(g_game_base + RVA_GET_ACTOR_BY_VID);
    void* target_actor = get_actor(player, vid);
    if (!target_actor) {
        AppendStatus(g_feature_status_path, "native queue wrapper skipped: actor unresolved");
        return ADD_NOT_ADDED;
    }

    // Re-validate the singletons immediately before mutating shared state; a
    // phase change may have replaced them between the checks above.
    if (*reinterpret_cast<BYTE**>(g_game_base + RVA_PLAYER_SINGLETON) != player ||
        *reinterpret_cast<BYTE**>(g_game_base + RVA_CHARACTER_MANAGER) != manager) {
        AppendStatus(g_feature_status_path, "native queue wrapper skipped: singleton changed");
        return ADD_NOT_ADDED;
    }

    // Resolve the click coordinates: explicit, or native projection.
    int px = click_x;
    int py = click_y;
    if (click_x < 0 || click_y < 0) {
        if (!ProjectActorToScreen(vid, PROJECT_CLICK_HEIGHT, &px, &py)) {
            AppendStatus(g_feature_status_path,
                         "native queue wrapper rejected: actor not projectable");
            return ADD_NOT_ADDED;
        }
        {
            char line[160] = {};
            sprintf_s(line,
                      "native queue wrapper route: native-projection vid=%d x=%d y=%d",
                      vid, px, py);
            AppendStatus(g_feature_status_path, line);
        }
    } else {
        {
            char line[160] = {};
            sprintf_s(line,
                      "native queue wrapper route: full-dispatch vid=%d x=%d y=%d",
                      vid, px, py);
            AppendStatus(g_feature_status_path, line);
        }
    }

    // Reproduce the hover-pick state a physical mouse establishes: the click
    // router resolves its actor through the manager's picked-actor field
    // (manager+0xE0), which the synthetic down dispatch does not set (a real
    // mouse sets it on hover, before the click).  Override it for the duration
    // of the click, then restore it.  Combined with the full down/up dispatch
    // above this reproduces the physical path: hover-pick + click.
    void** picked_actor = reinterpret_cast<void**>(
        manager + CHARACTER_MANAGER_PICKED_ACTOR_OFFSET);
    void* saved_picked_actor = *picked_actor;
    bool dispatched = false;
    __try {
        *picked_actor = target_actor;
        dispatched = DispatchClickAt(vid, px, py);
    } __finally {
        // Restore only if the manager is still the same object we overrode.
        __try {
            if (*reinterpret_cast<BYTE**>(g_game_base + RVA_CHARACTER_MANAGER) == manager) {
                *picked_actor = saved_picked_actor;
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
    if (!dispatched) {
        return ADD_NOT_ADDED;
    }

    // Acknowledge by requested-VID membership change.  If the VID is not
    // present after dispatch the outcome is unknown: do not report success and
    // never immediately retry (the click may already have executed).
    int outcome = QueueContainsVid(player, vid) ? ADD_ADDED : ADD_UNKNOWN;
    {
        char line[128] = {};
        sprintf_s(line, "native queue wrapper result: vid=%d code=%d", vid, outcome);
        AppendStatus(g_feature_status_path, line);
    }
    return outcome;
}

static void* NativeMetinQueueAdd(void*, void* args) {
    auto parse_integer = reinterpret_cast<ParseTupleInteger>(g_game_base + RVA_PARSE_TUPLE_INTEGER);
    auto argument_error = reinterpret_cast<ArgumentError>(g_game_base + RVA_ARGUMENT_ERROR);
    auto build_value = reinterpret_cast<BuildValue>(g_game_base + RVA_BUILD_VALUE);
    const char* int_format = reinterpret_cast<const char*>(g_game_base + RVA_INTEGER_FORMAT);

    int vid = 0;
    if (!parse_integer(args, 0, &vid)) return argument_error(0);

    if (vid < 0) return build_value(int_format, ADD_NOT_ADDED);

    // Optional explicit click coordinates (client pixels).  When provided, the
    // wrapper reproduces the full WndProc mouse-down/up dispatch at these
    // coordinates.  vid == 0 with coordinates is a UI-control click; a positive
    // VID with coordinates is a world-target click.
    int click_x = -1;
    int click_y = -1;
    parse_integer(args, 1, &click_x);
    parse_integer(args, 2, &click_y);

    // Reject recursive re-entry before any mutation.  The owner is released on
    // every exit below.
    LONG owner = static_cast<LONG>(GetCurrentThreadId());
    if (InterlockedCompareExchange(&g_wrapper_owner, owner, 0) != 0) {
        AppendStatus(g_feature_status_path, "native queue wrapper re-entrant call rejected");
        return build_value(int_format, ADD_NOT_ADDED);
    }

    int result = ADD_NOT_ADDED;
    __try {
        if (vid == 0) {
            // vid == 0 sentinel: a bare synthetic click, or (with coordinates)
            // a full-dispatch click on a UI control.  The latter is the
            // replacement for the deprecated bare-record UI path.
            if (click_x >= 0 && click_y >= 0) {
                result = DispatchClickAt(vid, click_x, click_y) ? 1 : 0;
            } else {
                result = EmitSyntheticClick() ? 1 : 0;
            }
        } else {
            result = NativeMetinQueueAddInner(vid, click_x, click_y);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        AppendStatus(g_feature_status_path, "native input queue wrapper access fault");
        result = ADD_NOT_ADDED;
    }
    InterlockedExchange(&g_wrapper_owner, 0);
    return build_value(int_format, result);
}

static bool InstallNativeMetinQueueWrapper(BYTE* base) {
    // Only patch when the patch site is readable and the current entry is still
    // the stock binding we expect.  The guard read below faults on an
    // out-of-image or protected address instead of writing through it.
    void** method = reinterpret_cast<void**>(base + RVA_METIN_QUEUE_ADD_METHOD);
    void* expected = base + RVA_METIN_QUEUE_ADD_BINDING;
    __try {
        if (*method != expected) {
            AppendStatus(g_feature_status_path,
                         "native queue wrapper skipped: binding already changed");
            return false;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        AppendStatus(g_feature_status_path,
                     "native queue wrapper skipped: method table unreadable");
        return false;
    }
    DWORD old_protection = 0;
    if (!VirtualProtect(method, sizeof(*method), PAGE_READWRITE, &old_protection)) {
        AppendStatus(g_feature_status_path,
                     "native queue wrapper skipped: method table protect failed");
        return false;
    }
    *method = reinterpret_cast<void*>(&NativeMetinQueueAdd);
    DWORD ignored = 0;
    VirtualProtect(method, sizeof(*method), old_protection, &ignored);
    g_native_queue_wrapper_installed = true;
    AppendStatus(g_feature_status_path, "native full-input queue wrapper installed");
    return true;
}

static void RestoreNativeMetinQueueWrapper() {
    if (!g_native_queue_wrapper_installed || !g_game_base) return;
    void** method = reinterpret_cast<void**>(g_game_base + RVA_METIN_QUEUE_ADD_METHOD);
    __try {
        // Restore only the entry we own; never overwrite a foreign change.
        if (*method != reinterpret_cast<void*>(&NativeMetinQueueAdd)) return;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
    DWORD old_protection = 0;
    if (!VirtualProtect(method, sizeof(*method), PAGE_READWRITE, &old_protection)) return;
    *method = g_game_base + RVA_METIN_QUEUE_ADD_BINDING;
    DWORD ignored = 0;
    VirtualProtect(method, sizeof(*method), old_protection, &ignored);
    g_native_queue_wrapper_installed = false;
}

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
