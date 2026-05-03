import pygame

from blaster.entities import BossEnemy, Enemy, Player, ShooterEnemy


def test_player_shoot_respects_cooldown_and_double_mode():
    player = Player()
    bullets = pygame.sprite.Group()
    all_sprites = pygame.sprite.Group()
    all_sprites.add(player)

    fired = player.shoot(1000, bullets, all_sprites)
    assert fired == 1
    assert len(bullets) == 1

    fired = player.shoot(1100, bullets, all_sprites)
    assert fired == 0
    assert len(bullets) == 1

    player.double_end = 10_000
    fired = player.shoot(1300, bullets, all_sprites)
    assert fired == 2
    assert len(bullets) == 3

    xs = sorted(b.rect.centerx for b in bullets)
    assert xs[1] != xs[2]


def test_player_ship_weapon_profiles_create_distinct_bullets():
    cases = [
        ("interceptor", 2, "interceptor", 0),
        ("vanguard", 1, "vanguard", 0),
        ("lancer", 1, "lancer", 1),
    ]

    for style, expected_count, expected_variant, expected_pierce in cases:
        player = Player(style=style)
        bullets = pygame.sprite.Group()
        all_sprites = pygame.sprite.Group(player)

        fired = player.shoot(1000, bullets, all_sprites)
        assert fired == expected_count
        assert len(bullets) == expected_count
        assert {b.variant for b in bullets} == {expected_variant}
        assert all(b.pierce_remaining == expected_pierce for b in bullets)


def test_boss_enemy_stats_scale_by_wave():
    boss_w4 = BossEnemy(wave=4)
    boss_w8 = BossEnemy(wave=8)
    assert boss_w4.is_boss is True
    assert boss_w8.max_health > boss_w4.max_health
    assert boss_w8.score_reward > boss_w4.score_reward


def test_boss_enemy_attacks_and_changes_phase():
    boss = BossEnemy(wave=4)
    bullets = pygame.sprite.Group()
    all_sprites = pygame.sprite.Group(boss)

    boss.next_attack_at = 0
    fired, phase_changed = boss.maybe_attack(10_000, bullets, all_sprites, player_x=420)
    assert fired > 0
    assert len(bullets) == fired
    assert phase_changed is None

    boss.health = int(boss.max_health * 0.62)
    boss.next_attack_at = 0
    fired2, phase_changed2 = boss.maybe_attack(11_000, bullets, all_sprites, player_x=420)
    assert fired2 > 0
    assert phase_changed2 == 2

    boss.health = int(boss.max_health * 0.30)
    boss.next_attack_at = 0
    fired3, phase_changed3 = boss.maybe_attack(12_000, bullets, all_sprites, player_x=420)
    assert fired3 > 0
    assert phase_changed3 == 3


def test_boss_enemy_heavy_attack_has_telegraph_then_fires():
    boss = BossEnemy(wave=6)
    bullets = pygame.sprite.Group()
    all_sprites = pygame.sprite.Group(boss)

    boss.health = int(boss.max_health * 0.60)  # phase 2
    boss.attack_index = 2  # phase 2 pattern 2 -> rain -> telegraphed
    boss.next_attack_at = 0

    fired, _ = boss.maybe_attack(20_000, bullets, all_sprites, player_x=420)
    assert fired == 0
    assert boss.telegraph_remaining_ms(20_000) > 0

    fired2, _ = boss.maybe_attack(boss.telegraph_until, bullets, all_sprites, player_x=420)
    assert fired2 > 0
    assert len(bullets) >= fired2


def test_enemy_promote_elite_increases_stats_once():
    enemy = Enemy(etype="orb")
    base_health = enemy.health
    base_score = enemy.score_reward
    base_speed = enemy.speedy

    enemy.promote_elite(wave=6, role="raider")
    assert enemy.is_elite is True
    assert enemy.health > base_health
    assert enemy.max_health == enemy.health
    assert enemy.score_reward > base_score
    assert enemy.speedy > base_speed

    hp_after_first = enemy.health
    score_after_first = enemy.score_reward
    speed_after_first = enemy.speedy
    enemy.promote_elite(wave=9)
    assert enemy.health == hp_after_first
    assert enemy.score_reward == score_after_first
    assert enemy.speedy == speed_after_first


def test_enemy_elite_bulwark_blocks_part_of_damage():
    enemy = Enemy(etype="saucer")
    enemy.promote_elite(wave=7, role="bulwark")
    hp_before = enemy.health

    effective, blocked = enemy.absorb_player_damage(2, now=12_000)
    assert blocked is True
    assert effective == 1
    assert enemy.health == hp_before - 1


def test_enemy_elite_sniper_shoots_enemy_bullet():
    enemy = Enemy(etype="drone")
    enemy.promote_elite(wave=7, role="sniper")
    enemy.rect.y = 96
    enemy.next_shot_at = 0

    bullets = pygame.sprite.Group()
    all_sprites = pygame.sprite.Group(enemy)
    fired = enemy.maybe_shoot(15_000, bullets, all_sprites, player_x=430)

    assert fired is True
    assert len(bullets) == 1
    bullet = next(iter(bullets))
    assert getattr(bullet, "from_enemy", False) is True


def test_enemy_depth_entry_scales_then_returns_to_normal():
    enemy = Enemy(etype="orb")
    base_width = enemy._frames[enemy._frame_idx].get_width()

    enemy.enter_depth_lane(lane=-1, wave=4, now=10_000)
    far_width = enemy.image.get_width()
    assert enemy.depth_intro_active is True
    assert enemy.is_targetable() is False
    assert far_width < base_width

    enemy._depth_started_at = pygame.time.get_ticks() - enemy._depth_duration_ms // 2
    enemy.update(16)
    assert enemy.image.get_width() > far_width
    assert enemy.is_targetable() is True
    assert enemy._depth_ready_flash_until > pygame.time.get_ticks()

    enemy._depth_started_at = pygame.time.get_ticks() - int(enemy._depth_duration_ms * 0.20)
    enemy._depth_ready_announced = False
    enemy._depth_ready_flash_until = 0
    enemy.update(16)
    assert enemy.is_targetable() is False

    enemy._depth_started_at = pygame.time.get_ticks() - enemy._depth_duration_ms - 1
    enemy.update(16)
    assert enemy.depth_intro_active is False
    assert enemy.image.get_width() == base_width


def test_shooter_enemy_settles_and_shoots():
    shooter = ShooterEnemy(wave=3, start_x=120, target_y=80)
    bullets = pygame.sprite.Group()
    all_sprites = pygame.sprite.Group(shooter)

    for _ in range(200):
        shooter.update(16)

    assert shooter.rect.y >= 78
    shooter.next_shot_at = 0
    fired = shooter.maybe_shoot(10_000, bullets, all_sprites)
    assert fired is True
    assert len(bullets) == 1
    bullet = next(iter(bullets))
    assert getattr(bullet, "from_enemy", False) is True
