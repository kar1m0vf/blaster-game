import os
import random
import math
from collections import deque

import pygame

from . import menu
from . import settings
from .assets import ensure_sounds, load_sounds, load_window_icon, set_sounds_volume
from .combat import CombatSystem
from .entities import BossEnemy, Enemy, Explosion, FloatingText, Particle, Player, PowerUp, ShooterEnemy
from .storage import (
    add_highscore,
    load_user_settings,
    normalize_player_name,
    save_user_settings,
)
from .ui import clear_background_cache, draw_background, draw_text, make_stars, render_text_fit, ui_microtext


SHIP_LOADOUTS = (
    {
        "id": "interceptor",
        "name": "Interceptor",
        "short": "INT",
        "role": "Fast assault frame",
        "desc": "High speed, faster cannon cycling, twin pulse cannons.",
        "weapon": "Twin Pulse",
        "speed_bonus": 0.8,
        "cooldown": 220,
        "damage": 1,
        "lives": 3,
        "accent": (112, 214, 255),
        "rarity": "AGILE",
    },
    {
        "id": "vanguard",
        "name": "Vanguard",
        "short": "VGD",
        "role": "Armored shield frame",
        "desc": "Extra hull and opening shield, wide plasma caster.",
        "weapon": "Plasma Caster",
        "speed_bonus": -0.2,
        "cooldown": 275,
        "damage": 1,
        "lives": 4,
        "start_shield_ms": 2800,
        "accent": (118, 238, 202),
        "rarity": "ARMORED",
    },
    {
        "id": "lancer",
        "name": "Lancer",
        "short": "LNC",
        "role": "Precision rail frame",
        "desc": "Heavy opening damage, slower rail weapon with pierce.",
        "weapon": "Rail Lance",
        "speed_bonus": -0.45,
        "cooldown": 320,
        "damage": 2,
        "lives": 3,
        "accent": (255, 202, 116),
        "rarity": "HEAVY",
    },
)

RUN_FINAL_WAVE = 8
RUN_SECTOR_NAMES = (
    "Outer Drift",
    "Neon Belt",
    "Debris Graveyard",
    "Command Spire",
)

_ORIGINAL_DISPLAY_FLIP = pygame.display.flip
_ORIGINAL_DISPLAY_UPDATE = pygame.display.update
_ORIGINAL_EVENT_GET = pygame.event.get


class Game:
    def __init__(self):
        pygame.init()
        try:
            pygame.mixer.pre_init(44100, -16, 1, 1024)
            pygame.mixer.init()
        except pygame.error:
            pass

        self.master_volume = 0.6
        self.fullscreen = True
        self.selected_ship_id = SHIP_LOADOUTS[0]["id"]
        self.display_surface = None
        self.present_rect = pygame.Rect(0, 0, settings.WIDTH, settings.HEIGHT)
        self._load_user_preferences()
        self.screen = None
        self._apply_display_mode()
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 32)
        self.small_font = pygame.font.SysFont(None, 22)
        self.notice_font = pygame.font.SysFont(None, 17)
        self.notice_text = ui_microtext()
        self.stars = make_stars(width=settings.WIDTH, height=settings.HEIGHT)
        self.replay_duration_ms = 5000
        self.replay_fps = self._replay_fps_for_quality()
        self.replay_capture_interval_ms = max(50, 1000 // max(1, self.replay_fps))
        self.replay_buffer_size = (settings.WIDTH, settings.HEIGHT)
        self.replay_max_frames = max(1, int(self.replay_duration_ms / self.replay_capture_interval_ms) + 2)
        self.replay_frames = deque(maxlen=self.replay_max_frames)
        self.replay_last_capture_at = 0
        self.combat = CombatSystem(self)

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

    def _ship_loadout(self, ship_id=None):
        wanted = ship_id or self.selected_ship_id
        for loadout in SHIP_LOADOUTS:
            if loadout["id"] == wanted:
                return loadout
        return SHIP_LOADOUTS[0]

    def _set_selected_ship(self, ship_id):
        self.selected_ship_id = self._ship_loadout(ship_id)["id"]
        self._save_user_preferences()

    def _current_player_speed(self):
        return settings.PLAYER_SPEED + getattr(self, "player_speed_bonus", 0.0)

    def _reset_round(self, start_timers=True):
        self.all_sprites = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.enemy_bullets = pygame.sprite.Group()
        self.powerups = pygame.sprite.Group()
        self.floating = pygame.sprite.Group()
        self.explosions = pygame.sprite.Group()
        self.effects = pygame.sprite.Group()

        loadout = self._ship_loadout()
        self.player_speed_bonus = float(loadout.get("speed_bonus", 0.0))
        self.player = Player(style=loadout["id"])
        self.player.speed = self._current_player_speed()
        self.player._base_shoot_cooldown = int(loadout.get("cooldown", self.player._base_shoot_cooldown))
        self.player.shoot_cooldown = self.player._base_shoot_cooldown
        self.all_sprites.add(self.player)

        self.score = 0
        self.lives = int(loadout.get("lives", 3))
        self.running = True
        self.round_active = False
        self.shake_time_left = 0
        self.shake_strength = 0
        self.wave = 1
        self.run_final_wave = RUN_FINAL_WAVE
        self.run_sector_names = RUN_SECTOR_NAMES
        self.wave_kills = 0
        self.wave_target_kills = 0
        self.pending_wave_advance = False
        self.current_spawn_time = settings.ENEMY_SPAWN_TIME
        self.current_max_enemies = settings.MAX_ENEMIES
        self.boss_active = False
        self.boss_spawned_for_wave = False
        self.wave_locked_by_shooters = False
        self.player_bullet_damage = int(loadout.get("damage", 1))
        self.upgrade_pick_count = 0
        self.combo_chain = 0
        self.combo_multiplier = 1.0
        self.combo_timeout_ms = 2800
        self.combo_last_kill_at = 0
        self.engine_fx_last_at = 0
        self.damage_flash_until = 0
        self.combat.reset_round_state()
        self.replay_frames.clear()
        self.replay_last_capture_at = 0

        if start_timers:
            if loadout.get("start_shield_ms"):
                self.player.apply_powerup("shield", duration_ms=int(loadout["start_shield_ms"]))
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
        self.selected_ship_id = self._ship_loadout(prefs.get("selected_ship", self.selected_ship_id))["id"]
        self.master_volume = float(prefs.get("master_volume", 0.6))
        self.fullscreen = bool(prefs.get("fullscreen", True))
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
                "selected_ship": self.selected_ship_id,
            }
        )

    def _desktop_size(self):
        try:
            sizes = pygame.display.get_desktop_sizes()
            if sizes:
                width, height = sizes[0]
                if width > 0 and height > 0:
                    return int(width), int(height)
        except (pygame.error, AttributeError):
            pass
        info = pygame.display.Info()
        width = int(getattr(info, "current_w", settings.WIDTH) or settings.WIDTH)
        height = int(getattr(info, "current_h", settings.HEIGHT) or settings.HEIGHT)
        return max(settings.WIDTH, width), max(settings.HEIGHT, height)

    def _recalculate_present_rect(self):
        if self.display_surface is None:
            self.present_rect = pygame.Rect(0, 0, settings.WIDTH, settings.HEIGHT)
            return
        display_w, display_h = self.display_surface.get_size()
        scale = min(display_w / settings.WIDTH, display_h / settings.HEIGHT)
        target_w = max(1, int(settings.WIDTH * scale))
        target_h = max(1, int(settings.HEIGHT * scale))
        self.present_rect = pygame.Rect(
            (display_w - target_w) // 2,
            (display_h - target_h) // 2,
            target_w,
            target_h,
        )

    def _display_to_logical_pos(self, pos):
        x, y = pos
        rect = self.present_rect
        if rect.width <= 0 or rect.height <= 0:
            return int(x), int(y)
        if x < rect.left or x >= rect.right or y < rect.top or y >= rect.bottom:
            return -10000, -10000
        lx = (x - rect.left) * settings.WIDTH / rect.width
        ly = (y - rect.top) * settings.HEIGHT / rect.height
        return int(lx), int(ly)

    def _mapped_event_get(self, *args, **kwargs):
        events = _ORIGINAL_EVENT_GET(*args, **kwargs)
        if self.display_surface is None:
            return events
        for event in events:
            if hasattr(event, "pos"):
                try:
                    event.pos = self._display_to_logical_pos(event.pos)
                except (TypeError, ValueError):
                    pass
        return events

    def _present(self, *args, **kwargs):
        if self.display_surface is None or self.screen is None:
            return _ORIGINAL_DISPLAY_FLIP()
        self.display_surface.fill((0, 0, 0))
        rect = self.present_rect
        if rect.size == (settings.WIDTH, settings.HEIGHT):
            self.display_surface.blit(self.screen, rect.topleft)
        else:
            try:
                frame = pygame.transform.smoothscale(self.screen, rect.size)
            except pygame.error:
                frame = pygame.transform.scale(self.screen, rect.size)
            self.display_surface.blit(frame, rect.topleft)
        return _ORIGINAL_DISPLAY_FLIP()

    def _install_display_hooks(self):
        pygame.display.flip = self._present
        pygame.display.update = self._present
        pygame.event.get = self._mapped_event_get

    def _apply_display_mode(self):
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        if self.fullscreen:
            os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
            desktop_size = self._desktop_size()
            flags = pygame.NOFRAME
            fallback_flags = pygame.FULLSCREEN
            target_size = desktop_size
        else:
            flags = pygame.RESIZABLE
            fallback_flags = pygame.RESIZABLE
            target_size = (settings.WIDTH, settings.HEIGHT)
        try:
            self.display_surface = pygame.display.set_mode(target_size, flags)
        except pygame.error:
            fallback_size = (0, 0) if self.fullscreen else target_size
            self.display_surface = pygame.display.set_mode(fallback_size, fallback_flags)
        self.screen = pygame.Surface((settings.WIDTH, settings.HEIGHT)).convert()
        self._recalculate_present_rect()
        self._install_display_hooks()
        icon = load_window_icon(dest_dir=os.path.dirname(__file__))
        if icon is not None:
            pygame.display.set_icon(icon)
        pygame.display.set_caption("Blaster - polished")

    def _toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self._apply_display_mode()
        self._handle_window_change()
        self._save_user_preferences()

    def _handle_window_change(self):
        surface = pygame.display.get_surface()
        if surface is not None:
            self.display_surface = surface
        self._recalculate_present_rect()
        clear_background_cache()
        self.stars = make_stars(width=settings.WIDTH, height=settings.HEIGHT)

    def _set_spawn_timer(self, interval_ms):
        pygame.time.set_timer(self.spawn_event, max(0, int(interval_ms)))

    def _stop_round_timers(self):
        self._set_spawn_timer(0)
        pygame.time.set_timer(self.powerup_event, 0)

    def _recompute_wave_params(self):
        wave_idx = max(0, self.wave - 1)
        early_targets = {1: 9, 2: 13, 3: 17}
        self.wave_target_kills = early_targets.get(self.wave, 8 + self.wave * 4)
        entry_pressure = 0.90 if self.wave <= 2 else 0.94
        self.current_spawn_time = max(260, int(settings.ENEMY_SPAWN_TIME * entry_pressure * (0.94 ** wave_idx)))
        early_enemy_bonus = 1 if self.wave <= 3 else 0
        self.current_max_enemies = min(settings.MAX_ENEMIES + early_enemy_bonus + wave_idx // 2, settings.MAX_ENEMIES + 10)

    def _is_boss_wave(self):
        return self.wave > 0 and self.wave % 4 == 0

    def _run_sector_for_wave(self, wave=None):
        wave = self.wave if wave is None else wave
        waves_per_sector = max(1, math.ceil(self.run_final_wave / max(1, len(self.run_sector_names))))
        return max(1, min(len(self.run_sector_names), ((max(1, wave) - 1) // waves_per_sector) + 1))

    def _run_sector_name(self, sector=None):
        sector = self._run_sector_for_wave() if sector is None else sector
        idx = max(0, min(len(self.run_sector_names) - 1, sector - 1))
        return self.run_sector_names[idx]

    def _run_progress_ratio(self):
        if self.pending_wave_advance:
            wave_progress = 1.0
        elif self._is_boss_wave():
            boss = self._boss_from_enemies()
            if boss is None:
                wave_progress = 0.0
            else:
                wave_progress = 1.0 - (boss.health / max(1, boss.max_health))
        elif self.wave_locked_by_shooters:
            total = max(1, self._shooter_enemy_count_for_wave())
            wave_progress = 1.0 - len(self._alive_shooters()) / total
        else:
            wave_progress = self.wave_kills / max(1, self.wave_target_kills)
        completed = (max(1, self.wave) - 1) + max(0.0, min(1.0, wave_progress))
        return max(0.0, min(1.0, completed / max(1, self.run_final_wave)))

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
            sector = self._run_sector_for_wave()
            sector_text = FloatingText(
                settings.WIDTH // 2,
                120,
                f"Sector {sector}: {self._run_sector_name(sector)}",
                color=(150, 210, 255),
                lifetime=1050,
            )
            self.floating.add(sector_text)
            self.all_sprites.add(sector_text)

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
        previous_sector = self._run_sector_for_wave(self.wave)
        self.wave += 1
        self._start_wave(announce=True, start_timers=self.round_active)
        next_sector = self._run_sector_for_wave(self.wave)
        if next_sector != previous_sector:
            ft = FloatingText(
                settings.WIDTH // 2,
                148,
                f"Entering {self._run_sector_name(next_sector)}",
                color=(255, 226, 146),
                lifetime=1500,
            )
            self.floating.add(ft)
            self.all_sprites.add(ft)

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
        if is_boss:
            self._emit_burst_fx(enemy.rect.center, kind="boss", count=18)
        elif is_elite:
            self._emit_burst_fx(enemy.rect.center, kind="elite", count=12)
        else:
            self._emit_burst_fx(enemy.rect.center, kind="enemy", count=8)
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
            self.player.speed = self._current_player_speed()
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
        self.selected_ship_id = SHIP_LOADOUTS[0]["id"]
        self.master_volume = 0.6
        set_sounds_volume(self.master_volume)
        self.fullscreen = True
        self._apply_display_mode()
        self._handle_window_change()
        self.replay_fps = self._replay_fps_for_quality()
        self.replay_capture_interval_ms = max(50, 1000 // max(1, self.replay_fps))
        self.replay_max_frames = max(1, int(self.replay_duration_ms / self.replay_capture_interval_ms) + 2)
        kept = list(self.replay_frames)[-self.replay_max_frames :]
        self.replay_frames = deque(kept, maxlen=self.replay_max_frames)
        if hasattr(self, "player") and self.player:
            base_bonus = self._ship_loadout().get("speed_bonus", 0.0)
            self.player_speed_bonus = float(base_bonus)
            self.player.speed = self._current_player_speed()
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

    def _draw_glass_panel(
        self,
        rect,
        base_rgba=(10, 16, 32, 170),
        edge_rgba=(90, 140, 220, 130),
        highlight_rgba=(120, 180, 255, 34),
        radius=8,
        shadow=True,
    ):
        if shadow:
            shadow_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            pygame.draw.rect(
                shadow_surf,
                (4, 8, 18, 120),
                shadow_surf.get_rect(),
                border_radius=max(2, radius + 1),
            )
            self.screen.blit(shadow_surf, (rect.x, rect.y + 3))

        panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        panel.fill(base_rgba)
        top_tint = (
            min(255, base_rgba[0] + 22),
            min(255, base_rgba[1] + 36),
            min(255, base_rgba[2] + 56),
            min(255, base_rgba[3] + 18),
        )
        top_h = max(8, rect.height // 3)
        pygame.draw.rect(panel, top_tint, (0, 0, rect.width, top_h), border_radius=radius)
        sheen_h = max(10, rect.height // 2)
        sheen = pygame.Surface((max(1, rect.width - 2), sheen_h), pygame.SRCALPHA)
        sheen.fill(highlight_rgba)
        panel.blit(sheen, (1, 1))
        pygame.draw.line(panel, (255, 255, 255, 24), (radius, 1), (rect.width - radius, 1), 1)
        pygame.draw.line(panel, edge_rgba, (1, max(2, radius)), (1, rect.height - max(3, radius)), 1)
        pygame.draw.rect(panel, edge_rgba, panel.get_rect(), 1, border_radius=radius)
        self.screen.blit(panel, rect.topleft)

    def _draw_text_shadow(self, font, text, x, y, color, shadow=(8, 12, 24), offset=(2, 2), max_width=None):
        shadow_img = render_text_fit(font, text, shadow, max_width, shadow=False, outline=False)
        self.screen.blit(shadow_img, (x + offset[0], y + offset[1]))
        img = render_text_fit(font, text, color, max_width)
        self.screen.blit(img, (x, y))

    def _add_effect(self, effect):
        self.effects.add(effect)

    def _quality_fx_scale(self):
        if settings.VISUAL_QUALITY == "Performance":
            return 0.45
        if settings.VISUAL_QUALITY == "Balanced":
            return 0.75
        if settings.VISUAL_QUALITY == "Cinematic":
            return 1.0
        return 1.18

    def _emit_engine_trail(self, now):
        interval = 86 if settings.VISUAL_QUALITY == "Performance" else 42
        if now - self.engine_fx_last_at < interval:
            return
        self.engine_fx_last_at = now
        moving = pygame.key.get_pressed()[pygame.K_a] or pygame.key.get_pressed()[pygame.K_d]
        base_life = 360 if moving else 290
        for offset in (-10, 10):
            jitter = random.uniform(-1.8, 1.8)
            self._add_effect(
                Particle(
                    self.player.rect.centerx + offset + jitter,
                    self.player.rect.bottom - 8,
                    vel=(random.uniform(-0.26, 0.26), random.uniform(1.4, 2.35)),
                    color=random.choice(((86, 194, 255), (255, 168, 78), (255, 226, 146))),
                    life=base_life + random.randint(-45, 60),
                    size=random.randint(2, 4),
                    shape="soft",
                )
            )

    def _emit_muzzle_fx(self, fired):
        offsets = (-8, 8) if fired >= 2 else (0,)
        for offset in offsets:
            origin = (self.player.rect.centerx + offset, self.player.rect.top + 6)
            self._add_effect(
                Particle(
                    origin[0],
                    origin[1],
                    vel=(0, -1.4),
                    color=(164, 236, 255),
                    life=145,
                    size=5,
                    shape="ring",
                )
            )
            for _ in range(2):
                self._add_effect(
                    Particle(
                        origin[0] + random.uniform(-2, 2),
                        origin[1] + random.uniform(-1, 2),
                        vel=(random.uniform(-0.55, 0.55), random.uniform(-1.9, -0.8)),
                        color=(255, 236, 178),
                        life=160 + random.randint(-20, 40),
                        size=2,
                        shape="spark",
                    )
                )

    def _emit_burst_fx(self, center, kind="impact", count=None):
        scale = self._quality_fx_scale()
        if count is None:
            count = int(8 * scale)
        else:
            count = int(count * scale)
        if count <= 0:
            return
        palettes = {
            "impact": ((156, 238, 255), (255, 238, 174), (92, 196, 255)),
            "armor": ((172, 248, 255), (224, 255, 255), (126, 220, 255)),
            "enemy": ((255, 112, 128), (255, 196, 110), (255, 238, 170)),
            "elite": ((255, 178, 82), (255, 238, 156), (176, 228, 255)),
            "boss": ((255, 96, 132), (255, 206, 150), (222, 132, 255)),
            "shield": ((126, 236, 255), (236, 255, 255), (110, 190, 255)),
            "player": ((255, 122, 104), (255, 226, 144), (118, 214, 255)),
        }
        palette = palettes.get(kind, palettes["impact"])
        cx, cy = center
        for idx in range(count):
            ang = random.uniform(0.0, math.tau)
            speed = random.uniform(1.3, 4.4 if kind != "boss" else 5.8)
            shape = "spark" if idx % 2 == 0 else "soft"
            self._add_effect(
                Particle(
                    cx + random.uniform(-4, 4),
                    cy + random.uniform(-4, 4),
                    vel=(math.cos(ang) * speed, math.sin(ang) * speed),
                    color=random.choice(palette),
                    life=random.randint(300, 720),
                    size=random.randint(2, 6 if kind != "boss" else 8),
                    shape=shape,
                    gravity=0.015,
                )
            )
        if kind in ("boss", "shield", "player", "elite"):
            self._add_effect(
                Particle(
                    cx,
                    cy,
                    vel=(0, 0),
                    color=random.choice(palette),
                    life=280,
                    size=11 if kind == "boss" else 8,
                    shape="ring",
                )
            )

    def _draw_meter(self, rect, ratio, fill_rgb, label=None, label_color=(230, 242, 255)):
        ratio = max(0.0, min(1.0, ratio))
        pygame.draw.rect(self.screen, (13, 24, 44), rect, border_radius=rect.height // 2)
        pygame.draw.rect(self.screen, (36, 54, 84), rect.inflate(-2, -2), border_radius=max(1, rect.height // 2 - 1))
        fill_w = int(rect.width * ratio)
        if fill_w > 0:
            fill_rect = pygame.Rect(rect.x, rect.y, fill_w, rect.height)
            pygame.draw.rect(self.screen, fill_rgb, fill_rect, border_radius=rect.height // 2)
            shine_h = max(1, rect.height // 3)
            pygame.draw.rect(
                self.screen,
                (min(255, fill_rgb[0] + 72), min(255, fill_rgb[1] + 58), min(255, fill_rgb[2] + 38)),
                (fill_rect.x + 1, fill_rect.y + 1, max(0, fill_rect.width - 2), shine_h),
                border_radius=max(1, shine_h // 2),
            )
            glow = pygame.Surface((rect.width + 16, rect.height + 16), pygame.SRCALPHA)
            pygame.draw.rect(
                glow,
                (*fill_rgb, 58),
                pygame.Rect(8, 8, fill_w, rect.height),
                border_radius=rect.height // 2,
            )
            self.screen.blit(glow, (rect.x - 8, rect.y - 8), special_flags=pygame.BLEND_RGBA_ADD)
        pygame.draw.rect(self.screen, (126, 190, 255), rect, 1, border_radius=rect.height // 2)
        if label:
            text = render_text_fit(self.small_font, label, label_color, rect.width - 12)
            self.screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def _draw_status_chip(self, rect, label, accent=(116, 202, 255), active=True):
        base = (13, 24, 48, 178) if active else (10, 16, 30, 132)
        edge = (*accent, 154 if active else 80)
        self._draw_glass_panel(rect, base_rgba=base, edge_rgba=edge, highlight_rgba=(*accent, 18), radius=8, shadow=False)
        pygame.draw.circle(self.screen, accent if active else (76, 92, 116), (rect.left + 12, rect.centery), 4)
        text = render_text_fit(
            self.small_font,
            label,
            (228, 240, 255) if active else (162, 184, 216),
            rect.width - 34,
        )
        self.screen.blit(text, (rect.left + 24, rect.centery - text.get_height() // 2))

    def _wave_label_and_progress(self):
        if self._is_boss_wave():
            return ("BOSS ACTIVE" if self.boss_active else "BOSS WAVE"), 1.0, (255, 154, 132)
        if self.wave_locked_by_shooters:
            remaining = len(self._alive_shooters())
            total = max(1, self._shooter_enemy_count_for_wave())
            return f"GUNNERS {remaining}", 1.0 - remaining / total, (255, 210, 132)
        ratio = self.wave_kills / max(1, self.wave_target_kills)
        return f"WAVE {self.wave}", ratio, (120, 218, 255)

    def _draw_modern_hud(self, now):
        hud_rect = pygame.Rect(10, 10, 318, 104)
        self._draw_glass_panel(
            hud_rect,
            base_rgba=(8, 18, 40, 190),
            edge_rgba=(112, 186, 255, 176),
            highlight_rgba=(144, 216, 255, 34),
            radius=10,
        )
        self._draw_text_shadow(self.font, f"{self.score:08d}", 22, 18, (244, 250, 255))
        score_label = render_text_fit(self.small_font, "SCORE", (132, 196, 246), 82)
        self.screen.blit(score_label, (230, 20))

        life_x = 22
        for idx in range(8):
            x = life_x + idx * 17
            active = idx < self.lives
            col = (255, 104, 122) if active else (54, 66, 88)
            pygame.draw.circle(self.screen, col, (x, 50), 5)
            pygame.draw.circle(self.screen, (255, 220, 220) if active else (80, 96, 126), (x, 50), 5, 1)
        life_text = render_text_fit(self.small_font, f"HULL {self.lives}/8", (255, 222, 222), 130)
        self.screen.blit(life_text, (174, 42))

        wave_text, wave_ratio, wave_col = self._wave_label_and_progress()
        wave_label = render_text_fit(self.small_font, wave_text, wave_col, 78)
        self.screen.blit(wave_label, (22, 70))
        self._draw_meter(pygame.Rect(106, 72, 206, 10), wave_ratio, wave_col)
        if not self._is_boss_wave() and not self.wave_locked_by_shooters:
            kills = render_text_fit(self.small_font, f"{self.wave_kills}/{self.wave_target_kills}", (206, 228, 250), 50)
            self.screen.blit(kills, (264, 86))

        if not self._is_boss_wave():
            mission_rect = pygame.Rect(settings.WIDTH // 2 - 190, 10, 380, 54)
            self._draw_glass_panel(
                mission_rect,
                base_rgba=(7, 18, 38, 176),
                edge_rgba=(116, 206, 255, 132),
                highlight_rgba=(150, 226, 255, 28),
                radius=10,
            )
            sector = self._run_sector_for_wave()
            mission = render_text_fit(
                self.notice_font,
                f"WAVE {self.wave} | SECTOR {sector}: {self._run_sector_name(sector)}",
                (232, 246, 255),
                mission_rect.width - 36,
            )
            self.screen.blit(mission, (mission_rect.centerx - mission.get_width() // 2, mission_rect.top + 9))
            self._draw_meter(
                pygame.Rect(mission_rect.left + 22, mission_rect.top + 34, mission_rect.width - 44, 8),
                self._run_progress_ratio(),
                (92, 216, 255),
            )

        if self.combo_chain > 1:
            rem_ms = max(0, self.combo_timeout_ms - (now - self.combo_last_kill_at))
            rem_ratio = rem_ms / max(1, self.combo_timeout_ms)
            if self._boss_from_enemies() is not None:
                combo_rect = pygame.Rect(342, 64, 174, 52)
            else:
                combo_rect = pygame.Rect(settings.WIDTH - 196, 146, 186, 54)
            self._draw_glass_panel(
                combo_rect,
                base_rgba=(38, 25, 30, 190),
                edge_rgba=(255, 220, 126, 190),
                highlight_rgba=(255, 236, 156, 28),
                radius=10,
            )
            combo = render_text_fit(self.font, f"x{self.combo_multiplier:.1f}", (255, 232, 150), 58)
            chain = render_text_fit(self.small_font, f"COMBO {self.combo_chain}", (236, 218, 174), combo_rect.width - 90)
            self.screen.blit(combo, (combo_rect.left + 14, combo_rect.top + 8))
            self.screen.blit(chain, (combo_rect.left + 76, combo_rect.top + 13))
            self._draw_meter(pygame.Rect(combo_rect.left + 14, combo_rect.bottom - 14, combo_rect.width - 28, 7), rem_ratio, (255, 210, 108))

        info_rect = pygame.Rect(10, 122, 416, 44)
        self._draw_glass_panel(
            info_rect,
            base_rgba=(8, 16, 34, 154),
            edge_rgba=(88, 154, 224, 110),
            highlight_rgba=(132, 204, 255, 20),
            radius=9,
            shadow=False,
        )
        profile = render_text_fit(
            self.small_font,
            f"{self._ship_loadout()['short']} {self._ship_loadout()['weapon']}  |  {settings.DIFFICULTY}  |  DMG x{self.player_bullet_damage}  |  {self.player._base_shoot_cooldown}ms",
            (198, 222, 248),
            info_rect.width - 20,
        )
        controls = render_text_fit(
            self.notice_font,
            "A/D move   Space fire   P/Esc pause   F11 fullscreen",
            (164, 194, 228),
            info_rect.width - 20,
        )
        self.screen.blit(profile, (20, 128))
        self.screen.blit(controls, (20, 148))

        sector = self._run_sector_for_wave()
        run_rect = pygame.Rect(438, 122, 282, 44)
        self._draw_glass_panel(
            run_rect,
            base_rgba=(8, 16, 34, 150),
            edge_rgba=(92, 184, 242, 118),
            highlight_rgba=(138, 220, 255, 22),
            radius=9,
            shadow=False,
        )
        run_title = render_text_fit(
            self.notice_font,
            f"RUN SECTOR {sector}/{len(self.run_sector_names)}",
            (166, 206, 244),
            116,
        )
        self.screen.blit(run_title, (run_rect.left + 12, run_rect.top + 8))
        sector_name = render_text_fit(self.notice_font, self._run_sector_name(sector), (226, 238, 255), 116)
        self.screen.blit(sector_name, (run_rect.left + 12, run_rect.top + 25))
        self._draw_meter(
            pygame.Rect(run_rect.left + 138, run_rect.top + 18, 126, 9),
            self._run_progress_ratio(),
            (92, 200, 255),
        )

        powerup_rect = pygame.Rect(settings.WIDTH - 196, 10, 186, 126)
        self._draw_glass_panel(
            powerup_rect,
            base_rgba=(8, 16, 34, 172),
            edge_rgba=(98, 166, 242, 132),
            highlight_rgba=(146, 214, 255, 24),
            radius=10,
        )
        title = render_text_fit(self.small_font, "ACTIVE SYSTEMS", (190, 218, 248), powerup_rect.width - 28)
        self.screen.blit(title, (powerup_rect.left + 14, powerup_rect.top + 10))
        entries = [
            ("SHD", self.player.shield, self.player.shield_end, (118, 222, 255)),
            ("RPD", bool(self.player.rapid_end), self.player.rapid_end, (255, 174, 106)),
            ("DBL", bool(self.player.double_end), self.player.double_end, (220, 154, 255)),
        ]
        y = powerup_rect.top + 36
        active_count = 0
        for label, active, end_at, accent in entries:
            if not active:
                continue
            active_count += 1
            rem = max(0, (end_at - now) // 1000)
            self._draw_status_chip(
                pygame.Rect(powerup_rect.left + 12, y, powerup_rect.width - 24, 24),
                f"{label}  {rem}s",
                accent=accent,
                active=True,
            )
            y += 28
        if active_count == 0:
            self._draw_status_chip(
                pygame.Rect(powerup_rect.left + 12, powerup_rect.top + 52, powerup_rect.width - 24, 24),
                "NOMINAL",
                accent=(92, 142, 202),
                active=False,
            )

        if settings.SHOW_FPS:
            fps_box = pygame.Rect(settings.WIDTH - 128, settings.HEIGHT - 34, 118, 26)
            self._draw_glass_panel(
                fps_box,
                base_rgba=(12, 20, 38, 148),
                edge_rgba=(98, 146, 220, 120),
                highlight_rgba=(136, 194, 255, 20),
                radius=7,
                shadow=False,
            )
            draw_text(
                self.screen,
                self.small_font,
                f"FPS: {self.clock.get_fps():.0f}/{settings.FPS}",
                settings.WIDTH - 118,
                settings.HEIGHT - 28,
                (176, 212, 246),
            )

    def _draw_damage_flash(self, now):
        if now >= self.damage_flash_until:
            return
        remain = (self.damage_flash_until - now) / 180.0
        alpha = int(74 * max(0.0, min(1.0, remain)))
        flash = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        flash.fill((255, 54, 54, alpha))
        self.screen.blit(flash, (0, 0))

    def _draw_sprite_depth_shadow(self, sprite, cam_x=0, cam_y=0):
        if not isinstance(sprite, (Player, Enemy, ShooterEnemy, BossEnemy, PowerUp)):
            return
        if settings.VISUAL_QUALITY == "Performance" and sprite is not self.player:
            return
        depth_intro = bool(getattr(sprite, "depth_intro_active", False))
        if depth_intro and getattr(sprite, "depth_progress", 1.0) < 0.48:
            return
        rect = sprite.rect.move(cam_x, cam_y)
        if rect.bottom < 0 or rect.top > settings.HEIGHT:
            return
        depth = max(0.0, min(1.0, rect.centery / max(1, settings.HEIGHT)))
        shadow_w = max(18, int(rect.width * (0.72 + depth * 0.36)))
        shadow_h = max(5, int(rect.height * (0.10 + depth * 0.05)))
        shadow_y = rect.bottom + int(5 + depth * 13)
        if shadow_y > settings.HEIGHT + shadow_h:
            return
        alpha = int(28 + depth * 34)
        if depth_intro:
            alpha = int(alpha * max(0.2, min(1.0, getattr(sprite, "depth_progress", 1.0))))
        layer = pygame.Surface((shadow_w + 10, shadow_h + 8), pygame.SRCALPHA)
        pygame.draw.ellipse(layer, (0, 0, 0, alpha), (5, 2, shadow_w, shadow_h))
        pygame.draw.ellipse(layer, (74, 154, 255, max(10, alpha // 3)), (5, 2, shadow_w, shadow_h), 1)
        self.screen.blit(layer, (rect.centerx - layer.get_width() // 2, shadow_y - layer.get_height() // 2))

    def _world_sprite_draw_key(self, sprite):
        if isinstance(sprite, FloatingText):
            return (5, sprite.rect.centery)
        if sprite is self.player:
            return (4, settings.HEIGHT + 10)
        if getattr(sprite, "depth_intro_active", False):
            return (1, float(getattr(sprite, "depth_progress", 0.0)))
        if isinstance(sprite, (Enemy, ShooterEnemy, BossEnemy)):
            return (2, sprite.rect.centery)
        return (3, sprite.rect.centery)

    def _sorted_world_sprites(self):
        return sorted(tuple(self.all_sprites), key=self._world_sprite_draw_key)

    def _depth_wake_color(self, enemy):
        if getattr(enemy, "is_elite", False):
            return tuple(max(0, int(c * 0.82)) for c in getattr(enemy, "_elite_glow_rgb", (255, 190, 120)))
        if enemy.etype == "saucer":
            return (76, 132, 190)
        if enemy.etype == "drone":
            return (70, 188, 168)
        if enemy.etype == "spiky":
            return (154, 96, 206)
        return (200, 104, 124)

    def _draw_depth_entry_wakes(self, now, cam_x=0, cam_y=0):
        if settings.VISUAL_QUALITY == "Performance":
            return
        depth_enemies = [enemy for enemy in self.enemies if getattr(enemy, "depth_intro_active", False)]
        if not depth_enemies:
            return
        layer = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        for enemy in depth_enemies:
            progress = max(0.0, min(1.0, float(getattr(enemy, "depth_progress", 0.0))))
            color = self._depth_wake_color(enemy)
            trail = list(getattr(enemy, "depth_trail", []))
            if len(trail) >= 2:
                points = [(int(x + cam_x), int(y + cam_y)) for x, y in trail]
                for i in range(1, len(points)):
                    t = i / max(1, len(points) - 1)
                    alpha = int((14 + 54 * t) * (0.35 + progress * 0.65))
                    width = max(1, int(1 + 3 * t * progress))
                    pygame.draw.line(layer, (*color, alpha), points[i - 1], points[i], width)
                    if i == len(points) - 1 and progress < 0.72:
                        p = points[i]
                        pygame.draw.circle(layer, (*color, int(22 + 34 * progress)), p, max(5, int(enemy.rect.width * 0.26)), 1)

            if progress < 0.18:
                sx, sy = getattr(enemy, "_depth_start", enemy.rect.center)
                pulse = 0.5 + 0.5 * math.sin(now * 0.014 + getattr(enemy, "_depth_wobble_phase", 0.0))
                ring_r = int(10 + 11 * (1.0 - progress) + pulse * 3)
                alpha = int(46 * (1.0 - progress / 0.18))
                center = (int(sx + cam_x), int(sy + cam_y))
                pygame.draw.circle(layer, (*color, alpha), center, ring_r, 1)
                pygame.draw.circle(layer, (230, 250, 255, max(18, alpha // 2)), center, max(3, ring_r // 3), 1)
        self.screen.blit(layer, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_player_bullet_trail(self, bullet, cam_x=0, cam_y=0):
        points = bullet.trail_points + [(bullet.rect.centerx, bullet.rect.bottom)]
        if len(points) < 2:
            return

        variant = getattr(bullet, "variant", "standard")
        if variant == "vanguard":
            recent = points[-4:]
            min_x = int(min(p[0] for p in recent) + cam_x - 18)
            max_x = int(max(p[0] for p in recent) + cam_x + 18)
            min_y = int(min(p[1] for p in recent) + cam_y - 8)
            max_y = int(max(p[1] for p in recent) + cam_y + 24)
            layer = pygame.Surface((max(1, max_x - min_x), max(1, max_y - min_y)), pygame.SRCALPHA)

            def local(point):
                return (int(point[0] + cam_x - min_x), int(point[1] + cam_y - min_y))

            for i in range(1, len(recent)):
                p1 = local(recent[i - 1])
                p2 = local(recent[i])
                t = i / max(1, len(recent) - 1)
                pygame.draw.line(layer, (64, 238, 205, int(40 + 72 * t)), p1, p2, max(1, int(4 * t)))
                rib_w = int(5 + 5 * t)
                pygame.draw.line(layer, (166, 255, 232, int(34 + 58 * t)), (p2[0] - rib_w, p2[1] + 2), (p2[0] + rib_w, p2[1] - 2), 1)

            cx = int(bullet.rect.centerx + cam_x - min_x)
            cy = int(bullet.rect.bottom + cam_y - min_y)
            wake = [(cx - 8, cy + 3), (cx, cy + 15), (cx + 8, cy + 3)]
            pygame.draw.polygon(layer, (42, 226, 196, 58), wake)
            pygame.draw.line(layer, (192, 255, 238, 95), (cx - 5, cy + 5), (cx + 5, cy + 5), 1)
            self.screen.blit(layer, (min_x, min_y), special_flags=pygame.BLEND_RGBA_ADD)
            return

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
                    "icon": "RLD",
                    "rarity": "common",
                }
            )
        if self.player.speed < 9.0:
            pool.append(
                {
                    "id": "engine_overclock",
                    "title": "Engine Overclock",
                    "desc": "+0.6 move speed",
                    "icon": "ENG",
                    "rarity": "common",
                }
            )
        if self.player_bullet_damage < 4:
            pool.append(
                {
                    "id": "piercing_rounds",
                    "title": "Piercing Rounds",
                    "desc": "+1 bullet damage",
                    "icon": "DMG",
                    "rarity": "rare",
                }
            )
        if self.lives < 8:
            pool.append(
                {
                    "id": "hull_patch",
                    "title": "Hull Patch",
                    "desc": "+1 life",
                    "icon": "HP",
                    "rarity": "common",
                }
            )
        pool.append(
            {
                "id": "shield_pulse",
                "title": "Shield Pulse",
                "desc": "Instant shield (4.5s)",
                "icon": "SHD",
                "rarity": "rare",
            }
        )
        pool.append(
            {
                "id": "bounty_protocol",
                "title": "Bounty Protocol",
                "desc": f"+{180 + self.wave * 15} score",
                "icon": "BNT",
                "rarity": "bonus",
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
            self.player_speed_bonus = min(4.0, self.player_speed_bonus + 0.6)
            self.player.speed = min(9.0, self._current_player_speed())
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
        card_w = 286
        card_h = 226
        gap = 28
        total_w = card_w * len(choices) + gap * max(0, len(choices) - 1)
        start_x = (settings.WIDTH - total_w) // 2
        card_y = 238
        card_rects = [
            pygame.Rect(start_x + idx * (card_w + gap), card_y, card_w, card_h)
            for idx in range(len(choices))
        ]

        def rarity_style(rarity):
            if rarity == "rare":
                return (116, 214, 255), (18, 36, 70, 232), "RARE"
            if rarity == "bonus":
                return (255, 210, 116), (50, 36, 18, 232), "BONUS"
            return (154, 176, 214), (18, 28, 52, 226), "STANDARD"

        while True:
            dt = self.clock.tick(settings.FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.MOUSEMOTION:
                    for idx, rect in enumerate(card_rects):
                        if rect.collidepoint(event.pos):
                            selected = idx
                            break
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for idx, rect in enumerate(card_rects):
                        if rect.collidepoint(event.pos):
                            self._apply_upgrade_choice(choices[idx])
                            return "selected"
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
            overlay.fill((4, 8, 18, 196))
            self.screen.blit(overlay, (0, 0))

            top_panel = pygame.Rect(settings.WIDTH // 2 - 330, 70, 660, 96)
            self._draw_glass_panel(
                top_panel,
                base_rgba=(8, 16, 34, 190),
                edge_rgba=(98, 158, 240, 140),
                highlight_rgba=(126, 194, 255, 22),
                radius=12,
            )
            title = render_text_fit(
                self.font,
                f"Wave {self.wave} cleared - choose upgrade",
                (238, 246, 255),
                top_panel.width - 56,
            )
            self.screen.blit(title, (settings.WIDTH // 2 - title.get_width() // 2, 86))
            stats = render_text_fit(
                self.small_font,
                f"Hull {self.lives}/8  |  Speed {self.player.speed:.1f}  |  Damage x{self.player_bullet_damage}  |  Cooldown {self.player._base_shoot_cooldown}ms",
                (184, 212, 246),
                top_panel.width - 56,
            )
            self.screen.blit(stats, (settings.WIDTH // 2 - stats.get_width() // 2, 122))

            for idx, choice in enumerate(choices):
                rect = card_rects[idx]
                active = idx == selected
                accent, base_col, rarity_label = rarity_style(choice.get("rarity", "common"))
                border_col = accent if active else (86, 132, 205)
                card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
                card.fill(base_col)
                if active:
                    glow = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
                    pygame.draw.rect(glow, (*accent, 42), glow.get_rect(), border_radius=12)
                    card.blit(glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
                pygame.draw.rect(card, border_col, card.get_rect(), 2 if active else 1, border_radius=12)
                pygame.draw.rect(card, (*accent, 176 if active else 108), pygame.Rect(0, 0, card_w, 5), border_radius=3)
                text_panel = pygame.Rect(12, 100, card_w - 24, 106)
                pygame.draw.rect(card, (4, 10, 22, 174), text_panel, border_radius=9)
                pygame.draw.rect(card, (*accent, 72 if active else 46), text_panel, 1, border_radius=9)

                icon_rect = pygame.Rect(18, 22, 64, 64)
                pygame.draw.rect(card, (8, 16, 30, 196), icon_rect, border_radius=10)
                pygame.draw.rect(card, (*accent, 180), icon_rect, 1, border_radius=10)
                icon = render_text_fit(self.small_font, choice.get("icon", "UPG"), accent, icon_rect.width - 10)
                card.blit(icon, (icon_rect.centerx - icon.get_width() // 2, icon_rect.centery - icon.get_height() // 2))

                key_text = render_text_fit(self.small_font, f"{idx + 1}", (226, 240, 255), 22)
                key_rect = pygame.Rect(card_w - 44, 18, 28, 28)
                pygame.draw.rect(card, (8, 16, 30, 180), key_rect, border_radius=6)
                pygame.draw.rect(card, (*accent, 140), key_rect, 1, border_radius=6)
                card.blit(key_text, (key_rect.centerx - key_text.get_width() // 2, key_rect.centery - key_text.get_height() // 2))

                rarity_rect = pygame.Rect(92, 22, card_w - 154, 25)
                pygame.draw.rect(card, (4, 10, 22, 188), rarity_rect, border_radius=7)
                pygame.draw.rect(card, (*accent, 84), rarity_rect, 1, border_radius=7)
                rarity = render_text_fit(self.notice_font, rarity_label, accent, rarity_rect.width - 12)
                title_text = render_text_fit(self.font, choice["title"], (238, 246, 255), card_w - 36)
                desc_text = render_text_fit(self.small_font, choice["desc"], (208, 228, 250), card_w - 36)
                card.blit(rarity, (rarity_rect.centerx - rarity.get_width() // 2, rarity_rect.centery - rarity.get_height() // 2))
                card.blit(title_text, (18, 112))
                pygame.draw.line(card, (118, 162, 226, 130), (18, 152), (card_w - 18, 152), 1)
                card.blit(desc_text, (18, 170))

                if active:
                    pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.008)
                    pygame.draw.rect(
                        card,
                        (*accent, int(90 + 80 * pulse)),
                        pygame.Rect(6, 6, card_w - 12, card_h - 12),
                        1,
                        border_radius=10,
                    )
                self.screen.blit(card, rect.topleft)

            hint = render_text_fit(
                self.small_font,
                "A/D or arrows select   Enter/Space confirm   Mouse supported",
                (172, 205, 242),
                settings.WIDTH - 80,
            )
            self.screen.blit(hint, (settings.WIDTH // 2 - hint.get_width() // 2, settings.HEIGHT - 86))
            pygame.display.flip()

    def _ship_selection_screen(self):
        selected = 0
        for idx, loadout in enumerate(SHIP_LOADOUTS):
            if loadout["id"] == self.selected_ship_id:
                selected = idx
                break

        card_w = 330
        card_h = 372
        gap = 34
        total_w = card_w * len(SHIP_LOADOUTS) + gap * (len(SHIP_LOADOUTS) - 1)
        start_x = settings.WIDTH // 2 - total_w // 2
        card_y = 220
        card_rects = [
            pygame.Rect(start_x + idx * (card_w + gap), card_y, card_w, card_h)
            for idx in range(len(SHIP_LOADOUTS))
        ]

        while True:
            dt = self.clock.tick(settings.FPS)
            now = pygame.time.get_ticks()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                    self._handle_window_change()
                    continue
                if event.type == pygame.MOUSEMOTION:
                    for idx, rect in enumerate(card_rects):
                        if rect.collidepoint(event.pos):
                            selected = idx
                            break
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for idx, rect in enumerate(card_rects):
                        if rect.collidepoint(event.pos):
                            self._set_selected_ship(SHIP_LOADOUTS[idx]["id"])
                            return "selected"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return "back"
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        selected = (selected - 1) % len(SHIP_LOADOUTS)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        selected = (selected + 1) % len(SHIP_LOADOUTS)
                    elif event.key in (pygame.K_1, pygame.K_KP1):
                        selected = 0
                        self._set_selected_ship(SHIP_LOADOUTS[selected]["id"])
                        return "selected"
                    elif event.key in (pygame.K_2, pygame.K_KP2):
                        selected = min(1, len(SHIP_LOADOUTS) - 1)
                        self._set_selected_ship(SHIP_LOADOUTS[selected]["id"])
                        return "selected"
                    elif event.key in (pygame.K_3, pygame.K_KP3):
                        selected = min(2, len(SHIP_LOADOUTS) - 1)
                        self._set_selected_ship(SHIP_LOADOUTS[selected]["id"])
                        return "selected"
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._set_selected_ship(SHIP_LOADOUTS[selected]["id"])
                        return "selected"

            draw_background(self.screen, self.stars, max(1, int(dt * 0.55)))
            overlay = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
            overlay.fill((3, 7, 18, 144))
            self.screen.blit(overlay, (0, 0))

            title_panel = pygame.Rect(settings.WIDTH // 2 - 390, 54, 780, 112)
            self._draw_glass_panel(
                title_panel,
                base_rgba=(8, 16, 34, 188),
                edge_rgba=(98, 158, 240, 144),
                highlight_rgba=(126, 194, 255, 24),
                radius=14,
            )
            title_font = pygame.font.SysFont(None, 46)
            title = render_text_fit(title_font, "Select Ship Frame", (240, 248, 255), title_panel.width - 56)
            subtitle = render_text_fit(
                self.small_font,
                "Local profile loadout - no online account required",
                (176, 206, 238),
                title_panel.width - 56,
            )
            self.screen.blit(title, (settings.WIDTH // 2 - title.get_width() // 2, title_panel.top + 18))
            self.screen.blit(subtitle, (settings.WIDTH // 2 - subtitle.get_width() // 2, title_panel.top + 66))

            for idx, loadout in enumerate(SHIP_LOADOUTS):
                rect = card_rects[idx]
                active = idx == selected
                accent = loadout["accent"]
                card = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                card.fill((8, 16, 34, 230))
                if active:
                    pygame.draw.rect(card, (*accent, 50), card.get_rect(), border_radius=16)
                pygame.draw.rect(card, accent if active else (84, 128, 196), card.get_rect(), 2 if active else 1, border_radius=16)
                pygame.draw.rect(card, (*accent, 190 if active else 110), pygame.Rect(0, 0, rect.width, 6), border_radius=4)

                label = render_text_fit(self.notice_font, loadout["rarity"], accent, rect.width - 88)
                key = render_text_fit(self.small_font, str(idx + 1), (230, 242, 255), 24)
                card.blit(label, (22, 22))
                key_rect = pygame.Rect(rect.width - 48, 18, 30, 30)
                pygame.draw.rect(card, (4, 10, 22, 190), key_rect, border_radius=8)
                pygame.draw.rect(card, (*accent, 140), key_rect, 1, border_radius=8)
                card.blit(key, (key_rect.centerx - key.get_width() // 2, key_rect.centery - key.get_height() // 2))

                preview = Player(width=82, height=94, style=loadout["id"]).image
                bob = int(math.sin(now * 0.002 + idx) * 5)
                glow = pygame.Surface((150, 140), pygame.SRCALPHA)
                pygame.draw.ellipse(glow, (*accent, 34), glow.get_rect())
                card.blit(glow, (rect.width // 2 - 75, 62 + bob), special_flags=pygame.BLEND_RGBA_ADD)
                card.blit(preview, (rect.width // 2 - preview.get_width() // 2, 82 + bob))

                name = render_text_fit(self.font, loadout["name"], (240, 248, 255), rect.width - 44)
                role = render_text_fit(self.small_font, loadout["role"], (194, 220, 248), rect.width - 44)
                weapon = render_text_fit(self.notice_font, loadout["weapon"], accent, rect.width - 44)
                desc = render_text_fit(self.notice_font, loadout["desc"], (188, 210, 238), rect.width - 44)
                card.blit(name, (22, 198))
                card.blit(role, (22, 232))
                card.blit(weapon, (22, 254))
                pygame.draw.line(card, (94, 142, 210, 120), (22, 262), (rect.width - 22, 262), 1)
                card.blit(desc, (22, 278))

                stats = [
                    ("SPD", f"{settings.PLAYER_SPEED + loadout['speed_bonus']:.1f}"),
                    ("DMG", f"x{loadout['damage']}"),
                    ("HULL", str(loadout["lives"])),
                    ("CD", f"{loadout['cooldown']}ms"),
                ]
                sx = 22
                sy = 318
                for stat_label, value in stats:
                    stat_rect = pygame.Rect(sx, sy, 66, 32)
                    pygame.draw.rect(card, (5, 12, 26, 180), stat_rect, border_radius=8)
                    pygame.draw.rect(card, (*accent, 95), stat_rect, 1, border_radius=8)
                    cap = render_text_fit(self.notice_font, stat_label, (148, 178, 212), stat_rect.width - 8)
                    val = render_text_fit(self.small_font, value, (230, 242, 255), stat_rect.width - 8)
                    card.blit(cap, (stat_rect.centerx - cap.get_width() // 2, stat_rect.y + 3))
                    card.blit(val, (stat_rect.centerx - val.get_width() // 2, stat_rect.y + 15))
                    sx += 72

                if active:
                    pulse = 0.5 + 0.5 * math.sin(now * 0.007)
                    pygame.draw.rect(
                        card,
                        (*accent, int(100 + 80 * pulse)),
                        pygame.Rect(8, 8, rect.width - 16, rect.height - 16),
                        1,
                        border_radius=13,
                    )
                self.screen.blit(card, rect.topleft)

            hint = render_text_fit(
                self.small_font,
                "A/D or arrows select   Enter/Space launch   Esc back   Mouse supported",
                (170, 202, 238),
                settings.WIDTH - 80,
            )
            self.screen.blit(hint, (settings.WIDTH // 2 - hint.get_width() // 2, settings.HEIGHT - 58))
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
            draw_text(self.screen, self.font, "Death Replay (5s)", 14, 12, (232, 244, 255), max_width=260)
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
            skip_label = render_text_fit(self.font, "Skip", (230, 240, 255), skip_rect.width - 12)
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
            for sprite in self._sorted_world_sprites():
                if sprite is self.player:
                    continue
                self.screen.blit(sprite.image, sprite.rect.move(cam_x, cam_y))

            pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.018)
            msg = render_text_fit(self.font, "Ship Destroyed", (255, 196, 168), settings.WIDTH - 80)
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
        enemy.enter_depth_lane(lane=self._choose_depth_lane(), wave=self.wave, now=pygame.time.get_ticks())
        self.enemies.add(enemy)
        self.all_sprites.add(enemy)

    def _draw_boss_combat_overlay(self, boss, cam_x, cam_y, now):
        if boss is None:
            return
        charge_left = int(getattr(boss, "telegraph_remaining_ms", lambda _n: 0)(now))
        if charge_left <= 0:
            return

        ratio = float(getattr(boss, "telegraph_progress", lambda _n: 0.0)(now))
        cx = boss.rect.centerx + cam_x
        cy = boss.rect.centery + cam_y
        base_r = boss.rect.width // 2 + 40
        pulse = 0.5 + 0.5 * math.sin(now * 0.02)
        ring_r = base_r + int(14 * pulse) + int(26 * ratio)
        glow_alpha = int(90 + 130 * ratio)
        ring = pygame.Surface((ring_r * 2 + 44, ring_r * 2 + 44), pygame.SRCALPHA)
        rcx = ring.get_width() // 2
        rcy = ring.get_height() // 2
        pygame.draw.circle(ring, (255, 88, 112, glow_alpha // 5), (rcx, rcy), ring_r + 22)
        pygame.draw.circle(ring, (255, 132, 132, glow_alpha // 2), (rcx, rcy), ring_r + 9, 2)
        pygame.draw.circle(ring, (255, 204, 142, glow_alpha), (rcx, rcy), ring_r, 3)
        arc_rect = pygame.Rect(rcx - ring_r, rcy - ring_r, ring_r * 2, ring_r * 2)
        sweep = max(0.35, math.tau * ratio)
        pygame.draw.arc(ring, (255, 244, 190, min(255, glow_alpha + 36)), arc_rect, -math.pi / 2, -math.pi / 2 + sweep, 6)
        for idx in range(8):
            ang = now * 0.004 + idx * math.tau / 8
            inner = ring_r - 18
            outer = ring_r + 8
            pygame.draw.line(
                ring,
                (255, 132, 132, max(40, glow_alpha // 3)),
                (int(rcx + math.cos(ang) * inner), int(rcy + math.sin(ang) * inner)),
                (int(rcx + math.cos(ang) * outer), int(rcy + math.sin(ang) * outer)),
                2,
            )
        self.screen.blit(ring, (cx - rcx, cy - rcy))

    def _draw_boss_status_panel(self, now):
        boss = self._boss_from_enemies()
        if boss is None:
            return

        bar_w = 420
        bar_h = 18
        bx = settings.WIDTH // 2 - bar_w // 2
        by = 18
        bar_bg = pygame.Rect(bx - 12, by - 8, bar_w + 24, bar_h + 34)
        self._draw_glass_panel(
            bar_bg,
            base_rgba=(24, 12, 30, 190),
            edge_rgba=(226, 132, 188, 150),
            highlight_rgba=(255, 166, 226, 30),
            radius=10,
            shadow=False,
        )
        pygame.draw.rect(self.screen, (34, 22, 44), (bx, by, bar_w, bar_h), border_radius=7)
        ratio = max(0.0, min(1.0, boss.health / max(1, boss.max_health)))
        fill_w = int((bar_w - 4) * ratio)
        pulse = 0.5 + 0.5 * math.sin(now * 0.012)
        hp_col = (238, 82 + int(36 * pulse), 128 + int(24 * pulse))
        pygame.draw.rect(self.screen, hp_col, (bx + 2, by + 2, fill_w, bar_h - 4), border_radius=5)
        pygame.draw.rect(self.screen, (255, 218, 230), (bx, by, bar_w, bar_h), 1, border_radius=7)
        draw_text(
            self.screen,
            self.font,
            f"Boss HP: {boss.health}/{boss.max_health}  Phase {getattr(boss, 'phase', 1)}",
            bx + 104,
            by - 1,
            (255, 235, 240),
            max_width=bar_w - 116,
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
                max_width=bar_w - 100,
            )
            charge_w = 230
            charge_x = bx + 95
            charge_y = by + 38
            pygame.draw.rect(self.screen, (42, 26, 36), (charge_x, charge_y, charge_w, 8), border_radius=4)
            fill = int((charge_w - 2) * max(0.0, min(1.0, charge_ratio)))
            pygame.draw.rect(self.screen, (255, 124, 120), (charge_x + 1, charge_y + 1, fill, 6), border_radius=3)
        else:
            attack_eta = max(0, int(getattr(boss, "next_attack_at", 0) - now))
            if attack_eta <= 260:
                draw_text(
                    self.screen,
                    self.small_font,
                    "Incoming attack!",
                    bx + 150,
                    by + 20,
                    (255, 198, 160),
                    max_width=bar_w - 160,
                )

    def _draw_gameplay_frame(self, dt, now):
        draw_background(self.screen, self.stars, dt)
        cam_x, cam_y = self._consume_camera_offset(dt)
        self._draw_depth_entry_wakes(now, cam_x=cam_x, cam_y=cam_y)

        if settings.BULLET_TRAIL_LENGTH > 0:
            for bullet in self.bullets:
                self._draw_player_bullet_trail(bullet, cam_x=cam_x, cam_y=cam_y)

        world_sprites = self._sorted_world_sprites()
        for sprite in world_sprites:
            self._draw_sprite_depth_shadow(sprite, cam_x=cam_x, cam_y=cam_y)
        for effect in tuple(self.effects):
            self.screen.blit(effect.image, effect.rect.move(cam_x, cam_y))
        for sprite in world_sprites:
            self.combat.draw_world_sprite(sprite, cam_x=cam_x, cam_y=cam_y, now=now)
        if self.player.shield:
            self.player.draw_shield(self.screen, cam_x=cam_x, cam_y=cam_y, now=now)

        self._draw_boss_combat_overlay(self._boss_from_enemies(), cam_x, cam_y, now)
        self._draw_damage_flash(now)
        self._draw_modern_hud(now)
        self._draw_boss_status_panel(now)

    def _choose_depth_lane(self):
        lanes = (-2, -1, 0, 1, 2)
        active_counts = {lane: 0 for lane in lanes}
        for enemy in self.enemies:
            if getattr(enemy, "depth_intro_active", False):
                lane = max(-2, min(2, int(getattr(enemy, "depth_lane", 0))))
                active_counts[lane] += 1
        least_loaded = min(active_counts.values())
        candidates = [lane for lane, count in active_counts.items() if count == least_loaded]
        if 0 in candidates and random.random() < 0.35:
            return 0
        return random.choice(candidates)

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

            ship_result = self._ship_selection_screen()
            if ship_result == "quit":
                self.should_quit = True
                break
            if ship_result == "back":
                continue

            while not self.should_quit:
                self._reset_round()
                outcome = self.gameplay_loop()

                if outcome == "restart":
                    continue
                if outcome == "victory":
                    if self.prompt_and_save_score() == "quit":
                        self.should_quit = True
                        break
                    if self.victory_screen() == "quit":
                        self.should_quit = True
                    break
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
                    self._emit_muzzle_fx(fired)

            self.player.update(dt, keys)
            self._emit_engine_trail(now)
            for sprite in tuple(self.all_sprites):
                if sprite is self.player:
                    continue
                sprite.update(dt)
            for effect in tuple(self.effects):
                effect.update(dt)

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

            self.combat.resolve_player_bullet_hits(now)
            if self.combat.resolve_player_enemy_collisions(now):
                return self._finish_game_over_with_animation()

            if self.pending_wave_advance and len(self.enemies) == 0:
                if self.wave >= self.run_final_wave:
                    return self._finish_round("victory")
                upg_result = self._upgrade_selection_screen()
                if upg_result == "quit":
                    return self._finish_round("quit")
                self._advance_wave()
            self._update_combo_timeout(now)

            self.combat.resolve_powerup_pickups()
            if self.combat.resolve_enemy_bullet_hits(now):
                return self._finish_game_over_with_animation()

            self._draw_gameplay_frame(dt, now)

            self._capture_replay_frame(pygame.time.get_ticks())
            pygame.display.flip()

        return self._finish_round("menu")

    def prompt_and_save_score(self):
        name = ""
        max_len = 16
        prompt_font = pygame.font.SysFont(None, 32)
        while True:
            self.clock.tick(settings.FPS)
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
            prompt = render_text_fit(
                prompt_font,
                "Enter highscore name (Enter save, Esc skip):",
                (200, 200, 200),
                settings.WIDTH - 80,
            )
            self.screen.blit(
                prompt,
                (settings.WIDTH // 2 - prompt.get_width() // 2, settings.HEIGHT // 2 - 50),
            )

            shown_name = normalize_player_name(name) if name.strip() else name
            name_surface = render_text_fit(prompt_font, shown_name, (255, 255, 255), settings.WIDTH - 120)
            self.screen.blit(
                name_surface,
                (settings.WIDTH // 2 - name_surface.get_width() // 2, settings.HEIGHT // 2),
            )

            limit = render_text_fit(self.font, f"{len(name)}/{max_len}", (170, 170, 170), 120)
            self.screen.blit(limit, (settings.WIDTH // 2 - limit.get_width() // 2, settings.HEIGHT // 2 + 40))
            pygame.display.flip()

    def game_over_screen(self):
        over_font = pygame.font.SysFont(None, 64)
        small = pygame.font.SysFont(None, 28)
        self.screen.fill((0, 0, 0))
        text = render_text_fit(over_font, "GAME OVER", (220, 50, 50), settings.WIDTH - 80)
        sub = render_text_fit(small, f"Score: {self.score} - press any key to return", (255, 255, 255), settings.WIDTH - 80)
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

    def victory_screen(self):
        title_font = pygame.font.SysFont(None, 72)
        headline_font = pygame.font.SysFont(None, 34)
        small = pygame.font.SysFont(None, 24)
        panel_rect = pygame.Rect(settings.WIDTH // 2 - 260, settings.HEIGHT // 2 - 152, 520, 304)

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
                    return "menu"
                if event.type == pygame.MOUSEBUTTONDOWN:
                    return "menu"

            draw_background(self.screen, self.stars, dt)
            veil = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
            veil.fill((0, 0, 0, 94))
            self.screen.blit(veil, (0, 0))
            self._draw_glass_panel(
                panel_rect,
                base_rgba=(8, 16, 34, 202),
                edge_rgba=(112, 210, 255, 160),
                highlight_rgba=(130, 230, 255, 28),
                radius=12,
            )

            title = render_text_fit(title_font, "RUN COMPLETE", (230, 248, 255), panel_rect.width - 56)
            self.screen.blit(title, (settings.WIDTH // 2 - title.get_width() // 2, panel_rect.top + 30))
            subtitle = render_text_fit(headline_font, "Command Spire cleared", (255, 222, 146), panel_rect.width - 56)
            self.screen.blit(subtitle, (settings.WIDTH // 2 - subtitle.get_width() // 2, panel_rect.top + 92))

            loadout = self._ship_loadout()
            rows = [
                f"Score: {self.score:08d}",
                f"Ship: {loadout['name']} / {loadout['weapon']}",
                f"Operation: {self.run_final_wave}/{self.run_final_wave} waves",
                "Press any key or click to return to menu",
            ]
            y = panel_rect.top + 150
            for i, row in enumerate(rows):
                color = (214, 232, 252) if i < len(rows) - 1 else (152, 184, 220)
                text = render_text_fit(small, row, color, panel_rect.width - 56)
                self.screen.blit(text, (settings.WIDTH // 2 - text.get_width() // 2, y))
                y += 34

            pygame.display.flip()

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
            panel_w = min(700, max(520, sw - 140))
            panel_h = min(560, max(470, sh - 120))
            panel = pygame.Rect(sw // 2 - panel_w // 2, sh // 2 - panel_h // 2, panel_w, panel_h)

            panel_surf = pygame.Surface((panel.width, panel.height), pygame.SRCALPHA)
            panel_surf.fill((8, 14, 30, 196))
            pygame.draw.rect(panel_surf, (90, 142, 220, 176), panel_surf.get_rect(), 2, border_radius=14)
            self.screen.blit(panel_surf, panel.topleft)

            title = render_text_fit(self.font, "Options", (242, 244, 255), panel.width - 68)
            self.screen.blit(title, (sw // 2 - title.get_width() // 2, panel.top + 16))
            profile = render_text_fit(
                self.small_font,
                f"{settings.VISUAL_QUALITY} | {settings.DIFFICULTY} | cap {settings.FPS} | vol {int(self.master_volume * 100)}%",
                (176, 198, 228),
                panel.width - 68,
            )
            self.screen.blit(profile, (sw // 2 - profile.get_width() // 2, panel.top + 46))

            row_rects = {}
            left_buttons = {}
            right_buttons = {}
            start_y = panel.top + 88
            row_gap = 44
            row_h = 36
            for i, opt in enumerate(options):
                is_selected = i == idx
                row_rect = pygame.Rect(panel.left + 34, start_y + i * row_gap, panel.width - 68, row_h)
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
                    ltxt = render_text_fit(self.small_font, "<", (210, 228, 255), 18)
                    rtxt = render_text_fit(self.small_font, ">", (210, 228, 255), 18)
                    self.screen.blit(ltxt, (lrect.centerx - ltxt.get_width() // 2, lrect.centery - ltxt.get_height() // 2))
                    self.screen.blit(rtxt, (rrect.centerx - rtxt.get_width() // 2, rrect.centery - rtxt.get_height() // 2))

                text = render_text_fit(
                    self.font,
                    option_label(opt),
                    (255, 232, 146) if is_selected else (220, 232, 248),
                    row_rect.width - (94 if opt in adjustable else 24),
                )
                self.screen.blit(text, (row_rect.centerx - text.get_width() // 2, row_rect.centery - text.get_height() // 2))

            selected_opt = options[idx]
            desc = descriptions.get(selected_opt, "")
            desc_rect = pygame.Rect(panel.left + 34, panel.bottom - 94, panel.width - 68, 42)
            desc_surf = pygame.Surface((desc_rect.width, desc_rect.height), pygame.SRCALPHA)
            desc_surf.fill((10, 20, 40, 172))
            pygame.draw.rect(desc_surf, (98, 142, 210, 120), desc_surf.get_rect(), 1, border_radius=8)
            self.screen.blit(desc_surf, desc_rect.topleft)
            dimg = render_text_fit(self.small_font, desc, (206, 226, 250), desc_rect.width - 22)
            self.screen.blit(dimg, (desc_rect.centerx - dimg.get_width() // 2, desc_rect.centery - dimg.get_height() // 2))

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

            hint = render_text_fit(
                self.small_font,
                "Arrows/WASD navigate, Q/E change, Enter apply, mouse click, R reset, F11 fullscreen, Esc back",
                (152, 176, 208),
                panel.width - 68,
            )
            self.screen.blit(hint, (sw // 2 - hint.get_width() // 2, panel.bottom - 20))
            tag = render_text_fit(self.notice_font, self.notice_text, (120, 138, 164), sw - 16)
            self.screen.blit(tag, (8, sh - 16))
            pygame.display.flip()


def run():
    Game().run()
