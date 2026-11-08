"""Writes practice sentences for sound phenomena from the learner's known words.

A language model writes candidates, each told to contain a given piece of text (これは, 薬を ...), and
every candidate is checked here: the phenomenon is really in it, the words are known, it is a sentence
worth hearing. What fails is thrown away and asked for again. The sentence is then written the way it is
said (これは -> こりゃ), so the voice model says it so.
"""
import random
import re
import uuid

from . import morph, phenomena

MAX_ROUNDS = 6
MIN_CHARS, MAX_CHARS = 6, 50

# Language codes the app sends, as the names the models understand.
LANGUAGE_NAMES = {
    "en": "English", "sv": "Swedish", "de": "German", "fr": "French", "es": "Spanish", "it": "Italian", "pt": "Portuguese",
    "ca": "Catalan", "nl": "Dutch", "da": "Danish", "nb": "Norwegian", "fi": "Finnish", "pl": "Polish", "ru": "Russian",
    "uk": "Ukrainian", "ko": "Korean", "zh": "Chinese (Simplified)", "zh-Hant": "Chinese (Traditional)", "ar": "Arabic",
    "fa": "Persian", "he": "Hebrew", "iw": "Hebrew", "tr": "Turkish", "el": "Greek", "hr": "Croatian", "sl": "Slovenian",
    "hu": "Hungarian", "ro": "Romanian", "lt": "Lithuanian", "th": "Thai", "vi": "Vietnamese", "id": "Indonesian",
    "in": "Indonesian", "fil": "Filipino", "tl": "Filipino",
}

WRITER_SYSTEM = (
    "You are a native Japanese speaker and a teacher. You write example sentences for listening practice: natural things "
    "people really say in everyday conversation. Every sentence must make sense, be grammatical and sound natural, never "
    "like a textbook exercise or a random combination of words. Answer with JSON only."
)

# What each sentence must contain, per phenomenon, besides the words it is built around.
WA_FORMS = ["これは", "それは", "あれは", "どれは", "では", "ては", "には"]
TE_FORMS = ["ている", "ていた", "ておく", "ておいた", "てしまう", "てしまった", "ていく", "ていった"]
NO_DA_FORMS = ["のです", "のだ", "ので", "のですか", "のでした"]
NAKEREBA_FORMS = ["なければ", "なくては"]
SHORT_FORMS = ["本当", "ありがとう", "大丈夫", "ところ"]


def required_pieces(pid, vocab, n, rng):
    """For `n` sentences: (text the sentence must contain or None, a word to build it around or None)."""
    triggers = vocab.trigger_words(pid, max(n, 6), rng)
    pieces = []
    for i in range(n):
        word = triggers[i % len(triggers)] if triggers else None
        if pid == "i_wo" and word:
            pieces.append((word + "を", word))
        elif pid == "n_particle" and word:
            pieces.append((word + rng.choice(["を", "は"]), word))
        elif pid == "wa":
            pieces.append((rng.choice(WA_FORMS), None))
        elif pid == "te_aux":
            pieces.append((None, word))
        elif pid == "no_da":
            pieces.append((rng.choice(NO_DA_FORMS), None))
        elif pid == "nakereba":
            pieces.append((rng.choice(NAKEREBA_FORMS), None))
        elif pid == "toiu":
            pieces.append(("という", None))
        elif pid == "shortened":
            pieces.append((rng.choice(SHORT_FORMS), None))
        else:
            pieces.append((None, word))
    return pieces


def build_prompt(pid, pieces, allowed):
    p = phenomena.BY_ID[pid]
    lines = []
    for i, (must, word) in enumerate(pieces, 1):
        parts = []
        if must:
            parts.append(f'it must contain "{must}"')
        if word and not (must and word in must):
            parts.append(f"build it around the word {word}")
        if pid == "te_aux":
            parts.append("it must have a verb in the te-form followed by いる, いく, おく or しまう")
        if pid == "devoice_final":
            parts.append("it must end with です or ます")
        lines.append(f"{i}. " + ("; ".join(parts) if parts else "free"))
    return (
        f"Sound phenomenon to practice: {p.title}. {p.description}\n"
        f"Write {len(pieces)} sentences, one for each line below, in casual spoken style, each {MIN_CHARS + 2} to 30 characters, "
        f"each about a different everyday situation.\n"
        "Write every sentence in standard written Japanese, never in the contracted spoken form: the contraction only happens "
        "when it is spoken (write これは, not こりゃ; 食べている, not 食べてる; のです, not んです).\n"
        "Prefer simple, common everyday vocabulary and make each sentence about something ordinary people talk about.\n"
        f"Use only words from this list, plus particles and verb and adjective endings (take a word only where it fits naturally): "
        f"{', '.join(allowed)}.\n"
        + "\n".join(lines)
        + '\nReply as {"sentences": [{"ja": "...", "en": "English translation"}, ...]} in the same order.'
    )


def valid(ja, pid, vocab, max_unknown, seen):
    """The analyzed sentence if it is worth using, else None."""
    ja = ja.strip()
    if not (MIN_CHARS <= len(ja) <= MAX_CHARS) or ja in seen:
        return None
    if re.search(r"[A-Za-z]{2,}|[\r\n]", ja):
        return None
    morphs = morph.analyze(ja)
    if pid not in phenomena.phenomena(morphs):
        return None
    if len(vocab.unknown_words(morphs)) > max_unknown:
        return None
    return morphs


def make_item(ja, en, pid, morphs):
    spoken = phenomena.spoken_text(morphs, pid)
    return {
        "id": uuid.uuid4().hex,
        "text": ja,
        "spoken": spoken or ja,
        "forced": spoken is not None,
        "translation": en,
        "target": pid,
        "phenomena": phenomena.phenomena(morphs),
        "matches": [m.text for m in phenomena.find(morphs) if m.phenomenon == pid],
    }


def distribute(count, ids):
    """How many sentences each phenomenon gets, as even as it can be."""
    base, extra = divmod(count, len(ids))
    return {pid: base + (1 if i < extra else 0) for i, pid in enumerate(ids)}


def write_sentences(llm, vocab, pid, need, max_unknown, rng, seen, log=lambda m: None):
    """Up to `need` valid items for one phenomenon (fewer if the model can't deliver)."""
    items = []
    for round_ in range(MAX_ROUNDS):
        if len(items) >= need:
            break
        ask = min(12, max(4, int((need - len(items)) * 1.8) + 1))
        pieces = required_pieces(pid, vocab, ask, rng)
        triggers = [w for _, w in pieces if w]
        allowed = list(dict.fromkeys(triggers + vocab.sample(70, rng)))
        try:
            answer = llm.chat_json(WRITER_SYSTEM, build_prompt(pid, pieces, allowed), temperature=0.9)
        except Exception as e:  # a bad answer is a lost round, not a lost batch
            log(f"{pid}: round {round_ + 1} failed: {e}")
            continue
        rows = answer.get("sentences") if isinstance(answer, dict) else answer
        if not isinstance(rows, list):
            continue
        candidates = []
        for row in rows:
            if len(items) + len(candidates) >= need:
                break
            if not isinstance(row, dict) or not isinstance(row.get("ja"), str):
                continue
            morphs = valid(row["ja"], pid, vocab, max_unknown, seen)
            if morphs is None:
                continue
            seen.add(row["ja"].strip())
            candidates.append(make_item(row["ja"].strip(), str(row.get("en", "")).strip(), pid, morphs))
        items += review(llm, candidates, log)
        log(f"{pid}: round {round_ + 1}: {len(items)}/{need}")
    return items


REVIEW_SYSTEM = (
    "You are a strict native Japanese proofreader. Answer with JSON only."
)


def review(llm, items, log=lambda m: None):
    """The items a proofreader finds natural. A model writing under rules now and then produces a sentence that fits
    the rules but that nobody would say (a fragment, a broken quotation, words that do not go together)."""
    if not items:
        return items
    listing = "\n".join(f"{i + 1}. {it['text']}" for i, it in enumerate(items))
    prompt = (
        "For each sentence decide whether it is natural, grammatical Japanese that a person could really say in conversation, "
        "that makes sense on its own and is complete. Say false for a fragment, a quotation without anything quoted, an unnatural "
        "word choice, or a meaning that is unclear or absurd.\n"
        f'Reply as {{"verdicts": [true, false, ...]}} with exactly {len(items)} booleans in the same order.\n{listing}'
    )
    try:
        answer = llm.chat_json(REVIEW_SYSTEM, prompt, temperature=0.0)
        verdicts = answer.get("verdicts") if isinstance(answer, dict) else None
        if isinstance(verdicts, list) and len(verdicts) == len(items):
            kept = [it for it, ok in zip(items, verdicts) if ok is not False]
            log(f"review kept {len(kept)} of {len(items)}")
            return kept
    except Exception as e:  # a failed review keeps the sentences: they passed the other checks
        log(f"review failed: {e}")
    return items


def translate(llm, model, items, language_code, log=lambda m: None):
    """Fills in the translations in the language the learner reads (the writer's English is kept for English)."""
    if language_code in ("en", "", None) or not items:
        return
    name = LANGUAGE_NAMES.get(language_code, language_code)
    for start in range(0, len(items), 10):
        chunk = items[start : start + 10]
        listing = "\n".join(f"{i + 1}. {it['text']}" for i, it in enumerate(chunk))
        prompt = (
            f"Translate these Japanese sentences into {name}. Natural, everyday {name}, not word for word. "
            f'Reply as {{"translations": ["...", ...]}} with exactly {len(chunk)} translations in the same order.\n{listing}'
        )
        try:
            answer = llm.chat_json("You are a professional Japanese to " + name + " translator. Answer with JSON only.",
                                   prompt, temperature=0.2, keep_alive="30s", model=model)
            texts = answer.get("translations") if isinstance(answer, dict) else None
            if isinstance(texts, list) and len(texts) == len(chunk):
                for it, t in zip(chunk, texts):
                    if isinstance(t, str) and t.strip():
                        it["translation"] = t.strip()
        except Exception as e:
            log(f"translation failed: {e}")


def generate(llm, vocab, ids, count, max_unknown, language_code, translate_model=None, rng=None, log=lambda m: None):
    """The items of a batch: `count` sentences spread over the phenomena in `ids`."""
    rng = rng or random.Random()
    quotas = distribute(count, ids)
    seen = set()
    items = []
    for pid in ids:
        items += write_sentences(llm, vocab, pid, quotas[pid], max_unknown, rng, seen, log)
    translate(llm, translate_model or llm.model, items, language_code, log)
    rng.shuffle(items)
    return items
