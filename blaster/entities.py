import pygame
import random
import math
from . import settings

_BASE_FRAME_MS = 16.6667


def _dt_scale(dt):
    if dt is None:
        return 1.0
    return max(0.0, min(3.0, float(dt) / _BASE_FRAME_MS))


class Player(pygame.sprite.Sprite):
    def __init__(self, width=60, height=68):
        super().__init__()
        self.width = width
        self.height = height
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

    def _build_ship_sprite(self, flame_level):
        surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        w = self.width
        h = self.height

        wing_left = [(w // 2 - 6, h - 34), (8, h - 18), (w // 2 - 18, h - 12)]
        wing_right = [(w // 2 + 6, h - 34), (w - 8, h - 18), (w // 2 + 18, h - 12)]
        pygame.draw.polygon(surf, (30, 74, 150), wing_left)
        pygame.draw.polygon(surf, (30, 74, 150), wing_right)
        pygame.draw.polygon(surf, (92, 156, 242), wing_left, 2)
        pygame.draw.polygon(surf, (92, 156, 242), wing_right, 2)

        hull = [(w // 2, 2), (w - 14, h - 22), (w // 2, h - 34), (14, h - 22)]
        pygame.draw.polygon(surf, (40, 128, 228), hull)
        pygame.draw.polygon(surf, (140, 208, 255), hull, 2)
        pygame.draw.polygon(
            surf,
            (24, 40, 74),
            [(w // 2, 9), (w - 22, h - 24), (w // 2, h - 36), (22, h - 24)],
        )

        pygame.draw.ellipse(surf, (148, 230, 255), (w // 2 - 8, 15, 16, 20))
        pygame.draw.ellipse(surf, (220, 252, 255), (w // 2 - 5, 18, 10, 13))

        pygame.draw.rect(surf, (255, 218, 108), (w // 2 - 2, 0, 4, 13), border_radius=2)
        pygame.draw.circle(surf, (255, 246, 182), (w // 2, 2), 3)
        pygame.draw.circle(surf, (255, 208, 120), (w // 2 - 7, 9), 2)
        pygame.draw.circle(surf, (255, 208, 120), (w // 2 + 7, 9), 2)

        left_nozzle = pygame.Rect(w // 2 - 13, h - 16, 7, 7)
        right_nozzle = pygame.Rect(w // 2 + 6, h - 16, 7, 7)
        pygame.draw.rect(surf, (38, 48, 76), left_nozzle, border_radius=2)
        pygame.draw.rect(surf, (38, 48, 76), right_nozzle, border_radius=2)
        pygame.draw.rect(surf, (110, 134, 170), left_nozzle, 1, border_radius=2)
        pygame.draw.rect(surf, (110, 134, 170), right_nozzle, 1, border_radius=2)

        flame_len = (5, 9, 13)[flame_level]
        for cx in (left_nozzle.centerx, right_nozzle.centerx):
            pygame.draw.polygon(
                surf,
                (255, 170, 70, 170),
                [(cx - 3, h - 10), (cx + 3, h - 10), (cx, min(h - 1, h - 10 + flame_len))],
            )
            pygame.draw.polygon(
                surf,
                (255, 236, 176, 210),
                [(cx - 1, h - 10), (cx + 1, h - 10), (cx, min(h - 1, h - 11 + flame_len - 2))],
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

        offsets = (-8, 8) if self.double_end and now <= self.double_end else (0,)
        for offset in offsets:
            b = Bullet(self.rect.centerx + offset, self.rect.top + 3)
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
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((6, 16), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (255, 255, 255), (2, 2, 2, 12))
        pygame.draw.rect(self.image, (120, 220, 255), (1, 0, 4, 16), 1)
        self.rect = self.image.get_rect(center=(x, y))
        self.speedy = -settings.BULLET_SPEED
        self.pos_y = float(self.rect.y)
        self.trail_points = []

    def update(self, dt=None):
        if settings.BULLET_TRAIL_LENGTH > 0:
            self.trail_points.append((self.rect.centerx, self.rect.bottom))
            if len(self.trail_points) > settings.BULLET_TRAIL_LENGTH:
                self.trail_points.pop(0)
        self.pos_y += self.speedy * _dt_scale(dt)
        self.rect.y = int(self.pos_y)
        if self.rect.bottom < 0:
            self.kill()


class EnemyBullet(pygame.sprite.Sprite):
    def __init__(self, x, y, speed=4.6, speedx=0.0, color=(255, 118, 118), core_color=(255, 214, 152)):
        super().__init__()
        self.image = pygame.Surface((6, 14), pygame.SRCALPHA)
        pygame.draw.rect(self.image, color, (1, 0, 4, 14), border_radius=2)
        pygame.draw.rect(self.image, core_color, (2, 2, 2, 8), border_radius=1)
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
        pygame.draw.circle(surf, (110, 34, 64), (c, c), s // 2)
        pygame.draw.circle(surf, (228, 78, 120), (c, c), s // 2 - 2)
        pygame.draw.circle(surf, (255, 162, 174), (c, c), s // 2 - 6, 2)
        core_r = max(3, s // 6 + pulse)
        pygame.draw.circle(surf, (255, 236, 166), (c, c), core_r)
        glow = 3 + pulse * 2
        pygame.draw.circle(surf, (255, 180, 120, 120), (c, c), min(s // 2 - 1, core_r + glow), 2)
        pygame.draw.circle(surf, (255, 255, 220), (c - s // 5, c - s // 5), max(2, s // 12))
        return surf

    def _draw_saucer_frame(self, pulse):
        w = self.size
        h = max(18, self.size // 2 + 3)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (74, 86, 154), (0, h // 4, w, h // 2 + h // 3))
        pygame.draw.ellipse(surf, (126, 154, 232), (3, h // 4 + 2, w - 6, h // 2), 2)
        dome = pygame.Rect(w // 5, 1, w - (w // 5) * 2, h // 2 + 2)
        pygame.draw.ellipse(surf, (170, 218, 255), dome)
        pygame.draw.ellipse(surf, (230, 248, 255), dome, 2)
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
        points = []
        spikes = 10
        for i in range(spikes * 2):
            ang = (math.pi * 2 / (spikes * 2)) * i - math.pi / 2
            r = r_outer if i % 2 == 0 else r_inner
            points.append((c + int(math.cos(ang) * r), c + int(math.sin(ang) * r)))
        pygame.draw.polygon(surf, (96, 26, 136), points)
        pygame.draw.polygon(surf, (214, 118, 255), points, 2)
        pygame.draw.circle(surf, (34, 16, 60), (c, c), s // 4 + 2)
        pygame.draw.circle(surf, (228, 192, 255), (c, c), max(3, s // 7 + pulse))
        return surf

    def _draw_drone_frame(self, pulse):
        s = self.size
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        nose = (s // 2, 1)
        left = (3, s - 4)
        right = (s - 3, s - 4)
        pygame.draw.polygon(surf, (28, 118, 106), (nose, right, left))
        pygame.draw.polygon(surf, (142, 236, 216), (nose, right, left), 2)
        pygame.draw.polygon(
            surf,
            (14, 42, 50),
            [(s // 2, 7), (s - 10, s - 8), (s // 2, s - 14), (10, s - 8)],
        )
        wing_glow = 2 + pulse
        pygame.draw.circle(surf, (132, 255, 230), (s // 2, s // 2 + 2), wing_glow + 2)
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
        hull = [(w // 2, 2), (w - 6, h // 2), (w // 2, h - 4), (6, h // 2)]
        pygame.draw.polygon(surf, (142, 72, 50), hull)
        pygame.draw.polygon(surf, (242, 142, 92), hull, 2)
        pygame.draw.polygon(surf, (36, 24, 22), [(w // 2, 8), (w - 16, h // 2), (w // 2, h - 10), (16, h // 2)])
        pygame.draw.circle(surf, (255, 214, 122), (w // 2, h // 2), 5)
        pygame.draw.rect(surf, (86, 44, 36), (4, h // 2 - 3, 10, 6), border_radius=2)
        pygame.draw.rect(surf, (86, 44, 36), (w - 14, h // 2 - 3, 10, 6), border_radius=2)
        pygame.draw.circle(surf, (255, 132, 94), (w // 2 - 10, h // 2), 2)
        pygame.draw.circle(surf, (255, 132, 94), (w // 2 + 10, h // 2), 2)
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
        shell = [
            (14, self.height // 2),
            (44, 14),
            (self.width - 44, 14),
            (self.width - 14, self.height // 2),
            (self.width - 44, self.height - 14),
            (44, self.height - 14),
        ]
        pygame.draw.polygon(surf, (94, 34, 168), shell)
        pygame.draw.polygon(surf, (214, 126, 255), shell, 3)
        pygame.draw.polygon(
            surf,
            (30, 24, 52),
            [
                (38, 22),
                (self.width - 38, 22),
                (self.width - 26, self.height // 2),
                (self.width - 38, self.height - 22),
                (38, self.height - 22),
                (26, self.height // 2),
            ],
        )
        pygame.draw.rect(surf, (255, 210, 90), (self.width // 2 - 16, self.height // 2 - 10, 32, 20), border_radius=6)
        core_r = 7 + pulse
        pygame.draw.circle(surf, (255, 160, 120), (self.width // 2, self.height // 2), core_r + 2)
        pygame.draw.circle(surf, (255, 236, 188), (self.width // 2, self.height // 2), core_r)
        pygame.draw.circle(surf, (70, 235, 255), (28, self.height // 2), 8 + (pulse % 2))
        pygame.draw.circle(surf, (70, 235, 255), (self.width - 28, self.height // 2), 8 + (pulse % 2))
        pygame.draw.rect(surf, (138, 90, 210), (self.width // 2 - 54, self.height - 26, 108, 8), border_radius=4)
        pygame.draw.rect(surf, (210, 160, 250), (self.width // 2 - 54, self.height - 26, 108, 8), 1, border_radius=4)
        pygame.draw.rect(surf, (74, 50, 126), (14, self.height // 2 - 8, 16, 16), border_radius=4)
        pygame.draw.rect(surf, (74, 50, 126), (self.width - 30, self.height // 2 - 8, 16, 16), border_radius=4)
        pygame.draw.circle(surf, (255, 170, 90), (22, self.height // 2), 3 + (pulse % 2))
        pygame.draw.circle(surf, (255, 170, 90), (self.width - 22, self.height // 2), 3 + (pulse % 2))
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
        self.rect = self.image.get_rect(center=(x,y))

    def update(self, dt=None):
        now = pygame.time.get_ticks()
        elapsed = now - self.start
        if elapsed > self.lifetime:
            self.kill()
            return
        self.rect.y -= 0.4 * (dt if dt else 16)
        prog = elapsed / self.lifetime
        a = max(0, 255 - int(prog*255))
        self.image.set_alpha(a)


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
        pygame.draw.circle(self.image, (*self.inner_rgb, inner_alpha), center, max(1, int(radius * 0.55)))
