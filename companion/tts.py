"""Speech for the sentences, from the Irodori server (the same one the Anki add-on uses)."""
import httpx

from . import selector


class TTSError(Exception):
    pass


def mp3_seconds(data):
    """Duration of an MPEG-1 Layer III file from its Xing/Info frame count, else from the first frame header (0 if unknown)."""
    bitrates = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
    rates = [44100, 48000, 32000]
    i = data.find(b"\xff")
    while 0 <= i < len(data) - 4 and (data[i + 1] & 0xE0) != 0xE0:
        i = data.find(b"\xff", i + 1)
    if i < 0 or i >= len(data) - 4:
        return 0.0
    rate_idx = (data[i + 2] >> 2) & 3
    if rate_idx == 3:
        return 0.0
    rate = rates[rate_idx]
    for tag in (b"Xing", b"Info"):
        t = data.find(tag, i, i + 200)
        if t >= 0 and len(data) >= t + 12 and data[t + 7] & 1:
            frames = int.from_bytes(data[t + 8 : t + 12], "big")
            return frames * 1152 / rate
    idx = (data[i + 2] >> 4) & 15
    if idx == 0 or idx == 15:
        return 0.0
    return len(data) * 8 / (bitrates[idx] * 1000)


def pick_voice(cfg, text, key):
    """A voice for the sentence: the gender its speech style says, otherwise any of the voices, always calm."""
    voices = cfg["VOICES"]
    name = selector.pick_voice(voices, selector.rule_gender(text), "neutral", key)
    return voices[name]["voice"], name


def _speak_once(cfg, text, voice, seed):
    body = {
        "model": cfg["MODEL"],
        "input": text,
        "voice": voice,
        "response_format": "mp3",
        "irodori": {"seed": seed},
    }
    try:
        r = httpx.post(cfg["SERVER_URL"].rstrip("/") + "/v1/audio/speech", json=body, timeout=cfg["TIMEOUT_SECONDS"])
        r.raise_for_status()
        return r.content
    except httpx.HTTPError as e:
        raise TTSError(f"voice server: {e}") from e


def synthesize(cfg, spoken, voice, base_seed=7):
    """Speech for `spoken`. A voice model now and then keeps "speaking" after the text ends (a stray breath or cry), and such
    a clip is much longer than the text needs, so the shortest of a few attempts is kept."""
    limit = cfg["MAX_SECONDS_PER_CHAR"] * len(spoken) + cfg["MAX_SECONDS_BASE"]
    best = None
    for attempt in range(1 + cfg["RETRIES"]):
        data = _speak_once(cfg, spoken, voice, base_seed + attempt)
        seconds = mp3_seconds(data)
        if best is None or (seconds and seconds < best[0]):
            best = (seconds or 1e9, data)
        if not seconds or seconds <= limit:
            return data, seconds
    return best[1], best[0]
