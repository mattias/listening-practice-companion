"""Downloading models into Ollama."""
import json

import httpx

# What the program recommends: small enough to share a 16 GB graphics card with the voice model, and it wrote the most
# natural sentences in tests.
RECOMMENDED_MODEL = "qwen3:8b"


def pull(base_url, model, progress, cancelled=lambda: False):
    """Downloads `model` into Ollama at `base_url`. `progress(text)` is told how far it has come.
    Returns False if cancelled. Raises RuntimeError if Ollama refuses."""
    try:
        with httpx.stream("POST", base_url.rstrip("/") + "/api/pull", json={"model": model, "stream": True}, timeout=None) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if cancelled():
                    return False
                if not line:
                    continue
                data = json.loads(line)
                if data.get("error"):
                    raise RuntimeError(data["error"])
                total, done = data.get("total"), data.get("completed")
                if total and done is not None:
                    progress(f"{data.get('status', 'downloading')} {done * 100 // total}%")
                else:
                    progress(data.get("status", ""))
    except httpx.HTTPError as e:
        raise RuntimeError(f"Could not reach Ollama at {base_url}: {e}. Is Ollama installed and running (ollama.com)?") from e
    return True
