import os
import pygame
from blaster import settings
from blaster import assets
from blaster.ui import render_text_fit


def test_set_difficulty():
    assert settings.set_difficulty('Easy')
    assert settings.DIFFICULTY == 'Easy'
    assert settings.set_difficulty('Normal')


def test_set_visual_quality():
    assert settings.set_visual_quality('Performance')
    assert settings.VISUAL_QUALITY == 'Performance'
    assert settings.STAR_COUNT == settings.VISUAL_PRESETS['Performance']['STAR_COUNT']
    assert settings.set_visual_quality('Enhanced')
    assert settings.VISUAL_QUALITY == 'Enhanced'
    assert settings.set_visual_quality('Balanced')


def test_set_fps_cap():
    assert settings.set_fps_cap(120)
    assert settings.FPS == 120
    assert not settings.set_fps_cap(999)
    assert settings.set_fps_cap(60)


def test_set_show_fps():
    assert settings.set_show_fps(False)
    assert settings.SHOW_FPS is False
    assert settings.set_show_fps(True)
    assert settings.SHOW_FPS is True


def test_generate_tone_file(tmp_path):
    p = tmp_path / 'tone.wav'
    assets.generate_tone(str(p), freq=440.0, duration=0.01, volume=0.1)
    assert p.exists()
    assert p.stat().st_size > 0


def test_ensure_sounds_includes_enemy_shot(tmp_path):
    paths = assets.ensure_sounds(dest_dir=str(tmp_path))
    assert 'enemy_shot' in paths
    assert os.path.exists(paths['enemy_shot'])


def test_render_text_fit_respects_max_width():
    pygame.font.init()
    font = pygame.font.SysFont(None, 28)

    image = render_text_fit(font, "A very long interface label that should not overflow", (255, 255, 255), 120)

    assert image.get_width() <= 120
