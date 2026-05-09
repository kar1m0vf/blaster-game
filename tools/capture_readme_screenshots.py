import os
import random
import sys
from pathlib import Path

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pygame

from blaster import menu, settings
from blaster.entities import BossEnemy, Bullet, Enemy, EnemyBullet, FloatingText, Particle, PowerUp, ShooterEnemy
from blaster.main import Game


MEDIA_DIR = ROOT / "docs" / "media"


def _configure_capture_defaults():
    random.seed(1427)
    settings.set_visual_quality("Enhanced")
    settings.set_difficulty("Normal")
    settings.set_fps_cap(60)
    settings.set_show_fps(False)


def _make_game():
    _configure_capture_defaults()
    game = Game()
    _configure_capture_defaults()
    game.selected_ship_id = "vanguard"
    game._reset_round(start_timers=False)
    game.shake_time_left = 0
    game.shake_strength = 0
    return game


def _save(screen, filename):
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    pygame.image.save(screen, str(MEDIA_DIR / filename))


def _sync_sprite(sprite):
    if hasattr(sprite, "pos_x"):
        sprite.pos_x = float(sprite.rect.x)
    if hasattr(sprite, "pos_y"):
        sprite.pos_y = float(sprite.rect.y)
    return sprite


def _add_sprite(game, sprite, *groups):
    game.all_sprites.add(sprite)
    for group in groups:
        group.add(sprite)
    return sprite


def _enemy(etype, center, wave=3, elite_role=None):
    enemy = Enemy(etype=etype)
    enemy.wave = wave
    enemy.rect.center = center
    if elite_role:
        enemy.promote_elite(wave=wave, role=elite_role)
    return _sync_sprite(enemy)


def _bullet(x, y, variant="standard", trail_len=4):
    bullet = Bullet(x, y, variant=variant)
    bullet.rect.center = (x, y)
    bullet.trail_points = [(x, y + offset) for offset in range(62, 8, -max(1, 54 // max(1, trail_len)))]
    return _sync_sprite(bullet)


def capture_menu(game):
    menu.draw_menu(
        game.screen,
        game.font,
        "Blaster",
        ["Start Game", "Options", "High Scores", "Quit"],
        0,
        dt=16,
        subtitle="Enhanced visuals | Normal | cap 60",
        descriptions={"Start Game": "Launch a new run with your current difficulty and visual preset."},
        footer_hint="W/S or arrows, Enter, mouse, wheel. Quick keys: 1/2/3/4",
    )
    _save(game.screen, "preview-menu.png")


def capture_battle(game):
    game._reset_round(start_timers=False)
    game.wave = 3
    game.wave_target_kills = 16
    game.wave_kills = 9
    game.score = 24750
    game.lives = 4
    game.combo_chain = 6
    game.combo_multiplier = game._combo_multiplier_for_chain(game.combo_chain)
    game.combo_last_kill_at = pygame.time.get_ticks()
    game.player.apply_powerup("shield", duration_ms=7000)
    game.player.apply_powerup("double", duration_ms=5200)

    game.player.rect.centerx = settings.WIDTH // 2
    game.player.rect.bottom = settings.HEIGHT - 24
    _sync_sprite(game.player)

    for enemy in (
        _enemy("orb", (310, 160), wave=3),
        _enemy("drone", (520, 220), wave=3, elite_role="raider"),
        _enemy("saucer", (790, 150), wave=3),
        _enemy("spiky", (960, 260), wave=3),
    ):
        _add_sprite(game, enemy, game.enemies)

    shooter = ShooterEnemy(wave=3, start_x=1120, target_y=92)
    shooter.rect.center = (1120, 96)
    _sync_sprite(shooter)
    _add_sprite(game, shooter, game.enemies)

    for x, y, variant in (
        (590, 430, "vanguard"),
        (640, 385, "vanguard"),
        (690, 440, "vanguard"),
    ):
        _add_sprite(game, _bullet(x, y, variant=variant), game.bullets)

    for x, y, speedx in ((380, 310, 0.3), (845, 340, -0.25), (1035, 380, -0.1)):
        enemy_bullet = EnemyBullet(x, y, speed=4.2, speedx=speedx)
        _add_sprite(game, enemy_bullet, game.enemy_bullets)

    powerup = PowerUp(1090, 470, ptype="rapid")
    _add_sprite(game, powerup, game.powerups)

    for center, color in (((520, 220), (255, 210, 120)), ((790, 150), (120, 220, 255))):
        game.effects.add(Particle(center[0], center[1], vel=(0, 0), color=color, life=700, size=9, shape="ring"))

    label = FloatingText(settings.WIDTH // 2, 112, "Sector 2: Neon Belt", color=(150, 210, 255), lifetime=1200)
    _add_sprite(game, label, game.floating)

    game._draw_gameplay_frame(16, pygame.time.get_ticks())
    _save(game.screen, "preview-battle.png")


def capture_boss(game):
    game._reset_round(start_timers=False)
    game.wave = 4
    game.wave_target_kills = 1
    game.score = 46820
    game.lives = 3
    game.combo_chain = 3
    game.combo_multiplier = game._combo_multiplier_for_chain(game.combo_chain)
    game.combo_last_kill_at = pygame.time.get_ticks()

    game.player.rect.centerx = settings.WIDTH // 2
    game.player.rect.bottom = settings.HEIGHT - 24
    _sync_sprite(game.player)

    now = pygame.time.get_ticks()
    boss = BossEnemy(wave=4)
    boss.rect.center = (settings.WIDTH // 2, 145)
    boss.pos_x = float(boss.rect.x)
    boss.pos_y = float(boss.rect.y)
    boss.health = int(boss.max_health * 0.58)
    boss.phase = 2
    boss.telegraph_duration = 1000
    boss.telegraph_started_at = now - 440
    boss.telegraph_until = now + 560
    boss.telegraph_kind = "rain"
    boss._pending_phase = 2
    boss._pending_pattern = 2
    _add_sprite(game, boss, game.enemies)
    game.boss_active = True
    game.boss_spawned_for_wave = True

    for enemy in (
        _enemy("drone", (310, 270), wave=4),
        _enemy("spiky", (980, 285), wave=4, elite_role="bulwark"),
    ):
        _add_sprite(game, enemy, game.enemies)

    for x, y in ((594, 408), (640, 392), (686, 408)):
        _add_sprite(game, _bullet(x, y, variant="vanguard"), game.bullets)

    for x, y, speedx in ((560, 300, -0.45), (620, 320, -0.15), (700, 320, 0.15), (760, 300, 0.45)):
        enemy_bullet = EnemyBullet(x, y, speed=4.4, speedx=speedx, color=(255, 96, 136), core_color=(255, 206, 224))
        _add_sprite(game, enemy_bullet, game.enemy_bullets)

    game.effects.add(Particle(settings.WIDTH // 2, 145, vel=(0, 0), color=(255, 140, 150), life=900, size=15, shape="ring"))

    game._draw_gameplay_frame(16, now)
    _save(game.screen, "preview-boss.png")


def main():
    game = _make_game()
    try:
        capture_menu(game)
        capture_battle(game)
        capture_boss(game)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
