from blaster import storage


def test_highscores_roundtrip(tmp_path, monkeypatch):
    # Use temporary data directory by monkeypatching module constants
    monkeypatch.setattr(storage, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(storage, 'HIGHSCORES_FILE', str(tmp_path / 'highscores.json'))
    # Initially empty
    assert storage.load_highscores() == []
    scores = storage.add_highscore('Alice', 123)
    assert isinstance(scores, list)
    assert scores[0]['name'] == 'Alice'
    assert scores[0]['score'] == 123
    # add another and ensure ordering
    storage.add_highscore('Bob', 200)
    out = storage.load_highscores()
    assert out[0]['name'] == 'Bob'


def test_highscore_sanitization(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(storage, 'HIGHSCORES_FILE', str(tmp_path / 'highscores.json'))

    scores = storage.add_highscore('   ', -50)
    assert scores[0]['name'] == 'Player'
    assert scores[0]['score'] == 0

    storage.add_highscore('VeryLongName123456789', 15)
    out = storage.load_highscores()
    assert all(len(item['name']) <= storage.MAX_NAME_LEN for item in out)
    assert all(item['score'] >= 0 for item in out)


def test_load_highscores_sanitizes_broken_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(storage, 'HIGHSCORES_FILE', str(tmp_path / 'highscores.json'))
    payload = '[{"name":"  ","score":"9"},{"name":null,"score":-2},"bad"]'
    (tmp_path / 'highscores.json').write_text(payload, encoding='utf-8')

    out = storage.load_highscores()
    assert out == [
        {'name': 'Player', 'score': 9},
        {'name': 'Player', 'score': 0},
    ]


def test_user_settings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(storage, 'SETTINGS_FILE', str(tmp_path / 'settings.json'))

    loaded = storage.load_user_settings()
    assert loaded["difficulty"] == "Normal"
    assert loaded["visual_quality"] == "Balanced"
    assert loaded["fps_cap"] in storage.settings.FPS_OPTIONS
    assert loaded["show_fps"] is True

    saved = storage.save_user_settings(
        {
            "difficulty": "Hard",
            "visual_quality": "Performance",
            "master_volume": 0.33,
            "fullscreen": True,
            "fps_cap": 120,
            "show_fps": False,
        }
    )
    assert saved["difficulty"] == "Hard"
    assert saved["visual_quality"] == "Performance"
    assert saved["fullscreen"] is True
    assert saved["fps_cap"] == 120
    assert saved["show_fps"] is False

    loaded2 = storage.load_user_settings()
    assert loaded2 == saved


def test_user_settings_sanitization(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(storage, 'SETTINGS_FILE', str(tmp_path / 'settings.json'))

    out = storage.save_user_settings(
        {
            "difficulty": "Impossible",
            "visual_quality": "Ultra",
            "master_volume": 999,
            "fullscreen": "yes",
            "fps_cap": 999,
            "show_fps": 0,
        }
    )
    assert out["difficulty"] == "Normal"
    assert out["visual_quality"] == "Balanced"
    assert out["master_volume"] == 1.0
    assert out["fullscreen"] is True
    assert out["fps_cap"] == storage.settings.FPS
    assert out["show_fps"] is False
