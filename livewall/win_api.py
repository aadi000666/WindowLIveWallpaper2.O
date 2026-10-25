"""Small Win32 helpers for placing a window behind the desktop icons."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

if sys.platform == "win32":
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowExW.argtypes = (
        wintypes.HWND,
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
    )
    user32.FindWindowExW.restype = wintypes.HWND
    user32.SendMessageTimeoutW.argtypes = (
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_size_t),
    )
    user32.SendMessageTimeoutW.restype = wintypes.LPARAM
    _WNDENUMPROC = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
    )
    user32.EnumWindows.argtypes = (_WNDENUMPROC, wintypes.LPARAM)
    user32.EnumWindows.restype = wintypes.BOOL
    user32.FindWindowExW.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = (
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    )
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = (
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_ssize_t,
    )
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetParent.argtypes = (wintypes.HWND, wintypes.HWND)
    user32.SetParent.restype = wintypes.HWND
    user32.GetParent.argtypes = (wintypes.HWND,)
    user32.GetParent.restype = wintypes.HWND
    user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.GetClientRect.restype = wintypes.BOOL
    user32.SetThreadDpiAwarenessContext.argtypes = (ctypes.c_void_p,)
    user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    user32.SetWindowPos.argtypes = (
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    )
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.IsWindow.restype = wintypes.BOOL
    kernel32.GetCurrentProcessId.restype = wintypes.DWORD


class WindowsApiError(RuntimeError):
    """Raised when a required desktop-window operation fails."""


def _require_windows() -> None:
    if sys.platform != "win32":
        raise OSError("LiveWall's desktop wallpaper integration requires Windows.")


def _set_per_monitor_dpi_context() -> int:
    """Set the calling thread to per-monitor awareness and return its old context."""
    # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 is the pseudo-handle -4.
    previous = user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    if not previous:
        error = ctypes.get_last_error()
        raise WindowsApiError(
            f"Could not set per-monitor DPI awareness (Win32 {error})."
        )
    return int(previous)


def find_desktop_host() -> int:
    """Ask Explorer to create WorkerW and return the wallpaper-layer HWND."""
    _require_windows()

    progman = user32.FindWindowW("Progman", None)
    if not progman:
        raise WindowsApiError("Could not find the Windows desktop (Progman).")

    result = ctypes.c_size_t()
    sent = user32.SendMessageTimeoutW(
        progman,
        0x052C,
        0xD,
        0x1,
        0x0002,
        1000,
        ctypes.byref(result),
    )
    if not sent:
        error = ctypes.get_last_error()
        raise WindowsApiError(
            f"Explorer did not respond to the WorkerW request (Win32 {error})."
        )

    # Current Explorer builds can create the wallpaper WorkerW as a child of
    # Progman. It is the preferred host because it sits behind SHELLDLL_DefView.
    wallpaper_host = user32.FindWindowExW(progman, 0, "WorkerW", None)
    if wallpaper_host:
        return int(wallpaper_host)

    icon_host = 0

    @_WNDENUMPROC
    def find_icon_host(hwnd: int, _lparam: int) -> bool:
        nonlocal icon_host
        view = user32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None)
        if view:
            icon_host = hwnd
            return False
        return True

    user32.EnumWindows(find_icon_host, 0)
    if icon_host:
        wallpaper_host = user32.FindWindowExW(0, icon_host, "WorkerW", None)
        if wallpaper_host:
            return int(wallpaper_host)

    # Some Explorer configurations expose the icon view directly under
    # Progman without creating a separate WorkerW. Parenting to Progman and
    # placing LiveWall at the bottom keeps it underneath the icon view.
    if user32.IsWindow(progman):
        return int(progman)

    raise WindowsApiError(
        "Could not find a usable Windows desktop host. Restart Windows "
        "Explorer and try again."
    )


def _keep_desktop_icons_in_front() -> None:
    """Keep Explorer's icon view above wallpaper windows in the desktop tree."""
    progman = user32.FindWindowW("Progman", None)
    icon_view = user32.FindWindowExW(progman, 0, "SHELLDLL_DefView", None)
    if not icon_view:
        return

    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010
    HWND_TOP = wintypes.HWND(0)
    flags = SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE

    if not user32.SetWindowPos(icon_view, HWND_TOP, 0, 0, 0, 0, flags):
        error = ctypes.get_last_error()
        raise WindowsApiError(
            f"Could not keep desktop icons above the wallpaper (Win32 {error})."
        )

    icon_list = user32.FindWindowExW(icon_view, 0, "SysListView32", None)
    if icon_list and not user32.SetWindowPos(
        icon_list, HWND_TOP, 0, 0, 0, 0, flags
    ):
        error = ctypes.get_last_error()
        raise WindowsApiError(
            f"Could not raise the desktop icon list (Win32 {error})."
        )


def attach_to_desktop(window_handle: int) -> None:
    """Parent a native Qt window to the desktop wallpaper layer."""
    _require_windows()
    if not user32.IsWindow(window_handle):
        raise WindowsApiError("The wallpaper window handle is not valid.")

    host = find_desktop_host()
    if not host or not user32.IsWindow(host):
        raise WindowsApiError("Could not find a usable WorkerW desktop window.")

    # WS_CHILD replaces the top-level popup style used by a frameless Qt window.
    GWL_STYLE = -16
    WS_CHILD = 0x40000000
    WS_POPUP = 0x80000000
    WS_CAPTION = 0x00C00000
    WS_THICKFRAME = 0x00040000
    style = user32.GetWindowLongPtrW(window_handle, GWL_STYLE)
    style = (style | WS_CHILD) & ~(WS_POPUP | WS_CAPTION | WS_THICKFRAME)
    ctypes.set_last_error(0)
    user32.SetWindowLongPtrW(window_handle, GWL_STYLE, style)
    error = ctypes.get_last_error()
    if error:
        raise WindowsApiError(f"Could not update wallpaper window style (Win32 {error}).")

    ctypes.set_last_error(0)
    user32.SetParent(window_handle, host)
    error = ctypes.get_last_error()
    if error:
        if error == 5:
            raise WindowsApiError(
                "Windows denied attaching LiveWall to the desktop (Win32 5: "
                "Access is denied). Close LiveWall and relaunch it normally "
                "(not as administrator). If the error remains, a Windows "
                "policy or desktop customization utility may block WorkerW."
            )
        raise WindowsApiError(f"Could not attach wallpaper to WorkerW (Win32 {error}).")
    if user32.GetParent(window_handle) != host:
        raise WindowsApiError(
            "Windows did not attach the wallpaper window to WorkerW. "
            "Try restarting Windows Explorer and LiveWall."
        )

    # Qt geometry is expressed in device-independent pixels. SetWindowPos
    # needs the actual native client size, which can be larger under Windows
    # display scaling (for example, 150% scaling).
    previous_dpi_context = _set_per_monitor_dpi_context()
    try:
        host_rect = wintypes.RECT()
        if not user32.GetClientRect(host, ctypes.byref(host_rect)):
            error = ctypes.get_last_error()
            raise WindowsApiError(
                f"Could not read desktop host dimensions (Win32 {error})."
            )
        host_width = host_rect.right - host_rect.left
        host_height = host_rect.bottom - host_rect.top
        if host_width <= 0 or host_height <= 0:
            raise WindowsApiError("Windows returned an empty desktop host area.")

        SWP_NOACTIVATE = 0x0010
        SWP_FRAMECHANGED = 0x0020
        SWP_SHOWWINDOW = 0x0040
        HWND_BOTTOM = wintypes.HWND(1)
        if not user32.SetWindowPos(
            window_handle,
            HWND_BOTTOM,
            0,
            0,
            host_width,
            host_height,
            SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_SHOWWINDOW,
        ):
            error = ctypes.get_last_error()
            raise WindowsApiError(
                f"Could not position the wallpaper window (Win32 {error})."
            )
        _keep_desktop_icons_in_front()
    finally:
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(previous_dpi_context))


def foreground_window_is_fullscreen(
    screen_rect: tuple[int, int, int, int], excluded_handle: int = 0
) -> bool:
    """Return whether another foreground window covers the supplied screen."""
    _require_windows()
    hwnd = user32.GetForegroundWindow()
    if not hwnd or hwnd == excluded_handle:
        return False

    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    if process_id.value == kernel32.GetCurrentProcessId():
        return False

    class_name = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, class_name, len(class_name))
    if class_name.value in {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}:
        return False

    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False

    left, top, right, bottom = screen_rect
    tolerance = 2
    return (
        rect.left <= left + tolerance
        and rect.top <= top + tolerance
        and rect.right >= right - tolerance
        and rect.bottom >= bottom - tolerance
    )