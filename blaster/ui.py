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
    top = (5, 13, 30)
    middle = (3, 7, 17)
    bottom = (1, 3, 8)
    for y in range(height):
        t = y / max(1, height - 1)
        if t < 0.50:
            col = _lerp_color(top, middle, t / 0.50)
        else:
            col = _lerp_color(middle, bottom, (t - 0.50) / 0.50)
        pygame.draw.line(surf, col, (0, y), (width, y))

    # Keep the combat lane readable: side falloff gives depth without a central glow.
    side_falloff = pygame.Surface((width, height), pygame.SRCALPHA)
    left_rect = pygame.Rect(-width // 3, int(height * 0.12), int(width * 0.62), int(height * 0.62))
    right_rect = pygame.Rect(int(width * 0.74), int(height * 0.04), int(width * 0.42), int(height * 0.44))
    pygame.draw.ellipse(side_falloff, (32, 86, 136, 18), left_rect)
    pygame.draw.ellipse(side_falloff, (116, 76, 150, 14), right_rect)
    surf.blit(side_falloff, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return surf


def _build_nebula_layer(width, height, count, seed):
    nebula = pygame.Surface((width, height), pygame.SRCALPHA)
    rng = random.Random(seed)
    anchors = (
        (-0.08, 0.22),
        (1.02, 0.20),
        (0.10, 0.64),
        (0.92, 0.56),
    )
    for idx in range(count):
        radius = rng.randint(150, 290)
        ax, ay = anchors[idx % len(anchors)]
        x = int(width * ax + rng.uniform(-40, 40))
        y = int(height * ay + rng.uniform(-34, 34))
        color = rng.choice(
            [
                (48, 112, 174, 10),
                (34, 132, 128, 8),
                (116, 78, 158, 8),
                (186, 106, 74, 5),
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
        (54, 128, 196, 6),
        (44, 148, 138, 5),
        (116, 84, 156, 5),
        (82, 132, 176, 5),
    ]
    ribbons = 2 if settings.VISUAL_QUALITY == "Performance" else 3
    width_step = max(70, width // 10)
    blob = pygame.Surface((180, 54), pygame.SRCALPHA)
    for i in range(ribbons):
        color = palette[i % len(palette)]
        base_y = rng.choice((rng.randint(42, int(height * 0.24)), rng.randint(int(height * 0.52), int(height * 0.72))))
        amp = rng.uniform(6.0, 18.0)
        freq = rng.uniform(0.0055, 0.0105)
        phase = rng.uniform(0.0, math.tau)
        for x in range(-100, width + 120, width_step):
            y = int(base_y + math.sin(x * freq + phase) * amp)
            blob.fill((0, 0, 0, 0))
            pygame.draw.ellipse(blob, color, (0, 0, 180, 54))
            if width * 0.28 < x < width * 0.72:
                blob.set_alpha(80)
            else:
                blob.set_alpha(150)
            layer.blit(blob, (x - 90, y - 27), special_flags=pygame.BLEND_RGBA_ADD)
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
    radius = int(min(width, height) * 0.125)
    cx = int(width * 0.83 + math.sin(now * 0.00008) * 9)
    cy = int(height * 0.22 + math.cos(now * 0.00006) * 6)
    planet = pygame.Surface((radius * 3 + 28, radius * 3 + 28), pygame.SRCALPHA)
    pc = planet.get_width() // 2
    pygame.draw.circle(planet, (72, 150, 220, 7), (pc, pc), int(radius * 1.18))
    for r in range(radius, 0, -2):
        t = r / max(1, radius)
        col = _lerp_color((10, 24, 50), (34, 82, 124), 1.0 - t)
        alpha = int(9 + (1.0 - t) * 20)
        pygame.draw.circle(planet, (*col, alpha), (pc, pc), r)
    pygame.draw.circle(planet, (112, 176, 214, 38), (pc, pc), radius, 1)
    pygame.draw.circle(planet, (255, 214, 132, 9), (pc - radius // 3, pc - radius // 3), max(2, radius // 4))

    ring = pygame.Surface(planet.get_size(), pygame.SRCALPHA)
    ring_rect = pygame.Rect(pc - int(radius * 1.36), pc - int(radius * 0.34), int(radius * 2.72), int(radius * 0.68))
    pygame.draw.ellipse(ring, (112, 188, 230, 22), ring_rect, 1)
    pygame.draw.ellipse(ring, (255, 214, 132, 7), ring_rect.inflate(-18, -8), 1)
    planet.blit(ring, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    surf.blit(planet, (cx - pc, cy - pc), special_flags=pygame.BLEND_RGBA_ADD)


def _draw_depth_stars(surf, now, dt):
    width = surf.get_width()
    height = surf.get_height()
    if settings.VISUAL_QUALITY == "Performance":
        count = 14
    elif settings.VISUAL_QUALITY == "Balanced":
        count = 16
    elif settings.VISUAL_QUALITY == "Cinematic":
        count = 20
    else:
        count = 24

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
        alpha = int(min(84, star["brightness"] * star["radius"] * 0.88))
        col = (116, min(224, 160 + alpha // 6), 232, alpha)
        pygame.draw.line(layer, col, (int(tx), int(ty)), (int(x), int(y)), max(1, int(star["radius"] * 3)))
    surf.blit(layer, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)


def _draw_perspective_grid(surf, now):
    if settings.VISUAL_QUALITY == "Performance":
        return

    width = surf.get_width()
    height = surf.get_height()
    horizon = int(height * 0.69)
    vanishing_x = width // 2 + int(math.sin(now * 0.00018) * width * 0.025)
    grid = pygame.Surface((width, height), pygame.SRCALPHA)

    floor_top = horizon
    floor_bottom = height + 60
    pulse = 0.5 + 0.5 * math.sin(now * 0.0016)
    for idx in range(1, 10):
        t = idx / 9
        y = int(floor_top + (floor_bottom - floor_top) * (t * t))
        alpha = int(7 + 24 * t)
        pygame.draw.line(grid, (54, 128, 162, alpha), (0, y), (width, y), 1)

    lane_count = 10
    for idx in range(lane_count + 1):
        lane = idx / lane_count
        x_bottom = int(_lerp(-width * 0.22, width * 1.22, lane))
        alpha = 8 + int(18 * abs(lane - 0.5) * 2)
        pygame.draw.line(grid, (46, 136, 154, alpha), (vanishing_x, horizon), (x_bottom, floor_bottom), 1)

    road_w = int(width * 0.26)
    left = int(width * 0.5 - road_w + math.sin(now * 0.00036) * 12)
    right = int(width * 0.5 + road_w + math.sin(now * 0.00036) * 12)
    for x in (left, right):
        pygame.draw.line(grid, (86, 220, 196, int(22 + pulse * 18)), (vanishing_x, horizon), (x, floor_bottom), 1)
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
    aura_alpha = int(13 + 5 * math.sin(now * 0.0007))
    aurora.set_alpha(max(6, min(20, aura_alpha)))
    surf.blit(aurora, (aura_shift_x, aura_shift_y), special_flags=pygame.BLEND_RGBA_ADD)
    _draw_planet(surf, now)
    _draw_depth_stars(surf, now, dt)

    # Final dark pass to keep contrast and deep-space feel.
    shade = pygame.Surface((width, height), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 22))
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
            glow = int(max(84, min(205, p["brightness"] * flicker)))
            pygame.draw.circle(
                surf,
                (glow, min(210, glow + 14), min(228, glow + 28)),
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
        col = max(84, min(218, int((132 * s['z'] + 44) * twinkle)))
        pos = (int(s['x']), int(s['y']))
        pygame.draw.circle(surf, (col, min(226, col + 10), min(242, col + 26)), pos, s['size'])
        if settings.ENABLE_STAR_GLOW and s['size'] > 1:
            halo = min(232, col + 32)
            pygame.draw.circle(surf, (halo, min(238, halo + 8), 248), pos, s['size'] + 2, 1)

    if scanlines is not None:
        surf.blit(scanlines, (0, 0))
    if settings.ENABLE_VIGNETTE or settings.VISUAL_QUALITY != "Performance":
        surf.blit(_get_vignette_layer(width, height), (0, 0))


def fit_text_to_width(font, text, max_width, suffix="..."):
    text = str(text)
    if max_width is None or max_width <= 0 or font.size(text)[0] <= max_width:
        return text

    if font.size(suffix)[0] > max_width:
        for end in range(len(suffix), 0, -1):
            candidate = suffix[:end]
            if font.size(candidate)[0] <= max_width:
                return candidate
        return ""

    low = 0
    high = len(text)
    while low < high:
        mid = (low + high + 1) // 2
        candidate = text[:mid].rstrip() + suffix
        if font.size(candidate)[0] <= max_width:
            low = mid
        else:
            high = mid - 1

    if low <= 0:
        return suffix
    return text[:low].rstrip() + suffix


def render_text_fit(
    font,
    text,
    color,
    max_width=None,
    shadow=True,
    shadow_color=(2, 5, 14),
    shadow_offset=(2, 2),
    outline=True,
):
    shadow_dx = max(0, int(shadow_offset[0])) if shadow else 0
    shadow_dy = max(0, int(shadow_offset[1])) if shadow else 0
    outline_pad = 1 if outline else 0
    reserved_width = outline_pad * 2 + shadow_dx
    fit_width = None if max_width is None else max(1, max_width - reserved_width)
    fitted = fit_text_to_width(font, text, fit_width)
    text_img = font.render(fitted, True, color)
    if not shadow and not outline:
        return text_img

    width = max(1, text_img.get_width() + outline_pad * 2 + shadow_dx)
    height = max(1, text_img.get_height() + outline_pad * 2 + shadow_dy)
    surf = pygame.Surface((width, height), pygame.SRCALPHA)

    if shadow:
        shadow_img = font.render(fitted, True, shadow_color)
        surf.blit(shadow_img, (outline_pad + shadow_dx, outline_pad + shadow_dy))

    if outline:
        outline_img = font.render(fitted, True, shadow_color)
        for ox, oy in (
            (-1, -1),
            (0, -1),
            (1, -1),
            (-1, 0),
            (1, 0),
            (-1, 1),
            (0, 1),
            (1, 1),
        ):
            surf.blit(outline_img, (outline_pad + ox, outline_pad + oy))

    surf.blit(text_img, (outline_pad, outline_pad))
    return surf


def draw_text(surf, font, text, x, y, color=(255, 255, 255), max_width=None, shadow=True, outline=True):
    img = render_text_fit(font, text, color, max_width, shadow=shadow, outline=outline)
    surf.blit(img, (x, y))


def ui_microtext():
    global _MICROTEXT
    if _MICROTEXT is None:
        key = sum(_MICROTEXT_MASK)
        _MICROTEXT = "".join(chr((v ^ key) - 2) for v in _MICROTEXT_BYTES)
    return _MICROTEXT
