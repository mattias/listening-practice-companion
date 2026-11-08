"""Runs the service inside this program (in a thread), so the window can start and stop it."""
import socket
import threading
import time
import urllib.request

import uvicorn

from . import config
from .service import create_app


def lan_addresses():
    """This computer's addresses on the local network (what the phone connects to), the likeliest first."""
    found = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and not ip.startswith("169.254.") and ip not in found:
                found.append(ip)
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            ip = s.getsockname()[0]
            if ip in found:
                found.remove(ip)
            found.insert(0, ip)
    except OSError:
        pass
    return found


def port_free(port, host="0.0.0.0"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
        except OSError:
            return False
    return True


class Service:
    """The sound training service, started and stopped on demand."""

    def __init__(self):
        self._server = None
        self._thread = None
        self.error = ""

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive() and self._server is not None and self._server.started

    def start(self, cfg):
        """Starts listening. Raises RuntimeError if the port is taken."""
        if self.running:
            return
        host = "0.0.0.0" if cfg["ALLOW_NETWORK"] else "127.0.0.1"
        port = int(cfg["PORT"])
        if not port_free(port, host):
            raise RuntimeError(f"Port {port} is already in use (is the Companion already running?). Change the port or close the other program.")
        app = create_app(config.service_config(cfg))
        server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning", log_config=None))
        self._server = server
        self.error = ""

        def serve():
            try:
                server.run()
            except Exception as e:  # noqa: BLE001
                self.error = str(e)

        self._thread = threading.Thread(target=serve, name="service", daemon=True)
        self._thread.start()
        deadline = time.time() + 15
        while time.time() < deadline and not server.started and self._thread.is_alive():
            time.sleep(0.1)
        if not server.started:
            raise RuntimeError(self.error or "The service did not start.")

    def stop(self):
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=10)
        self._server = None
        self._thread = None


def service_health(port, timeout=2):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{int(port)}/v1/sound/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False
