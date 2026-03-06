import math

import pygame

from . import settings
from .storage import load_highscores
from .ui import draw_background, make_stars, ui_microtext

_MENU_STARS = None
_NOTICE_FONT = None
_NOTICE_TEXT = None

_TITLE_DESCRIPTIONS = {
    "Start Game": "Launch a new run with your current difficulty and visual preset.",
    "Options": "Tune graphics, FPS cap, sound and comfort toggles.",
    "High Scores": "View local records and top pilots.",
    "Quit": "Exit the game.",
}

_PAUSE_DESCRIPTIONS = {
    "Resume": "Continue the current battle immediately.",
    "Restart": "Restart this run from wave 1.",
    "Quit to Menu": "Leave the run and return to title screen.",
}


def _ensure_menu_stars():
    global _MENU_STARS
    if _MENU_STARS is None or len(_MENU_STARS) != settings.STAR_COUNT:
        _MENU_STARS = make_stars(width=settings.WIDTH, height=settings.HEIGHT)
    return _MENU_STARS


def _invalidate_menu_stars():
    global _MENU_STARS
    _MENU_STARS = None


def _draw_footer_notice(screen):
    global _NOTICE_FONT, _NOTICE_TEXT
    if _NOTICE_FONT is None:
        _NOTICE_FONT = pygame.font.SysFont(None, 15)
    if _NOTICE_TEXT is None:
        _NOTICE_TEXT = ui_microtext()
    tag = _NOTICE_FONT.render(_NOTICE_TEXT, True, (120, 138, 164))
    screen.blit(tag, (8, screen.get_height() - 16))


def draw_menu(screen, font, title, items, selected_idx, dt=16, subtitle="", descriptions=None, footer_hint=None):
    stars = _ensure_menu_stars()
    draw_background(screen, stars, max(1, int(dt * 0.5)))

    now = pygame.time.get_ticks()
    pulse = 0.5 + 0.5 * math.sin(now * 0.0035)
    sw = screen.get_width()
    sh = screen.get_height()

    panel_w = min(560, max(420, sw - 120))
    panel_h = min(470, max(360, sh - 120))
    panel = pygame.Rect(sw // 2 - panel_w // 2, sh // 2 - panel_h // 2, panel_w, panel_h)

    panel_surf = pygame.Surface((panel.width, panel.height), pygame.SRCALPHA)
    panel_surf.fill((8, 14, 28, 182))
    pygame.draw.rect(panel_surf, (86, 132, 210, 170), panel_surf.get_rect(), 2, border_radius=14)
    glow = pygame.Surface((panel.width, panel.height), pygame.SRCALPHA)
    glow_alpha = int(18 + 24 * pulse)
    pygame.draw.rect(glow, (70, 126, 220, glow_alpha), glow.get_rect(), 1, border_radius=14)
    panel_surf.blit(glow, (0, 0))
    screen.blit(panel_surf, panel.topleft)

    title_shadow = font.render(title, True, (18, 26, 42))
    title_col = (235, 242, min(255, 242 + int(8 * pulse)))
    title_surf = font.render(title, True, title_col)
    tx = sw // 2 - title_surf.get_width() // 2
    title_y = panel.top + 14
    screen.blit(title_shadow, (tx + 2, title_y + 2))
    screen.blit(title_surf, (tx, title_y))

    if subtitle:
        sub = font.render(subtitle, True, (168, 190, 225))
        screen.blit(sub, (sw // 2 - sub.get_width() // 2, title_y + 34))

    btn_w = panel.width - 92
    btn_h = 46
    base_y = panel.top + 96
    rects = []
    for i, item in enumerate(items):
        is_selected = i == selected_idx
        btn_x = panel.left + (panel.width - btn_w) // 2
        y = base_y + i * 54
        if is_selected:
            btn_x -= 6
        btn_rect = pygame.Rect(btn_x, y, btn_w, btn_h)
        base_col = (20, 36, 66, 184)
        active_col = (46, 92, 180, 225)
        btn_surf = pygame.Surface((btn_rect.width, btn_rect.height), pygame.SRCALPHA)
        btn_surf.fill(active_col if is_selected else base_col)
        border = (140, 196, 255, 228) if is_selected else (90, 120, 170, 120)
        pygame.draw.rect(btn_surf, border, btn_surf.get_rect(), 1, border_radius=8)
        if is_selected:
            pygame.draw.rect(btn_surf, (255, 214, 132, 190), pygame.Rect(0, 0, 5, btn_h), border_radius=3)
        screen.blit(btn_surf, btn_rect.topleft)

        txt_col = (255, 245, 220) if is_selected else (208, 220, 240)
        text = font.render(item, True, txt_col)
        screen.blit(text, (btn_rect.centerx - text.get_width() // 2, y + 10))
        rects.append(btn_rect)

    desc_text = ""
    if descriptions and 0 <= selected_idx < len(items):
        desc_text = descriptions.get(items[selected_idx], "")
    if desc_text:
        desc_rect = pygame.Rect(panel.left + 22, panel.bottom - 96, panel.width - 44, 48)
        desc_surf = pygame.Surface((desc_rect.width, desc_rect.height), pygame.SRCALPHA)
        desc_surf.fill((14, 24, 48, 168))
        pygame.draw.rect(desc_surf, (112, 162, 232, 120), desc_surf.get_rect(), 1, border_radius=8)
        screen.blit(desc_surf, desc_rect.topleft)
        desc_font = pygame.font.SysFont(None, 22)
        desc_img = desc_font.render(desc_text, True, (186, 210, 240))
        screen.blit(
            desc_img,
            (desc_rect.centerx - desc_img.get_width() // 2, desc_rect.y + 14),
        )

    if footer_hint is None:
        footer_hint = "W/S or arrows - Enter select - mouse click"
    hint = font.render(footer_hint, True, (152, 174, 205))
    screen.blit(hint, (sw // 2 - hint.get_width() // 2, panel.bottom - 34))
    _draw_footer_notice(screen)
    pygame.display.flip()
    return rects


def title_menu(screen, clock, font, joystick=None):
    items = ["Start Game", "Options", "High Scores", "Quit"]
    idx = 0
    while True:
        dt = clock.tick(settings.FPS)
        rects = draw_menu(
            screen,
            font,
            "Blaster",
            items,
            idx,
            dt=dt,
            subtitle=f"{settings.VISUAL_QUALITY} visuals  |  {settings.DIFFICULTY}  |  cap {settings.FPS}",
            descriptions=_TITLE_DESCRIPTIONS,
            footer_hint="W/S or arrows, Enter, mouse, wheel. Quick keys: 1/2/3/4",
        )
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "quit", {}
            if e.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                _invalidate_menu_stars()
                continue
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_UP, pygame.K_w):
                    idx = (idx - 1) % len(items)
                elif e.key in (pygame.K_DOWN, pygame.K_s):
                    idx = (idx + 1) % len(items)
                elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return items[idx].lower().replace(" ", "_"), {}
                elif e.key == pygame.K_1:
                    return "start_game", {}
                elif e.key == pygame.K_2:
                    return "options", {}
                elif e.key == pygame.K_3:
                    return "high_scores", {}
                elif e.key == pygame.K_4:
                    return "quit", {}
            if e.type == pygame.MOUSEWHEEL:
                idx = (idx - (1 if e.y > 0 else -1)) % len(items)
            if e.type == pygame.MOUSEMOTION:
                mx, my = e.pos
                for i, rect in enumerate(rects):
                    if rect.collidepoint(mx, my):
                        idx = i
                        break
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                for i, rect in enumerate(rects):
                    if rect.collidepoint(mx, my):
                        return items[i].lower().replace(" ", "_"), {}
            if joystick is not None and e.type == pygame.JOYBUTTONDOWN:
                if e.button == 0:
                    return items[idx].lower().replace(" ", "_"), {}
                if e.button == 1:
                    idx = (idx + 1) % len(items)


def show_highscores(screen, clock, font):
    while True:
        dt = clock.tick(settings.FPS)
        scores = load_highscores()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return
            if e.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                _invalidate_menu_stars()
                continue
            if e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                return

        stars = _ensure_menu_stars()
        draw_background(screen, stars, max(1, int(dt * 0.5)))

        sw = screen.get_width()
        sh = screen.get_height()
        panel_w = min(540, max(440, sw - 100))
        panel_h = min(520, max(400, sh - 80))
        panel = pygame.Rect(sw // 2 - panel_w // 2, sh // 2 - panel_h // 2, panel_w, panel_h)
        panel_surf = pygame.Surface((panel.width, panel.height), pygame.SRCALPHA)
        panel_surf.fill((8, 14, 28, 178))
        pygame.draw.rect(panel_surf, (86, 132, 210, 170), panel_surf.get_rect(), 2, border_radius=14)
        screen.blit(panel_surf, panel.topleft)

        title = font.render("High Scores", True, (235, 242, 255))
        screen.blit(title, (sw // 2 - title.get_width() // 2, panel.top + 20))

        y = panel.top + 82
        if not scores:
            line = font.render("No scores yet - play to set a record.", True, (210, 220, 235))
            screen.blit(line, (sw // 2 - line.get_width() // 2, y))
        else:
            for i, item in enumerate(scores[:10], start=1):
                label = f"{i:>2}. {item.get('name', '---'):<16} {item.get('score', 0):>6}"
                color = (248, 224, 155) if i <= 3 else (214, 225, 240)
                line = font.render(label, True, color)
                screen.blit(line, (sw // 2 - line.get_width() // 2, y))
                y += 34

        hint = font.render("Press any key to return", True, (152, 174, 205))
        screen.blit(hint, (sw // 2 - hint.get_width() // 2, panel.bottom - 34))
        _draw_footer_notice(screen)
        pygame.display.flip()


def pause_menu(screen, clock, font):
    items = ["Resume", "Restart", "Quit to Menu"]
    idx = 0
    while True:
        dt = clock.tick(settings.FPS)
        rects = draw_menu(
            screen,
            font,
            "Paused",
            items,
            idx,
            dt=dt,
            descriptions=_PAUSE_DESCRIPTIONS,
            footer_hint="W/S or arrows, Enter select, Esc resume, mouse click",
        )
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "quit"
            if e.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                _invalidate_menu_stars()
                continue
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_UP, pygame.K_w):
                    idx = (idx - 1) % len(items)
                elif e.key in (pygame.K_DOWN, pygame.K_s):
                    idx = (idx + 1) % len(items)
                elif e.key == pygame.K_ESCAPE:
                    return "resume"
                elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return items[idx].lower().replace(" ", "_")
            if e.type == pygame.MOUSEMOTION:
                mx, my = e.pos
                for i, rect in enumerate(rects):
                    if rect.collidepoint(mx, my):
                        idx = i
                        break
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                for i, rect in enumerate(rects):
                    if rect.collidepoint(mx, my):
                        return items[i].lower().replace(" ", "_")
