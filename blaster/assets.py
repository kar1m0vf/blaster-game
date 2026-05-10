import os
import wave
import struct
import math
import random

def generate_tone(path, freq=440.0, duration=0.2, volume=0.5, sample_rate=44100):
    n_samples = int(sample_rate * duration)
    amplitude = int(32767 * volume)
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            t = float(i) / sample_rate
            val = int(amplitude * math.sin(2.0 * math.pi * freq * t))
            wf.writeframes(struct.pack('<h', val))


def generate_shot_sound(path, base_freq=1200.0, duration=0.09, volume=0.35, sample_rate=44100):
    n = int(sample_rate * duration)
    max_amp = int(32767 * volume)
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n):
            t = i / sample_rate
            freq = base_freq * (1.0 - 0.4 * (t / duration))
            env = (1.0 - (t / duration)) ** 2.2
            tone = math.sin(2.0 * math.pi * freq * t)
            noise = (random.random() * 2.0 - 1.0) * 0.12
            val = int(max_amp * env * (0.9 * tone + 0.1 * noise))
            if val > 32767:
                val = 32767
            if val < -32768:
                val = -32768
            wf.writeframes(struct.pack('<h', val))


def generate_explosion_sound(path, duration=0.35, sample_rate=44100):
    n = int(sample_rate * duration)
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n):
            t = i / sample_rate
            decay = (1.0 - (t / duration))
            freq = 400.0 * (1.0 - t / duration) + 100.0
            noise = (random.random() * 2 - 1) * 0.6
            val = int(32767 * decay * 0.6 * math.sin(2 * math.pi * freq * t) + 32767 * decay * 0.4 * noise)
            if val > 32767:
                val = 32767
            if val < -32768:
                val = -32768
            wf.writeframes(struct.pack('<h', val))


_loaded_sounds = None


def _asset_path(dest_dir, filename):
    base = dest_dir or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, filename)


def _build_fallback_window_icon():
    try:
        import pygame
        surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.rect(surf, (7, 15, 34), surf.get_rect(), border_radius=14)
        pygame.draw.rect(surf, (112, 214, 255), surf.get_rect().inflate(-4, -4), 3, border_radius=12)
        pygame.draw.circle(surf, (255, 196, 88), (32, 34), 15, 3)
        pygame.draw.polygon(surf, (50, 154, 238), [(32, 5), (48, 42), (32, 54), (16, 42)])
        pygame.draw.polygon(surf, (202, 244, 255), [(32, 5), (48, 42), (32, 54), (16, 42)], 2)
        pygame.draw.polygon(surf, (28, 92, 168), [(26, 28), (5, 42), (23, 52)])
        pygame.draw.polygon(surf, (28, 92, 168), [(38, 28), (59, 42), (41, 52)])
        pygame.draw.polygon(surf, (255, 136, 72), [(25, 50), (31, 50), (28, 63)])
        pygame.draw.polygon(surf, (255, 136, 72), [(33, 50), (39, 50), (36, 63)])
        return surf
    except Exception:
        return None


def load_window_icon(dest_dir=None):
    try:
        import pygame
        icon_path = _asset_path(dest_dir, "icon.png")
        if os.path.exists(icon_path):
            icon = pygame.image.load(icon_path).convert_alpha()
            if icon.get_width() > 256 or icon.get_height() > 256:
                icon = pygame.transform.smoothscale(icon, (64, 64))
            return icon
    except Exception:
        pass
    return _build_fallback_window_icon()


def ensure_sounds(dest_dir=None):
    base = dest_dir or os.path.dirname(os.path.abspath(__file__))
    shot_path = os.path.join(base, 'blaster_shot.wav')
    enemy_shot_path = os.path.join(base, 'blaster_enemy_shot.wav')
    expl_path = os.path.join(base, 'blaster_explosion.wav')
    hit_path = os.path.join(base, 'blaster_hit.wav')
    over_path = os.path.join(base, 'blaster_gameover.wav')
    try:
        if not os.path.exists(shot_path):
            generate_shot_sound(shot_path, base_freq=1400.0, duration=0.08, volume=0.32)
        if not os.path.exists(enemy_shot_path):
            generate_shot_sound(enemy_shot_path, base_freq=720.0, duration=0.11, volume=0.25)
        if not os.path.exists(expl_path):
            generate_explosion_sound(expl_path, duration=0.35)
        if not os.path.exists(hit_path):
            generate_tone(hit_path, freq=250.0, duration=0.14, volume=0.6)
        if not os.path.exists(over_path):
            generate_tone(over_path, freq=120.0, duration=0.5, volume=0.8)
    except Exception:
        pass
    return {
        'shot': shot_path,
        'enemy_shot': enemy_shot_path,
        'explosion': expl_path,
        'hit': hit_path,
        'gameover': over_path,
    }


def load_sounds(dest_dir=None):
    global _loaded_sounds
    paths = ensure_sounds(dest_dir)
    try:
        import pygame
        _loaded_sounds = {
            'shot': pygame.mixer.Sound(paths['shot']) if paths.get('shot') else None,
            'enemy_shot': pygame.mixer.Sound(paths['enemy_shot']) if paths.get('enemy_shot') else None,
            'explosion': pygame.mixer.Sound(paths['explosion']) if paths.get('explosion') else None,
            'hit': pygame.mixer.Sound(paths['hit']) if paths.get('hit') else None,
            'gameover': pygame.mixer.Sound(paths['gameover']) if paths.get('gameover') else None,
        }
    except Exception:
        _loaded_sounds = {k: None for k in ('shot','enemy_shot','explosion','hit','gameover')}
    return _loaded_sounds


def set_sounds_volume(volume: float):
    global _loaded_sounds
    try:
        if _loaded_sounds is None:
            return
        for s in _loaded_sounds.values():
            try:
                if s:
                    s.set_volume(max(0.0, min(1.0, volume)))
            except Exception:
                pass
    except Exception:
        pass
