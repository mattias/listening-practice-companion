"""The program's settings, kept in one JSON file in the user's config folder."""
import json
import os
import secrets
import sys

APP_DIR_NAME = "ListeningPracticeCompanion"

# The six voices the Irodori server has when it is set up with the Irodori Audio Anki add-on (or by hand with the
# voice files from that add-on). The names must match the files in the server's voices folder.
DEFAULT_VOICES = {
    "female_calm": {"gender": "f", "voice": "female_calm"},
    "female_bright": {"gender": "f", "voice": "female_bright"},
    "female_cool": {"gender": "f", "voice": "female_cool"},
    "male_calm": {"gender": "m", "voice": "male_calm"},
    "male_young": {"gender": "m", "voice": "male_young"},
    "male_deep": {"gender": "m", "voice": "male_deep"},
}

DEFAULTS = {
    # The voice server (Irodori).
    "IRODORI_URL": "http://127.0.0.1:8088",
    "IRODORI_MODEL": "irodori-tts",
    # Folder of the server installed by the Irodori Audio Anki add-on; empty = the add-on's default folder.
    "IRODORI_DIR": "",
    "IRODORI_AUTO_START": True,
    # The language model that writes and translates the sentences.
    "LLM_KIND": "ollama",
    "LLM_URL": "http://127.0.0.1:11434",
    "LLM_MODEL": "qwen3:8b",
    "LLM_API_KEY": "",
    "TRANSLATE_MODEL": "",
    # How the phone connects.
    "ALLOW_NETWORK": True,
    "PORT": 8089,
    "TOKEN": "",
    # Behaviour.
    "START_SERVICE_ON_LAUNCH": True,
    "START_WITH_WINDOWS": False,
    # Speech.
    "TIMEOUT_SECONDS": 120,
    "RETRIES": 2,
    "MAX_SECONDS_PER_CHAR": 0.18,
    "MAX_SECONDS_BASE": 0.6,
    "VOICES": DEFAULT_VOICES,
}


def config_dir():
    if sys.platform == "win32":
        return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_DIR_NAME)
    if sys.platform == "darwin":
        return os.path.expanduser(f"~/Library/Application Support/{APP_DIR_NAME}")
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "listening-practice-companion")


def data_dir():
    """Where finished sentences and the words the app sent are kept."""
    return os.path.join(config_dir(), "data")


def log_path():
    return os.path.join(config_dir(), "companion.log")


def config_path():
    return os.path.join(config_dir(), "config.json")


def new_token():
    return secrets.token_urlsafe(24)


def load(path=None):
    """The settings with defaults for what is missing. A token is made on first use."""
    path = path or config_path()
    cfg = json.loads(json.dumps(DEFAULTS))
    try:
        with open(path, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    if not cfg["TOKEN"]:
        cfg["TOKEN"] = new_token()
        save(cfg, path)
    return cfg


def save(cfg, path=None):
    path = path or config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def service_config(cfg):
    """The settings the service itself uses."""
    return {
        "SERVER_URL": cfg["IRODORI_URL"],
        "MODEL": cfg["IRODORI_MODEL"],
        "VOICES": cfg["VOICES"],
        "TIMEOUT_SECONDS": cfg["TIMEOUT_SECONDS"],
        "RETRIES": cfg["RETRIES"],
        "MAX_SECONDS_PER_CHAR": cfg["MAX_SECONDS_PER_CHAR"],
        "MAX_SECONDS_BASE": cfg["MAX_SECONDS_BASE"],
        "DATA_DIR": data_dir(),
        "TOKEN": cfg["TOKEN"],
        "LLM_KIND": cfg["LLM_KIND"],
        "LLM_URL": cfg["LLM_URL"],
        "LLM_MODEL": cfg["LLM_MODEL"],
        "LLM_API_KEY": cfg["LLM_API_KEY"],
        "TRANSLATE_MODEL": cfg["TRANSLATE_MODEL"],
    }
