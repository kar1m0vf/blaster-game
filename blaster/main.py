import os
import random
import math
from collections import deque

import pygame

from . import menu
from . import settings
from .assets import ensure_sounds, load_sounds, set_sounds_volume
from .entities import BossEnemy, Enemy, Explosion, FloatingText, Player, PowerUp, ShooterEnemy
from .storage import (
    add_highscore,
    load_user_settings,
    normalize_player_name,
    save_user_settings,
)
from .ui import clear_background_cache, draw_background, draw_text, make_stars, ui_microtext


class Game:
    def __init__(self):
        pygame.init()
        try:
            pygame.mixer.pre_init(44100, -16, 1, 1024)
            pygame.mixer.init()
        except pygame.error:
            pass

        self.master_volume = 0.6
        self.fullscreen = False
        self._load_user_preferences()
        self.screen = None
        self._apply_display_mode()
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 28)
        self.small_font = pygame.font.SysFont(None, 20)
        self.notice_font = pygame.font.SysFont(None, 15)
        self.notice_text = ui_microtext()
        self.stars = make_stars(width=settings.WIDTH, height=settings.HEIGHT)
        self.replay_duration_ms = 5000
        self.replay_fps = self._replay_fps_for_quality()
        self.replay_capture_interval_ms = max(50, 1000 // max(1, self.replay_fps))
        self.replay_buffer_size = (settings.WIDTH, settings.HEIGHT)
        self.replay_max_frames = max(1, int(self.replay_duration_ms / self.replay_capture_interval_ms) + 2)
        self.replay_frames = deque(maxlen=self.replay_max_frames)
        self.replay_last_capture_at = 0

        base_dir = os.path.dirname(__file__)
        ensure_sounds(dest_dir=base_dir)
        self.sounds = load_sounds(dest_dir=base_dir)
        set_sounds_volume(self.master_volume)

        self.joystick = None
        try:
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
        except pygame.error:
            self.joystick = None

        self.spawn_event = pygame.USEREVENT + 1
        self.powerup_event = pygame.USEREVENT + 2

        self.should_quit = False
        self.round_active = False
        self.shake_time_left = 0
        self.shake_strength = 0
        self._reset_round(start_timers=False)

    def _replay_fps_for_quality(self):
        if settings.VISUAL_QUALITY == "Performance":
            return 8
        if settings.VISUAL_QUALITY == "Balanced":
            return 10
        if settings.VISUAL_QUALITY == "Cinematic":
            return 12
        return 14

    def _reset_round(self, start_timers=True):
        self.all_sprites = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.enemy_bullets = pygame.sprite.Group()
        self.powerups = pygame.sprite.Group()
        self.floating = pygame.sprite.Group()
        self.explosions = pygame.sprite.Group()

        self.player = Player()
        self.player.speed = settings.PLAYER_SPEED
        self.all_sprites.add(self.player)

        self.score = 0
        self.lives = 3
        self.running = True
        self.round_active = False
        self.shake_time_left = 0
        self.shake_strength = 0
        self.wave = 1
        self.wave_kills = 0
        self.wave_target_kills = 0
        self.pending_wave_advance = False
        self.current_spawn_time = settings.ENEMY_SPAWN_TIME
        self.current_max_enemies = settings.MAX_ENEMIES
        self.boss_active = False
        self.boss_spawned_for_wave = False
        self.wave_locked_by_shooters = False
        self.player_bullet_damage = 1
        self.upgrade_pick_count = 0
        self.combo_chain = 0
        self.combo_multiplier = 1.0
        self.combo_timeout_ms = 2800
        self.combo_last_kill_at = 0
        self.replay_frames.clear()
        self.replay_last_capture_at = 0

        if start_timers:
            pygame.time.set_timer(self.powerup_event, 9000)
            self._start_wave(announce=True, start_timers=True)
        else:
            self._stop_round_timers()
            self._start_wave(announce=False, start_timers=False)

    def _load_user_preferences(self):
        prefs = load_user_settings()
        settings.set_difficulty(prefs.get("difficulty", settings.DIFFICULTY))
        settings.set_visual_quality(prefs.get("visual_quality", settings.VISUAL_QUALITY))
        settings.set_fps_cap(prefs.get("fps_cap", settings.FPS))
        settings.set_show_fps(prefs.get("show_fps", settings.SHOW_FPS))
        self.master_volume = float(prefs.get("master_volume", 0.6))
        self.fullscreen = bool(prefs.get("fullscreen", False))
        clear_background_cache()

    def _save_user_preferences(self):
        save_user_settings(
            {
                "difficulty": settings.DIFFICULTY,
                "visual_quality": settings.VISUAL_QUALITY,
                "master_volume": self.master_volume,
                "fullscreen": self.fullscreen,
                "fps_cap": settings.FPS,
                "show_fps": settings.SHOW_FPS,
            }
        )

    def _apply_display_mode(self):
        scaled = getattr(pygame, "SCALED", 0)
        if self.fullscreen:
            flags = scaled | pygame.FULLSCREEN
            fallback_flags = pygame.FULLSCREEN
        else:
            flags = scaled | pygame.RESIZABLE
            fallback_flags = pygame.RESIZABLE
        try:
            self.screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), flags)
        except pygame.error:
            self.screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), fallback_flags)
        pygame.display.set_caption("Blaster - polished")

    def _toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self._apply_display_mode()
        self._handle_window_change()
        self._save_user_preferences()

    def _handle_window_change(self):
        clear_background_cache()
        self.stars = make_stars(width=settings.WIDTH, height=settings.HEIGHT)

    def _set_spawn_timer(self, interval_ms):
        pygame.time.set_timer(self.spawn_event, max(0, int(interval_ms)))

    def _stop_round_timers(self):
        self._set_spawn_timer(0)
        pygame.time.set_timer(self.powerup_event, 0)

    def _recompute_wave_params(self):
        wave_idx = max(0, self.wave - 1)
        self.wave_target_kills = 8 + self.wave * 4
        self.current_spawn_time = max(260, int(settings.ENEMY_SPAWN_TIME * (0.94 ** wave_idx)))
        self.current_max_enemies = min(settings.MAX_ENEMIES + wave_idx // 2, settings.MAX_ENEMIES + 10)

    def _is_boss_wave(self):
        return self.wave > 0 and self.wave % 4 == 0

    def _shooter_enemy_count_for_wave(self):
        return min(6, max(0, self.wave - 1))

    def _alive_shooters(self):
        return [e for e in self.enemies if getattr(e, "is_shooter", False)]

    def _spawn_wave_shooters(self):
        count = self._shooter_enemy_count_for_wave()
        if count <= 0:
            self.wave_locked_by_shooters = False
            return
        self.wave_locked_by_shooters = True
        spacing = settings.WIDTH / (count + 1)
        for i in range(count):
            start_x = int((i + 1) * spacing)
            target_y = 68 + (i % 2) * 34
            shooter = ShooterEnemy(wave=self.wave, start_x=start_x, target_y=target_y)
            self.enemies.add(shooter)
            self.all_sprites.add(shooter)

    def _unlock_wave_if_ready(self):
        if not self.wave_locked_by_shooters:
            return
        if self._alive_shooters():
            return
        self.wave_locked_by_shooters = False
        self._set_spawn_timer(self.current_spawn_time)
        ft = FloatingText(
            settings.WIDTH // 2,
            120,
            "Enemy wave incoming!",
            color=(255, 216, 146),
            lifetime=1100,
        )
        self.floating.add(ft)
        self.all_sprites.add(ft)

    def _start_wave(self, announce=True, start_timers=True):
        self.wave_kills = 0
        self.pending_wave_advance = False
        self.boss_active = False
        self.boss_spawned_for_wave = False
        self.wave_locked_by_shooters = False
        self._recompute_wave_params()

        if announce:
            title = f"Boss Wave {self.wave}" if self._is_boss_wave() else f"Wave {self.wave}"
            color = (255, 170, 120) if self._is_boss_wave() else (160, 230, 255)
            ft = FloatingText(settings.WIDTH // 2, 92, title, color=color, lifetime=1300)
            self.floating.add(ft)
            self.all_sprites.add(ft)

        if not start_timers:
            return
        if self._is_boss_wave():
            self._set_spawn_timer(0)
            self._spawn_boss()
        else:
            self._set_spawn_timer(0)
            if self.wave >= 2:
                self._spawn_wave_shooters()
                if not self.wave_locked_by_shooters:
                    self._set_spawn_timer(self.current_spawn_time)
            else:
                self._set_spawn_timer(self.current_spawn_time)

    def _advance_wave(self):
        self.wave += 1
        self._start_wave(announce=True, start_timers=self.round_active)

    def _spawn_boss(self):
        if self.boss_spawned_for_wave:
            return
        boss = BossEnemy(wave=self.wave)
        self.enemies.add(boss)
        self.all_sprites.add(boss)
        self.boss_active = True
        self.boss_spawned_for_wave = True
        self._start_shake(3, duration_ms=180)

    def _spawn_boss_reinforcements(self, boss, phase):
        if boss is None:
            return 0
        max_allowed = settings.MAX_ENEMIES + 8
        slots = max(0, max_allowed - len(self.enemies))
        if slots <= 0:
            return 0

        count = min(slots, 1 + (1 if phase >= 3 else 0))
        spawn_types = ["orb", "drone"]
        if self.wave >= 6:
            spawn_types.append("saucer")
        if phase >= 3:
            spawn_types.append("spiky")

        spread = max(80, boss.rect.width // 2 + 24)
        created = 0
        for _ in range(count):
            enemy = Enemy(etype=random.choice(spawn_types))
            spawn_x = boss.rect.centerx + random.randint(-spread, spread)
            enemy.rect.x = max(0, min(settings.WIDTH - enemy.rect.width, spawn_x - enemy.rect.width // 2))
            enemy.rect.y = -enemy.rect.height - random.randint(6, 36)
            enemy.speedy *= 1.08 + phase * 0.08 + min(0.14, self.wave * 0.015)
            if phase >= 3 and random.random() < 0.2:
                enemy.health += 1
                enemy.max_health = enemy.health
                enemy.score_reward += 8
            self.enemies.add(enemy)
            self.all_sprites.add(enemy)
            created += 1
        return created

    def _boss_from_enemies(self):
        for enemy in self.enemies:
            if getattr(enemy, "is_boss", False):
                return enemy
        return None

    def _handle_enemy_defeat(self, enemy, allow_powerup_drop=True, combo_eligible=True):
        reward_base = int(getattr(enemy, "score_reward", 10 + int(getattr(enemy, "size", 0))))
        now = pygame.time.get_ticks()
        if combo_eligible:
            self._register_combo_kill(now)
            reward = int(reward_base * self.combo_multiplier)
        else:
            reward = reward_base
        self.score += max(1, reward)
        is_boss = bool(getattr(enemy, "is_boss", False))
        is_shooter = bool(getattr(enemy, "is_shooter", False))
        is_elite = bool(getattr(enemy, "is_elite", False))
        if is_boss:
            expl = Explosion(
                enemy.rect.center,
                lifetime=380,
                max_radius=36,
                outer_rgb=(255, 200, 40),
                inner_rgb=(255, 120, 40),
            )
        elif is_shooter:
            expl = Explosion(
                enemy.rect.center,
                lifetime=330,
                max_radius=34,
                outer_rgb=(110, 190, 255),
                inner_rgb=(180, 120, 255),
            )
        elif is_elite:
            expl = Explosion(
                enemy.rect.center,
                lifetime=350,
                max_radius=34,
                outer_rgb=(255, 190, 92),
                inner_rgb=(255, 234, 154),
            )
        else:
            expl = Explosion(enemy.rect.center, lifetime=300)
        self.explosions.add(expl)
        self.all_sprites.add(expl)
        self._play_sound("explosion")

        if is_boss:
            self.boss_active = False
            self.pending_wave_advance = True
            self.wave_kills = self.wave_target_kills
            self._start_shake(6, duration_ms=180)
            ft = FloatingText(settings.WIDTH // 2, 120, "Boss Defeated!", color=(255, 205, 135), lifetime=1300)
            self.floating.add(ft)
            self.all_sprites.add(ft)
        else:
            self._start_shake(2, duration_ms=70)
            if is_shooter:
                ft = FloatingText(enemy.rect.centerx, enemy.rect.centery, "GUNNER DOWN", color=(180, 230, 255), lifetime=850)
                self.floating.add(ft)
                self.all_sprites.add(ft)
                self._unlock_wave_if_ready()
            else:
                self.wave_kills += 1
                if is_elite:
                    role = getattr(enemy, "elite_role", None)
                    if role == "raider":
                        down_text = "RAIDER DOWN"
                        down_color = (255, 210, 164)
                    elif role == "bulwark":
                        down_text = "BULWARK DOWN"
                        down_color = (170, 234, 255)
                    elif role == "sniper":
                        down_text = "SNIPER DOWN"
                        down_color = (230, 196, 255)
                    else:
                        down_text = "ELITE DOWN"
                        down_color = (255, 224, 154)
                    ft = FloatingText(
                        enemy.rect.centerx,
                        enemy.rect.centery,
                        down_text,
                        color=down_color,
                        lifetime=900,
                    )
                    self.floating.add(ft)
                    self.all_sprites.add(ft)
                if allow_powerup_drop and random.random() < 0.12:
                    pu = PowerUp(enemy.rect.centerx, enemy.rect.centery)
                    self.powerups.add(pu)
                    self.all_sprites.add(pu)
                if self.wave_kills >= self.wave_target_kills and not self.pending_wave_advance:
                    self.pending_wave_advance = True
                    self._set_spawn_timer(0)
                    self._reset_combo(show_text=False)
                    ft = FloatingText(settings.WIDTH // 2, 96, "Wave complete! Clear remaining enemies.", color=(170, 225, 255), lifetime=1300)
                    self.floating.add(ft)
                    self.all_sprites.add(ft)
        enemy.kill()

    def _apply_difficulty(self, level):
        if settings.set_difficulty(level):
            self.player.speed = settings.PLAYER_SPEED
            self._recompute_wave_params()
            if self.round_active and not self.boss_active:
                if self.pending_wave_advance or self.wave_locked_by_shooters:
                    self._set_spawn_timer(0)
                else:
                    self._set_spawn_timer(self.current_spawn_time)
            self._save_user_preferences()

    def _apply_visual_quality(self, level):
        if settings.set_visual_quality(level):
            clear_background_cache()
            self.stars = make_stars(width=settings.WIDTH, height=settings.HEIGHT)
            self.replay_fps = self._replay_fps_for_quality()
            self.replay_capture_interval_ms = max(50, 1000 // max(1, self.replay_fps))
            self.replay_buffer_size = (settings.WIDTH, settings.HEIGHT)
            self.replay_max_frames = max(1, int(self.replay_duration_ms / self.replay_capture_interval_ms) + 2)
            kept = list(self.replay_frames)[-self.replay_max_frames :]
            self.replay_frames = deque(kept, maxlen=self.replay_max_frames)
            self._save_user_preferences()
            return True
        return False

    def _apply_fps_cap(self, cap):
        if settings.set_fps_cap(cap):
            self._save_user_preferences()
            return True
        return False

    def _toggle_show_fps(self):
        settings.set_show_fps(not settings.SHOW_FPS)
        self._save_user_preferences()

    def _reset_preferences_to_defaults(self):
        settings.set_difficulty("Normal")
        settings.set_visual_quality("Balanced")
        settings.set_fps_cap(60)
        settings.set_show_fps(True)
        self.master_volume = 0.6
        set_sounds_volume(self.master_volume)
        if self.fullscreen:
            self.fullscreen = False
            self._apply_display_mode()
        self._handle_window_change()
        self.replay_fps = self._replay_fps_for_quality()
        self.replay_capture_interval_ms = max(50, 1000 // max(1, self.replay_fps))
        self.replay_max_frames = max(1, int(self.replay_duration_ms / self.replay_capture_interval_ms) + 2)
        kept = list(self.replay_frames)[-self.replay_max_frames :]
        self.replay_frames = deque(kept, maxlen=self.replay_max_frames)
        if hasattr(self, "player") and self.player:
            self.player.speed = settings.PLAYER_SPEED
        self._save_user_preferences()

    def _start_shake(self, strength, duration_ms=120):
        if not settings.ENABLE_SCREEN_SHAKE:
            return
        self.shake_strength = max(self.shake_strength, int(strength))
        self.shake_time_left = max(self.shake_time_left, int(duration_ms))

    def _consume_camera_offset(self, dt):
        if not settings.ENABLE_SCREEN_SHAKE or self.shake_time_left <= 0 or self.shake_strength <= 0:
            return 0, 0
        self.shake_time_left = max(0, self.shake_time_left - dt)
        max_offset = max(1, self.shake_strength)
        return (
            random.randint(-max_offset, max_offset),
            random.randint(-max_offset, max_offset),
        )

    def _play_sound(self, key):
        sound = self.sounds.get(key)
        if sound:
            try:
                sound.play()
            except pygame.error:
                pass

    def _combo_multiplier_for_chain(self, chain):
        # Every 3 kills increases multiplier by 0.2, capped at x2.2.
        steps = min(6, max(0, chain - 1) // 3)
        return 1.0 + steps * 0.2

    def _reset_combo(self, show_text=False):
        if self.combo_chain <= 0:
            self.combo_chain = 0
            self.combo_multiplier = 1.0
            self.combo_last_kill_at = 0
            return

        prev_mult = self.combo_multiplier
        self.combo_chain = 0
        self.combo_multiplier = 1.0
        self.combo_last_kill_at = 0
        if show_text and prev_mult > 1.0:
            ft = FloatingText(
                settings.WIDTH // 2,
                176,
                "Combo lost",
                color=(255, 170, 154),
                lifetime=900,
            )
            self.floating.add(ft)
            self.all_sprites.add(ft)

    def _register_combo_kill(self, now):
        if self.combo_last_kill_at and now - self.combo_last_kill_at > self.combo_timeout_ms:
            self.combo_chain = 0
            self.combo_multiplier = 1.0
        self.combo_chain += 1
        old_mult = self.combo_multiplier
        self.combo_multiplier = self._combo_multiplier_for_chain(self.combo_chain)
        self.combo_last_kill_at = now
        if self.combo_multiplier > old_mult:
            ft = FloatingText(
                settings.WIDTH // 2,
                148,
                f"Combo x{self.combo_multiplier:.1f}",
                color=(255, 228, 150),
                lifetime=880,
            )
            self.floating.add(ft)
            self.all_sprites.add(ft)

    def _update_combo_timeout(self, now):
        if self.combo_chain <= 0 or self.combo_last_kill_at <= 0:
            return
        if now - self.combo_last_kill_at > self.combo_timeout_ms:
            self._reset_combo(show_text=True)

    def _build_upgrade_pool(self):
        pool = []
        if self.player._base_shoot_cooldown > 100:
            pool.append(
                {
                    "id": "rapid_loader",
                    "title": "Rapid Loader",
                    "desc": "-20ms shot cooldown",
                }
            )
        if self.player.speed < 9.0:
            pool.append(
                {
                    "id": "engine_overclock",
                    "title": "Engine Overclock",
                    "desc": "+0.6 move speed",
                }
            )
        if self.player_bullet_damage < 4:
            pool.append(
                {
                    "id": "piercing_rounds",
                    "title": "Piercing Rounds",
                    "desc": "+1 bullet damage",
                }
            )
        if self.lives < 8:
            pool.append(
                {
                    "id": "hull_patch",
                    "title": "Hull Patch",
                    "desc": "+1 life",
                }
            )
        pool.append(
            {
                "id": "shield_pulse",
                "title": "Shield Pulse",
                "desc": "Instant shield (4.5s)",
            }
        )
        pool.append(
            {
                "id": "bounty_protocol",
                "title": "Bounty Protocol",
                "desc": f"+{180 + self.wave * 15} score",
            }
        )
        return pool

    def _roll_upgrade_choices(self):
        pool = self._build_upgrade_pool()
        if len(pool) <= 3:
            return pool
        return random.sample(pool, 3)

    def _apply_upgrade_choice(self, choice):
        cid = choice.get("id")
        if cid == "rapid_loader":
            self.player._base_shoot_cooldown = max(100, self.player._base_shoot_cooldown - 20)
            if not self.player.rapid_end:
                self.player.shoot_cooldown = self.player._base_shoot_cooldown
        elif cid == "engine_overclock":
            self.player.speed = min(9.0, self.player.speed + 0.6)
        elif cid == "piercing_rounds":
            self.player_bullet_damage = min(4, self.player_bullet_damage + 1)
        elif cid == "hull_patch":
            self.lives = min(8, self.lives + 1)
        elif cid == "shield_pulse":
            self.player.apply_powerup("shield", duration_ms=4500)
        elif cid == "bounty_protocol":
            self.score += 180 + self.wave * 15

        self.upgrade_pick_count += 1
        ft = FloatingText(
            settings.WIDTH // 2,
            156,
            f"Upgrade: {choice.get('title', 'Applied')}",
            color=(200, 236, 255),
            lifetime=1100,
        )
        self.floating.add(ft)
        self.all_sprites.add(ft)
        self._play_sound("hit")

    def _upgrade_selection_screen(self):
        choices = self._roll_upgrade_choices()
        selected = 0
        card_w = 220
        card_h = 156
        gap = 18
        total_w = card_w * 3 + gap * 2
        start_x = (settings.WIDTH - total_w) // 2

        while True:
            dt = self.clock.tick(settings.FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        selected = (selected - 1) % len(choices)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        selected = (selected + 1) % len(choices)
                    elif event.key in (pygame.K_1, pygame.K_KP1) and len(choices) >= 1:
                        self._apply_upgrade_choice(choices[0])
                        return "selected"
                    elif event.key in (pygame.K_2, pygame.K_KP2) and len(choices) >= 2:
                        self._apply_upgrade_choice(choices[1])
                        return "selected"
                    elif event.key in (pygame.K_3, pygame.K_KP3) and len(choices) >= 3:
                        self._apply_upgrade_choice(choices[2])
                        return "selected"
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._apply_upgrade_choice(choices[selected])
                        return "selected"
                    elif event.key == pygame.K_ESCAPE:
                        self._apply_upgrade_choice(choices[selected])
                        return "selected"

            draw_background(self.screen, self.stars, dt)
            overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
            overlay.fill((8, 12, 26, 188))
            self.screen.blit(overlay, (0, 0))

            title = self.font.render("Choose Upgrade (1 of 3)", True, (236, 244, 255))
            self.screen.blit(title, (settings.WIDTH // 2 - title.get_width() // 2, 64))
            stats = self.small_font.render(
                f"Lives: {self.lives}   Speed: {self.player.speed:.1f}   Damage: x{self.player_bullet_damage}   Base cooldown: {self.player._base_shoot_cooldown}ms",
                True,
                (184, 212, 246),
            )
            self.screen.blit(stats, (settings.WIDTH // 2 - stats.get_width() // 2, 96))

            for idx, choice in enumerate(choices):
                x = start_x + idx * (card_w + gap)
                y = 174
                rect = pygame.Rect(x, y, card_w, card_h)
                active = idx == selected
                base_col = (28, 40, 72, 230) if active else (18, 28, 52, 220)
                border_col = (152, 210, 255) if active else (86, 132, 205)
                card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
                card.fill(base_col)
                pygame.draw.rect(card, border_col, card.get_rect(), 2, border_radius=10)
                key_text = self.small_font.render(f"[{idx + 1}]", True, (226, 240, 255))
                title_text = self.font.render(choice["title"], True, (238, 246, 255))
                desc_text = self.small_font.render(choice["desc"], True, (192, 220, 252))
                card.blit(key_text, (10, 10))
                card.blit(title_text, (10, 46))
                card.blit(desc_text, (10, 90))
                self.screen.blit(card, rect.topleft)

            hint = self.small_font.render(
                "Use A/D or arrows. Enter/Space to confirm.",
                True,
                (172, 205, 242),
            )
            self.screen.blit(hint, (settings.WIDTH // 2 - hint.get_width() // 2, settings.HEIGHT - 70))
            pygame.display.flip()

    def _capture_replay_frame(self, now):
        if now - self.replay_last_capture_at < self.replay_capture_interval_ms:
            return
        try:
            if self.replay_buffer_size == (settings.WIDTH, settings.HEIGHT):
                frame = self.screen.copy()
            else:
                frame = pygame.transform.smoothscale(self.screen, self.replay_buffer_size)
        except pygame.error:
            return
        self.replay_frames.append(frame)
        self.replay_last_capture_at = now

    def death_replay_screen(self):
        if not self.replay_frames:
            return "done"

        frames = list(self.replay_frames)
        frame_ms = max(1, int(1000 / max(1, self.replay_fps)))
        idx = 0
        last_step_at = pygame.time.get_ticks()
        skip_rect = pygame.Rect(settings.WIDTH - 116, 14, 96, 34)

        while idx < len(frames):
            self.clock.tick(settings.FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_ESCAPE):
                    return "skip"
                if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
                    if skip_rect.collidepoint(event.pos):
                        return "skip"

            now = pygame.time.get_ticks()
            elapsed = now - last_step_at
            if elapsed >= frame_ms:
                idx += max(1, elapsed // frame_ms)
                last_step_at = now
                if idx >= len(frames):
                    break

            current = frames[idx]
            if current.get_size() == (settings.WIDTH, settings.HEIGHT):
                frame = current
            else:
                frame = pygame.transform.smoothscale(current, (settings.WIDTH, settings.HEIGHT))
            self.screen.blit(frame, (0, 0))

            top = pygame.Surface((settings.WIDTH, 64), pygame.SRCALPHA)
            top.fill((10, 16, 32, 165))
            pygame.draw.rect(top, (120, 168, 240, 110), top.get_rect(), 1, border_radius=6)
            self.screen.blit(top, (0, 0))
            draw_text(self.screen, self.font, "Death Replay (5s)", 14, 12, (232, 244, 255))
            draw_text(
                self.screen,
                self.small_font,
                "Space / Esc to skip",
                14,
                38,
                (182, 212, 245),
            )
            draw_text(
                self.screen,
                self.small_font,
                f"{min(idx + 1, len(frames))}/{len(frames)}",
                settings.WIDTH // 2 - 20,
                38,
                (182, 212, 245),
            )

            pygame.draw.rect(self.screen, (22, 34, 62), skip_rect, border_radius=7)
            pygame.draw.rect(self.screen, (130, 176, 255), skip_rect, 1, border_radius=7)
            skip_label = self.font.render("Skip", True, (230, 240, 255))
            self.screen.blit(
                skip_label,
                (
                    skip_rect.centerx - skip_label.get_width() // 2,
                    skip_rect.centery - skip_label.get_height() // 2,
                ),
            )
            pygame.display.flip()

        return "done"

    def _play_player_death_animation(self, duration_ms=760):
        started = pygame.time.get_ticks()
        original_alpha = self.player.image.get_alpha()
        self.player.image.set_alpha(0)
        while pygame.time.get_ticks() - started < duration_ms:
            dt = self.clock.tick(settings.FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.player.image.set_alpha(original_alpha if original_alpha is not None else 255)
                    return "quit"

            self.explosions.update(dt)
            self.floating.update(dt)
            draw_background(self.screen, self.stars, dt)
            cam_x, cam_y = self._consume_camera_offset(dt)
            for sprite in tuple(self.all_sprites):
                if sprite is self.player:
                    continue
                self.screen.blit(sprite.image, sprite.rect.move(cam_x, cam_y))

            pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.018)
            msg = self.font.render("Ship Destroyed", True, (255, 196, 168))
            msg.set_alpha(int(180 + 75 * pulse))
            self.screen.blit(msg, (settings.WIDTH // 2 - msg.get_width() // 2, settings.HEIGHT // 2 + 38))
            pygame.display.flip()

        self.player.image.set_alpha(original_alpha if original_alpha is not None else 255)
        return "done"

    def _finish_game_over_with_animation(self):
        self._capture_replay_frame(pygame.time.get_ticks())
        self._stop_round_timers()
        self._play_sound("gameover")
        animation_result = self._play_player_death_animation()
        if animation_result == "quit":
            return self._finish_round("quit")
        return self._finish_round("game_over")

    def spawn_enemy(self):
        if self.wave_locked_by_shooters:
            return
        if self._is_boss_wave():
            if not self.boss_spawned_for_wave:
                self._spawn_boss()
            return
        if len(self.enemies) >= self.current_max_enemies:
            return

        pool = ["orb", "drone"]
        if self.wave >= 2:
            pool.append("saucer")
        if self.wave >= 3:
            pool.append("spiky")
        enemy = Enemy(etype=random.choice(pool))
        speed_boost = 1.0 + min(0.45, 0.05 * (self.wave - 1))
        enemy.speedy *= speed_boost
        if self.wave >= 3:
            elite_chance = min(0.18, 0.045 + (self.wave - 3) * 0.012)
            if random.random() < elite_chance:
                role_pool = ["raider", "bulwark"]
                role_weights = [0.46, 0.36]
                if self.wave >= 5:
                    role_pool.append("sniper")
                    role_weights.append(0.18)
                elite_role = random.choices(role_pool, weights=role_weights, k=1)[0]
                enemy.promote_elite(self.wave, role=elite_role)
        if self.wave >= 5 and random.random() < 0.15:
            enemy.health += 1
            enemy.max_health = enemy.health
            enemy.score_reward += 8
        self.enemies.add(enemy)
        self.all_sprites.add(enemy)

    def _finish_round(self, outcome):
        self.running = False
        self.round_active = False
        self._stop_round_timers()
        return outcome

    def run(self):
        while not self.should_quit:
            action, _ = menu.title_menu(self.screen, self.clock, self.font, joystick=self.joystick)
            if action == "quit":
                self.should_quit = True
                break
            if action == "high_scores":
                menu.show_highscores(self.screen, self.clock, self.font)
                continue
            if action == "options":
                if self.options_menu() == "quit":
                    self.should_quit = True
                continue
            if action != "start_game":
                continue

            while not self.should_quit:
                self._reset_round()
                outcome = self.gameplay_loop()

                if outcome == "restart":
                    continue
                if outcome == "game_over":
                    replay_result = self.death_replay_screen()
                    if replay_result == "quit":
                        self.should_quit = True
                        break
                    if self.prompt_and_save_score() == "quit":
                        self.should_quit = True
                        break
                    if self.game_over_screen() == "quit":
                        self.should_quit = True
                    break
                if outcome == "menu":
                    break
                if outcome == "quit":
                    self.should_quit = True
                    break
                break

        self._stop_round_timers()
        self._save_user_preferences()
        pygame.quit()

    def gameplay_loop(self):
        self.round_active = True
        while self.running:
            dt = self.clock.tick(settings.FPS)
            now = pygame.time.get_ticks()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return self._finish_round("quit")
                if event.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                    self._handle_window_change()
                    continue
                if event.type == self.spawn_event:
                    self.spawn_enemy()
                elif event.type == self.powerup_event:
                    if random.random() < 0.9:
                        x = random.randint(40, settings.WIDTH - 40)
                        p = PowerUp(x, -10)
                        self.powerups.add(p)
                        self.all_sprites.add(p)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F11:
                        self._toggle_fullscreen()
                        continue
                    if event.key == pygame.K_F3:
                        self._toggle_show_fps()
                        continue
                    if event.key in (pygame.K_p, pygame.K_ESCAPE):
                        res = menu.pause_menu(self.screen, self.clock, self.font)
                        if res == "restart":
                            return self._finish_round("restart")
                        if res == "quit_to_menu":
                            return self._finish_round("menu")
                        if res == "quit":
                            return self._finish_round("quit")
                    elif event.key == pygame.K_1:
                        self._apply_difficulty("Easy")
                    elif event.key == pygame.K_2:
                        self._apply_difficulty("Normal")
                    elif event.key == pygame.K_3:
                        self._apply_difficulty("Hard")
                elif event.type == pygame.JOYBUTTONDOWN and hasattr(event, "button"):
                    if event.button in (7, 9):
                        res = menu.pause_menu(self.screen, self.clock, self.font)
                        if res == "restart":
                            return self._finish_round("restart")
                        if res == "quit_to_menu":
                            return self._finish_round("menu")
                        if res == "quit":
                            return self._finish_round("quit")

            keys = pygame.key.get_pressed()
            if keys[pygame.K_SPACE]:
                fired = self.player.shoot(now, self.bullets, self.all_sprites)
                if fired:
                    self._play_sound("shot")

            self.player.update(dt, keys)
            for sprite in tuple(self.all_sprites):
                if sprite is self.player:
                    continue
                sprite.update(dt)

            for enemy in tuple(self.enemies):
                if getattr(enemy, "is_boss", False):
                    fired, phase_changed = enemy.maybe_attack(
                        now,
                        self.enemy_bullets,
                        self.all_sprites,
                        self.player.rect.centerx,
                    )
                    if fired:
                        self._play_sound("enemy_shot")
                    if phase_changed:
                        self._start_shake(4 + phase_changed, duration_ms=170)
                        ft = FloatingText(
                            settings.WIDTH // 2,
                            118,
                            f"BOSS PHASE {phase_changed}",
                            color=(255, 165, 135),
                            lifetime=1200,
                        )
                        self.floating.add(ft)
                        self.all_sprites.add(ft)
                        adds = self._spawn_boss_reinforcements(enemy, phase_changed)
                        if adds:
                            add_text = FloatingText(
                                settings.WIDTH // 2,
                                144,
                                f"+{adds} reinforcements",
                                color=(188, 228, 255),
                                lifetime=950,
                            )
                            self.floating.add(add_text)
                            self.all_sprites.add(add_text)
                elif getattr(enemy, "is_shooter", False):
                    if enemy.maybe_shoot(now, self.enemy_bullets, self.all_sprites):
                        self._play_sound("enemy_shot")
                elif getattr(enemy, "is_sniper", False):
                    if enemy.maybe_shoot(now, self.enemy_bullets, self.all_sprites, self.player.rect.centerx):
                        self._play_sound("enemy_shot")

            self._unlock_wave_if_ready()

            hits = pygame.sprite.groupcollide(self.enemies, self.bullets, False, True)
            for enemy, hit_bullets in hits.items():
                incoming = len(hit_bullets) * self.player_bullet_damage
                blocked = False
                if hasattr(enemy, "absorb_player_damage"):
                    _effective, blocked = enemy.absorb_player_damage(incoming, now=now)
                else:
                    enemy.health -= incoming
                if blocked:
                    ft = FloatingText(
                        enemy.rect.centerx,
                        enemy.rect.centery - 10,
                        "ARMOR",
                        color=(178, 234, 255),
                        lifetime=460,
                    )
                    self.floating.add(ft)
                    self.all_sprites.add(ft)
                if enemy.health <= 0:
                    self._handle_enemy_defeat(enemy, allow_powerup_drop=True)

            hits2 = pygame.sprite.spritecollide(self.player, self.enemies, False, pygame.sprite.collide_rect)
            if hits2:
                took_damage = False
                if self.player.shield:
                    for enemy in hits2:
                        if getattr(enemy, "is_boss", False):
                            enemy.health -= 3
                            if enemy.health <= 0:
                                self._handle_enemy_defeat(enemy, allow_powerup_drop=False)
                            else:
                                self._start_shake(3, duration_ms=90)
                        else:
                            self._handle_enemy_defeat(enemy, allow_powerup_drop=False)
                    ft = FloatingText(self.player.rect.centerx, self.player.rect.top, "BLOCK!", (120, 220, 255))
                    self.floating.add(ft)
                    self.all_sprites.add(ft)
                    self._play_sound("hit")
                    self._start_shake(2, duration_ms=80)
                else:
                    for enemy in hits2:
                        if not getattr(enemy, "is_boss", False):
                            enemy.kill()
                        took_damage = True
                    if took_damage:
                        self._reset_combo(show_text=True)
                        self.lives -= 1
                        expl = Explosion(self.player.rect.center, lifetime=500)
                        self.explosions.add(expl)
                        self.all_sprites.add(expl)
                        self._play_sound("hit")
                        self._start_shake(4, duration_ms=140)
                        if self.lives <= 0:
                            return self._finish_game_over_with_animation()

            if self.pending_wave_advance and len(self.enemies) == 0:
                upg_result = self._upgrade_selection_screen()
                if upg_result == "quit":
                    return self._finish_round("quit")
                self._advance_wave()
            self._update_combo_timeout(now)

            powerup_hits = pygame.sprite.spritecollide(self.player, self.powerups, True)
            for pu in powerup_hits:
                self.player.apply_powerup(pu.ptype)
                ft = FloatingText(
                    self.player.rect.centerx,
                    self.player.rect.top,
                    f"{pu.ptype.upper()}!",
                    (255, 220, 120),
                )
                self.floating.add(ft)
                self.all_sprites.add(ft)
                self._play_sound("hit")

            enemy_bullet_hits = pygame.sprite.spritecollide(self.player, self.enemy_bullets, True)
            if enemy_bullet_hits:
                if self.player.shield:
                    ft = FloatingText(self.player.rect.centerx, self.player.rect.top, "DEFLECT", (170, 235, 255), lifetime=700)
                    self.floating.add(ft)
                    self.all_sprites.add(ft)
                    self._start_shake(1, duration_ms=70)
                else:
                    self._reset_combo(show_text=True)
                    self.lives -= 1
                    expl = Explosion(self.player.rect.center, lifetime=420)
                    self.explosions.add(expl)
                    self.all_sprites.add(expl)
                    self._play_sound("hit")
                    self._start_shake(3, duration_ms=110)
                    if self.lives <= 0:
                        return self._finish_game_over_with_animation()

            draw_background(self.screen, self.stars, dt)
            cam_x, cam_y = self._consume_camera_offset(dt)

            if settings.BULLET_TRAIL_LENGTH > 0:
                for bullet in self.bullets:
                    points = bullet.trail_points + [(bullet.rect.centerx, bullet.rect.bottom)]
                    if len(points) < 2:
                        continue
                    if settings.ENABLE_STAR_GLOW and settings.BULLET_TRAIL_LENGTH >= 4:
                        pygame.draw.circle(
                            self.screen,
                            (170, 225, 255),
                            (bullet.rect.centerx + cam_x, bullet.rect.bottom + cam_y),
                            3,
                            1,
                        )
                    for i in range(1, len(points)):
                        p1 = points[i - 1]
                        p2 = points[i]
                        shade = 120 + int(100 * (i / len(points)))
                        color = (shade, min(255, shade + 20), 255)
                        pygame.draw.line(
                            self.screen,
                            color,
                            (p1[0] + cam_x, p1[1] + cam_y),
                            (p2[0] + cam_x, p2[1] + cam_y),
                            2,
                        )

            for sprite in tuple(self.all_sprites):
                self.screen.blit(sprite.image, sprite.rect.move(cam_x, cam_y))
            if self.player.shield:
                self.player.draw_shield(self.screen, cam_x=cam_x, cam_y=cam_y, now=now)
            boss_fx = self._boss_from_enemies()
            if boss_fx is not None:
                charge_left = int(getattr(boss_fx, "telegraph_remaining_ms", lambda _n: 0)(now))
                if charge_left > 0:
                    ratio = float(getattr(boss_fx, "telegraph_progress", lambda _n: 0.0)(now))
                    cx = boss_fx.rect.centerx + cam_x
                    cy = boss_fx.rect.centery + cam_y
                    base_r = boss_fx.rect.width // 2 + 12
                    pulse = 0.5 + 0.5 * math.sin(now * 0.02)
                    ring_r = base_r + int(4 * pulse)
                    glow_alpha = int(90 + 130 * ratio)
                    ring = pygame.Surface((ring_r * 2 + 20, ring_r * 2 + 20), pygame.SRCALPHA)
                    rcx = ring.get_width() // 2
                    rcy = ring.get_height() // 2
                    pygame.draw.circle(ring, (255, 132, 132, glow_alpha // 2), (rcx, rcy), ring_r + 6, 2)
                    pygame.draw.circle(ring, (255, 188, 146, glow_alpha), (rcx, rcy), ring_r, 3)
                    self.screen.blit(ring, (cx - rcx, cy - rcy))

            hud = pygame.Surface((280, 88), pygame.SRCALPHA)
            hud.fill((10, 16, 32, 170))
            pygame.draw.rect(hud, (90, 140, 220, 130), hud.get_rect(), 1, border_radius=8)
            self.screen.blit(hud, (8, 8))
            draw_text(self.screen, self.font, f"Score: {self.score}", 16, 14, (230, 240, 255))
            draw_text(self.screen, self.font, f"Lives: {self.lives}", 16, 38, (255, 220, 220))
            if self.combo_chain > 1:
                rem_tenths = max(0, (self.combo_timeout_ms - (now - self.combo_last_kill_at)) // 100)
                draw_text(
                    self.screen,
                    self.small_font,
                    f"Combo x{self.combo_multiplier:.1f} ({self.combo_chain}) {rem_tenths / 10:.1f}s",
                    152,
                    16,
                    (255, 232, 160),
                )
            if self._is_boss_wave():
                status = "Boss active" if self.boss_active else "Boss wave"
                draw_text(self.screen, self.font, f"Wave: {self.wave}  {status}", 16, 62, (255, 210, 170))
            elif self.wave_locked_by_shooters:
                remaining = len(self._alive_shooters())
                draw_text(self.screen, self.font, f"Wave: {self.wave}  Clear gunners: {remaining}", 16, 62, (255, 210, 170))
            else:
                draw_text(self.screen, self.font, f"Wave: {self.wave}  Kills: {self.wave_kills}/{self.wave_target_kills}", 16, 62, (180, 225, 255))

            info = pygame.Surface((430, 60), pygame.SRCALPHA)
            info.fill((10, 16, 32, 145))
            pygame.draw.rect(info, (90, 140, 220, 90), info.get_rect(), 1, border_radius=8)
            self.screen.blit(info, (8, 100))
            draw_text(
                self.screen,
                self.small_font,
                f"Diff: {settings.DIFFICULTY} (1/2/3)  Visual: {settings.VISUAL_QUALITY}  FPS cap: {settings.FPS}",
                16,
                108,
                (205, 220, 245),
            )
            draw_text(
                self.screen,
                self.small_font,
                f"A/D move  Space shoot  P/Esc pause  F11 fullscreen  F3 FPS  DMG x{self.player_bullet_damage}",
                16,
                132,
                (170, 205, 245),
            )
            if settings.SHOW_FPS:
                draw_text(
                    self.screen,
                    self.small_font,
                    f"FPS: {self.clock.get_fps():.0f}/{settings.FPS}",
                    settings.WIDTH - 108,
                    settings.HEIGHT - 24,
                    (160, 196, 236),
                )

            powerup_box = pygame.Surface((166, 96), pygame.SRCALPHA)
            powerup_box.fill((10, 16, 32, 140))
            pygame.draw.rect(powerup_box, (90, 140, 220, 100), powerup_box.get_rect(), 1, border_radius=8)
            self.screen.blit(powerup_box, (settings.WIDTH - 176, 8))
            y_off = 14
            now = pygame.time.get_ticks()
            if self.player.shield:
                rem = max(0, (self.player.shield_end - now) // 1000)
                draw_text(self.screen, self.font, f"Shield: {rem}s", settings.WIDTH - 166, y_off, (205, 235, 255))
                y_off += 24
            if self.player.rapid_end:
                rem = max(0, (self.player.rapid_end - now) // 1000)
                draw_text(self.screen, self.font, f"Rapid:  {rem}s", settings.WIDTH - 166, y_off, (205, 235, 255))
                y_off += 24
            if self.player.double_end:
                rem = max(0, (self.player.double_end - now) // 1000)
                draw_text(self.screen, self.font, f"Double: {rem}s", settings.WIDTH - 166, y_off, (205, 235, 255))
                y_off += 24

            boss = self._boss_from_enemies()
            if boss is not None:
                bar_w = 320
                bar_h = 16
                bx = settings.WIDTH // 2 - bar_w // 2
                by = 8
                pygame.draw.rect(self.screen, (32, 24, 44), (bx, by, bar_w, bar_h), border_radius=6)
                ratio = max(0.0, min(1.0, boss.health / max(1, boss.max_health)))
                fill_w = int((bar_w - 4) * ratio)
                pygame.draw.rect(self.screen, (225, 86, 118), (bx + 2, by + 2, fill_w, bar_h - 4), border_radius=5)
                pygame.draw.rect(self.screen, (255, 200, 220), (bx, by, bar_w, bar_h), 1, border_radius=6)
                draw_text(
                    self.screen,
                    self.font,
                    f"Boss HP: {boss.health}/{boss.max_health}  Phase {getattr(boss, 'phase', 1)}",
                    bx + 54,
                    by - 2,
                    (255, 235, 240),
                )
                charge_left = int(getattr(boss, "telegraph_remaining_ms", lambda _n: 0)(now))
                if charge_left > 0:
                    charge_ratio = float(getattr(boss, "telegraph_progress", lambda _n: 0.0)(now))
                    draw_text(
                        self.screen,
                        self.small_font,
                        "Boss charging heavy attack!",
                        bx + 88,
                        by + 18,
                        (255, 186, 150),
                    )
                    charge_w = 188
                    charge_x = bx + 66
                    charge_y = by + 36
                    pygame.draw.rect(self.screen, (42, 26, 36), (charge_x, charge_y, charge_w, 8), border_radius=4)
                    fill = int((charge_w - 2) * max(0.0, min(1.0, charge_ratio)))
                    pygame.draw.rect(self.screen, (255, 124, 120), (charge_x + 1, charge_y + 1, fill, 6), border_radius=3)
                else:
                    attack_eta = max(0, int(getattr(boss, "next_attack_at", 0) - now))
                    if attack_eta <= 260:
                        draw_text(self.screen, self.small_font, "Incoming attack!", bx + 112, by + 18, (255, 198, 160))

            self._capture_replay_frame(pygame.time.get_ticks())
            pygame.display.flip()

        return self._finish_round("menu")

    def prompt_and_save_score(self):
        name = ""
        max_len = 16
        prompt_font = pygame.font.SysFont(None, 32)
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        add_highscore(normalize_player_name(name), self.score)
                        return "saved"
                    if event.key == pygame.K_ESCAPE:
                        return "saved"
                    if event.key == pygame.K_BACKSPACE:
                        name = name[:-1]
                    else:
                        ch = event.unicode
                        if ch and len(ch) == 1 and ch.isprintable() and len(name) < max_len:
                            name += ch

            self.screen.fill((0, 0, 0))
            prompt = prompt_font.render(
                "Enter highscore name (Enter save, Esc skip):",
                True,
                (200, 200, 200),
            )
            self.screen.blit(
                prompt,
                (settings.WIDTH // 2 - prompt.get_width() // 2, settings.HEIGHT // 2 - 50),
            )

            shown_name = normalize_player_name(name) if name.strip() else name
            name_surface = prompt_font.render(shown_name, True, (255, 255, 255))
            self.screen.blit(
                name_surface,
                (settings.WIDTH // 2 - name_surface.get_width() // 2, settings.HEIGHT // 2),
            )

            limit = self.font.render(f"{len(name)}/{max_len}", True, (150, 150, 150))
            self.screen.blit(limit, (settings.WIDTH // 2 - limit.get_width() // 2, settings.HEIGHT // 2 + 40))
            pygame.display.flip()

    def game_over_screen(self):
        over_font = pygame.font.SysFont(None, 64)
        small = pygame.font.SysFont(None, 28)
        self.screen.fill((0, 0, 0))
        text = over_font.render("GAME OVER", True, (220, 50, 50))
        sub = small.render(f"Score: {self.score} - press any key to return", True, (255, 255, 255))
        self.screen.blit(text, (settings.WIDTH // 2 - text.get_width() // 2, settings.HEIGHT // 2 - 30))
        self.screen.blit(sub, (settings.WIDTH // 2 - sub.get_width() // 2, settings.HEIGHT // 2 + 30))
        pygame.display.flip()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    return "menu"
            self.clock.tick(settings.FPS)

    def options_menu(self):
        idx = 0
        options = [
            "Master Volume",
            "Difficulty",
            "Visual Quality",
            "FPS Cap",
            "Show FPS",
            "Fullscreen",
            "Reset to Defaults",
            "Back",
        ]
        order = ["Easy", "Normal", "Hard"]
        quality_order = list(settings.VISUAL_PRESETS.keys())
        fps_order = list(settings.FPS_OPTIONS)
        adjustable = {"Master Volume", "Difficulty", "Visual Quality", "FPS Cap"}
        descriptions = {
            "Master Volume": "Controls all game sounds.",
            "Difficulty": "Changes enemy pressure and your movement/bullet profile.",
            "Visual Quality": "Switch between performance and richer visuals.",
            "FPS Cap": "Limits max FPS for smoother frame pacing and cooler hardware.",
            "Show FPS": "Display a live FPS counter in the lower-right corner.",
            "Fullscreen": "Switch between windowed and fullscreen mode.",
            "Reset to Defaults": "Restore recommended defaults for all options.",
            "Back": "Return to title menu.",
        }
        row_rects = {}
        left_buttons = {}
        right_buttons = {}

        def cycle_value(values, current, step):
            if not values:
                return current
            if current not in values:
                return values[0]
            return values[(values.index(current) + step) % len(values)]

        def adjust_option(name, step):
            if name == "Master Volume":
                self.master_volume = max(0.0, min(1.0, self.master_volume + 0.05 * step))
                set_sounds_volume(self.master_volume)
                self._save_user_preferences()
                return
            if name == "Difficulty":
                self._apply_difficulty(cycle_value(order, settings.DIFFICULTY, step))
                return
            if name == "Visual Quality":
                self._apply_visual_quality(cycle_value(quality_order, settings.VISUAL_QUALITY, step))
                return
            if name == "FPS Cap":
                self._apply_fps_cap(cycle_value(fps_order, settings.FPS, step))

        def activate_option(name):
            if name == "Show FPS":
                self._toggle_show_fps()
                return None
            if name == "Fullscreen":
                self._toggle_fullscreen()
                return None
            if name == "Reset to Defaults":
                self._reset_preferences_to_defaults()
                return None
            if name == "Back":
                return "back"
            if name in adjustable:
                adjust_option(name, 1)
            return None

        def option_label(name):
            if name == "Master Volume":
                return f"{name}: {int(self.master_volume * 100)}%"
            if name == "Difficulty":
                return f"{name}: {settings.DIFFICULTY}"
            if name == "Visual Quality":
                return f"{name}: {settings.VISUAL_QUALITY}"
            if name == "FPS Cap":
                return f"{name}: {settings.FPS}"
            if name == "Show FPS":
                return f"{name}: {'On' if settings.SHOW_FPS else 'Off'}"
            if name == "Fullscreen":
                return f"{name}: {'On' if self.fullscreen else 'Off'}"
            return name

        while True:
            dt = self.clock.tick(settings.FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                    self._handle_window_change()
                    continue
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F11:
                        self._toggle_fullscreen()
                        continue
                    if event.key == pygame.K_F3:
                        self._toggle_show_fps()
                        continue
                    if event.key in (pygame.K_r,):
                        self._reset_preferences_to_defaults()
                        continue
                    if event.key in (pygame.K_UP, pygame.K_w):
                        idx = (idx - 1) % len(options)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        idx = (idx + 1) % len(options)
                    elif event.key in (pygame.K_LEFT, pygame.K_q):
                        if options[idx] in adjustable:
                            adjust_option(options[idx], -1)
                        elif options[idx] in ("Show FPS", "Fullscreen"):
                            activate_option(options[idx])
                    elif event.key in (pygame.K_RIGHT, pygame.K_e):
                        if options[idx] in adjustable:
                            adjust_option(options[idx], 1)
                        elif options[idx] in ("Show FPS", "Fullscreen"):
                            activate_option(options[idx])
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        result = activate_option(options[idx])
                        if result == "back":
                            return "back"
                    elif event.key == pygame.K_ESCAPE:
                        return "back"
                if event.type == pygame.MOUSEMOTION:
                    for i, opt in enumerate(options):
                        rect = row_rects.get(opt)
                        if rect and rect.collidepoint(event.pos):
                            idx = i
                            break
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    clicked = False
                    for i, opt in enumerate(options):
                        lrect = left_buttons.get(opt)
                        rrect = right_buttons.get(opt)
                        if lrect and lrect.collidepoint(event.pos):
                            idx = i
                            adjust_option(opt, -1)
                            clicked = True
                            break
                        if rrect and rrect.collidepoint(event.pos):
                            idx = i
                            adjust_option(opt, 1)
                            clicked = True
                            break
                    if clicked:
                        continue
                    for i, opt in enumerate(options):
                        rect = row_rects.get(opt)
                        if rect and rect.collidepoint(event.pos):
                            idx = i
                            result = activate_option(opt)
                            if result == "back":
                                return "back"
                            break

            draw_background(self.screen, self.stars, max(1, int(dt * 0.55)))
            sw, sh = self.screen.get_size()
            panel_w = min(620, max(470, sw - 100))
            panel_h = min(500, max(400, sh - 90))
            panel = pygame.Rect(sw // 2 - panel_w // 2, sh // 2 - panel_h // 2, panel_w, panel_h)

            panel_surf = pygame.Surface((panel.width, panel.height), pygame.SRCALPHA)
            panel_surf.fill((8, 14, 30, 196))
            pygame.draw.rect(panel_surf, (90, 142, 220, 176), panel_surf.get_rect(), 2, border_radius=14)
            self.screen.blit(panel_surf, panel.topleft)

            title = self.font.render("Options", True, (242, 244, 255))
            self.screen.blit(title, (sw // 2 - title.get_width() // 2, panel.top + 16))
            profile = self.small_font.render(
                f"{settings.VISUAL_QUALITY} | {settings.DIFFICULTY} | cap {settings.FPS} | vol {int(self.master_volume * 100)}%",
                True,
                (176, 198, 228),
            )
            self.screen.blit(profile, (sw // 2 - profile.get_width() // 2, panel.top + 46))

            row_rects = {}
            left_buttons = {}
            right_buttons = {}
            start_y = panel.top + 88
            for i, opt in enumerate(options):
                is_selected = i == idx
                row_rect = pygame.Rect(panel.left + 34, start_y + i * 44, panel.width - 68, 36)
                row_rects[opt] = row_rect
                row_bg = pygame.Surface((row_rect.width, row_rect.height), pygame.SRCALPHA)
                row_bg.fill((34, 64, 122, 170) if is_selected else (18, 32, 62, 155))
                border = (152, 206, 255, 220) if is_selected else (96, 132, 180, 120)
                pygame.draw.rect(row_bg, border, row_bg.get_rect(), 1, border_radius=8)
                self.screen.blit(row_bg, row_rect.topleft)
                if is_selected:
                    pygame.draw.rect(self.screen, (255, 220, 132), (row_rect.left + 2, row_rect.top + 5, 3, row_rect.height - 10), border_radius=2)

                if opt in adjustable:
                    lrect = pygame.Rect(row_rect.left + 8, row_rect.top + 6, 24, 24)
                    rrect = pygame.Rect(row_rect.right - 32, row_rect.top + 6, 24, 24)
                    left_buttons[opt] = lrect
                    right_buttons[opt] = rrect
                    pygame.draw.rect(self.screen, (24, 42, 78), lrect, border_radius=6)
                    pygame.draw.rect(self.screen, (24, 42, 78), rrect, border_radius=6)
                    pygame.draw.rect(self.screen, (110, 160, 226), lrect, 1, border_radius=6)
                    pygame.draw.rect(self.screen, (110, 160, 226), rrect, 1, border_radius=6)
                    ltxt = self.small_font.render("<", True, (210, 228, 255))
                    rtxt = self.small_font.render(">", True, (210, 228, 255))
                    self.screen.blit(ltxt, (lrect.centerx - ltxt.get_width() // 2, lrect.centery - ltxt.get_height() // 2))
                    self.screen.blit(rtxt, (rrect.centerx - rtxt.get_width() // 2, rrect.centery - rtxt.get_height() // 2))

                text = self.font.render(option_label(opt), True, (255, 232, 146) if is_selected else (210, 224, 244))
                self.screen.blit(text, (row_rect.centerx - text.get_width() // 2, row_rect.y + 6))

            selected_opt = options[idx]
            desc = descriptions.get(selected_opt, "")
            desc_rect = pygame.Rect(panel.left + 34, panel.bottom - 94, panel.width - 68, 42)
            desc_surf = pygame.Surface((desc_rect.width, desc_rect.height), pygame.SRCALPHA)
            desc_surf.fill((10, 20, 40, 172))
            pygame.draw.rect(desc_surf, (98, 142, 210, 120), desc_surf.get_rect(), 1, border_radius=8)
            self.screen.blit(desc_surf, desc_rect.topleft)
            dimg = self.small_font.render(desc, True, (182, 208, 238))
            self.screen.blit(dimg, (desc_rect.centerx - dimg.get_width() // 2, desc_rect.y + 12))

            if selected_opt == "Master Volume":
                ratio = self.master_volume
                bar_rect = pygame.Rect(panel.left + 34, panel.bottom - 44, panel.width - 68, 8)
                pygame.draw.rect(self.screen, (34, 50, 78), bar_rect, border_radius=4)
                pygame.draw.rect(self.screen, (94, 172, 255), (bar_rect.x, bar_rect.y, int(bar_rect.width * ratio), bar_rect.height), border_radius=4)
            elif selected_opt == "FPS Cap":
                min_fps = min(fps_order)
                max_fps = max(fps_order)
                ratio = (settings.FPS - min_fps) / max(1, (max_fps - min_fps))
                bar_rect = pygame.Rect(panel.left + 34, panel.bottom - 44, panel.width - 68, 8)
                pygame.draw.rect(self.screen, (34, 50, 78), bar_rect, border_radius=4)
                pygame.draw.rect(self.screen, (94, 172, 255), (bar_rect.x, bar_rect.y, int(bar_rect.width * ratio), bar_rect.height), border_radius=4)

            hint = self.small_font.render(
                "Arrows/WASD navigate, Q/E change, Enter apply, mouse click, R reset, F11 fullscreen, Esc back",
                True,
                (152, 176, 208),
            )
            self.screen.blit(hint, (sw // 2 - hint.get_width() // 2, panel.bottom - 20))
            tag = self.notice_font.render(self.notice_text, True, (120, 138, 164))
            self.screen.blit(tag, (8, sh - 16))
            pygame.display.flip()


def run():
    Game().run()
