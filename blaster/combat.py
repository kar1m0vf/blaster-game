import pygame

from .entities import Explosion, FloatingText

PLAYER_HIT_INVULNERABILITY_MS = 1050


class CombatSystem:
    def __init__(self, game, invulnerability_ms=PLAYER_HIT_INVULNERABILITY_MS):
        self.game = game
        self.invulnerability_ms = int(invulnerability_ms)

    def reset_round_state(self):
        self.game.player_invulnerable_until = 0
        self.game.invulnerable_fx_last_at = 0

    def player_is_invulnerable(self, now=None):
        now = pygame.time.get_ticks() if now is None else int(now)
        return now < getattr(self.game, "player_invulnerable_until", 0)

    def grant_player_invulnerability(self, now=None, duration_ms=None):
        now = pygame.time.get_ticks() if now is None else int(now)
        duration_ms = self.invulnerability_ms if duration_ms is None else int(duration_ms)
        self.game.player_invulnerable_until = max(
            getattr(self.game, "player_invulnerable_until", 0),
            now + max(0, duration_ms),
        )

    def emit_invulnerability_glance(self, now):
        game = self.game
        if now - getattr(game, "invulnerable_fx_last_at", 0) < 160:
            return
        game.invulnerable_fx_last_at = now
        game._emit_burst_fx(game.player.rect.center, kind="shield", count=4)

    def apply_player_damage(
        self,
        now,
        explosion_lifetime=420,
        burst_count=12,
        shake_strength=3,
        shake_duration_ms=110,
    ):
        game = self.game
        if self.player_is_invulnerable(now):
            self.emit_invulnerability_glance(now)
            return False

        game._reset_combo(show_text=True)
        game.lives -= 1
        self.grant_player_invulnerability(now)
        expl = Explosion(game.player.rect.center, lifetime=explosion_lifetime)
        game.explosions.add(expl)
        game.all_sprites.add(expl)
        game._emit_burst_fx(game.player.rect.center, kind="player", count=burst_count)
        game.damage_flash_until = now + 180
        game._play_sound("hit")
        game._start_shake(shake_strength, duration_ms=shake_duration_ms)
        return game.lives <= 0

    def draw_world_sprite(self, sprite, cam_x=0, cam_y=0, now=None):
        game = self.game
        if sprite is game.player and self.player_is_invulnerable(now):
            now = pygame.time.get_ticks() if now is None else int(now)
            phase = (now // 75) % 4
            image = sprite.image.copy()
            image.set_alpha(112 if phase in (0, 2) else 220)
            game.screen.blit(image, sprite.rect.move(cam_x, cam_y))
            return
        game.screen.blit(sprite.image, sprite.rect.move(cam_x, cam_y))

    def resolve_player_bullet_hits(self, now):
        game = self.game
        hits = pygame.sprite.groupcollide(game.enemies, game.bullets, False, False)
        for enemy, hit_bullets in hits.items():
            if hasattr(enemy, "is_targetable") and not enemy.is_targetable():
                continue
            processed_bullets = []
            for bullet in hit_bullets:
                if not bullet.alive():
                    continue
                processed_bullets.append(bullet)
                if hasattr(bullet, "register_hit"):
                    bullet.register_hit()
                else:
                    bullet.kill()
            if not processed_bullets:
                continue
            hit_centers = [bullet.rect.center for bullet in processed_bullets]
            incoming = sum(max(1, int(getattr(bullet, "damage", 1))) for bullet in processed_bullets)
            incoming *= game.player_bullet_damage
            blocked = False
            if hasattr(enemy, "absorb_player_damage"):
                _effective, blocked = enemy.absorb_player_damage(incoming, now=now)
            else:
                enemy.health -= incoming
            for center in hit_centers:
                game._emit_burst_fx(center, kind="armor" if blocked else "impact", count=3)
            if blocked:
                ft = FloatingText(
                    enemy.rect.centerx,
                    enemy.rect.centery - 10,
                    "ARMOR",
                    color=(178, 234, 255),
                    lifetime=460,
                )
                game.floating.add(ft)
                game.all_sprites.add(ft)
            if enemy.health <= 0:
                game._handle_enemy_defeat(enemy, allow_powerup_drop=True)

    def resolve_player_enemy_collisions(self, now):
        game = self.game
        hits = pygame.sprite.spritecollide(game.player, game.enemies, False, pygame.sprite.collide_rect)
        hits = [enemy for enemy in hits if not hasattr(enemy, "is_targetable") or enemy.is_targetable()]
        if not hits:
            return False

        if game.player.shield:
            for enemy in hits:
                if getattr(enemy, "is_boss", False):
                    enemy.health -= 3
                    if enemy.health <= 0:
                        game._handle_enemy_defeat(enemy, allow_powerup_drop=False)
                    else:
                        game._start_shake(3, duration_ms=90)
                else:
                    game._handle_enemy_defeat(enemy, allow_powerup_drop=False)
            ft = FloatingText(game.player.rect.centerx, game.player.rect.top, "BLOCK!", (120, 220, 255))
            game.floating.add(ft)
            game.all_sprites.add(ft)
            game._emit_burst_fx(game.player.rect.center, kind="shield", count=10)
            game._play_sound("hit")
            game._start_shake(2, duration_ms=80)
            return False

        if self.player_is_invulnerable(now):
            self.emit_invulnerability_glance(now)
            return False

        took_damage = False
        for enemy in hits:
            if not getattr(enemy, "is_boss", False):
                enemy.kill()
            took_damage = True
        if not took_damage:
            return False
        return self.apply_player_damage(
            now,
            explosion_lifetime=500,
            burst_count=14,
            shake_strength=4,
            shake_duration_ms=140,
        )

    def resolve_powerup_pickups(self):
        game = self.game
        powerup_hits = pygame.sprite.spritecollide(game.player, game.powerups, True)
        for pu in powerup_hits:
            game.player.apply_powerup(pu.ptype)
            ft = FloatingText(
                game.player.rect.centerx,
                game.player.rect.top,
                f"{pu.ptype.upper()}!",
                (255, 220, 120),
            )
            game.floating.add(ft)
            game.all_sprites.add(ft)
            game._emit_burst_fx(
                game.player.rect.center,
                kind="shield" if pu.ptype == "shield" else "impact",
                count=8,
            )
            game._play_sound("hit")

    def resolve_enemy_bullet_hits(self, now):
        game = self.game
        enemy_bullet_hits = pygame.sprite.spritecollide(game.player, game.enemy_bullets, True)
        if not enemy_bullet_hits:
            return False

        if game.player.shield:
            ft = FloatingText(game.player.rect.centerx, game.player.rect.top, "DEFLECT", (170, 235, 255), lifetime=700)
            game.floating.add(ft)
            game.all_sprites.add(ft)
            game._emit_burst_fx(game.player.rect.center, kind="shield", count=8)
            game._start_shake(1, duration_ms=70)
            return False

        if self.player_is_invulnerable(now):
            self.emit_invulnerability_glance(now)
            return False

        return self.apply_player_damage(
            now,
            explosion_lifetime=420,
            burst_count=12,
            shake_strength=3,
            shake_duration_ms=110,
        )
