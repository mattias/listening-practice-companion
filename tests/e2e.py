"""Runs a batch against a running service (Irodori server, Ollama and main.py up):
python tests/e2e.py <token> <phenomena,comma,separated|random> <count> [translation-language] [max-unknown]"""
import os
import sys
import time

import httpx

sys.path.insert(0, os.path.dirname(__file__))
from bench_llm_words import WORDS  # noqa: E402

BASE = "http://127.0.0.1:" + os.environ.get("COMPANION_PORT", "8089") + "/v1/sound"


def main():
    token, ids, count = sys.argv[1], sys.argv[2].split(","), int(sys.argv[3])
    language = sys.argv[4] if len(sys.argv) > 4 else "sv"
    max_unknown = int(sys.argv[5]) if len(sys.argv) > 5 else 2
    h = {"Authorization": f"Bearer {token}"}
    vocab = httpx.put(f"{BASE}/vocabulary", json={"words": WORDS}, headers=h).json()
    print("vocabulary", vocab)
    bid = httpx.post(f"{BASE}/batches", headers=h, json={
        "vocabulary_id": vocab["id"], "phenomena": ids, "count": count, "translation_language": language,
        "max_unknown": max_unknown}).json()["id"]
    started = time.time()
    while True:
        b = httpx.get(f"{BASE}/batches/{bid}", headers=h).json()
        print(f"{time.time() - started:5.0f}s {b['state']} {b['done']}/{b['total']}", flush=True)
        if b["state"] in ("done", "failed"):
            break
        time.sleep(4)
    if b["state"] == "failed":
        print("FAILED:", b["error"])
    out = os.environ.get("E2E_OUT")
    for it in b["items"]:
        print(f"[{it['target']}] {it['text']}\n    spoken: {it['spoken']} (forced={it['forced']}) voice={it.get('voice')} {it.get('seconds')}s\n"
              f"    {it['translation']}  matches={it['matches']} all={it['phenomena']}")
        if out and it.get("audio_ready"):
            audio = httpx.get(f"{BASE}/batches/{bid}/items/{it['id']}/audio", headers=h)
            os.makedirs(out, exist_ok=True)
            with open(os.path.join(out, f"{it['target']}_{it['id'][:6]}.mp3"), "wb") as f:
                f.write(audio.content)


main()
