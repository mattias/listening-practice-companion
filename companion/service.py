"""The sound training service: the Listening Practice app asks for a batch of sentences for a sound phenomenon, and
gets sentences, translations and speech back. Everything heavy happens here on the computer: a language model
writes the sentences, the Irodori server speaks them."""
import json
import os
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import generator, phenomena, tts
from .llm import LLM
from .vocab import Vocabulary

API_VERSION = 1
KEEP_BATCHES = 30
KEEP_DAYS = 21


class VocabularyBody(BaseModel):
    words: list[str]


class BatchBody(BaseModel):
    vocabulary_id: str
    # Phenomenon ids, or ["random"] for all of them.
    phenomena: list[str]
    count: int = 20
    translation_language: str = "en"
    # How many words outside the known ones a sentence may have (the app's n+ setting).
    max_unknown: int = 0


def create_app(cfg, llm=None, speak=None):
    """`cfg` is the service's settings; `llm` and `speak` can be replaced (tests)."""
    data_dir = cfg["DATA_DIR"]
    os.makedirs(os.path.join(data_dir, "vocab"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "batches"), exist_ok=True)
    llm = llm or LLM(cfg["LLM_URL"], cfg["LLM_MODEL"], cfg.get("LLM_API_KEY", ""), cfg.get("LLM_KIND", "ollama"))
    speak = speak or tts.synthesize
    app = FastAPI(title="Listening Practice sound training", version=str(API_VERSION))
    pool = ThreadPoolExecutor(max_workers=1)  # one batch at a time: the graphics card is shared
    vocabularies = {}
    batches = {}
    lock = threading.Lock()

    def auth(authorization: str = Header(default="")):
        token = cfg.get("TOKEN", "")
        if token and authorization != f"Bearer {token}":
            raise HTTPException(401, "wrong or missing token")

    def vocab_path(vid):
        return os.path.join(data_dir, "vocab", vid + ".json")

    def get_vocab(vid):
        if vid not in vocabularies:
            try:
                with open(vocab_path(vid), encoding="utf-8") as f:
                    vocabularies[vid] = Vocabulary(json.load(f))
            except OSError:
                raise HTTPException(404, "unknown vocabulary: send it again") from None
        return vocabularies[vid]

    def batch_dir(bid):
        return os.path.join(data_dir, "batches", bid)

    def save(batch):
        with open(os.path.join(batch_dir(batch["id"]), "batch.json"), "w", encoding="utf-8") as f:
            json.dump(batch, f, ensure_ascii=False)

    def load_batches():
        root = os.path.join(data_dir, "batches")
        for name in os.listdir(root):
            try:
                with open(os.path.join(root, name, "batch.json"), encoding="utf-8") as f:
                    b = json.load(f)
                if b["state"] not in ("done", "failed"):
                    b["state"], b["error"] = "failed", "the service was restarted"
                batches[b["id"]] = b
            except (OSError, ValueError, KeyError):
                continue

    def prune():
        old = sorted(batches.values(), key=lambda b: b["created"])
        for b in old[: max(0, len(old) - KEEP_BATCHES)] + [b for b in old if time.time() - b["created"] > KEEP_DAYS * 86400]:
            if b["id"] in batches and b["state"] in ("done", "failed"):
                shutil.rmtree(batch_dir(b["id"]), ignore_errors=True)
                batches.pop(b["id"], None)

    def translate_model():
        wanted = cfg.get("TRANSLATE_MODEL", "")
        if wanted:
            return wanted
        # A translation model if there is one (translategemma), else the one that writes.
        for name in llm.models():
            if "translategemma" in name.lower() or name.lower().startswith("tgemma"):
                return name
        return llm.model

    def run(batch, body, vocab):
        log = lambda m: print(m, flush=True)  # noqa: E731
        try:
            ids = [p.id for p in phenomena.CATALOG] if body.phenomena == ["random"] else body.phenomena
            batch["state"] = "writing"
            save(batch)
            items = generator.generate(llm, vocab, ids, body.count, body.max_unknown, body.translation_language,
                                       translate_model(), log=log)
            # Free the graphics card for the voice before it is used.
            llm.unload()
            llm.unload(translate_model())
            if not items:
                raise RuntimeError("the model wrote no usable sentences: is it installed and answering?")
            batch["total"] = len(items)
            batch["state"] = "speaking"
            os.makedirs(batch_dir(batch["id"]), exist_ok=True)
            for it in items:
                it["audio_ready"] = False
                batch["items"].append(it)
            save(batch)
            for it in items:
                voice, voice_name = tts.pick_voice(cfg, it["spoken"], it["id"])
                data, seconds = speak(cfg, it["spoken"], voice)
                with open(os.path.join(batch_dir(batch["id"]), it["id"] + ".mp3"), "wb") as f:
                    f.write(data)
                it.update(audio_ready=True, voice=voice_name, seconds=round(seconds, 2))
                batch["done"] += 1
            batch["state"] = "done"
        except Exception as e:  # noqa: BLE001 - whatever went wrong is reported to the app
            batch["state"], batch["error"] = "failed", str(e) or e.__class__.__name__
        save(batch)
        prune()

    @app.get("/v1/sound/health")
    def health():
        return {"service": "sound-training", "api": API_VERSION}

    @app.get("/v1/sound/status", dependencies=[Depends(auth)])
    def status():
        models = llm.models()
        tts_ok = False
        try:
            tts_ok = httpx.get(cfg["SERVER_URL"].rstrip("/") + "/health", timeout=5).status_code == 200
        except httpx.HTTPError:
            pass
        return {
            "api": API_VERSION,
            "llm": {"url": cfg["LLM_URL"], "model": llm.model, "available": llm.model in models if models else False,
                    "models": models},
            "voice": {"ok": tts_ok},
        }

    @app.get("/v1/sound/phenomena", dependencies=[Depends(auth)])
    def list_phenomena():
        return [
            {"id": p.id, "example": p.example, "title": p.title, "description": p.description, "forced": p.forceable}
            for p in phenomena.CATALOG
        ]

    @app.put("/v1/sound/vocabulary", dependencies=[Depends(auth)])
    def put_vocabulary(body: VocabularyBody):
        v = Vocabulary(body.words)
        with open(vocab_path(v.id), "w", encoding="utf-8") as f:
            json.dump(v.words, f, ensure_ascii=False)
        vocabularies[v.id] = v
        return {"id": v.id, "count": len(v)}

    @app.post("/v1/sound/batches", dependencies=[Depends(auth)])
    def create_batch(body: BatchBody):
        vocab = get_vocab(body.vocabulary_id)
        unknown = [p for p in body.phenomena if p != "random" and p not in phenomena.BY_ID]
        if unknown or not body.phenomena:
            raise HTTPException(400, f"unknown phenomenon: {unknown or 'none given'}")
        if not 1 <= body.count <= 200:
            raise HTTPException(400, "count must be 1 to 200")
        bid = uuid.uuid4().hex[:12]
        batch = {"id": bid, "created": time.time(), "state": "queued", "error": "", "total": 0, "done": 0, "items": [],
                 "phenomena": body.phenomena, "translation_language": body.translation_language}
        os.makedirs(batch_dir(bid), exist_ok=True)
        with lock:
            batches[bid] = batch
        save(batch)
        pool.submit(run, batch, body, vocab)
        return {"id": bid}

    @app.get("/v1/sound/batches/{bid}", dependencies=[Depends(auth)])
    def get_batch(bid: str):
        batch = batches.get(bid)
        if batch is None:
            raise HTTPException(404, "no such batch")
        return batch

    @app.get("/v1/sound/batches/{bid}/items/{item}/audio", dependencies=[Depends(auth)])
    def get_audio(bid: str, item: str):
        path = os.path.join(batch_dir(bid), os.path.basename(item) + ".mp3")
        if bid not in batches or not os.path.isfile(path):
            raise HTTPException(404, "no such audio")
        return FileResponse(path, media_type="audio/mpeg")

    @app.delete("/v1/sound/batches/{bid}", dependencies=[Depends(auth)])
    def delete_batch(bid: str):
        if batches.pop(bid, None) is not None:
            shutil.rmtree(batch_dir(bid), ignore_errors=True)
        return {"ok": True}

    load_batches()
    return app
