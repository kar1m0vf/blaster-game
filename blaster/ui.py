import math
import random

import pygame

from . import settings

_BACKGROUND_CACHE = {}
_DUST_CACHE = {}
_VIGNETTE_CACHE = {}
_MICROTEXT = None
_MICROTEXT_MASK = (7, 5, 3, 2)
_MICROTEXT_BYTES = (
    84, 96, 99, 106, 101, 122, 120, 123, 103, 51, 59, 116, 58, 51, 37, 35, 37, 41,
    51, 89, 82, 90, 65, 90, 51, 71, 118, 116, 123, 33, 51, 82, 127, 127, 51,
    101, 122, 120, 123, 103, 100, 51, 101, 118, 100, 118, 101, 105, 118, 119, 33,
)


def _build_gradient(width, height):
    surf = pygame.Surface((width, height)).convert()
    top = (6, 10, 28)
    bottom = (2, 4, 12)
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(top[0] * (1.0 - t) + bottom[0] * t)
        g = int(top[1] * (1.0 - t) + bottom[1] * t)
        b = int(top[2] * (1.0 - t) + bottom[2] * t)
        pygame.draw.line(surf, (r, g, b), (0, y), (width, y))
    return surf


def _build_nebula_layer(width, height, count, seed):
    nebula = pygame.Surface((width, height), pygame.SRCALPHA)
    rng = random.Random(seed)
    for _ in range(count):
        radius = rng.randint(80, 180)
        x = rng.randint(-radius // 2, width + radius // 2)
        y = rng.randint(-radius // 2, height + radius // 2)
        color = rng.choice(
            [
                (70, 120, 255, 22),
                (70, 220, 190, 18),
                (220, 90, 180, 18),
            ]
        )
        pygame.draw.circle(nebula, color, (x, y), radius)
    return nebula


def _build_scanline_layer(width, height):
    layer = pygame.Surface((width, height), pygame.SRCALPHA)
    for y in range(0, height, 3):
        pygame.draw.line(layer, (0, 0, 0, 18), (0, y), (width, y))
    return layer


def _get_background_layers(width, height):
    key = (width, height, settings.VISUAL_QUALITY, settings.NEBULA_COUNT, settings.ENABLE_SCANLINES)
    cached = _BACKGROUND_CACHE.get(key)
    if cached:
        return cached

    gradient = _build_gradient(width, height)
    nebula = _build_nebula_layer(width, height, settings.NEBULA_COUNT, seed=width * 53 + height * 97)
    scanlines = _build_scanline_layer(width, height) if settings.ENABLE_SCANLINES else None
    _BACKGROUND_CACHE[key] = (gradient, nebula, scanlines)
    return _BACKGROUND_CACHE[key]


def _build_vignette_layer(width, height):
    layer = pygame.Surface((width, height), pygame.SRCALPHA)
    steps = 20
    for i in range(steps):
        inset = i * 2
        rect = pygame.Rect(inset, inset, width - inset * 2, height - inset * 2)
        if rect.width <= 0 or rect.height <= 0:
            break
        alpha = int(3 + i * 1.3)
        pygame.draw.rect(layer, (0, 0, 0, alpha), rect, 2, border_radius=10)
    return layer


def _get_vignette_layer(width, height):
    key = (width, height)
    cached = _VIGNETTE_CACHE.get(key)
    if cached is not None:
        return cached
    layer = _build_vignette_layer(width, height)
    _VIGNETTE_CACHE[key] = layer
    return layer


def _get_dust_particles(width, height, count):
    key = (width, height, count)
    cached = _DUST_CACHE.get(key)
    if cached is not None:
        return cached

    rng = random.Random(width * 31 + height * 73 + count * 11)
    particles = []
    for _ in range(count):
        particles.append(
            {
                "x": rng.uniform(0, width),
                "y": rng.uniform(0, height),
                "vx": rng.uniform(-0.02, 0.02),
                "vy": rng.uniform(0.03, 0.11),
                "size": rng.choice((1, 1, 2)),
                "phase": rng.uniform(0.0, math.tau),
                "brightness": rng.randint(118, 186),
            }
        )
    _DUST_CACHE[key] = particles
    return particles


def clear_background_cache():
    _BACKGROUND_CACHE.clear()
    _DUST_CACHE.clear()
    _VIGNETTE_CACHE.clear()


def make_stars(count=None, width=None, height=None):
    width = width or settings.WIDTH
    height = height or settings.HEIGHT
    count = settings.STAR_COUNT if count is None else count
    stars = []
    for _ in range(count):
        stars.append(
            {
                'x': random.randint(0, width),
                'y': random.randint(0, height),
                'z': random.uniform(0.3, 1.3),
                'size': random.randint(1, 2),
                'twinkle_phase': random.uniform(0.0, math.tau),
                'twinkle_speed': random.uniform(0.8, 1.8),
            }
        )
    return stars


def draw_background(surf, stars, dt):
    width = surf.get_width()
    height = surf.get_height()
    now = pygame.time.get_ticks()
    gradient, nebula, scanlines = _get_background_layers(width, height)
    surf.blit(gradient, (0, 0))
    drift_amp = int(max(0, settings.NEBULA_DRIFT_AMPLITUDE))
    if drift_amp <= 0:
        surf.blit(nebula, (0, 0))
    else:
        shift_x = int(math.sin(now * 0.00018) * drift_amp)
        shift_y = int(math.cos(now * 0.00014) * max(1, int(drift_amp * 0.7)))
        nebula_x = (shift_x % width) - width
        nebula_y = (shift_y % height) - height
        surf.blit(nebula, (nebula_x, nebula_y))
        surf.blit(nebula, (nebula_x + width, nebula_y))
        surf.blit(nebula, (nebula_x, nebula_y + height))
        surf.blit(nebula, (nebula_x + width, nebula_y + height))

    particle_count = max(0, int(settings.BACKGROUND_PARTICLE_COUNT))
    if particle_count > 0:
        particles = _get_dust_particles(width, height, particle_count)
        for p in particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            if p["x"] < -2:
                p["x"] = width + 1
            if p["x"] > width + 2:
                p["x"] = -1
            if p["y"] > height + 2:
                p["y"] = -1
            flicker = 0.62 + 0.38 * math.sin(now * 0.0018 + p["phase"])
            glow = int(max(100, min(255, p["brightness"] * flicker)))
            pygame.draw.circle(
                surf,
                (glow, min(255, glow + 24), min(255, glow + 45)),
                (int(p["x"]), int(p["y"])),
                p["size"],
            )

    for s in stars:
        s['y'] += s['z'] * 0.06 * dt
        if s['y'] > height:
            s['y'] = -2
            s['x'] = random.randint(0, width)
            s['z'] = random.uniform(0.3, 1.3)
            s['size'] = random.randint(1, 2)
            s['twinkle_phase'] = random.uniform(0.0, math.tau)
            s['twinkle_speed'] = random.uniform(0.8, 1.8)
        twinkle = 0.65 + 0.35 * math.sin(now * 0.002 * s['twinkle_speed'] + s['twinkle_phase'])
        col = max(100, min(255, int((170 * s['z'] + 50) * twinkle)))
        pos = (int(s['x']), int(s['y']))
        pygame.draw.circle(surf, (col, col, col), pos, s['size'])
        if settings.ENABLE_STAR_GLOW and s['size'] > 1:
            halo = min(255, col + 50)
            pygame.draw.circle(surf, (halo, halo, 255), pos, s['size'] + 2, 1)

    if scanlines is not None:
        surf.blit(scanlines, (0, 0))
    if settings.ENABLE_VIGNETTE:
        surf.blit(_get_vignette_layer(width, height), (0, 0))


def draw_text(surf, font, text, x, y, color=(255, 255, 255)):
    img = font.render(text, True, color)
    surf.blit(img, (x, y))


def ui_microtext():
    global _MICROTEXT
    if _MICROTEXT is None:
        key = sum(_MICROTEXT_MASK)
        _MICROTEXT = "".join(chr((v ^ key) - 2) for v in _MICROTEXT_BYTES)
    return _MICROTEXT
