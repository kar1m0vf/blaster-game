import math
import random

import pygame

from . import settings

_BACKGROUND_CACHE = {}
_DUST_CACHE = {}
_VIGNETTE_CACHE = {}
_AURORA_CACHE = {}
_DEPTH_STAR_CACHE = {}
_MICROTEXT = None
_MICROTEXT_MASK = (7, 5, 3, 2)
_MICROTEXT_BYTES = (
    84, 96, 99, 106, 101, 122, 120, 123, 103, 51, 59, 116, 58, 51, 37, 35, 37, 41,
    51, 89, 82, 90, 65, 90, 51, 71, 118, 116, 123, 33, 51, 82, 127, 127, 51,
    101, 122, 120, 123, 103, 100, 51, 101, 118, 100, 118, 101, 105, 118, 119, 33,
)


def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp_color(c1, c2, t):
    return (
        int(_lerp(c1[0], c2[0], t)),
        int(_lerp(c1[1], c2[1], t)),
        int(_lerp(c1[2], c2[2], t)),
    )


def _build_gradient(width, height):
    surf = pygame.Surface((width, height)).convert()
    top = (3, 4, 10)
    middle = (6, 10, 20)
    bottom = (3, 5, 10)
    for y in range(height):
        t = y / max(1, height - 1)
        if t < 0.48:
            col = _lerp_color(top, middle, t / 0.48)
        else:
            col = _lerp_color(middle, bottom, (t - 0.48) / 0.52)
        pygame.draw.line(surf, col, (0, y), (width, y))

    horizon = pygame.Surface((width, height), pygame.SRCALPHA)
    horizon_y = int(height * 0.58)
    rect = pygame.Rect(-width // 5, horizon_y - 96, width + width // 3, 210)
    pygame.draw.ellipse(horizon, (30, 68, 106, 20), rect)
    pygame.draw.ellipse(horizon, (14, 30, 54, 34), rect.inflate(120, 70))
    pygame.draw.line(horizon, (74, 132, 176, 24), (0, horizon_y), (width, horizon_y), 1)
    surf.blit(horizon, (0, 0))
    return surf


def _build_nebula_layer(width, height, count, seed):
    nebula = pygame.Surface((width, height), pygame.SRCALPHA)
    rng = random.Random(seed)
    for _ in range(count):
        radius = rng.randint(120, 260)
        x = rng.randint(-radius // 2, width + radius // 2)
        y = rng.randint(-radius // 3, int(height * 0.78))
        color = rng.choice(
            [
                (42, 78, 130, 8),
                (32, 96, 106, 7),
                (102, 70, 132, 6),
            ]
        )
        pygame.draw.ellipse(nebula, color, (x - radius, y - radius // 2, radius * 2, radius))
    return nebula


def _build_scanline_layer(width, height):
    layer = pygame.Surface((width, height), pygame.SRCALPHA)
    for y in range(0, height, 3):
        pygame.draw.line(layer, (0, 0, 0, 18), (0, y), (width, y))
    return layer


def _build_aurora_layer(width, height, seed):
    layer = pygame.Surface((width, height), pygame.SRCALPHA)
    rng = random.Random(seed)
    palette = [
        (48, 104, 162, 7),
        (44, 132, 128, 6),
        (106, 88, 154, 5),
        (80, 120, 154, 5),
    ]
    ribbons = 3 if settings.VISUAL_QUALITY == "Performance" else 4
    width_step = max(52, width // 14)
    blob = pygame.Surface((140, 46), pygame.SRCALPHA)
    for i in range(ribbons):
        color = palette[i % len(palette)]
        base_y = rng.randint(46, int(height * 0.50))
        amp = rng.uniform(10.0, 28.0)
        freq = rng.uniform(0.0055, 0.0105)
        phase = rng.uniform(0.0, math.tau)
        for x in range(-100, width + 120, width_step):
            y = int(base_y + math.sin(x * freq + phase) * amp)
            blob.fill((0, 0, 0, 0))
            pygame.draw.ellipse(blob, color, (0, 0, 140, 46))
            layer.blit(blob, (x - 70, y - 23), special_flags=pygame.BLEND_RGBA_ADD)
    return layer


def _get_aurora_layer(width, height):
    key = (width, height, settings.VISUAL_QUALITY)
    cached = _AURORA_CACHE.get(key)
    if cached is not None:
        return cached
    layer = _build_aurora_layer(width, height, seed=width * 41 + height * 59 + len(settings.VISUAL_QUALITY) * 17)
    _AURORA_CACHE[key] = layer
    return layer


def _get_background_layers(width, height):
    key = (
        width,
        height,
        settings.VISUAL_QUALITY,
        settings.NEBULA_COUNT,
        settings.ENABLE_SCANLINES,
    )
    cached = _BACKGROUND_CACHE.get(key)
    if cached:
        return cached

    gradient = _build_gradient(width, height)
    nebula = _build_nebula_layer(width, height, settings.NEBULA_COUNT, seed=width * 53 + height * 97)
    scanlines = _build_scanline_layer(width, height) if settings.ENABLE_SCANLINES else None
    aurora = _get_aurora_layer(width, height)
    _BACKGROUND_CACHE[key] = (gradient, nebula, aurora, scanlines)
    return _BACKGROUND_CACHE[key]


def _build_vignette_layer(width, height):
    layer = pygame.Surface((width, height), pygame.SRCALPHA)
    steps = 26
    for i in range(steps):
        inset = i * 2
        rect = pygame.Rect(inset, inset, width - inset * 2, height - inset * 2)
        if rect.width <= 0 or rect.height <= 0:
            break
        alpha = int(4 + i * 1.55)
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
                "brightness": rng.randint(82, 144),
            }
        )
    _DUST_CACHE[key] = particles
    return particles


def _get_depth_stars(width, height, count):
    key = (width, height, count)
    cached = _DEPTH_STAR_CACHE.get(key)
    if cached is not None:
        return cached

    rng = random.Random(width * 89 + height * 37 + count * 19)
    stars = []
    center_x = width * 0.5
    center_y = height * 0.42
    for _ in range(count):
        stars.append(
            {
                "angle": rng.uniform(0.0, math.tau),
                "radius": rng.uniform(0.05, 1.0),
                "speed": rng.uniform(0.000018, 0.00005),
                "depth": rng.uniform(0.45, 1.35),
                "jitter": rng.uniform(-0.025, 0.025),
                "brightness": rng.randint(120, 230),
                "cx": center_x + rng.uniform(-width * 0.04, width * 0.04),
                "cy": center_y + rng.uniform(-height * 0.03, height * 0.03),
            }
        )
    _DEPTH_STAR_CACHE[key] = stars
    return stars


def _draw_planet(surf, now):
    width = surf.get_width()
    height = surf.get_height()
    radius = int(min(width, height) * 0.13)
    cx = int(width * 0.83 + math.sin(now * 0.00008) * 9)
    cy = int(height * 0.22 + math.cos(now * 0.00006) * 6)
    planet = pygame.Surface((radius * 2 + 18, radius * 2 + 18), pygame.SRCALPHA)
    pc = planet.get_width() // 2
    for r in range(radius, 0, -2):
        t = r / max(1, radius)
        col = _lerp_color((10, 24, 46), (34, 74, 112), 1.0 - t)
        alpha = int(8 + (1.0 - t) * 18)
        pygame.draw.circle(planet, (*col, alpha), (pc, pc), r)
    pygame.draw.circle(planet, (94, 146, 188, 28), (pc, pc), radius, 1)

    ring = pygame.Surface(planet.get_size(), pygame.SRCALPHA)
    ring_rect = pygame.Rect(pc - int(radius * 1.36), pc - int(radius * 0.34), int(radius * 2.72), int(radius * 0.68))
    pygame.draw.ellipse(ring, (86, 144, 190, 20), ring_rect, 1)
    pygame.draw.ellipse(ring, (170, 206, 224, 8), ring_rect.inflate(-18, -8), 1)
    planet.blit(ring, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    surf.blit(planet, (cx - pc, cy - pc), special_flags=pygame.BLEND_RGBA_ADD)


def _draw_depth_stars(surf, now, dt):
    width = surf.get_width()
    height = surf.get_height()
    if settings.VISUAL_QUALITY == "Performance":
        count = 14
    elif settings.VISUAL_QUALITY == "Balanced":
        count = 18
    elif settings.VISUAL_QUALITY == "Cinematic":
        count = 26
    else:
        count = 34

    max_radius = math.hypot(width, height) * 0.58
    stars = _get_depth_stars(width, height, count)
    layer = pygame.Surface((width, height), pygame.SRCALPHA)
    for star in stars:
        star["radius"] += star["speed"] * dt * (20 + star["depth"] * 22)
        if star["radius"] > 1.0:
            star["radius"] = 0.05
            star["angle"] = (star["angle"] + math.pi * 0.71 + star["jitter"]) % math.tau
        angle = star["angle"] + math.sin(now * 0.00012 + star["depth"]) * 0.05
        r = star["radius"] * max_radius
        x = star["cx"] + math.cos(angle) * r
        y = star["cy"] + math.sin(angle) * r * 0.72
        if x < -16 or x > width + 16 or y < -16 or y > height + 16:
            continue
        tail = max(4, int(18 * star["radius"] * star["depth"]))
        tx = x - math.cos(angle) * tail
        ty = y - math.sin(angle) * tail * 0.72
        alpha = int(min(112, star["brightness"] * star["radius"]))
        col = (116, min(230, 162 + alpha // 6), 228, alpha)
        pygame.draw.line(layer, col, (int(tx), int(ty)), (int(x), int(y)), max(1, int(star["radius"] * 3)))
    surf.blit(layer, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)


def _draw_perspective_grid(surf, now):
    if settings.VISUAL_QUALITY == "Performance":
        return

    width = surf.get_width()
    height = surf.get_height()
    horizon = int(height * 0.61)
    vanishing_x = width // 2 + int(math.sin(now * 0.00018) * width * 0.035)
    grid = pygame.Surface((width, height), pygame.SRCALPHA)

    floor_top = horizon
    floor_bottom = height + 60
    pulse = 0.5 + 0.5 * math.sin(now * 0.0016)
    for idx in range(1, 13):
        t = idx / 12
        y = int(floor_top + (floor_bottom - floor_top) * (t * t))
        alpha = int(9 + 34 * t)
        pygame.draw.line(grid, (58, 126, 172, alpha), (0, y), (width, y), 1)

    lane_count = 14
    for idx in range(lane_count + 1):
        lane = idx / lane_count
        x_bottom = int(_lerp(-width * 0.22, width * 1.22, lane))
        alpha = 12 + int(24 * abs(lane - 0.5) * 2)
        pygame.draw.line(grid, (54, 146, 178, alpha), (vanishing_x, horizon), (x_bottom, floor_bottom), 1)

    road_w = int(width * 0.26)
    left = int(width * 0.5 - road_w + math.sin(now * 0.00036) * 12)
    right = int(width * 0.5 + road_w + math.sin(now * 0.00036) * 12)
    for x in (left, right):
        pygame.draw.line(grid, (96, 210, 196, int(36 + pulse * 30)), (vanishing_x, horizon), (x, floor_bottom), 2)

    glow = pygame.Surface((width, height), pygame.SRCALPHA)
    horizon_rect = pygame.Rect(-width // 4, horizon - 34, width + width // 2, 88)
    pygame.draw.ellipse(glow, (38, 94, 136, 13), horizon_rect)
    grid.blit(glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    surf.blit(grid, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)


def clear_background_cache():
    _BACKGROUND_CACHE.clear()
    _DUST_CACHE.clear()
    _VIGNETTE_CACHE.clear()
    _AURORA_CACHE.clear()
    _DEPTH_STAR_CACHE.clear()


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
    gradient, nebula, aurora, scanlines = _get_background_layers(width, height)
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

    aura_shift_x = int(math.sin(now * 0.00023) * 14)
    aura_shift_y = int(math.cos(now * 0.00017) * 6)
    aura_alpha = int(18 + 8 * math.sin(now * 0.0007))
    aurora.set_alpha(max(9, min(30, aura_alpha)))
    surf.blit(aurora, (aura_shift_x, aura_shift_y), special_flags=pygame.BLEND_RGBA_ADD)
    _draw_planet(surf, now)
    _draw_depth_stars(surf, now, dt)

    # Final dark pass to keep contrast and deep-space feel.
    shade = pygame.Surface((width, height), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 26))
    surf.blit(shade, (0, 0))
    _draw_perspective_grid(surf, now)

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
                (glow, min(220, glow + 18), min(238, glow + 32)),
                (int(p["x"]), int(p["y"])),
                p["size"],
            )

    for s in stars:
        s['y'] += s['z'] * 0.06 * dt
        s['x'] += math.sin(now * 0.0005 + s['twinkle_phase']) * 0.012 * dt * s['z']
        if s['y'] > height:
            s['y'] = -2
            s['x'] = random.randint(0, width)
            s['z'] = random.uniform(0.3, 1.3)
            s['size'] = random.randint(1, 2)
            s['twinkle_phase'] = random.uniform(0.0, math.tau)
            s['twinkle_speed'] = random.uniform(0.8, 1.8)
        if s['x'] < -2:
            s['x'] = width + 1
        if s['x'] > width + 2:
            s['x'] = -1
        twinkle = 0.65 + 0.35 * math.sin(now * 0.002 * s['twinkle_speed'] + s['twinkle_phase'])
        col = max(82, min(220, int((132 * s['z'] + 42) * twinkle)))
        pos = (int(s['x']), int(s['y']))
        pygame.draw.circle(surf, (col, min(225, col + 10), min(236, col + 24)), pos, s['size'])
        if settings.ENABLE_STAR_GLOW and s['size'] > 1:
            halo = min(230, col + 34)
            pygame.draw.circle(surf, (halo, min(236, halo + 8), 246), pos, s['size'] + 2, 1)

    if scanlines is not None:
        surf.blit(scanlines, (0, 0))
    if settings.ENABLE_VIGNETTE or settings.VISUAL_QUALITY != "Performance":
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
