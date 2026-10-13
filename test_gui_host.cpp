#define WIN32_LEAN_AND_MEAN
#include <windows.h>

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int) {
    HWND window = CreateWindowExW(WS_EX_TOOLWINDOW | WS_EX_LAYERED, L"STATIC", L"Lirin",
                                  WS_POPUP, -10000, -10000, 1, 1, nullptr, nullptr, instance, nullptr);
    if (!window) return 1;
    SetLayeredWindowAttributes(window, 0, 0, LWA_ALPHA);
    ShowWindow(window, SW_SHOWNOACTIVATE);
    MSG message = {};
    while (GetMessageW(&message, nullptr, 0, 0) > 0) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }
    return 0;
}
