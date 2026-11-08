"""python -m companion [window|serve] [--minimized]"""
import argparse
import logging
import os
import sys
import threading

from . import __version__, config, irodori
from .runner import Service


def setup_logging():
    os.makedirs(config.config_dir(), exist_ok=True)
    logging.basicConfig(filename=config.log_path(), level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # A packaged program without a console has no stdout: print() and uvicorn's output go to the log.
    if sys.stdout is None or sys.stderr is None:
        log = open(config.log_path(), "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log


def serve(cfg):
    """No window: runs the service until interrupted (for a computer without a screen, or to try it from a terminal)."""
    voice_proc = None
    if cfg["IRODORI_AUTO_START"] and not irodori.health(cfg["IRODORI_URL"]):
        try:
            voice_proc = irodori.start(cfg["IRODORI_DIR"] or irodori.default_dir(), cfg["IRODORI_URL"], print)
        except RuntimeError as e:
            print("Voice server:", e)
    service = Service()
    service.start(cfg)
    print(f"Listening Practice Companion {__version__}: listening on port {cfg['PORT']}. Token: {cfg['TOKEN']}")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
        irodori.kill_tree(voice_proc)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="companion", description="Listening Practice Companion")
    parser.add_argument("mode", nargs="?", choices=["window", "serve"], default="window")
    parser.add_argument("--minimized", action="store_true", help="open the window minimized")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    setup_logging()
    cfg = config.load()
    if args.mode == "serve":
        serve(cfg)
        return
    from .gui import App

    App(cfg, minimized=args.minimized).mainloop()


if __name__ == "__main__":
    main()
