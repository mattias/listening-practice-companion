"""The Irodori voice server: is it running, and if it was installed by the Irodori Audio Anki add-on, start it.

The Companion does not install the server: that is what the Irodori Audio add-on (or the server's own
instructions) is for. This only finds an existing install and starts it, so the voice is there when it is needed."""
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request

IS_WINDOWS = sys.platform == "win32"
CREATE_NO_WINDOW = 0x08000000


def default_dir():
    """Where the Irodori Audio add-on installs the server."""
    if IS_WINDOWS:
        return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "IrodoriAudio")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/IrodoriAudio")
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "irodori-audio")


class Paths:
    def __init__(self, root):
        self.root = root
        self.server = os.path.join(root, "server")
        self.bin = os.path.join(root, "bin")
        self.marker = os.path.join(root, "installed.json")
        exe = "Scripts" if IS_WINDOWS else "bin"
        self.venv_python = os.path.join(self.server, ".venv", exe, "python.exe" if IS_WINDOWS else "python")


def is_installed(root):
    p = Paths(root)
    return os.path.isfile(p.marker) and os.path.isfile(p.venv_python)


def health(url, timeout=2):
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def is_local(url):
    return url.split("://", 1)[-1].split(":")[0].split("/")[0] in ("127.0.0.1", "localhost")


def port_of(url):
    tail = url.rsplit(":", 1)[-1].split("/")[0]
    return int(tail) if tail.isdigit() else 8088


def clean_env(extra_path=None):
    """Environment for the server's process, without Python settings of this program leaking in."""
    env = dict(os.environ)
    for key in ("PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONUSERBASE", "VIRTUAL_ENV", "PYTHONEXECUTABLE", "_MEIPASS2"):
        env.pop(key, None)
    env["PYTHONUTF8"] = "1"
    if extra_path:
        env["PATH"] = extra_path + os.pathsep + env.get("PATH", "")
    return env


def kill_tree(proc):
    if proc is None or proc.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                           creationflags=CREATE_NO_WINDOW, timeout=15)
        else:
            os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def start(root, url, log, timeout=900):
    """Starts the server installed in `root` on the address `url`, and waits until it answers. Returns the process,
    or None if one already answers. Raises RuntimeError with what went wrong."""
    if health(url):
        return None
    if not is_local(url):
        raise RuntimeError(f"The voice server at {url} is not on this computer, so it can not be started from here.")
    if not is_installed(root):
        raise RuntimeError(
            "The voice server is not installed. Install it with the Irodori Audio add-on for Anki "
            "(Tools > Irodori Audio > Set up local server), or follow the server's own instructions.")
    paths = Paths(root)
    env = clean_env(paths.bin)
    env["IRODORI_PRELOAD"] = "true"  # load the model at startup so the first sentence is fast
    cmd = [paths.venv_python, "-m", "irodori_openai_tts", "--host", "127.0.0.1", "--port", str(port_of(url))]
    logfile = open(os.path.join(root, "server.log"), "w", encoding="utf-8")
    kwargs = {"creationflags": CREATE_NO_WINDOW} if IS_WINDOWS else {"start_new_session": True}
    proc = subprocess.Popen(cmd, cwd=paths.server, env=env, stdout=logfile, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, **kwargs)
    log("Starting the voice server (loading the voice model)...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("The voice server stopped while starting. See " + os.path.join(root, "server.log"))
        if health(url):
            log("The voice server is ready.")
            return proc
        time.sleep(1)
    kill_tree(proc)
    raise RuntimeError("The voice server did not become ready in time.")
