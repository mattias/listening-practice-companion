import json
import os
import sys
import time

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from companion import config, generator, service  # noqa: E402
from companion.vocab import Vocabulary  # noqa: E402

CONFIG = config.service_config({**config.DEFAULTS, "TOKEN": "x"})

WORDS = "薬 本 水 息 友達 飲む 食べる 待つ 買う 行く これ それ 私 学校 今日 昨日 は が を に で と の も です ます だ た て いる ない ので 好き 、 。 ？ 静か".split()


class FakeLLM:
    """Answers the way a model would: sentences for each numbered line, with translations."""

    model = "fake"

    def __init__(self, sentences, reject=()):
        self.sentences = sentences
        self.calls = 0
        self.reject = set(reject)
        self.reviews = 0

    def chat_json(self, system, user, temperature=0.8, keep_alive="2m", model=None):
        self.calls += 1
        if "verdicts" in user:
            n = int(user.split("exactly ")[1].split(" ")[0])
            self.reviews += 1
            # Only the first review throws anything out.
            return {"verdicts": [not (self.reviews == 1 and i in self.reject) for i in range(n)]}
        if "Translate" in user:
            n = int(user.split("exactly ")[1].split(" ")[0])
            return {"translations": [f"översättning {i}" for i in range(n)]}
        return {"sentences": [{"ja": s, "en": "english " + s} for s in self.sentences]}

    def unload(self, model=None):
        pass

    def models(self):
        return ["fake"]


def test_generate_keeps_only_valid_sentences():
    vocab = Vocabulary(WORDS)
    llm = FakeLLM([
        "今日、薬を飲む。",         # i_wo, known
        "水を飲む。",             # no i-row before を
        "友達を待つ。",           # not the phenomenon (ち before を? 友達 ends in ち): valid
        "今日、薬を飲む。",         # a duplicate
        "I take 薬を. today",           # latin letters
        "薬を飲みたいですか。",   # words outside the known ones
    ])
    items = generator.generate(llm, vocab, ["i_wo"], 2, 0, "en", rng=__import__("random").Random(1))
    texts = [i["text"] for i in items]
    assert "水を飲む。" not in texts
    assert texts.count("今日、薬を飲む。") == 1
    assert all("i_wo" in i["phenomena"] for i in items)
    # 薬を is not respelled: the voice says it from the normal text.
    by_text = {i["text"]: i for i in items}
    assert by_text["今日、薬を飲む。"]["spoken"] == "今日、薬を飲む。"
    assert by_text["今日、薬を飲む。"]["forced"] is False


def test_a_written_contraction_is_forced():
    vocab = Vocabulary(WORDS + ["これ"])
    llm = FakeLLM(["これは本です、今日。", "これは私の本ですか。"])
    items = generator.generate(llm, vocab, ["wa"], 1, 0, "en", rng=__import__("random").Random(1))
    assert items and items[0]["forced"] is True and items[0]["spoken"].startswith("こりゃ")


def test_the_proofreader_can_throw_a_sentence_out():
    vocab = Vocabulary(WORDS)
    # The first valid sentence is judged unnatural.
    llm = FakeLLM(["今日、薬を飲む。", "友達を待つ。"], reject={0})
    items = generator.generate(llm, vocab, ["i_wo"], 1, 0, "en", rng=__import__("random").Random(1))
    assert [i["text"] for i in items] == ["友達を待つ。"]


def test_translation_in_the_learners_language():
    vocab = Vocabulary(WORDS)
    llm = FakeLLM(["今日、薬を飲む。", "友達を待つ。"])
    items = generator.generate(llm, vocab, ["i_wo"], 2, 0, "sv", rng=__import__("random").Random(1))
    assert items and all(i["translation"].startswith("översättning") for i in items)


def test_distribution_over_phenomena():
    assert generator.distribute(7, ["a", "b", "c"]) == {"a": 3, "b": 2, "c": 2}


@pytest.fixture
def client(tmp_path):
    cfg = {**CONFIG, "DATA_DIR": str(tmp_path), "TOKEN": "secret", "LLM_URL": "http://x", "LLM_MODEL": "fake"}
    llm = FakeLLM(["今日、薬を飲む。", "友達を待つ。", "今日、息を待つ。"])

    def speak(c, text, voice, base_seed=7):
        return b"\xff\xfb\x90\x00" + text.encode("utf-8"), 1.0

    return TestClient(service.create_app(cfg, llm=llm, speak=speak))


AUTH = {"Authorization": "Bearer secret"}


def test_needs_the_token(client):
    assert client.get("/v1/sound/health").status_code == 200
    assert client.get("/v1/sound/phenomena").status_code == 401
    assert client.get("/v1/sound/phenomena", headers=AUTH).status_code == 200


def test_a_batch_from_start_to_audio(client):
    vocab = client.put("/v1/sound/vocabulary", json={"words": WORDS}, headers=AUTH).json()
    assert vocab["count"] == len(set(WORDS))
    created = client.post("/v1/sound/batches", headers=AUTH, json={
        "vocabulary_id": vocab["id"], "phenomena": ["i_wo"], "count": 3, "translation_language": "en"})
    assert created.status_code == 200
    bid = created.json()["id"]
    for _ in range(100):
        batch = client.get(f"/v1/sound/batches/{bid}", headers=AUTH).json()
        if batch["state"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert batch["state"] == "done", batch
    assert batch["done"] == batch["total"] == len(batch["items"]) >= 1
    item = batch["items"][0]
    assert item["audio_ready"] and item["target"] == "i_wo"
    audio = client.get(f"/v1/sound/batches/{bid}/items/{item['id']}/audio", headers=AUTH)
    assert audio.status_code == 200 and audio.content.startswith(b"\xff\xfb")
    assert client.delete(f"/v1/sound/batches/{bid}", headers=AUTH).status_code == 200
    assert client.get(f"/v1/sound/batches/{bid}", headers=AUTH).status_code == 404


def test_bad_requests(client):
    assert client.post("/v1/sound/batches", headers=AUTH, json={
        "vocabulary_id": "nope", "phenomena": ["i_wo"], "count": 3}).status_code == 404
    vocab = client.put("/v1/sound/vocabulary", json={"words": WORDS}, headers=AUTH).json()
    assert client.post("/v1/sound/batches", headers=AUTH, json={
        "vocabulary_id": vocab["id"], "phenomena": ["nonsense"], "count": 3}).status_code == 400
