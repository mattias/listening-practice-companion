"""Tries models on the real task: writing sentences that show a sound phenomenon, from known words.
Not a test (needs Ollama and models): python tests/bench_llm.py <model> [phenomenon-id]"""
import json
import os
import random
import sys
import time

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from companion import morph, phenomena  # noqa: E402
from companion.vocab import Vocabulary  # noqa: E402

from bench_llm_words import WORDS  # noqa: E402


def ask(model, system, user, base="http://127.0.0.1:11434"):
    # Ollama's own API: thinking can be switched off, which the OpenAI-style one does not offer.
    body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False, "think": False, "format": "json", "keep_alive": "5m",
            "options": {"temperature": 0.8, "num_ctx": 4096}}
    t = time.time()
    r = httpx.post(base + "/api/chat", json=body, timeout=300)
    r.raise_for_status()
    return r.json()["message"]["content"], time.time() - t


def main():
    model = sys.argv[1]
    pid = sys.argv[2] if len(sys.argv) > 2 else "i_wo"
    vocab = Vocabulary(WORDS)
    pheno = phenomena.BY_ID[pid]
    triggers = vocab.trigger_words(pid, 6)
    allowed = vocab.sample(60)
    system = ("You are a native Japanese speaker and a teacher. You write example sentences for listening practice: "
              "natural things people really say in everyday conversation. Every sentence must make sense, be grammatical "
              "and sound natural, never like a textbook exercise or a random word combination. Answer with JSON only.")
    user = (
        f"Sound phenomenon to practice: {pheno.title}. {pheno.description}\n"
        f"Write 10 different sentences where this can be heard, each 8 to 25 characters, casual everyday speech.\n"
        f"Build them around these words where you can: {', '.join(triggers)}.\n"
        f"Use only words from this list (plus particles and verb/adjective endings): {', '.join(allowed)}.\n"
        'Reply as {"sentences": [{"ja": "...", "en": "English translation"}, ...]}.'
    )
    text, seconds = ask(model, system, user)
    print(f"{model}: {seconds:.1f} s")
    try:
        items = json.loads(text)["sentences"]
    except Exception as e:
        print("bad JSON:", e, text[:300])
        return
    ok = known = 0
    for it in items:
        ms = morph.analyze(it["ja"])
        has = pid in phenomena.phenomena(ms)
        unknown = vocab.unknown_words(ms)
        ok += has
        known += not unknown
        print(("OK " if has else "-- ") + ("known " if not unknown else f"unk{len(unknown)} ") + it["ja"] + "  |  " + it.get("en", ""))
    print(f"phenomenon present {ok}/{len(items)}, all words known {known}/{len(items)}")


main()
