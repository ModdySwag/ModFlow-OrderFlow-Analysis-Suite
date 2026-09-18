"""One windowed instance per config profile (finding N-1).

A windowed launch takes a named mutex keyed to the *config directory*. A second windowed launch
in the same profile finds the mutex held, brings the existing window forward when it can, and
exits — instead of starting a second server and a second engine over the same ``config.json`` and
the same SQLite file, which is exactly what a double-click used to do (observed on the frozen
build: the second copy quietly bound the next free port).

Headless runs are deliberately exempt: every documented smoke recipe opens its own scratch
``APPDATA`` and must be able to run alongside the owner's window, and the recipes never need the
guard for anything. Non-Windows platforms are a no-op — the mutex is a Windows kernel object and
the shipped product is Windows-only; the guard fails *open* on any unexpected OS error, because a
broken guard must never block the app from starting.
"""

from __future__ import annotations

import ctypes
import hashlib
import logging
import sys

logger = logging.getLogger(__name__)

_MUTEX_PREFIX = "ModFlowOrderFlowAnalysisSuite"
_ERROR_ALREADY_EXISTS = 183
_APP_TITLE = "ModFlow OrderFlow Analysis Suite"

#: Held for the whole process life: closing the handle would release the name and let the next
#: launch through. One handle, one process — the kernel releases it on exit.
_held_handle: int | None = None
_kernel32 = None
_user32 = None


def instance_mutex_name(profile_dir: str) -> str:
    """The mutex name for a config directory — stable per profile, case- and slash-insensitive.

    A trailing separator is ignored so ``…\\OrderFlowAnalysisPro`` and ``…\\OrderFlowAnalysisPro\\``
    are the same profile (they are).
    """
    key = str(profile_dir).strip().casefold().replace("/", "\\").rstrip("\\")
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"{_MUTEX_PREFIX}-{digest}"


def _k32():
    global _kernel32
    if _kernel32 is None:
        _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        _kernel32.CreateMutexW.restype = ctypes.c_void_p
        _kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        _kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        _kernel32.CloseHandle.restype = ctypes.c_bool
    return _kernel32


def _u32():
    global _user32
    if _user32 is None:
        _user32 = ctypes.WinDLL("user32", use_last_error=True)
        _user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
        _user32.GetWindowTextLengthW.restype = ctypes.c_int
        _user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
        _user32.GetWindowTextW.restype = ctypes.c_int
        _user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
        _user32.IsWindowVisible.restype = ctypes.c_bool
        _user32.EnumWindows.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        _user32.EnumWindows.restype = ctypes.c_bool
        _user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        _user32.ShowWindow.restype = ctypes.c_bool
        _user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        _user32.SetForegroundWindow.restype = ctypes.c_bool
        _user32.MessageBoxW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        _user32.MessageBoxW.restype = ctypes.c_int
    return _user32


def _create_mutex(name: str) -> int | None:
    """Create the named mutex.

    Returns its handle on first creation, ``None`` when a process already holds the name.
    Raises on genuine kernel failure (the caller decides whether that blocks startup).
    """
    k32 = _k32()
    ctypes.set_last_error(0)
    handle = k32.CreateMutexW(None, False, name)
    if not handle:
        raise OSError(ctypes.get_last_error(), f"CreateMutexW failed for {name!r}")
    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        k32.CloseHandle(handle)
        return None
    return int(handle)


def _close_handle(handle: int) -> None:
    """Release a handle from :func:`_create_mutex` (tests; the app keeps its handle forever)."""
    try:
        _k32().CloseHandle(handle)
    except Exception:                                  # a released kernel object is not an error
        pass


def _focus_existing(title_prefix: str = _APP_TITLE) -> bool:
    """Best-effort: bring the running window forward. True when a matching window was found."""
    try:
        user32 = _u32()
        found: list[int] = []

        def _cb(hwnd, _lparam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if buf.value.startswith(title_prefix) and user32.IsWindowVisible(hwnd):
                    found.append(hwnd)
            return True

        user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(_cb), None)
        if not found:
            return False
        hwnd = found[0]
        user32.ShowWindow(hwnd, 9)                     # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        logger.warning("could not bring the existing window forward", exc_info=True)
        return False


#: How long the already-running notice stays on screen before it closes itself. The old plain
#: MessageBoxW was modal with no deadline: a launch that could not find the owner's window (a
#: second click during the app's slow start-up) left an invisible modal process sitting for as
#: long as nobody clicked OK — measured live as a 7 MB windowless process, no ports, no log
#: line, alive for 15+ minutes and mistaken for a duplicate instance.
NOTICE_MS = 10_000


def _notify_existing() -> None:
    """Say the app is already running — focus it when possible, tell the user when not.

    The notice bounds itself with ``MessageBoxTimeoutW`` (user32's own timeout variant); the
    plain modal call remains the fallback where that export is missing.
    """
    if _focus_existing():
        return
    try:
        user32 = _u32()
        MB_OK, MB_ICONINFORMATION, MB_SETFOREGROUND, MB_TOPMOST = 0x0, 0x40, 0x10000, 0x40000
        style = MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND | MB_TOPMOST
        timeout_fn = getattr(user32, "MessageBoxTimeoutW", None)
        if timeout_fn is not None:
            timeout_fn.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                                   ctypes.c_uint, ctypes.c_ushort, ctypes.c_uint]
            timeout_fn.restype = ctypes.c_int
            timeout_fn(None, f"{_APP_TITLE} is already running.", _APP_TITLE, style, 0, NOTICE_MS)
        else:                                          # pragma: no cover — user32 always has it here
            user32.MessageBoxW(None, f"{_APP_TITLE} is already running.", _APP_TITLE, style)
    except Exception:
        logger.warning("could not show the already-running notice", exc_info=True)


def acquire_for_app(profile_dir: str) -> bool:
    """True when this process may start; False when another instance owns this profile.

    Windows only; fails open (True) on anything unexpected.
    """
    global _held_handle
    if sys.platform != "win32":
        return True
    try:
        if _held_handle:
            return True                                # already ours (main() called twice in-process)
        handle = _create_mutex(instance_mutex_name(profile_dir))
        if handle is None:
            _notify_existing()
            return False
        _held_handle = handle
        return True
    except Exception:
        logger.warning("single-instance guard unavailable — starting anyway", exc_info=True)
        return True
