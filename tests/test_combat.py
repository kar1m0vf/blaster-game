import pygame

from blaster.combat import CombatSystem
from blaster.entities import Bullet, Enemy, EnemyBullet, Player
from blaster import settings


class FakeGame:
    def __init__(self):
        self.player = Player()
        self.all_sprites = pygame.sprite.Group(self.player)
        self.explosions = pygame.sprite.Group()
        self.floating = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.enemy_bullets = pygame.sprite.Group()
        self.powerups = pygame.sprite.Group()
        self.player_bullet_damage = 1
        self.lives = 2
        self.damage_flash_until = 0
        self.player_invulnerable_until = 0
        self.invulnerable_fx_last_at = 0
        self.screen = pygame.Surface((settings.WIDTH, settings.HEIGHT))
        self.combo_resets = 0
        self.burst_events = []
        self.played_sounds = []
        self.shakes = []
        self.defeated = []

    def _reset_combo(self, show_text=False):
        self.combo_resets += 1

    def _emit_burst_fx(self, center, kind="impact", count=None):
        self.burst_events.append((center, kind, count))

    def _play_sound(self, key):
        self.played_sounds.append(key)

    def _start_shake(self, strength, duration_ms=120):
        self.shakes.append((strength, duration_ms))

    def _handle_enemy_defeat(self, enemy, allow_powerup_drop=True, combo_eligible=True):
        self.defeated.append((enemy, allow_powerup_drop, combo_eligible))
        enemy.kill()


def test_apply_player_damage_grants_invulnerability():
    game = FakeGame()
    combat = CombatSystem(game, invulnerability_ms=1000)
    combat.reset_round_state()

    game_over = combat.apply_player_damage(10_000)

    assert game_over is False
    assert game.lives == 1
    assert game.player_invulnerable_until == 11_000
    assert game.damage_flash_until == 10_180
    assert len(game.explosions) == 1
    assert game.played_sounds == ["hit"]

    game_over_while_invulnerable = combat.apply_player_damage(10_200)
    assert game_over_while_invulnerable is False
    assert game.lives == 1

    game_over_after_window = combat.apply_player_damage(11_100)
    assert game_over_after_window is True
    assert game.lives == 0


def test_enemy_bullet_hit_consumes_bullet_but_respects_invulnerability():
    game = FakeGame()
    combat = CombatSystem(game, invulnerability_ms=1000)
    combat.reset_round_state()
    combat.grant_player_invulnerability(10_000)

    bullet = EnemyBullet(game.player.rect.centerx, game.player.rect.centery)
    game.enemy_bullets.add(bullet)
    game.all_sprites.add(bullet)

    game_over = combat.resolve_enemy_bullet_hits(10_200)

    assert game_over is False
    assert game.lives == 2
    assert len(game.enemy_bullets) == 0
    assert any(event[1] == "shield" for event in game.burst_events)


def test_player_bullet_hit_defeats_enemy_through_combat_system():
    game = FakeGame()
    combat = CombatSystem(game)
    enemy = Enemy(etype="orb")
    enemy.rect.center = (420, 180)
    bullet = Bullet(enemy.rect.centerx, enemy.rect.centery)
    game.enemies.add(enemy)
    game.bullets.add(bullet)
    game.all_sprites.add(enemy, bullet)

    combat.resolve_player_bullet_hits(10_000)

    assert not enemy.alive()
    assert not bullet.alive()
    assert game.defeated and game.defeated[0][0] is enemy
    assert any(event[1] == "impact" for event in game.burst_events)
