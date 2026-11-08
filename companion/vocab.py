"""The learner's known words: what counts as a known word, and words to build sentences around."""
import hashlib
import random

from . import morph, phenomena


class Vocabulary:
    def __init__(self, words):
        self.words = sorted({w.strip() for w in words if w and w.strip()})
        self.id = hashlib.sha256("\n".join(self.words).encode("utf-8")).hexdigest()[:16]
        self._known = set(self.words)
        self._analyzed = None

    def __len__(self):
        return len(self.words)

    def is_known(self, m):
        """A word is known if its dictionary form, its spelling or its kana reading is listed (Jiten exports
        may spell a word in kana where the dictionary uses kanji), the same rule as the app."""
        return m.base in self._known or m.surface in self._known or m.reading in self._known

    def unknown_words(self, morphs):
        """The different words of a sentence that are not known, by dictionary form."""
        unknown = []
        for m in morphs:
            if morph.is_symbol(m) or self.is_known(m):
                continue
            if m.base not in unknown:
                unknown.append(m.base)
        return unknown

    def _single_words(self):
        """Known words that are one morpheme, analyzed once: (word, morph)."""
        if self._analyzed is None:
            out = []
            for w in self.words:
                ms = morph.analyze(w)
                if len(ms) == 1:
                    out.append((w, ms[0]))
            self._analyzed = out
        return self._analyzed

    def trigger_words(self, pheno_id, k, rng=random):
        """Up to `k` known words that let a sentence show the phenomenon, to build it around."""
        singles = self._single_words()
        if pheno_id == "i_wo":
            pool = [w for w, m in singles if m.pos == "名詞" and m.reading[-1:] in phenomena.I_ROW]
        elif pheno_id == "n_particle":
            pool = [w for w, m in singles if m.pos == "名詞" and m.reading[-1:] == "ん"]
        elif pheno_id == "te_aux":
            pool = [w for w, m in singles if m.pos == "動詞" and m.pos2 == "自立"]
        elif pheno_id == "shortened":
            pool = [w for w, m in singles if phenomena._shortened(m.reading) is not None]
        elif pheno_id == "devoice_mid":
            pool = [w for w, m in singles if m.pos in ("名詞", "動詞") and _has_devoicing(m.reading)]
        elif pheno_id == "nasal_g":
            pool = [w for w, m in singles if m.pos == "名詞" and any(c in phenomena.NASAL_G_KANA for c in m.reading[1:])]
        else:
            # wa, no_da, nakereba, toiu, devoice_final: the pattern is in the grammar, any known verb or noun will do.
            pool = [w for w, m in singles if m.pos in ("名詞", "動詞", "形容詞") and len(w) >= 2]
        rng.shuffle(pool)
        return pool[:k]

    def sample(self, k, rng=random):
        """Known content words to show the writer of the sentences what vocabulary is allowed. Short words are
        favored: in a long list the everyday words are mostly short, and the rare ones lead to odd sentences."""
        words = [w for w, m in self._single_words() if m.pos in ("名詞", "動詞", "形容詞", "副詞")]
        rng.shuffle(words)
        short = [w for w in words if len(w) <= 3]
        rest = [w for w in words if len(w) > 3]
        return (short[: k * 3 // 4] + rest)[:k] if len(short) >= k * 3 // 4 else (short + rest)[:k]


def _has_devoicing(reading):
    return any(reading[i] in phenomena.DEVOICING and reading[i + 1] in phenomena.VOICELESS_START for i in range(len(reading) - 1))
