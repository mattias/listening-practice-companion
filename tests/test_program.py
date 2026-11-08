import json
import os

import pytest

from companion import config, irodori, runner


def test_settings_have_defaults_and_a_token_is_made_once(tmp_path):
    path = str(tmp_path / "config.json")
    first = config.load(path)
    assert first["PORT"] == 8089 and first["LLM_MODEL"] == "qwen3:8b" and first["ALLOW_NETWORK"] is True
    assert len(first["TOKEN"]) >= 24
    # The token is kept, and what is saved comes back.
    first["LLM_MODEL"] = "other"
    config.save(first, path)
    second = config.load(path)
    assert second["TOKEN"] == first["TOKEN"] and second["LLM_MODEL"] == "other"


def test_a_broken_settings_file_does_not_stop_the_program(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    assert config.load(str(path))["PORT"] == 8089


def test_service_settings_carry_the_voices_and_the_model(tmp_path):
    cfg = {**config.DEFAULTS, "TOKEN": "t", "IRODORI_URL": "http://127.0.0.1:9000", "LLM_MODEL": "m"}
    s = config.service_config(cfg)
    assert s["SERVER_URL"] == "http://127.0.0.1:9000" and s["LLM_MODEL"] == "m" and s["TOKEN"] == "t"
    assert set(s["VOICES"]) == {"female_calm", "female_bright", "female_cool", "male_calm", "male_young", "male_deep"}


def test_voice_server_address_helpers():
    assert irodori.port_of("http://127.0.0.1:8088") == 8088
    assert irodori.port_of("http://localhost") == 8088
    assert irodori.is_local("http://localhost:8088") and not irodori.is_local("http://192.168.1.5:8088")
    assert irodori.health("http://127.0.0.1:59999") is False


def test_the_voice_server_is_not_started_when_it_is_somewhere_else_or_missing(tmp_path):
    with pytest.raises(RuntimeError, match="not on this computer"):
        irodori.start(str(tmp_path), "http://192.168.1.5:59998", print)
    with pytest.raises(RuntimeError, match="not installed"):
        irodori.start(str(tmp_path), "http://127.0.0.1:59998", print)


def test_lan_addresses_are_ipv4():
    for ip in runner.lan_addresses():
        assert ip.count(".") == 3 and not ip.startswith("127.")


def test_the_service_starts_and_stops_in_the_program(tmp_path):
    cfg = {**config.DEFAULTS, "TOKEN": "t", "ALLOW_NETWORK": False, "PORT": 58712}
    # Keep the test's files out of the real data folder.
    os.environ["APPDATA"] = str(tmp_path)
    os.environ["XDG_CONFIG_HOME"] = str(tmp_path)
    service = runner.Service()
    service.start(cfg)
    try:
        assert service.running and runner.service_health(58712)
        # A second one on the same port says so instead of failing in a thread.
        with pytest.raises(RuntimeError, match="already in use"):
            runner.Service().start(cfg)
    finally:
        service.stop()
    assert not runner.service_health(58712, timeout=1)


def test_the_window_opens_and_closes(tmp_path):
    tk = pytest.importorskip("tkinter")
    os.environ["APPDATA"] = str(tmp_path)
    os.environ["XDG_CONFIG_HOME"] = str(tmp_path)
    try:
        root = tk.Tk()
        root.destroy()
    except tk.TclError:
        pytest.skip("no display")
    from companion.gui import App

    app = App({**config.DEFAULTS, "TOKEN": "t", "START_SERVICE_ON_LAUNCH": False, "IRODORI_AUTO_START": False, "PORT": 58713})
    app.update()
    assert "t" in app.token.get()
    app.quit_program()
    assert json.load(open(config.config_path(), encoding="utf-8"))["TOKEN"] == "t"
