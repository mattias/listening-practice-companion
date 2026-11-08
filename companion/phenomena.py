"""Ways spoken Japanese runs together or changes, so that what is heard differs from the written form.

The detection rules mirror the Listening Practice app's Kotlin version (SoundPhenomena.kt); both are
tested against the same sentences. `spoken_text` rewrites a sentence the way it is said, so the voice
model is made to say it that way.
"""
import re
from dataclasses import dataclass

I_ROW = set("いきしちにひみりぎじぢびぴ")
WA_CONTRACTING_WORDS = {"これ", "それ", "あれ", "どれ"}
WA_CONTRACTING_PARTICLES = {"て", "で", "に"}
TE_HELPERS = {"いる", "いく", "おく", "しまう"}
DEVOICING = set("きくしすちつひふ")
VOICELESS_START = set("かきくけこさしすせそたちつてとはひふへほぱぴぷぺぽ")
NASAL_G_KANA = set("がぎぐげご")
FINAL_FILLERS = {"ね", "よ", "か", "な", "わ", "ぞ", "さ"}
# Words that start with ほんとう (ほんとうに), and words that are only the word itself (ところ, not ところで).
SHORTENABLE_PREFIXES = {"ほんとう": "ほんと", "ありがとう": "ありがと", "だいじょうぶ": "だいじょぶ"}
SHORTENABLE_WORDS = {"ところ": "とこ"}



@dataclass(frozen=True)
class Phenomenon:
    id: str
    example: str
    title: str
    description: str
    # The sentence can be written the way it is said (これは -> こりゃ), which is how people write it. A change nobody writes
    # (薬を -> くすりょ) is left out: the voice says it right from the normal text, and a made-up spelling could change the accent.
    forceable: bool = True


CATALOG = [
    Phenomenon("i_wo", "薬を → くすりょ", "い-row sound + を",
               "A word ending in い, き, し, ち, に, ひ, み or り (or a voiced form) before the particle を: the two vowels run into one, 'kusuri o' sounds like 'kusuryo'. The text is written normally; the voice says it so by itself.", forceable=False),
    Phenomenon("n_particle", "本を → ほんの", "ん + を / は / に / が",
               "ん before a particle runs into its vowel: 本を sounds like 'honno', パンは like 'panna'. The text is written normally; the voice says it so by itself.", forceable=False),
    Phenomenon("wa", "これは → こりゃ", "Contractions with は",
               "これ/それ/あれ/どれ, て, で or に before は contract: これは → こりゃ, では → じゃ, ては → ちゃ, には → にゃ."),
    Phenomenon("te_aux", "食べている → 食べてる", "て-form + helper verb",
               "ている → てる, ていく → てく, ておく → とく, てしまう → ちゃう, でしまう → じゃう."),
    Phenomenon("no_da", "のだ → んだ", "のだ / のです / ので",
               "の before だ, です or で is said ん: のだ → んだ, ので → んで."),
    Phenomenon("nakereba", "なければ → なきゃ", "なければ / なくては",
               "なければ → なきゃ, なくては → なくちゃ."),
    Phenomenon("toiu", "という → って", "という",
               "という is said って (or ていう)."),
    Phenomenon("devoice_final", "です → des", "Devoiced です / ます",
               "The す of です and ます at the end of a sentence is hardly voiced: 'des', 'mas'.", forceable=False),
    Phenomenon("devoice_mid", "しました → shmashta", "Devoiced vowels inside words",
               "き く し す ち つ ひ ふ lose the voice of their vowel before a voiceless consonant.", forceable=False),
    Phenomenon("nasal_g", "学校が → がっこうŋa", "Nasal が",
               "が inside a sentence is often nasal [ŋ]. Fading in younger speakers.", forceable=False),
    Phenomenon("shortened", "本当 → ほんと", "Shortened words",
               "Words often said shorter: ほんとう → ほんと, ところ → とこ, ありがとう → ありがと, だいじょうぶ → だいじょぶ."),
]
BY_ID = {p.id: p for p in CATALOG}


@dataclass(frozen=True)
class Match:
    """Where a phenomenon was found: morphemes start..end (end exclusive), or the whole sentence (start == end == -1)."""

    phenomenon: str
    start: int
    end: int
    text: str


def _shortened(reading):
    """The reading said shorter, or None if the word is not one that is."""
    if reading in SHORTENABLE_WORDS:
        return SHORTENABLE_WORDS[reading]
    for long, short in SHORTENABLE_PREFIXES.items():
        if reading.startswith(long):
            return short + reading[len(long):]
    return None


def _is_particle(m, *surfaces):
    return m.pos == "助詞" and m.surface in surfaces


def find(morphs):
    found = []

    def add(pid, start, end):
        found.append(Match(pid, start, end, "".join(m.surface for m in morphs[start:end])))

    for i, m in enumerate(morphs):
        prev = morphs[i - 1] if i > 0 else None
        nxt = morphs[i + 1] if i + 1 < len(morphs) else None
        if prev is not None and prev.pos not in ("助詞", "記号"):
            if _is_particle(m, "を") and prev.reading[-1:] in I_ROW:
                add("i_wo", i - 1, i + 1)
            if _is_particle(m, "を", "は", "に", "が") and prev.reading[-1:] == "ん":
                add("n_particle", i - 1, i + 1)
        if prev is not None and _is_particle(m, "は") and (
            prev.reading in WA_CONTRACTING_WORDS or (prev.pos == "助詞" and prev.surface in WA_CONTRACTING_PARTICLES)
        ):
            add("wa", i - 1, i + 1)
        if prev is not None and nxt is not None and _is_particle(m, "て", "で") and nxt.base in TE_HELPERS:
            add("te_aux", i - 1, i + 2)
        if nxt is not None and m.surface == "の" and m.pos == "名詞" and nxt.surface in ("だ", "です", "で", "だった", "でした"):
            add("no_da", i, i + 2)
        if m.surface == "ので" and m.pos == "助詞":
            add("no_da", i, i + 1)
        if _is_particle(m, "という") or (nxt is not None and _is_particle(m, "と") and nxt.base == "いう"):
            add("toiu", i, i + 1)
        if _shortened(m.reading) is not None:
            add("shortened", i, i + 1)
        if _is_particle(m, "が") and prev is not None and prev.pos != "助詞":
            add("nasal_g", i - 1, i + 1)
        elif m.pos != "助詞" and any(c in NASAL_G_KANA for c in m.reading[1:]):
            add("nasal_g", i, i + 1)

    text = "".join(m.surface for m in morphs)
    for hit in re.finditer("なければ|なくては", text):
        found.append(Match("nakereba", -1, -1, hit.group()))

    tail = list(morphs)
    while tail and (tail[-1].pos == "記号" or (tail[-1].pos == "助詞" and tail[-1].surface in FINAL_FILLERS)):
        tail.pop()
    if tail and tail[-1].surface in ("です", "ます"):
        found.append(Match("devoice_final", len(tail) - 1, len(tail), tail[-1].surface))

    reading = "".join(m.reading for m in morphs)
    for i in range(len(reading) - 1):
        if reading[i] in DEVOICING and reading[i + 1] in VOICELESS_START:
            found.append(Match("devoice_mid", -1, -1, reading[i : i + 2]))
            break
    return found


def phenomena(morphs):
    """The ids of the phenomena `morphs` show, in order."""
    seen = []
    for m in find(morphs):
        if m.phenomenon not in seen:
            seen.append(m.phenomenon)
    return seen


def _rewrite_span(morphs, match):
    """How the morphemes of a match are said, or None if this one is left as it is written."""
    span = morphs[match.start : match.end]
    pid = match.phenomenon
    if pid == "wa":
        first = span[0]
        forms = {"これ": "こりゃ", "それ": "そりゃ", "あれ": "ありゃ", "どれ": "どりゃ", "て": "ちゃ", "で": "じゃ", "に": "にゃ"}
        return forms.get(first.reading if first.pos != "助詞" else first.surface)
    if pid == "te_aux":
        verb, te, helper = span
        voiced = te.surface == "で"
        tail = helper.surface
        if helper.base == "いる" or helper.base == "いく":
            # ている -> てる, ていた -> てた, ていく -> てく, ていった -> てった
            return verb.surface + te.surface + (tail[1:] if tail else tail)
        if helper.base == "おく":
            return verb.surface + ("ど" if voiced else "と") + tail[1:]
        if helper.base == "しまう":
            return verb.surface + ("じゃ" if voiced else "ちゃ") + tail[2:]
        return None
    if pid == "no_da":
        if span[0].surface == "ので":
            return "んで"
        return "ん" + span[1].surface
    if pid == "toiu":
        return "って" if span[0].surface == "という" else None
    if pid == "shortened":
        return _shortened(span[0].reading)
    return None


def spoken_text(morphs, target):
    """The sentence written the way it is said for the phenomenon `target`, so a voice model says it so.
    None if `target` can't be forced or does not occur."""
    pheno = BY_ID.get(target)
    if pheno is None or not pheno.forceable:
        return None
    matches = [m for m in find(morphs) if m.phenomenon == target]
    pieces = [m.surface for m in morphs]
    done = False
    claimed = set()
    for match in matches:
        if match.start < 0 or any(i in claimed for i in range(match.start, match.end)):
            continue
        replacement = _rewrite_span(morphs, match)
        if replacement is None:
            continue
        pieces[match.start] = replacement
        for i in range(match.start + 1, match.end):
            pieces[i] = ""
        claimed.update(range(match.start, match.end))
        done = True
    text = "".join(pieces)
    if target == "nakereba":
        replaced = text.replace("なければ", "なきゃ").replace("なくては", "なくちゃ")
        done = replaced != text
        text = replaced
    return text if done else None
