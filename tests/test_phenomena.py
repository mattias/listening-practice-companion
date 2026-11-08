from companion import morph, phenomena
from companion.vocab import Vocabulary


def found(sentence):
    return set(phenomena.phenomena(morph.analyze(sentence)))


def spoken(sentence, target):
    return phenomena.spoken_text(morph.analyze(sentence), target)


def test_i_row_before_wo():
    assert "i_wo" in found("薬を飲んだ。")
    assert "i_wo" in found("息を吸った。")
    assert "i_wo" not in found("水を飲んだ。")
    assert "i_wo" not in found("本を読んだ。")


def test_n_before_particle():
    assert "n_particle" in found("本を読んだ。")
    assert "n_particle" in found("パンは好きです。")
    assert "n_particle" not in found("薬を飲んだ。")


def test_wa_contractions():
    assert "wa" in found("これは本です。")
    assert "wa" in found("それは違います。")
    assert "wa" in found("食べては駄目です。")
    assert "wa" in found("ここでは静かにして。")
    assert "wa" not in found("私は学生です。")


def test_te_with_helper_verbs():
    assert "te_aux" in found("今、食べている。")
    assert "te_aux" in found("先に買っておく。")
    assert "te_aux" in found("全部飲んでしまった。")
    assert "te_aux" not in found("食べた。")


def test_no_da_toiu_nakereba():
    assert "no_da" in found("行くのです。")
    assert "no_da" in found("遅れたので、走った。")
    assert "toiu" in found("来ないという話だ。")
    assert "nakereba" in found("早く行かなければならない。")
    assert "nakereba" in found("急がなくてはいけない。")


def test_devoicing():
    assert "devoice_final" in found("これは本です。")
    assert "devoice_final" in found("明日行きますね。")
    assert "devoice_final" not in found("ですから行く。")
    assert "devoice_mid" in found("北へ行く。")
    assert "devoice_mid" not in found("私は笑う。")


def test_spoken_forms():
    assert spoken("これは本です。", "wa") == "こりゃ本です。"
    assert spoken("ここでは静かにして。", "wa") == "ここじゃ静かにして。"
    assert spoken("食べては駄目です。", "wa") == "食べちゃ駄目です。"
    assert spoken("今、食べている。", "te_aux") == "今、食べてる。"
    assert spoken("先に買っておく。", "te_aux") == "先に買っとく。"
    assert spoken("全部飲んでしまった。", "te_aux") == "全部飲んじゃった。"
    assert spoken("行くのです。", "no_da") == "行くんです。"
    assert spoken("遅れたので、走った。", "no_da") == "遅れたんで、走った。"
    assert spoken("早く行かなければならない。", "nakereba") == "早く行かなきゃならない。"
    assert spoken("急がなくてはいけない。", "nakereba") == "急がなくちゃいけない。"
    assert spoken("来ないという話だ。", "toiu") == "来ないって話だ。"
    assert spoken("本当に行く。", "shortened") == "ほんとに行く。"
    assert spoken("ところで行く。", "shortened") is None


def test_what_is_not_respelled():
    # Devoicing, nasal g, and い-row + を and ん + particle are left to the voice: nobody writes 薬を as くすりょ, and a made-up
    # spelling could change the accent. A phenomenon that is not in the sentence gives nothing either.
    assert spoken("これは本です。", "devoice_final") is None
    assert spoken("薬を飲んだ。", "i_wo") is None
    assert spoken("本を読んだ。", "n_particle") is None
    assert spoken("水を飲んだ。", "wa") is None


def test_known_words_rule():
    v = Vocabulary(["薬", "飲む", "を", "だ", "私", "。"])
    ms = morph.analyze("私は薬を飲んだ。")
    # は is not in the list.
    assert v.unknown_words(ms) == ["は"]
    assert Vocabulary(["薬", "飲む", "を", "だ", "私", "は"]).unknown_words(ms) == []


def test_trigger_words():
    v = Vocabulary(["薬", "本", "水", "食べる", "ありがとう", "犬"])
    assert v.trigger_words("i_wo", 5) == ["薬"]
    assert v.trigger_words("n_particle", 5) == ["本"]
    assert sorted(v.trigger_words("te_aux", 5)) == ["食べる"]
