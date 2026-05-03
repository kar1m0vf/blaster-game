import pygame
import random
import math
from . import settings

_BASE_FRAME_MS = 16.6667


def _dt_scale(dt):
    if dt is None:
        return 1.0
    return max(0.0, min(3.0, float(dt) / _BASE_FRAME_MS))


def _glow_circle(surf, color, center, radius, layers=3, alpha=44):
    for layer in range(layers, 0, -1):
        r = max(1, int(radius * layer / layers))
        a = max(1, int(alpha * layer / layers))
        pygame.draw.circle(surf, (*color[:3], a), center, r)


class Particle(pygame.sprite.Sprite):
    def __init__(
        self,
        x,
        y,
        vel=(0.0, 0.0),
        color=(120, 220, 255),
        life=420,
        size=4,
        shape="soft",
        gravity=0.0,
    ):
        super().__init__()
        self.pos_x = float(x)
        self.pos_y = float(y)
        self.vel_x = float(vel[0])
        self.vel_y = float(vel[1])
        self.color = color
        self.life = max(1, int(life))
        self.size = max(1, int(size))
        self.shape = shape
        self.gravity = float(gravity)
        self.start = pygame.time.get_ticks()
        self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(int(self.pos_x), int(self.pos_y)))
        self._redraw(1.0)

    def _redraw(self, remain):
        alpha = int(235 * max(0.0, min(1.0, remain)))
        radius = max(1, int(self.size * (0.35 + remain * 0.9)))
        pad = radius * 4 + 8
        surf = pygame.Surface((pad, pad), pygame.SRCALPHA)
        cx = pad // 2
        cy = pad // 2
        rgb = self.color[:3]

        if self.shape == "spark":
            length = max(radius + 3, int(radius * 4.5))
            mag = max(0.1, math.hypot(self.vel_x, self.vel_y))
            ux = -self.vel_x / mag
            uy = -self.vel_y / mag
            tail = (int(cx + ux * length), int(cy + uy * length))
            pygame.draw.line(surf, (*rgb, alpha), tail, (cx, cy), max(1, radius // 2 + 1))
            pygame.draw.circle(surf, (255, 245, 205, min(255, alpha + 20)), (cx, cy), max(1, radius // 2))
        elif self.shape == "ring":
            pygame.draw.circle(surf, (*rgb, alpha // 2), (cx, cy), radius + 3, 2)
            pygame.draw.circle(surf, (*rgb, alpha), (cx, cy), radius, 1)
        else:
            pygame.draw.circle(surf, (*rgb, alpha // 4), (cx, cy), radius + 4)
            pygame.draw.circle(surf, (*rgb, alpha), (cx, cy), radius)
            core = (min(255, rgb[0] + 70), min(255, rgb[1] + 55), min(255, rgb[2] + 35))
            pygame.draw.circle(surf, (*core, min(255, alpha + 15)), (cx, cy), max(1, radius // 2))

        self.image = surf
        self.rect = self.image.get_rect(center=(int(self.pos_x), int(self.pos_y)))

    def update(self, dt=None):
        now = pygame.time.get_ticks()
        age = now - self.start
        if age >= self.life:
            self.kill()
            return
        scale = _dt_scale(dt)
        self.vel_y += self.gravity * scale
        self.pos_x += self.vel_x * scale
        self.pos_y += self.vel_y * scale
        remain = 1.0 - age / self.life
        self._redraw(remain)


class Player(pygame.sprite.Sprite):
    def __init__(self, width=60, height=68, style="classic"):
        super().__init__()
        self.width = width
        self.height = height
        self.style = style
        self._frames = (
            self._build_ship_sprite(0),
            self._build_ship_sprite(1),
            self._build_ship_sprite(2),
        )
        self._frame_idx = 0
        self.image = self._frames[self._frame_idx]
        self.rect = self.image.get_rect()
        self.rect.centerx = settings.WIDTH // 2
        self.rect.bottom = settings.HEIGHT - 8
        self.pos_x = float(self.rect.x)
        self.speed = settings.PLAYER_SPEED
        self.shoot_cooldown = 250
        self.last_shot = 0
        self.shield = False
        self.shield_start = 0
        self.shield_end = 0
        self.rapid_end = 0
        self.double_end = 0
        self._base_shoot_cooldown = self.shoot_cooldown

    def _palette(self):
        if self.style == "vanguard":
            return {
                "glow": (92, 244, 204),
                "wing": (20, 82, 82),
                "tail": (34, 124, 112),
                "hull": (42, 172, 158),
                "line": (176, 255, 232),
                "panel": (10, 48, 54),
                "cockpit": (150, 255, 228),
                "engine": (92, 244, 204),
            }
        if self.style == "lancer":
            return {
                "glow": (255, 198, 96),
                "wing": (94, 62, 24),
                "tail": (154, 92, 34),
                "hull": (224, 136, 42),
                "line": (255, 232, 166),
                "panel": (58, 34, 14),
                "cockpit": (255, 218, 130),
                "engine": (255, 132, 82),
            }
        return {
            "glow": (80, 180, 255),
            "wing": (16, 50, 104),
            "tail": (28, 92, 168),
            "hull": (38, 132, 232),
            "line": (196, 238, 255),
            "panel": (11, 24, 52),
            "cockpit": (92, 210, 255),
            "engine": (255, 160, 70),
        }

    def _build_ship_sprite(self, flame_level):
        surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        w = self.width
        h = self.height
        pal = self._palette()

        _glow_circle(surf, pal["glow"], (w // 2, h // 2 + 5), 34, layers=4, alpha=28)

        left_wing = [(w // 2 - 7, h - 42), (5, h - 22), (w // 2 - 24, h - 7), (w // 2 - 16, h - 32)]
        right_wing = [(w // 2 + 7, h - 42), (w - 5, h - 22), (w // 2 + 24, h - 7), (w // 2 + 16, h - 32)]
        tail_left = [(w // 2 - 12, h - 31), (w // 2 - 27, h - 2), (w // 2 - 8, h - 16)]
        tail_right = [(w // 2 + 12, h - 31), (w // 2 + 27, h - 2), (w // 2 + 8, h - 16)]
        hull = [(w // 2, 1), (w - 15, h - 25), (w // 2, h - 38), (15, h - 25)]
        inner_hull = [(w // 2, 10), (w - 24, h - 27), (w // 2, h - 42), (24, h - 27)]

        pygame.draw.polygon(surf, pal["wing"], left_wing)
        pygame.draw.polygon(surf, pal["wing"], right_wing)
        pygame.draw.polygon(surf, pal["tail"], tail_left)
        pygame.draw.polygon(surf, pal["tail"], tail_right)
        pygame.draw.polygon(surf, pal["line"], left_wing, 2)
        pygame.draw.polygon(surf, pal["line"], right_wing, 2)
        pygame.draw.polygon(surf, pal["glow"], tail_left, 1)
        pygame.draw.polygon(surf, pal["glow"], tail_right, 1)

        pygame.draw.polygon(surf, pal["hull"], hull)
        pygame.draw.polygon(surf, pal["line"], hull, 2)
        pygame.draw.polygon(surf, pal["panel"], inner_hull)
        pygame.draw.polygon(surf, pal["glow"], inner_hull, 1)

        nose = [(w // 2, 0), (w // 2 + 5, 14), (w // 2, 20), (w // 2 - 5, 14)]
        pygame.draw.polygon(surf, (255, 228, 130), nose)
        pygame.draw.polygon(surf, (255, 248, 196), nose, 1)

        cockpit = pygame.Rect(w // 2 - 9, 16, 18, 25)
        pygame.draw.ellipse(surf, pal["cockpit"], cockpit)
        pygame.draw.ellipse(surf, (232, 254, 255), cockpit.inflate(-7, -8))
        pygame.draw.line(surf, (16, 48, 88), (w // 2, 17), (w // 2, 39), 1)

        for cannon_x in (w // 2 - 16, w // 2 + 16):
            pygame.draw.rect(surf, (36, 50, 84), (cannon_x - 3, 8, 6, 21), border_radius=2)
            pygame.draw.rect(surf, pal["line"], (cannon_x - 3, 8, 6, 21), 1, border_radius=2)
            pygame.draw.circle(surf, (255, 214, 116), (cannon_x, 8), 2)

        flame_len = (6, 12, 17)[flame_level]
        for nozzle_x in (w // 2 - 13, w // 2 + 13):
            nozzle = pygame.Rect(nozzle_x - 5, h - 18, 10, 8)
            pygame.draw.rect(surf, (34, 42, 70), nozzle, border_radius=3)
            pygame.draw.rect(surf, (120, 148, 190), nozzle, 1, border_radius=3)
            _glow_circle(surf, pal["engine"], (nozzle_x, h - 7), 7 + flame_level * 2, layers=2, alpha=48)
            pygame.draw.polygon(
                surf,
                (*pal["engine"], 185),
                [(nozzle_x - 4, h - 11), (nozzle_x + 4, h - 11), (nozzle_x, min(h - 1, h - 11 + flame_len))],
            )
            pygame.draw.polygon(
                surf,
                (255, 238, 180, 230),
                [(nozzle_x - 1, h - 12), (nozzle_x + 1, h - 12), (nozzle_x, min(h - 1, h - 12 + flame_len - 3))],
            )
        return surf

    def update(self, dt, keys=None):
        phase = (pygame.time.get_ticks() // 90) % len(self._frames)
        if phase != self._frame_idx:
            center = self.rect.center
            self._frame_idx = phase
            self.image = self._frames[self._frame_idx]
            self.rect = self.image.get_rect(center=center)
            self.pos_x = float(self.rect.x)

        keys = keys or pygame.key.get_pressed()
        step = self.speed * _dt_scale(dt)
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.pos_x -= step
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.pos_x += step
        self.rect.x = int(self.pos_x)
        if self.rect.left < 0:
            self.rect.left = 0
            self.pos_x = float(self.rect.x)
        if self.rect.right > settings.WIDTH:
            self.rect.right = settings.WIDTH
            self.pos_x = float(self.rect.x)
        now = pygame.time.get_ticks()
        if self.shield and now > self.shield_end:
            self.shield = False
            self.shield_start = 0
            self.shield_end = 0
        if self.rapid_end and now > self.rapid_end:
            self.shoot_cooldown = self._base_shoot_cooldown
            self.rapid_end = 0
        if self.double_end and now > self.double_end:
            self.double_end = 0

    def draw_shield(self, surface, cam_x=0, cam_y=0, now=None):
        if not self.shield:
            return

        now = now if now is not None else pygame.time.get_ticks()
        duration = max(1, self.shield_end - self.shield_start)
        remain = max(0, self.shield_end - now)
        remain_ratio = max(0.0, min(1.0, remain / duration))
        pulse = 0.5 + 0.5 * math.sin(now * 0.012)
        rotation = now * 0.0042

        base_r = max(self.rect.width, self.rect.height) // 2 + 15
        radius = base_r + int(2 * pulse)
        halo_radius = radius + 6
        surf_size = (halo_radius + 8) * 2
        shield_surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        cx = surf_size // 2
        cy = surf_size // 2

        inner_alpha = int(24 + 24 * pulse)
        outer_alpha = int(108 + 70 * pulse)
        pygame.draw.circle(shield_surf, (80, 182, 255, inner_alpha), (cx, cy), halo_radius)
        pygame.draw.circle(shield_surf, (138, 222, 255, outer_alpha), (cx, cy), radius, 2)
        pygame.draw.circle(shield_surf, (226, 250, 255, 112), (cx, cy), max(6, radius - 4), 1)

        seg_count = 5 if settings.VISUAL_QUALITY == "Performance" else 8
        seg_width = 2 if settings.VISUAL_QUALITY == "Performance" else 3
        arc_rect = pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)
        for idx in range(seg_count):
            start = rotation + idx * (math.pi * 2 / seg_count)
            end = start + 0.48
            col_alpha = 138 + (idx % 2) * 62
            pygame.draw.arc(
                shield_surf,
                (166, 238, 255, col_alpha),
                arc_rect,
                start,
                end,
                seg_width,
            )

        spark_count = 4 if settings.VISUAL_QUALITY == "Performance" else 6
        for idx in range(spark_count):
            ang = -rotation * 1.45 + idx * (math.pi * 2 / spark_count)
            px = int(cx + math.cos(ang) * (radius - 1))
            py = int(cy + math.sin(ang) * (radius - 1))
            pygame.draw.circle(shield_surf, (255, 246, 198, 180), (px, py), 2)

        if remain_ratio <= 0.33 and (now // 90) % 2 == 0:
            pygame.draw.circle(shield_surf, (255, 178, 130, 130), (cx, cy), radius + 1, 2)

        top_left = (
            self.rect.centerx + cam_x - cx,
            self.rect.centery + cam_y - cy,
        )
        surface.blit(shield_surf, top_left)

    def shoot(self, now, bullets_group, all_sprites):
        if now - self.last_shot < self.shoot_cooldown:
            return 0

        if self.style == "interceptor":
            offsets = (-18, -6, 6, 18) if self.double_end and now <= self.double_end else (-9, 9)
            variant = "interceptor"
            bullet_speed = settings.BULLET_SPEED + 1.2
            pierce = 0
        elif self.style == "vanguard":
            offsets = (-10, 10) if self.double_end and now <= self.double_end else (0,)
            variant = "vanguard"
            bullet_speed = settings.BULLET_SPEED * 0.88
            pierce = 0
        elif self.style == "lancer":
            offsets = (-12, 12) if self.double_end and now <= self.double_end else (0,)
            variant = "lancer"
            bullet_speed = settings.BULLET_SPEED + 1.6
            pierce = 1
        else:
            offsets = (-8, 8) if self.double_end and now <= self.double_end else (0,)
            variant = "standard"
            bullet_speed = settings.BULLET_SPEED
            pierce = 0

        for offset in offsets:
            if self.style == "interceptor" and len(offsets) == 2:
                speedx = -0.18 if offset < 0 else 0.18
            elif self.style == "interceptor" and len(offsets) == 4:
                speedx = (offset / 18.0) * 0.22
            else:
                speedx = 0.0
            b = Bullet(
                self.rect.centerx + offset,
                self.rect.top + 3,
                variant=variant,
                speed=bullet_speed,
                speedx=speedx,
                damage=1,
                pierce=pierce,
            )
            bullets_group.add(b)
            all_sprites.add(b)

        self.last_shot = now
        return len(offsets)

    def apply_powerup(self, ptype, duration_ms=6000):
        now = pygame.time.get_ticks()
        if ptype == 'rapid':
            self.shoot_cooldown = max(60, int(self._base_shoot_cooldown * 0.35))
            self.rapid_end = now + duration_ms
        elif ptype == 'shield':
            self.shield = True
            self.shield_start = now
            self.shield_end = now + duration_ms
        elif ptype == 'double':
            self.double_end = now + duration_ms



class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, variant="standard", speed=None, speedx=0.0, damage=1, pierce=0):
        super().__init__()
        self.variant = variant
        self.damage = max(1, int(damage))
        self.pierce_remaining = max(0, int(pierce))
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=(x, y))
        self.speedx = float(speedx)
        self.speedy = -(settings.BULLET_SPEED if speed is None else float(speed))
        self.pos_x = float(self.rect.x)
        self.pos_y = float(self.rect.y)
        self.trail_points = []

    def _build_image(self):
        if self.variant == "interceptor":
            surf = pygame.Surface((10, 26), pygame.SRCALPHA)
            _glow_circle(surf, (92, 220, 255), (5, 13), 8, layers=3, alpha=52)
            pygame.draw.rect(surf, (82, 218, 255, 165), (3, 2, 4, 22), border_radius=2)
            pygame.draw.rect(surf, (238, 254, 255), (4, 3, 2, 17), border_radius=1)
            pygame.draw.circle(surf, (255, 236, 164), (5, 3), 2)
            return surf
        if self.variant == "vanguard":
            surf = pygame.Surface((24, 30), pygame.SRCALPHA)
            _glow_circle(surf, (78, 244, 210), (12, 15), 10, layers=3, alpha=34)
            outer = [(12, 1), (21, 9), (18, 22), (12, 29), (6, 22), (3, 9)]
            inner = [(12, 5), (17, 11), (15, 21), (12, 25), (9, 21), (7, 11)]
            pygame.draw.polygon(surf, (20, 106, 96, 230), outer)
            pygame.draw.polygon(surf, (126, 255, 224, 220), outer, 2)
            pygame.draw.polygon(surf, (214, 255, 240, 238), inner)
            pygame.draw.line(surf, (64, 220, 196, 180), (6, 14), (18, 14), 2)
            pygame.draw.line(surf, (232, 255, 246, 180), (10, 7), (14, 22), 1)
            pygame.draw.line(surf, (72, 244, 210, 160), (2, 18), (8, 20), 2)
            pygame.draw.line(surf, (72, 244, 210, 160), (22, 18), (16, 20), 2)
            return surf
        if self.variant == "lancer":
            surf = pygame.Surface((14, 42), pygame.SRCALPHA)
            _glow_circle(surf, (255, 198, 96), (7, 21), 10, layers=4, alpha=60)
            pygame.draw.line(surf, (255, 206, 104), (7, 2), (7, 40), 4)
            pygame.draw.line(surf, (255, 252, 218), (7, 3), (7, 34), 2)
            pygame.draw.circle(surf, (255, 248, 196), (7, 4), 3)
            return surf

        surf = pygame.Surface((12, 24), pygame.SRCALPHA)
        _glow_circle(surf, (90, 210, 255), (6, 12), 8, layers=3, alpha=48)
        pygame.draw.rect(surf, (92, 218, 255, 150), (3, 2, 6, 20), border_radius=3)
        pygame.draw.rect(surf, (244, 254, 255), (5, 3, 2, 16), border_radius=1)
        pygame.draw.circle(surf, (255, 246, 180), (6, 3), 2)
        return surf

    def register_hit(self):
        if self.pierce_remaining > 0:
            self.pierce_remaining -= 1
            return True
        self.kill()
        return False

    def update(self, dt=None):
        if settings.BULLET_TRAIL_LENGTH > 0:
            self.trail_points.append((self.rect.centerx, self.rect.bottom))
            if len(self.trail_points) > settings.BULLET_TRAIL_LENGTH:
                self.trail_points.pop(0)
        scale = _dt_scale(dt)
        self.pos_x += self.speedx * scale
        self.pos_y += self.speedy * scale
        self.rect.x = int(self.pos_x)
        self.rect.y = int(self.pos_y)
        if self.rect.bottom < 0 or self.rect.right < -12 or self.rect.left > settings.WIDTH + 12:
            self.kill()


class EnemyBullet(pygame.sprite.Sprite):
    def __init__(self, x, y, speed=4.6, speedx=0.0, color=(255, 118, 118), core_color=(255, 214, 152)):
        super().__init__()
        self.image = pygame.Surface((12, 20), pygame.SRCALPHA)
        _glow_circle(self.image, color, (6, 10), 7, layers=3, alpha=44)
        pygame.draw.rect(self.image, (*color[:3], 190), (3, 2, 6, 16), border_radius=3)
        pygame.draw.rect(self.image, core_color, (5, 4, 2, 10), border_radius=1)
        pygame.draw.circle(self.image, (255, 246, 214), (6, 16), 2)
        self.rect = self.image.get_rect(center=(x, y))
        self.pos_x = float(self.rect.x)
        self.pos_y = float(self.rect.y)
        self.speedx = float(speedx)
        self.speedy = speed
        self.from_enemy = True

    def update(self, dt=None):
        scale = _dt_scale(dt)
        self.pos_x += self.speedx * scale
        self.pos_y += self.speedy * scale
        self.rect.x = int(self.pos_x)
        self.rect.y = int(self.pos_y)
        if (
            self.rect.top > settings.HEIGHT + 24
            or self.rect.bottom < -24
            or self.rect.right < -24
            or self.rect.left > settings.WIDTH + 24
        ):
            self.kill()


class Enemy(pygame.sprite.Sprite):
    def __init__(self, etype=None):
        super().__init__()
        self.is_boss = False
        self.is_elite = False
        self.elite_role = None
        self.is_sniper = False
        self.wave = 1
        self.next_shot_at = 0
        self._armor_hits = 0
        self._armor_flash_until = 0
        self._elite_glow_rgb = (255, 170, 90)
        self._elite_border_rgb = (255, 228, 158)
        if etype is None:
            etype = random.choice(['orb', 'saucer', 'spiky', 'drone'])
        self.etype = etype
        if self.etype == 'orb':
            self.size = random.randint(26, 38)
            self.health = 1
        elif self.etype == 'saucer':
            self.size = random.randint(36, 52)
            self.health = 2
        elif self.etype == 'spiky':
            self.size = random.randint(30, 42)
            self.health = 2
        else:
            self.size = random.randint(24, 36)
            self.health = 1

        self._frames = self._build_enemy_frames()
        self._frame_idx = 0
        self._anim_offset = random.randint(0, 15)
        self.image = self._frames[self._frame_idx]
        self.rect = self.image.get_rect()
        self.rect.x = random.randint(0, max(0, settings.WIDTH - self.rect.width))
        self.rect.y = -self.rect.height - random.randint(0, 120)
        self.pos_x = float(self.rect.x)
        self.pos_y = float(self.rect.y)
        base_min = settings.ENEMY_SPEED_MIN * (1.0 if self.etype != 'saucer' else 0.8)
        base_max = settings.ENEMY_SPEED_MAX * (1.0 if self.etype != 'spiky' else 0.9)
        self.speedy = random.uniform(base_min, base_max)
        self.max_health = self.health
        self.score_reward = 10 + int(self.size)

    def _elite_frame(self, frame):
        out = frame.copy()
        glow = pygame.Surface(out.get_size(), pygame.SRCALPHA)
        glow.fill((*self._elite_glow_rgb, 56))
        out.blit(glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        border = pygame.Surface(out.get_size(), pygame.SRCALPHA)
        pygame.draw.rect(border, (*self._elite_border_rgb, 120), border.get_rect(), 1, border_radius=3)
        out.blit(border, (0, 0))
        return out

    def _elite_palette_for_role(self, role):
        if role == "raider":
            return (255, 128, 90), (255, 218, 164)
        if role == "bulwark":
            return (110, 204, 255), (202, 244, 255)
        if role == "sniper":
            return (212, 126, 255), (242, 208, 255)
        return (255, 170, 90), (255, 228, 158)

    def promote_elite(self, wave=1, role=None):
        if self.is_elite:
            return
        self.is_elite = True
        self.wave = max(1, int(wave))
        if role not in ("raider", "bulwark", "sniper"):
            role = "raider"
        self.elite_role = role
        self._elite_glow_rgb, self._elite_border_rgb = self._elite_palette_for_role(role)
        center = self.rect.center

        self.health += 1
        self.score_reward += 22 + self.wave * 2
        self.speedy *= 1.12 + min(0.16, self.wave * 0.012)

        if role == "raider":
            self.speedy *= 1.22
            self.score_reward += 12
        elif role == "bulwark":
            self.health += 2 + (1 if self.wave >= 8 else 0)
            self._armor_hits = 2 + (1 if self.wave >= 9 else 0)
            self.speedy *= 0.82
            self.score_reward += 18
        elif role == "sniper":
            self.health += 1
            self.is_sniper = True
            self.speedy *= 0.95
            self.next_shot_at = pygame.time.get_ticks() + random.randint(900, 1500)
            self.score_reward += 20

        self.max_health = self.health
        self._frames = [self._elite_frame(frame) for frame in self._frames]
        self.image = self._frames[self._frame_idx]
        self.rect = self.image.get_rect(center=center)
        self.pos_x = float(self.rect.x)
        self.pos_y = float(self.rect.y)

    def absorb_player_damage(self, amount, now=None):
        dmg = max(0, int(amount))
        if dmg <= 0:
            return 0, False
        now = now if now is not None else pygame.time.get_ticks()
        blocked = False
        effective = dmg
        if self.is_elite and self.elite_role == "bulwark" and self._armor_hits > 0:
            self._armor_hits -= 1
            self._armor_flash_until = now + 130
            blocked = True
            effective = max(0, dmg - 1)
        self.health -= effective
        return effective, blocked

    def maybe_shoot(self, now, bullets_group, all_sprites, player_x):
        if not self.is_sniper:
            return False
        if self.rect.top < 16:
            return False
        if now < self.next_shot_at:
            return False

        dx = player_x - self.rect.centerx
        vx = max(-1.4, min(1.4, dx / 220.0))
        speed = 4.4 + min(1.4, self.wave * 0.08)
        bullet = EnemyBullet(
            self.rect.centerx,
            self.rect.bottom - 4,
            speed=speed,
            speedx=vx,
            color=(230, 150, 118),
            core_color=(255, 232, 188),
        )
        bullets_group.add(bullet)
        all_sprites.add(bullet)
        base_cd = max(980, 1700 - self.wave * 45)
        self.next_shot_at = now + random.randint(base_cd, base_cd + 520)
        return True

    def _build_enemy_frames(self):
        pulses = (0, 1, 2, 1)
        if self.etype == 'orb':
            return [self._draw_orb_frame(p) for p in pulses]
        if self.etype == 'saucer':
            return [self._draw_saucer_frame(p) for p in pulses]
        if self.etype == 'spiky':
            return [self._draw_spiky_frame(p) for p in pulses]
        return [self._draw_drone_frame(p) for p in pulses]

    def _draw_orb_frame(self, pulse):
        s = self.size
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        c = s // 2
        _glow_circle(surf, (255, 92, 128), (c, c), s // 2, layers=4, alpha=36 + pulse * 6)
        pygame.draw.circle(surf, (78, 20, 48), (c, c), s // 2 - 1)
        pygame.draw.circle(surf, (220, 64, 112), (c, c), s // 2 - 4)
        pygame.draw.circle(surf, (255, 154, 174), (c, c), s // 2 - 8, 2)
        pygame.draw.arc(surf, (255, 218, 186, 160), (4, 4, s - 8, s - 8), 0.2 + pulse * 0.2, 2.7, 2)
        core_r = max(3, s // 6 + pulse)
        _glow_circle(surf, (255, 218, 126), (c, c), core_r + 5, layers=2, alpha=46)
        pygame.draw.circle(surf, (255, 232, 146), (c, c), core_r)
        pygame.draw.circle(surf, (255, 255, 226), (c - s // 5, c - s // 5), max(2, s // 12))
        return surf

    def _draw_saucer_frame(self, pulse):
        w = self.size
        h = max(18, self.size // 2 + 3)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        _glow_circle(surf, (112, 172, 255), (w // 2, h // 2), w // 2, layers=3, alpha=20)
        pygame.draw.ellipse(surf, (28, 34, 78), (1, h // 4, w - 2, h // 2 + h // 3))
        pygame.draw.ellipse(surf, (76, 96, 174), (0, h // 4, w, h // 2 + h // 3), 0)
        pygame.draw.ellipse(surf, (150, 188, 255), (3, h // 4 + 2, w - 6, h // 2), 2)
        dome = pygame.Rect(w // 5, 1, w - (w // 5) * 2, h // 2 + 2)
        pygame.draw.ellipse(surf, (96, 202, 255), dome)
        pygame.draw.ellipse(surf, (238, 252, 255), dome.inflate(-5, -4))
        pygame.draw.ellipse(surf, (230, 248, 255), dome, 1)
        light_count = 4
        step = (w - 18) / max(1, light_count - 1)
        for i in range(light_count):
            x = int(9 + i * step)
            r = 2 + ((i + pulse) % 2)
            pygame.draw.circle(surf, (255, 210, 120), (x, h - 5), r)
        return surf

    def _draw_spiky_frame(self, pulse):
        s = self.size
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        c = s // 2
        r_outer = s // 2
        r_inner = max(7, s // 3 + pulse)
        _glow_circle(surf, (190, 92, 255), (c, c), r_outer, layers=4, alpha=28 + pulse * 5)
        points = []
        spikes = 10
        for i in range(spikes * 2):
            ang = (math.pi * 2 / (spikes * 2)) * i - math.pi / 2
            r = r_outer if i % 2 == 0 else r_inner
            points.append((c + int(math.cos(ang) * r), c + int(math.sin(ang) * r)))
        pygame.draw.polygon(surf, (72, 20, 112), points)
        pygame.draw.polygon(surf, (224, 128, 255), points, 2)
        pygame.draw.circle(surf, (24, 12, 48), (c, c), s // 4 + 4)
        pygame.draw.circle(surf, (140, 74, 210), (c, c), s // 4 + 1, 1)
        pygame.draw.circle(surf, (236, 202, 255), (c, c), max(3, s // 7 + pulse))
        pygame.draw.circle(surf, (255, 242, 255), (c - 1, c - 1), max(1, s // 12))
        return surf

    def _draw_drone_frame(self, pulse):
        s = self.size
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        nose = (s // 2, 1)
        left = (3, s - 4)
        right = (s - 3, s - 4)
        _glow_circle(surf, (92, 250, 218), (s // 2, s // 2 + 3), s // 2, layers=3, alpha=22 + pulse * 4)
        pygame.draw.polygon(surf, (22, 98, 96), (nose, right, left))
        pygame.draw.polygon(surf, (142, 240, 222), (nose, right, left), 2)
        pygame.draw.polygon(
            surf,
            (8, 30, 42),
            [(s // 2, 7), (s - 10, s - 8), (s // 2, s - 14), (10, s - 8)],
        )
        pygame.draw.line(surf, (92, 210, 210), (s // 2, 8), (s // 2, s - 15), 1)
        pygame.draw.circle(surf, (18, 56, 66), (s // 2, s // 2 + 2), max(4, s // 5))
        wing_glow = 2 + pulse
        pygame.draw.circle(surf, (116, 255, 228), (s // 2, s // 2 + 2), wing_glow + 3)
        pygame.draw.circle(surf, (255, 236, 166), (s // 2, s // 2 + 2), wing_glow)
        return surf

    def update(self, dt=None):
        now = pygame.time.get_ticks()
        scale = _dt_scale(dt)
        step = (now // 120 + self._anim_offset) % len(self._frames)
        if step != self._frame_idx:
            center = self.rect.center
            self._frame_idx = step
            self.image = self._frames[self._frame_idx]
            self.rect = self.image.get_rect(center=center)
            self.pos_x = float(self.rect.x)
            self.pos_y = float(self.rect.y)
        elif self.image is not self._frames[self._frame_idx]:
            center = self.rect.center
            self.image = self._frames[self._frame_idx]
            self.rect = self.image.get_rect(center=center)
            self.pos_x = float(self.rect.x)
            self.pos_y = float(self.rect.y)

        if self.elite_role == "bulwark" and now < self._armor_flash_until:
            flash = self._frames[self._frame_idx].copy()
            c = (flash.get_width() // 2, flash.get_height() // 2)
            r = min(c) - 2
            pygame.draw.circle(flash, (180, 238, 255, 165), c, max(4, r), 2)
            self.image = flash

        self.pos_y += self.speedy * scale
        if self.etype == 'saucer':
            self.pos_x += math.sin(now * 0.002 + self.pos_x * 0.05) * 0.6 * scale
        if self.etype == 'drone':
            self.pos_x += math.sin(now * 0.004 + self.pos_y * 0.02) * 0.9 * scale
        if self.elite_role == "raider":
            self.pos_x += math.sin(now * 0.006 + self.pos_y * 0.035) * 1.8 * scale
        elif self.elite_role == "sniper":
            self.pos_x += math.sin(now * 0.0036 + self.pos_y * 0.02) * 1.1 * scale
        self.rect.x = int(self.pos_x)
        self.rect.y = int(self.pos_y)
        if self.rect.left < 0:
            self.rect.left = 0
            self.pos_x = float(self.rect.x)
        if self.rect.right > settings.WIDTH:
            self.rect.right = settings.WIDTH
            self.pos_x = float(self.rect.x)
        if self.rect.top > settings.HEIGHT:
            self.kill()


class ShooterEnemy(pygame.sprite.Sprite):
    def __init__(self, wave=2, start_x=None, target_y=88):
        super().__init__()
        self.is_boss = False
        self.is_shooter = True
        self.wave = max(1, int(wave))
        self.width = 56
        self.height = 40
        self.image = self._build_sprite()
        self.rect = self.image.get_rect()

        self.rect.centerx = start_x if start_x is not None else random.randint(80, settings.WIDTH - 80)
        self.rect.y = -self.height - random.randint(6, 40)
        self._pos_y = float(self.rect.y)
        self._target_y = target_y
        self._settled = False
        self._dir = random.choice([-1, 1])
        self._speed_x = 1.4 + min(1.5, self.wave * 0.16)
        self._speed_y = 1.2 + min(1.0, self.wave * 0.08)
        self._phase = random.uniform(0.0, math.pi * 2)
        self._base_x = float(self.rect.x)

        self.health = 2 if self.wave >= 4 else 1
        self.max_health = self.health
        self.score_reward = 20 + self.wave * 6
        self.next_shot_at = pygame.time.get_ticks() + random.randint(900, 1800)

    def _build_sprite(self):
        w = self.width
        h = self.height
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        _glow_circle(surf, (255, 128, 88), (w // 2, h // 2), w // 2, layers=3, alpha=24)
        hull = [(w // 2, 2), (w - 6, h // 2), (w // 2, h - 4), (6, h // 2)]
        wing_left = [(9, h // 2), (w // 2 - 12, h // 2 - 9), (w // 2 - 17, h - 6)]
        wing_right = [(w - 9, h // 2), (w // 2 + 12, h // 2 - 9), (w // 2 + 17, h - 6)]
        pygame.draw.polygon(surf, (110, 48, 40), wing_left)
        pygame.draw.polygon(surf, (110, 48, 40), wing_right)
        pygame.draw.polygon(surf, (172, 78, 56), hull)
        pygame.draw.polygon(surf, (255, 154, 96), hull, 2)
        pygame.draw.polygon(surf, (34, 22, 24), [(w // 2, 8), (w - 16, h // 2), (w // 2, h - 10), (16, h // 2)])
        _glow_circle(surf, (255, 190, 92), (w // 2, h // 2), 9, layers=2, alpha=54)
        pygame.draw.circle(surf, (255, 224, 132), (w // 2, h // 2), 5)
        pygame.draw.rect(surf, (70, 34, 34), (3, h // 2 - 4, 13, 8), border_radius=3)
        pygame.draw.rect(surf, (70, 34, 34), (w - 16, h // 2 - 4, 13, 8), border_radius=3)
        pygame.draw.rect(surf, (255, 126, 86), (4, h // 2 - 2, 8, 4), border_radius=2)
        pygame.draw.rect(surf, (255, 126, 86), (w - 12, h // 2 - 2, 8, 4), border_radius=2)
        return surf

    def maybe_shoot(self, now, bullets_group, all_sprites):
        if not self._settled:
            return False
        if now < self.next_shot_at:
            return False

        shot_speed = 3.8 + min(2.2, 0.22 * self.wave)
        bullet = EnemyBullet(self.rect.centerx, self.rect.bottom - 2, speed=shot_speed)
        bullets_group.add(bullet)
        all_sprites.add(bullet)
        base_cd = max(850, 1650 - self.wave * 70)
        self.next_shot_at = now + random.randint(base_cd, base_cd + 520)
        return True

    def update(self, dt=None):
        scale = _dt_scale(dt)
        if not self._settled:
            self._pos_y += self._speed_y * scale
            if self._pos_y >= self._target_y:
                self._pos_y = float(self._target_y)
                self._settled = True
                self._base_x = float(self.rect.x)
            self.rect.y = int(self._pos_y)
            return

        self._base_x += self._dir * self._speed_x * scale
        margin = 24
        if self._base_x <= margin:
            self._base_x = margin
            self._dir = 1
        if self._base_x + self.rect.width >= settings.WIDTH - margin:
            self._base_x = settings.WIDTH - margin - self.rect.width
            self._dir = -1
        self._phase += 0.05 * scale
        self.rect.x = int(self._base_x)
        self.rect.y = int(self._target_y + math.sin(self._phase) * 2.0)


class BossEnemy(pygame.sprite.Sprite):
    def __init__(self, wave=4):
        super().__init__()
        self.is_boss = True
        self.wave = max(1, int(wave))
        self.width = 196
        self.height = 104
        self._frames = self._build_boss_frames()
        self._frame_idx = 0
        self._anim_offset = random.randint(0, 15)
        self.image = self._frames[self._frame_idx]

        self.rect = self.image.get_rect()
        self.rect.centerx = settings.WIDTH // 2
        self.rect.y = -self.height - 20

        self.pos_x = float(self.rect.x)
        self.pos_y = float(self.rect.y)
        self.entry_speed = 1.2
        self.hover_y = 70
        self.wave_amp = 44
        self.wave_speed = 0.0024
        self.phase = 1
        self.next_attack_at = pygame.time.get_ticks() + random.randint(1100, 1600)
        self.attack_index = 0
        self.rush_until = 0
        self.rush_dir = random.choice([-1, 1])
        self.rush_speed = 5.2
        self.telegraph_until = 0
        self.telegraph_started_at = 0
        self.telegraph_duration = 0
        self.telegraph_kind = ""
        self._pending_phase = None
        self._pending_pattern = None

        self.max_health = 22 + self.wave * 6
        self.health = self.max_health
        self.score_reward = 320 + self.wave * 80

    def _build_boss_frames(self):
        return [self._draw_boss_frame(pulse) for pulse in (0, 1, 2, 1)]

    def _draw_boss_frame(self, pulse):
        surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        _glow_circle(surf, (180, 96, 255), (self.width // 2, self.height // 2), 78, layers=5, alpha=22 + pulse * 5)
        shell = [
            (14, self.height // 2),
            (44, 14),
            (self.width - 44, 14),
            (self.width - 14, self.height // 2),
            (self.width - 44, self.height - 14),
            (44, self.height - 14),
        ]
        wing_left = [(18, self.height // 2), (4, self.height // 2 + 30), (56, self.height - 10), (48, self.height // 2 + 10)]
        wing_right = [
            (self.width - 18, self.height // 2),
            (self.width - 4, self.height // 2 + 30),
            (self.width - 56, self.height - 10),
            (self.width - 48, self.height // 2 + 10),
        ]
        pygame.draw.polygon(surf, (52, 24, 96), wing_left)
        pygame.draw.polygon(surf, (52, 24, 96), wing_right)
        pygame.draw.polygon(surf, (112, 42, 186), shell)
        pygame.draw.polygon(surf, (226, 142, 255), shell, 3)
        pygame.draw.polygon(
            surf,
            (22, 18, 44),
            [
                (38, 22),
                (self.width - 38, 22),
                (self.width - 26, self.height // 2),
                (self.width - 38, self.height - 22),
                (38, self.height - 22),
                (26, self.height // 2),
            ],
        )
        pygame.draw.polygon(
            surf,
            (76, 42, 126),
            [
                (self.width // 2, 18),
                (self.width // 2 + 58, self.height // 2),
                (self.width // 2, self.height - 18),
                (self.width // 2 - 58, self.height // 2),
            ],
            2,
        )
        core_rect = pygame.Rect(self.width // 2 - 20, self.height // 2 - 13, 40, 26)
        pygame.draw.rect(surf, (255, 190, 86), core_rect, border_radius=8)
        pygame.draw.rect(surf, (255, 238, 176), core_rect.inflate(-8, -8), border_radius=5)
        core_r = 7 + pulse
        _glow_circle(surf, (255, 132, 100), (self.width // 2, self.height // 2), core_r + 9, layers=2, alpha=70)
        pygame.draw.circle(surf, (255, 150, 112), (self.width // 2, self.height // 2), core_r + 2)
        pygame.draw.circle(surf, (255, 236, 188), (self.width // 2, self.height // 2), core_r)
        for x in (30, self.width - 30):
            _glow_circle(surf, (70, 235, 255), (x, self.height // 2), 13 + pulse, layers=2, alpha=48)
            pygame.draw.circle(surf, (70, 235, 255), (x, self.height // 2), 8 + (pulse % 2))
            pygame.draw.circle(surf, (230, 255, 255), (x, self.height // 2), 3)
        for x in (24, self.width - 24):
            pygame.draw.rect(surf, (74, 50, 126), (x - 9, self.height // 2 - 8, 18, 16), border_radius=5)
            pygame.draw.rect(surf, (210, 160, 250), (x - 9, self.height // 2 - 8, 18, 16), 1, border_radius=5)
            pygame.draw.circle(surf, (255, 170, 90), (x, self.height // 2), 3 + (pulse % 2))
        engine = pygame.Rect(self.width // 2 - 60, self.height - 27, 120, 9)
        pygame.draw.rect(surf, (126, 82, 206), engine, border_radius=5)
        pygame.draw.rect(surf, (218, 172, 255), engine, 1, border_radius=5)
        for x in range(self.width // 2 - 48, self.width // 2 + 49, 24):
            pygame.draw.circle(surf, (255, 120, 120), (x, self.height - 22), 2 + pulse % 2)
        return surf

    def _phase_from_health(self):
        ratio = self.health / max(1, self.max_health)
        if ratio <= 0.34:
            return 3
        if ratio <= 0.68:
            return 2
        return 1

    def _spawn_bullet(self, bullets_group, all_sprites, x, y, speedx, speedy, color, core_color):
        b = EnemyBullet(x, y, speed=speedy, speedx=speedx, color=color, core_color=core_color)
        bullets_group.add(b)
        all_sprites.add(b)

    def _fire_fan(self, bullets_group, all_sprites, count, spread_deg, speed, color, core_color):
        fired = 0
        if count <= 1:
            self._spawn_bullet(bullets_group, all_sprites, self.rect.centerx, self.rect.bottom - 6, 0.0, speed, color, core_color)
            return 1
        step = spread_deg / max(1, count - 1)
        start = 90.0 - spread_deg / 2.0
        for i in range(count):
            ang = math.radians(start + step * i)
            vx = math.cos(ang) * speed
            vy = math.sin(ang) * speed
            x = self.rect.centerx + (i % 2) * 8 - 4
            y = self.rect.bottom - 8
            self._spawn_bullet(bullets_group, all_sprites, x, y, vx, vy, color, core_color)
            fired += 1
        return fired

    def _fire_targeted(self, bullets_group, all_sprites, player_x, count, spread_x, speed, color, core_color):
        fired = 0
        mid = (count - 1) / 2.0
        dx = player_x - self.rect.centerx
        # Keep aimed shots readable: slight player bias, no hard homing.
        base_vx = max(-0.85, min(0.85, dx / 320.0))
        base_vx += random.uniform(-0.08, 0.08)
        base_vx = max(-1.0, min(1.0, base_vx))
        for i in range(count):
            vx = base_vx + (i - mid) * spread_x
            vy = speed + min(0.45, abs(vx) * 0.15)
            muzzle_x = self.rect.centerx + (-24 if i % 2 == 0 else 24)
            self._spawn_bullet(bullets_group, all_sprites, muzzle_x, self.rect.bottom - 10, vx, vy, color, core_color)
            fired += 1
        return fired

    def _fire_rain(self, bullets_group, all_sprites, count, speed, color, core_color):
        fired = 0
        left = self.rect.left + 14
        right = self.rect.right - 14
        for _ in range(count):
            x = random.randint(left, right)
            vx = random.uniform(-1.0, 1.0)
            vy = speed + random.uniform(0.2, 1.1)
            self._spawn_bullet(bullets_group, all_sprites, x, self.rect.bottom - 8, vx, vy, color, core_color)
            fired += 1
        return fired

    def _pattern_for_attack(self, phase, attack_index):
        if phase <= 1:
            return attack_index % 2
        if phase == 2:
            return attack_index % 3
        return attack_index % 4

    def _attack_kind(self, phase, pattern):
        if phase <= 1:
            return "targeted" if pattern == 0 else "fan_small"
        if phase == 2:
            if pattern == 0:
                return "fan_mid"
            if pattern == 1:
                return "targeted"
            return "rain"
        if pattern in (0, 2):
            return "fan_wide"
        if pattern == 1:
            return "targeted"
        return "rain"

    def _telegraph_duration_ms(self, phase, kind):
        if kind != "rain":
            return 0
        base = 320 + phase * 48
        return int(base + random.randint(20, 110))

    def telegraph_remaining_ms(self, now=None):
        now = now if now is not None else pygame.time.get_ticks()
        return max(0, int(self.telegraph_until - now))

    def telegraph_progress(self, now=None):
        if self.telegraph_duration <= 0:
            return 0.0
        now = now if now is not None else pygame.time.get_ticks()
        elapsed = now - self.telegraph_started_at
        return max(0.0, min(1.0, elapsed / self.telegraph_duration))

    def _execute_attack(self, phase, pattern, now, bullets_group, all_sprites, player_x):
        fired = 0
        if phase <= 1:
            if pattern == 0:
                fired += self._fire_targeted(
                    bullets_group, all_sprites, player_x, count=2, spread_x=0.36, speed=3.5,
                    color=(255, 132, 116), core_color=(255, 226, 176)
                )
            else:
                fired += self._fire_fan(
                    bullets_group, all_sprites, count=4, spread_deg=46, speed=3.7,
                    color=(255, 122, 120), core_color=(255, 212, 170)
                )
            self.next_attack_at = now + random.randint(1360, 1750)
            return fired

        if phase == 2:
            if pattern == 0:
                fired += self._fire_fan(
                    bullets_group, all_sprites, count=5, spread_deg=62, speed=3.9,
                    color=(255, 110, 132), core_color=(255, 206, 202)
                )
            elif pattern == 1:
                fired += self._fire_targeted(
                    bullets_group, all_sprites, player_x, count=3, spread_x=0.56, speed=4.1,
                    color=(255, 142, 110), core_color=(255, 232, 178)
                )
            else:
                fired += self._fire_rain(
                    bullets_group, all_sprites, count=4, speed=3.7,
                    color=(192, 132, 255), core_color=(236, 208, 255)
                )
                if random.random() < 0.55:
                    self.rush_until = now + 420
                    self.rush_dir = -1 if player_x < self.rect.centerx else 1
            self.next_attack_at = now + random.randint(1080, 1450)
            return fired

        if pattern in (0, 2):
            fired += self._fire_fan(
                bullets_group, all_sprites, count=6, spread_deg=78, speed=4.2,
                color=(255, 96, 136), core_color=(255, 206, 224)
            )
        elif pattern == 1:
            fired += self._fire_targeted(
                bullets_group, all_sprites, player_x, count=4, spread_x=0.68, speed=4.4,
                color=(255, 150, 114), core_color=(255, 236, 184)
            )
        else:
            fired += self._fire_rain(
                bullets_group, all_sprites, count=6, speed=4.1,
                color=(196, 142, 255), core_color=(236, 208, 255)
            )
        if pattern in (1, 3):
            self.rush_until = now + 520
            self.rush_dir = -1 if player_x < self.rect.centerx else 1
        self.next_attack_at = now + random.randint(860, 1220)
        return fired

    def maybe_attack(self, now, bullets_group, all_sprites, player_x):
        phase = self._phase_from_health()
        phase_changed = None
        if phase > self.phase:
            self.phase = phase
            phase_changed = phase

        if self.telegraph_remaining_ms(now) > 0:
            return 0, phase_changed

        if self.telegraph_until and self._pending_phase is not None and self._pending_pattern is not None:
            fired = self._execute_attack(
                self._pending_phase,
                self._pending_pattern,
                now,
                bullets_group,
                all_sprites,
                player_x,
            )
            self.telegraph_until = 0
            self.telegraph_started_at = 0
            self.telegraph_duration = 0
            self.telegraph_kind = ""
            self._pending_phase = None
            self._pending_pattern = None
            self.attack_index += 1
            return fired, phase_changed

        if now < self.next_attack_at:
            return 0, phase_changed

        pattern = self._pattern_for_attack(self.phase, self.attack_index)
        kind = self._attack_kind(self.phase, pattern)
        windup_ms = self._telegraph_duration_ms(self.phase, kind)
        if windup_ms > 0:
            self.telegraph_started_at = now
            self.telegraph_duration = windup_ms
            self.telegraph_until = now + windup_ms
            self.telegraph_kind = kind
            self._pending_phase = self.phase
            self._pending_pattern = pattern
            return 0, phase_changed

        fired = self._execute_attack(self.phase, pattern, now, bullets_group, all_sprites, player_x)

        self.attack_index += 1
        return fired, phase_changed

    def update(self, dt=None):
        now = pygame.time.get_ticks()
        scale = _dt_scale(dt)
        anim_ms = max(56, 100 - (self.phase - 1) * 16)
        if self.telegraph_remaining_ms(now) > 0:
            anim_ms = max(44, anim_ms - 20)
        step = (now // anim_ms + self._anim_offset) % len(self._frames)
        if step != self._frame_idx:
            center = self.rect.center
            self._frame_idx = step
            self.image = self._frames[self._frame_idx]
            self.rect = self.image.get_rect(center=center)

        if self.pos_y < self.hover_y:
            self.pos_y += self.entry_speed * scale
        else:
            if now < self.rush_until:
                self.pos_x += self.rush_dir * self.rush_speed * scale
            else:
                amp = self.wave_amp + (self.phase - 1) * 10
                freq = self.wave_speed + (self.phase - 1) * 0.0007
                self.pos_x = (settings.WIDTH - self.width) / 2 + math.sin(now * freq) * amp
            y_amp = (2 + self.phase) + (1.8 if self.telegraph_remaining_ms(now) > 0 else 0.0)
            self.pos_y = self.hover_y + math.sin(now * 0.0021) * y_amp

        min_x = 12
        max_x = settings.WIDTH - self.width - 12
        if self.pos_x < min_x:
            self.pos_x = min_x
            self.rush_dir = 1
        if self.pos_x > max_x:
            self.pos_x = max_x
            self.rush_dir = -1
        self.rect.x = int(self.pos_x)
        self.rect.y = int(self.pos_y)


class PowerUp(pygame.sprite.Sprite):
    def __init__(self, x, y, ptype=None):
        super().__init__()
        if ptype is None:
            ptype = random.choice(['rapid', 'shield', 'double'])
        self.ptype = ptype
        self.size = 26
        self._pulse_frames = self._build_frames()
        self._frame_idx = 0
        self.image = self._pulse_frames[self._frame_idx]
        self.rect = self.image.get_rect(center=(x, y))
        self.pos_x = float(self.rect.x)
        self.speedy = 1.2
        self.pos_y = float(self.rect.y)
        self._base_x = float(self.rect.x)
        self._float_phase = random.uniform(0.0, math.tau)

    def _palette(self):
        if self.ptype == 'rapid':
            return (236, 118, 72), (255, 194, 128), (255, 244, 216)
        if self.ptype == 'shield':
            return (86, 176, 255), (156, 224, 255), (235, 248, 255)
        return (172, 116, 255), (220, 166, 255), (247, 230, 255)

    def _draw_rapid_icon(self, surf, center):
        cx, cy = center
        bolt = [
            (cx - 1, cy - 8),
            (cx + 3, cy - 8),
            (cx + 0, cy - 2),
            (cx + 5, cy - 2),
            (cx - 2, cy + 8),
            (cx + 0, cy + 2),
            (cx - 5, cy + 2),
        ]
        pygame.draw.polygon(surf, (255, 248, 224), bolt)
        pygame.draw.polygon(surf, (255, 206, 142), bolt, 1)

    def _draw_shield_icon(self, surf, center):
        cx, cy = center
        shield_shape = [
            (cx, cy - 8),
            (cx + 6, cy - 5),
            (cx + 5, cy + 2),
            (cx, cy + 8),
            (cx - 5, cy + 2),
            (cx - 6, cy - 5),
        ]
        pygame.draw.polygon(surf, (236, 250, 255), shield_shape)
        pygame.draw.polygon(surf, (172, 228, 255), shield_shape, 1)
        pygame.draw.line(surf, (146, 208, 255), (cx, cy - 6), (cx, cy + 6), 1)

    def _draw_double_icon(self, surf, center):
        cx, cy = center
        left = pygame.Rect(cx - 7, cy - 6, 4, 12)
        right = pygame.Rect(cx + 3, cy - 6, 4, 12)
        pygame.draw.rect(surf, (247, 238, 255), left, border_radius=2)
        pygame.draw.rect(surf, (247, 238, 255), right, border_radius=2)
        pygame.draw.rect(surf, (212, 178, 255), left, 1, border_radius=2)
        pygame.draw.rect(surf, (212, 178, 255), right, 1, border_radius=2)
        pygame.draw.polygon(
            surf,
            (255, 220, 255),
            [(cx - 5, cy - 9), (cx - 2, cy - 5), (cx - 8, cy - 5)],
        )
        pygame.draw.polygon(
            surf,
            (255, 220, 255),
            [(cx + 5, cy - 9), (cx + 8, cy - 5), (cx + 2, cy - 5)],
        )

    def _build_frame(self, pulse):
        s = self.size
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        cx = s // 2
        cy = s // 2
        base_rgb, accent_rgb, light_rgb = self._palette()

        core_r = s // 2 - 4
        halo_r = core_r + 2 + pulse
        pygame.draw.circle(surf, (*accent_rgb, 54 + pulse * 16), (cx, cy), halo_r + 2)
        pygame.draw.circle(surf, (*base_rgb, 230), (cx, cy), core_r + 1)
        pygame.draw.circle(surf, (*accent_rgb, 200), (cx, cy), core_r - 1, 2)
        pygame.draw.circle(surf, (*light_rgb, 86), (cx - 3, cy - 4), max(2, core_r // 2))

        if self.ptype == 'rapid':
            self._draw_rapid_icon(surf, (cx, cy))
        elif self.ptype == 'shield':
            self._draw_shield_icon(surf, (cx, cy))
        else:
            self._draw_double_icon(surf, (cx, cy))
        return surf

    def _build_frames(self):
        return [self._build_frame(pulse) for pulse in (0, 1, 2, 1)]

    def update(self, dt=None):
        now = pygame.time.get_ticks()
        step = (now // 110 + int(self._float_phase * 5)) % len(self._pulse_frames)
        if step != self._frame_idx:
            center = self.rect.center
            self._frame_idx = step
            self.image = self._pulse_frames[self._frame_idx]
            self.rect = self.image.get_rect(center=center)
            self.pos_x = float(self.rect.x)
            self.pos_y = float(self.rect.y)

        scale = _dt_scale(dt)
        self.pos_y += self.speedy * scale
        self._float_phase += 0.03 * scale
        self.pos_x = self._base_x + math.sin(self._float_phase) * 1.4
        self.rect.x = int(self.pos_x)
        self.rect.y = int(self.pos_y)
        if self.rect.top > settings.HEIGHT:
            self.kill()


class FloatingText(pygame.sprite.Sprite):
    def __init__(self, x, y, text, color=(255,255,255), lifetime=900):
        super().__init__()
        self.start = pygame.time.get_ticks()
        self.lifetime = lifetime
        self.font = pygame.font.SysFont(None, 22)
        self.image = self.font.render(text, True, color)
        self.image.set_alpha(255)
        self.rect = self.image.get_rect(center=(x, y))
        self.base_x = float(x)
        self.base_y = float(y)
        self.rise_px = random.uniform(20.0, 32.0)
        self.sway_amp = random.uniform(1.2, 3.8)
        self.sway_phase = random.uniform(0.0, math.tau)

    def update(self, dt=None):
        now = pygame.time.get_ticks()
        elapsed = now - self.start
        if elapsed > self.lifetime:
            self.kill()
            return
        prog = elapsed / self.lifetime
        eased = 1.0 - (1.0 - prog) * (1.0 - prog)
        sway = math.sin(prog * math.tau * 1.3 + self.sway_phase) * self.sway_amp
        self.rect.centerx = int(self.base_x + sway)
        self.rect.centery = int(self.base_y - self.rise_px * eased)
        alpha = int(max(0, 255 * (1.0 - prog ** 1.35)))
        self.image.set_alpha(alpha)


class Explosion(pygame.sprite.Sprite):
    def __init__(
        self,
        center,
        lifetime=300,
        max_radius=30,
        outer_rgb=(255, 200, 40),
        inner_rgb=(255, 120, 40),
    ):
        super().__init__()
        self.start = pygame.time.get_ticks()
        self.lifetime = lifetime
        self.max_radius = max_radius
        self.outer_rgb = outer_rgb
        self.inner_rgb = inner_rgb
        self.center = center
        self.image = pygame.Surface((self.max_radius * 2, self.max_radius * 2), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=center)
        self.spark_seed = random.uniform(0.0, math.tau)

    def update(self, dt=None):
        now = pygame.time.get_ticks()
        elapsed = now - self.start
        if elapsed > self.lifetime:
            self.kill()
            return
        progress = elapsed / self.lifetime
        radius = int(progress * self.max_radius)
        self.image.fill((0, 0, 0, 0))
        center = (self.max_radius, self.max_radius)
        outer_alpha = max(1, 180 - int(progress * 170))
        inner_alpha = max(1, 120 - int(progress * 120))
        ring_w = max(1, int(6 * (1 - progress)))
        pygame.draw.circle(self.image, (*self.outer_rgb, outer_alpha), center, radius, ring_w)
        pygame.draw.circle(self.image, (*self.inner_rgb, inner_alpha), center, max(1, int(radius * 0.58)))

        if progress > 0.14:
            secondary_alpha = max(0, 92 - int(progress * 110))
            if secondary_alpha > 0:
                pygame.draw.circle(
                    self.image,
                    (*self.outer_rgb, secondary_alpha),
                    center,
                    max(1, int(radius * 1.2)),
                    1,
                )

        spark_count = 4 if settings.VISUAL_QUALITY == "Performance" else 7
        spark_radius = max(2, int(radius * 0.72) + int(progress * 10))
        spark_alpha = max(0, 155 - int(progress * 160))
        if spark_alpha > 0:
            for idx in range(spark_count):
                ang = self.spark_seed + progress * 9.4 + idx * (math.tau / spark_count)
                px = center[0] + int(math.cos(ang) * spark_radius)
                py = center[1] + int(math.sin(ang) * spark_radius)
                pygame.draw.circle(
                    self.image,
                    (255, min(255, self.inner_rgb[1] + 40), min(255, self.inner_rgb[2] + 36), spark_alpha),
                    (px, py),
                    1 if idx % 2 == 0 else 2,
                )
