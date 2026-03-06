
import pygame
import random
import sys
import math
import wave
import struct
import os

# == Настройки ==
WIDTH, HEIGHT = 800, 600
FPS = 60
PLAYER_SPEED = 5
BULLET_SPEED = 9
# По умолчанию параметры будут подставлены через пресеты сложности
ENEMY_SPEED_MIN = 1
ENEMY_SPEED_MAX = 3
ENEMY_SPAWN_TIME = 800  # мс
MAX_ENEMIES = 10

# Уровни сложности и их пресеты. Можно изменить значения здесь.
DIFFICULTY = 'Normal'  # 'Easy' | 'Normal' | 'Hard'
DIFFICULTY_PRESETS = {
    'Easy': {
        'ENEMY_SPEED_MIN': 0.6,
        'ENEMY_SPEED_MAX': 1.5,
        'ENEMY_SPAWN_TIME': 1200,
        'MAX_ENEMIES': 6,
        'BULLET_SPEED': 10,
        'PLAYER_SPEED': 6,
    },
    'Normal': {
        'ENEMY_SPEED_MIN': 1.0,
        'ENEMY_SPEED_MAX': 3.0,
        'ENEMY_SPAWN_TIME': 800,
        'MAX_ENEMIES': 10,
        'BULLET_SPEED': 9,
        'PLAYER_SPEED': 5,
    },
    'Hard': {
        'ENEMY_SPEED_MIN': 1.8,
        'ENEMY_SPEED_MAX': 4.2,
        'ENEMY_SPAWN_TIME': 500,
        'MAX_ENEMIES': 14,
        'BULLET_SPEED': 8,
        'PLAYER_SPEED': 5,
    },
}


def set_difficulty(level):
    """Установить пресет сложности: обновляет глобальные параметры и таймер спавна.
    Можно вызывать до или после создания объектов; функция аккуратно проверяет существование объектов.
    """
    global ENEMY_SPEED_MIN, ENEMY_SPEED_MAX, ENEMY_SPAWN_TIME, MAX_ENEMIES, BULLET_SPEED, PLAYER_SPEED, DIFFICULTY
    if level not in DIFFICULTY_PRESETS:
        print(f"Unknown difficulty '{level}', keeping {DIFFICULTY}")
        return
    DIFFICULTY = level
    p = DIFFICULTY_PRESETS[level]
    ENEMY_SPEED_MIN = p['ENEMY_SPEED_MIN']
    ENEMY_SPEED_MAX = p['ENEMY_SPEED_MAX']
    ENEMY_SPAWN_TIME = p['ENEMY_SPAWN_TIME']
    MAX_ENEMIES = p['MAX_ENEMIES']
    BULLET_SPEED = p['BULLET_SPEED']
    PLAYER_SPEED = p['PLAYER_SPEED']
    # Если игрок уже создан, обновим его скорость
    try:
        player.speed = PLAYER_SPEED
    except NameError:
        pass
    # Если таймер спавна уже определён, обновим его
    try:
        pygame.time.set_timer(SPAWNENEMY, ENEMY_SPAWN_TIME)
    except NameError:
        pass
    print(f"Difficulty set to {DIFFICULTY}: spawn={ENEMY_SPAWN_TIME}ms speed={ENEMY_SPEED_MIN:.2f}-{ENEMY_SPEED_MAX:.2f} max_enemies={MAX_ENEMIES}")

# == Инициализация ==
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Blaster — простой шутер")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 28)

# Инициализация звукового движка
try:
    pygame.mixer.pre_init(44100, -16, 1, 1024)
    pygame.mixer.init()
except Exception:
    # если инициализация звуков не удалась — продолжим без звука
    print("Warning: mixer init failed, sound disabled")

# == Служебные цвета ==
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED   = (220, 50, 50)
GREEN = (50, 200, 50)
BLUE  = (50, 100, 220)
YELLOW= (230, 220, 50)

# == Классы ==
class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.width = 50
        self.height = 30
        # Размер спрайта игрока
        self.width = 64
        self.height = 36
        self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        # Нарисуем более детализированный бластер: корпус, ствол и светящийся элемент
        body_rect = pygame.Rect(6, 8, self.width-12, 20)
        pygame.draw.rect(self.image, (30, 80, 200), body_rect, border_radius=6)
        # ствол
        pygame.draw.rect(self.image, (20,20,20), (self.width-18, 12, 14, 10), border_radius=3)
        # светящийся глаз/канал
        pygame.draw.rect(self.image, (250, 200, 50), (self.width-26, 14, 6, 6), border_radius=3)
        # декоративные полосы
        pygame.draw.line(self.image, (50,120,240), (10, 16), (self.width-30, 16), 2)
        pygame.draw.line(self.image, (20,40,80), (10, 20), (self.width-30, 20), 1)
        self.rect = self.image.get_rect()
        self.rect.centerx = WIDTH // 2
        self.rect.bottom = HEIGHT - 8
        self.speed = PLAYER_SPEED
        self.shoot_cooldown = 250  # ms
        self.last_shot = 0

    def update(self, dt, keys):
        # движение
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.rect.x -= self.speed
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.rect.x += self.speed
        # ограничения по экрану
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > WIDTH:
            self.rect.right = WIDTH

    def shoot(self, now, bullets_group, all_sprites):
        if now - self.last_shot >= self.shoot_cooldown:
            bullet = Bullet(self.rect.centerx, self.rect.top)
            bullets_group.add(bullet)
            all_sprites.add(bullet)
            self.last_shot = now
            # звук выстрела
            try:
                shoot_sound.play()
            except Exception:
                pass

class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((4, 12))
        self.image.fill(WHITE)
        self.rect = self.image.get_rect(center=(x, y))
        self.speedy = -BULLET_SPEED

    def update(self, dt):
        self.rect.y += self.speedy
        if self.rect.bottom < 0:
            self.kill()

class Enemy(pygame.sprite.Sprite):
    def __init__(self, etype=None):
        super().__init__()
        # Тип врага: orb, saucer, spiky, drone
        if etype is None:
            etype = random.choice(['orb', 'saucer', 'spiky', 'drone'])
        self.etype = etype
        # разные размеры и рисунки по типу
        if self.etype == 'orb':
            self.size = random.randint(22, 34)
            self.image = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
            pygame.draw.ellipse(self.image, RED, (0,0,self.size,self.size))
            pygame.draw.circle(self.image, (255,160,160), (self.size//3, self.size//3), max(3,self.size//8))
            self.health = 1
        elif self.etype == 'saucer':
            self.size = random.randint(30, 46)
            self.image = pygame.Surface((self.size, self.size//2), pygame.SRCALPHA)
            pygame.draw.ellipse(self.image, (120,120,200), (0,0,self.size,self.size//2))
            pygame.draw.rect(self.image, (180,180,230), (self.size//3, self.size//8, self.size//3, self.size//6), border_radius=6)
            self.health = 2
        elif self.etype == 'spiky':
            self.size = random.randint(26, 38)
            self.image = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
            pygame.draw.circle(self.image, (200,50,80), (self.size//2, self.size//2), self.size//2)
            for i in range(6):
                ang = i * (2*math.pi/6)
                x1 = self.size//2 + int((self.size//2) * math.cos(ang))
                y1 = self.size//2 + int((self.size//2) * math.sin(ang))
                x2 = self.size//2 + int((self.size//2+6) * math.cos(ang))
                y2 = self.size//2 + int((self.size//2+6) * math.sin(ang))
                pygame.draw.line(self.image, (120,20,40), (x1,y1), (x2,y2), 3)
            self.health = 2
        else:  # drone
            self.size = random.randint(20, 32)
            self.image = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
            pygame.draw.polygon(self.image, (90,160,90), [(self.size//2,0),(self.size, self.size),(0,self.size)])
            pygame.draw.circle(self.image, (60,200,60), (self.size//2, self.size//2), max(3, self.size//6))
            self.health = 1
        self.rect = self.image.get_rect()
        self.rect.x = random.randint(0, max(0, WIDTH - self.rect.width))
        self.rect.y = -self.rect.height - random.randint(0, 120)
        # Скорость может зависеть от типа
        base_min = ENEMY_SPEED_MIN * (1.0 if self.etype != 'saucer' else 0.8)
        base_max = ENEMY_SPEED_MAX * (1.0 if self.etype != 'spiky' else 0.9)
        self.speedy = random.uniform(base_min, base_max)

    def update(self, dt):
        # поведение: спускаются вниз, некоторые типы могут иметь небольшие вариации
        self.rect.y += self.speedy
        # saucer может слегка маяться влево/вправо
        if self.etype == 'saucer':
            self.rect.x += int(math.sin(pygame.time.get_ticks() * 0.002 + self.rect.x) * 0.6)
        # drone может волнообразно смещаться
        if self.etype == 'drone':
            self.rect.x += int(math.sin(pygame.time.get_ticks() * 0.004 + self.rect.y * 0.02) * 0.9)
        if self.rect.top > HEIGHT:
            self.kill()

class Explosion(pygame.sprite.Sprite):
    def __init__(self, center, lifetime=300):
        super().__init__()
        self.start = pygame.time.get_ticks()
        self.lifetime = lifetime
        self.max_radius = 30
        self.center = center
        self.image = pygame.Surface((self.max_radius*2, self.max_radius*2), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=center)
        # play explosion sound
        try:
            explosion_sound.play()
        except Exception:
            pass

    def update(self, dt):
        now = pygame.time.get_ticks()
        elapsed = now - self.start
        if elapsed > self.lifetime:
            self.kill()
            return
        progress = elapsed / self.lifetime
        radius = int(progress * self.max_radius)
        self.image.fill((0,0,0,0))
        # draw expanding ring
        pygame.draw.circle(self.image, (255,200,0, max(1, 180 - int(progress*160))), (self.max_radius, self.max_radius), radius, max(1, int(6*(1-progress))))

# == Игровые группы ==
all_sprites = pygame.sprite.Group()
enemies = pygame.sprite.Group()
bullets = pygame.sprite.Group()
explosions = pygame.sprite.Group()

# Звёздное поле для фона
STAR_COUNT = 70
stars = []
for i in range(STAR_COUNT):
    stars.append({
        'x': random.randint(0, WIDTH),
        'y': random.randint(0, HEIGHT),
        'z': random.uniform(0.3, 1.2),
        'size': random.randint(1, 3)
    })


def draw_background(surf, dt):
    # простой слой: мелкие звёзды, двигающиеся вниз
    for s in stars:
        # скорость зависит от z и немного от dt
        s['y'] += s['z'] * 0.06 * dt
        if s['y'] > HEIGHT:
            s['y'] = -2
            s['x'] = random.randint(0, WIDTH)
            s['z'] = random.uniform(0.3, 1.2)
            s['size'] = random.randint(1, 3)
        col = int(180 * s['z']) + 50
        # clamp color to valid 0..255 range
        if col < 0:
            col = 0
        if col > 255:
            col = 255
        pygame.draw.circle(surf, (col, col, col), (int(s['x']), int(s['y'])), s['size'])


def generate_tone(path, freq=440.0, duration=0.2, volume=0.5, sample_rate=44100):
    n_samples = int(sample_rate * duration)
    amplitude = int(32767 * volume)
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            t = float(i) / sample_rate
            val = int(amplitude * math.sin(2.0 * math.pi * freq * t))
            wf.writeframes(struct.pack('<h', val))


def generate_shot_sound(path, base_freq=1200.0, duration=0.09, volume=0.35, sample_rate=44100):
    """Короткий звуковой эффект выстрела: чирп/блип с быстрой декой и небольшим шумом.
    Делает звук более похожим на бластер, не на «клацание клавиатуры».
    """
    n = int(sample_rate * duration)
    max_amp = int(32767 * volume)
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n):
            t = i / sample_rate
            # частотный чирп: частота понижается от base_freq -> base_freq*0.6
            freq = base_freq * (1.0 - 0.4 * (t / duration))
            # огибающая: быстрый атака и экспоненциальный спад
            env = (1.0 - (t / duration)) ** 2.2
            tone = math.sin(2.0 * math.pi * freq * t)
            # небольшая примесь белого шума для текстуры
            noise = (random.random() * 2.0 - 1.0) * 0.12
            val = int(max_amp * env * (0.9 * tone + 0.1 * noise))
            # clamp
            if val > 32767:
                val = 32767
            if val < -32768:
                val = -32768
            wf.writeframes(struct.pack('<h', val))


def generate_explosion_sound(path, duration=0.35, sample_rate=44100):
    # шум с затуханием + частотный спад
    n = int(sample_rate * duration)
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n):
            t = i / sample_rate
            decay = (1.0 - (t / duration))
            # комбинация шумового импульса и синуса со спадающей частотой
            freq = 400.0 * (1.0 - t / duration) + 100.0
            noise = (random.random() * 2 - 1) * 0.6
            val = int(32767 * decay * 0.6 * math.sin(2 * math.pi * freq * t) + 32767 * decay * 0.4 * noise)
            # clamp
            if val > 32767:
                val = 32767
            if val < -32768:
                val = -32768
            wf.writeframes(struct.pack('<h', val))


def ensure_sounds():
    global shoot_sound, explosion_sound, hit_sound, gameover_sound
    base = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    shot_path = os.path.join(base, 'blaster_shot.wav')
    expl_path = os.path.join(base, 'blaster_explosion.wav')
    hit_path = os.path.join(base, 'blaster_hit.wav')
    over_path = os.path.join(base, 'blaster_gameover.wav')
    try:
        # создаём файлы только если их нет
        if not os.path.exists(shot_path):
            # сгенерируем более подходящий короткий эффект выстрела
            generate_shot_sound(shot_path, base_freq=1400.0, duration=0.08, volume=0.32)
        if not os.path.exists(expl_path):
            generate_explosion_sound(expl_path, duration=0.35)
        if not os.path.exists(hit_path):
            generate_tone(hit_path, freq=250.0, duration=0.14, volume=0.6)
        if not os.path.exists(over_path):
            generate_tone(over_path, freq=120.0, duration=0.5, volume=0.8)
        # загрузка в pygame
        try:
            shoot_sound = pygame.mixer.Sound(shot_path)
            explosion_sound = pygame.mixer.Sound(expl_path)
            hit_sound = pygame.mixer.Sound(hit_path)
            gameover_sound = pygame.mixer.Sound(over_path)
            # настроим громкости (уменьшим выстрел и хит, сделаем взрыв сильнее)
            try:
                if shoot_sound:
                    shoot_sound.set_volume(0.22)
                if explosion_sound:
                    explosion_sound.set_volume(0.65)
                if hit_sound:
                    hit_sound.set_volume(0.42)
                if gameover_sound:
                    gameover_sound.set_volume(0.5)
            except Exception:
                pass
        except Exception:
            # если загрузка не удалась — заглушки
            shoot_sound = explosion_sound = hit_sound = gameover_sound = None
    except Exception as e:
        print('Warning: sound generation failed:', e)
        shoot_sound = explosion_sound = hit_sound = gameover_sound = None

# Попробуем подготовить звуки
ensure_sounds()

# Применим пресет сложности до создания игрока, чтобы его скорость и другие параметры были корректны
set_difficulty(DIFFICULTY)

player = Player()
all_sprites.add(player)

# Таймер спавна противников
SPAWNENEMY = pygame.USEREVENT + 1
pygame.time.set_timer(SPAWNENEMY, ENEMY_SPAWN_TIME)

score = 0
lives = 3
running = True

def draw_text(surf, text, x, y, color=WHITE):
    img = font.render(text, True, color)
    surf.blit(img, (x, y))


# == Главный цикл ==
while running:
    dt = clock.tick(FPS)
    now = pygame.time.get_ticks()
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == SPAWNENEMY:
            if len(enemies) < MAX_ENEMIES:
                e = Enemy()
                enemies.add(e)
                all_sprites.add(e)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_1:
                set_difficulty('Easy')
            elif event.key == pygame.K_2:
                set_difficulty('Normal')
            elif event.key == pygame.K_3:
                set_difficulty('Hard')

    keys = pygame.key.get_pressed()
    # управление стрельбой
    if keys[pygame.K_SPACE]:
        player.shoot(now, bullets, all_sprites)

    # обновление
    all_sprites.update(dt, keys) if hasattr(all_sprites, 'update') and False else None
    # our sprites expect different signatures; call individually
    for s in list(all_sprites):
        try:
            s.update(dt, keys)
        except TypeError:
            try:
                s.update(dt)
            except TypeError:
                s.update()

    # столкновения пуль и врагов
    hits = pygame.sprite.groupcollide(enemies, bullets, False, True)
    for enemy, hit_bullets in hits.items():
        enemy.health -= len(hit_bullets)
        if enemy.health <= 0:
            score += 10 + int(enemy.size)
            expl = Explosion(enemy.rect.center)
            explosions.add(expl)
            all_sprites.add(expl)
            enemy.kill()

    # столкновения врагов и игрока
    hits2 = pygame.sprite.spritecollide(player, enemies, True, pygame.sprite.collide_rect)
    if hits2:
        lives -= 1
        expl = Explosion(player.rect.center, lifetime=500)
        explosions.add(expl)
        all_sprites.add(expl)
        try:
            if hit_sound:
                hit_sound.play()
        except Exception:
            pass
        if lives <= 0:
            # play game over sound
            try:
                if gameover_sound:
                    gameover_sound.play()
            except Exception:
                pass
            running = False

    # отрисовка
    # фон и звёзды
    screen.fill((8, 10, 22))
    draw_background(screen, dt)
    all_sprites.draw(screen)

    # HUD
    # HUD panel
    hud_w = 320
    hud_h = 68
    hud_surf = pygame.Surface((hud_w, hud_h), pygame.SRCALPHA)
    hud_surf.fill((10, 10, 10, 150))
    # border
    pygame.draw.rect(hud_surf, (200,200,200,50), hud_surf.get_rect(), 1)
    screen.blit(hud_surf, (6, 6))
    draw_text(screen, f"Score: {score}", 12, 12)
    draw_text(screen, f"Lives: {lives}", 12, 36)
    draw_text(screen, f"Difficulty: {DIFFICULTY} (1-Easy 2-Normal 3-Hard)", 8, HEIGHT-60)
    draw_text(screen, "Controls: A/D or ←/→ — move. Space — shoot. Esc — exit.", 8, HEIGHT-28)

    pygame.display.flip()

# Конец игры — экран "Game Over"
over_font = pygame.font.SysFont(None, 64)
small = pygame.font.SysFont(None, 28)
screen.fill(BLACK)
text = over_font.render("GAME OVER", True, RED)
sub = small.render(f"Score: {score} — нажмите любую клавишу чтобы выйти", True, WHITE)
screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2 - 30))
screen.blit(sub, (WIDTH//2 - sub.get_width()//2, HEIGHT//2 + 30))
pygame.display.flip()

# ждём нажатия или выхода
waiting = True
while waiting:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            waiting = False
        if e.type == pygame.KEYDOWN or e.type == pygame.MOUSEBUTTONDOWN:
            waiting = False

pygame.quit()
sys.exit()
