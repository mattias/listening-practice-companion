# Sound training service API (version 1)

The service of the Companion (`companion/service.py`) listens on `PORT` (default 8089). Every call except `health` needs
`Authorization: Bearer <TOKEN>` (the token the window shows). Bodies are JSON (UTF-8).

## `GET /v1/sound/health`

No token. `{"service": "sound-training", "api": 1}`. Used to tell the address is right.

## `GET /v1/sound/status`

```json
{"api": 1,
 "llm": {"url": "http://127.0.0.1:11434", "model": "qwen3:8b", "available": true, "models": ["qwen3:8b", "..."]},
 "voice": {"ok": true}}
```

`llm.available`: the configured model is installed. `voice.ok`: the Irodori server answers.

## `GET /v1/sound/phenomena`

The phenomena the service can write sentences for:
`[{"id": "i_wo", "example": "薬を → くすりょ", "title": "...", "description": "...", "forced": true}, ...]`.
`forced` tells whether the voice is made to say it that way by writing it as it is said.

## `PUT /v1/sound/vocabulary`

`{"words": ["薬", "飲む", ...]}` → `{"id": "3d421aa47e11e820", "count": 108}`.
The learner's known words (as in the app: a word is known if its dictionary form, spelling or reading is in the list).
The id is a hash of the list: send the same list again and the same id comes back. The service keeps it on disk.

## `POST /v1/sound/batches`

```json
{"vocabulary_id": "...", "phenomena": ["i_wo", "wa"], "count": 20, "translation_language": "sv", "max_unknown": 0}
```

- `phenomena`: ids, or `["random"]` for all of them (the sentences are spread evenly).
- `count`: 1 to 200 sentences in all. `max_unknown`: how many words outside the known ones a sentence may have.
- `translation_language`: a language code (`en`, `sv`, `de`, `zh-Hant`, ...).

→ `{"id": "a1b2c3d4e5f6"}` (404 if the vocabulary id is not known any more: send it again; 400 for unknown phenomena).

## `GET /v1/sound/batches/{id}`

```json
{"id": "...", "state": "queued | writing | speaking | done | failed", "error": "", "total": 6, "done": 4,
 "items": [{"id": "...", "text": "今日、薬を飲む。", "spoken": "今日、くすりょ飲む。", "forced": true,
            "translation": "...", "target": "i_wo", "phenomena": ["i_wo", "devoice_mid"], "matches": ["薬を"],
            "audio_ready": true, "voice": "male_calm", "seconds": 2.3}]}
```

`text` is what is written and shown, `spoken` is what the voice was given. `phenomena` lists everything found in the
sentence, `target` the one it was written for, `matches` where in the text. `total` is known once the sentences are
written (`state` `speaking`); items appear then, with `audio_ready` false until their audio is done.

## `GET /v1/sound/batches/{id}/items/{item}/audio`

The mp3 of an item (404 until `audio_ready`).

## `DELETE /v1/sound/batches/{id}`

Removes a batch and its audio. The service also keeps only the latest 30 batches for 21 days.
