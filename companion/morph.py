"""Morphological analysis of Japanese with IPADIC (Janome), the same dictionary the Listening Practice
app's Kuromoji uses, so a sentence is split and read the same way on both sides."""
from dataclasses import dataclass

_tokenizer = None

# The particles は, へ and を are said わ, え and お.
PARTICLE_SOUNDS = {"は": "わ", "へ": "え", "を": "お"}
_KATA_TO_HIRA = {c: c - 0x60 for c in range(0x30A1, 0x30F7)}


@dataclass(frozen=True)
class Morph:
    """One morpheme: how it is written, how it is said (hiragana), part of speech (levels 1 and 2) and dictionary form."""

    surface: str
    reading: str
    pos: str
    pos2: str
    base: str


def to_hiragana(text):
    return text.translate(_KATA_TO_HIRA)


def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        from janome.tokenizer import Tokenizer  # loading the dictionary takes a moment, so only when first needed

        _tokenizer = Tokenizer()
    return _tokenizer


def analyze(text):
    """Every morpheme of `text`, particles and punctuation included."""
    result = []
    for t in _get_tokenizer().tokenize(text):
        parts = t.part_of_speech.split(",")
        pos, pos2 = parts[0], (parts[1] if len(parts) > 1 else "*")
        reading = to_hiragana(t.reading) if t.reading and t.reading != "*" else t.surface
        base = t.base_form if t.base_form and t.base_form != "*" else t.surface
        if pos == "助詞" and t.surface in PARTICLE_SOUNDS:
            reading = PARTICLE_SOUNDS[t.surface]
        result.append(Morph(t.surface, reading, pos, pos2, base))
    return result


def is_symbol(m):
    """Punctuation, symbols and spaces are not words."""
    return m.pos == "記号" or not m.surface.strip() or not any(c.isalnum() for c in m.surface)
