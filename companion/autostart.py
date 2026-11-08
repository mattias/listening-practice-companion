"""Start the program when the user logs in to Windows."""
import sys

VALUE_NAME = "ListeningPracticeCompanion"
KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def supported():
    """Only the packaged Windows program can start itself: it knows its own path."""
    return sys.platform == "win32" and getattr(sys, "frozen", False)


def is_enabled():
    if not supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except OSError:
        return False


def set_enabled(enabled):
    if not supported():
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, f'"{sys.executable}" --minimized')
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except OSError:
                pass
