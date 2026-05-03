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


def _blend(c1, c2, t):
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _draw_title_showcase(screen, panel, now, pulse):
    bay = pygame.Rect(panel.right - 430, panel.top + 122, 382, 360)
    bay_surf = pygame.Surface((bay.width, bay.height), pygame.SRCALPHA)
    bay_surf.fill((4, 10, 24, 130))
    pygame.draw.rect(bay_surf, (90, 154, 236, 112), bay_surf.get_rect(), 1, border_radius=16)

    for x in range(18, bay.width, 28):
        alpha = 14 + (x // 28) % 2 * 8
        pygame.draw.line(bay_surf, (70, 130, 210, alpha), (x, 12), (x, bay.height - 12), 1)
    for y in range(18, bay.height, 28):
        pygame.draw.line(bay_surf, (70, 130, 210, 16), (12, y), (bay.width - 12, y), 1)

    cx = bay.width // 2
    cy = bay.height // 2 - 18
    orbit_col = (94, 184, 255, int(42 + 26 * pulse))
    for idx, radius in enumerate((58, 88, 118)):
        rect = pygame.Rect(cx - radius, cy - radius // 2, radius * 2, radius)
        pygame.draw.ellipse(bay_surf, orbit_col, rect, 1)
        dot_ang = now * (0.0015 + idx * 0.0003) + idx * 1.7
        dot_x = int(cx + math.cos(dot_ang) * radius)
        dot_y = int(cy + math.sin(dot_ang) * (radius // 2))
        pygame.draw.circle(bay_surf, (255, 220, 132, 180), (dot_x, dot_y), 2)

    ship = pygame.Surface((148, 168), pygame.SRCALPHA)
    sx = ship.get_width() // 2
    ship_glow = pygame.Surface(ship.get_size(), pygame.SRCALPHA)
    pygame.draw.ellipse(ship_glow, (72, 180, 255, 48), (20, 18, 108, 118))
    ship.blit(ship_glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    left_wing = [(sx - 12, 68), (12, 106), (sx - 42, 138), (sx - 27, 84)]
    right_wing = [(sx + 12, 68), (136, 106), (sx + 42, 138), (sx + 27, 84)]
    hull = [(sx, 8), (sx + 38, 102), (sx, 148), (sx - 38, 102)]
    pygame.draw.polygon(ship, (24, 70, 134), left_wing)
    pygame.draw.polygon(ship, (24, 70, 134), right_wing)
    pygame.draw.polygon(ship, (112, 196, 255), left_wing, 2)
    pygame.draw.polygon(ship, (112, 196, 255), right_wing, 2)
    pygame.draw.polygon(ship, (42, 138, 232), hull)
    pygame.draw.polygon(ship, (186, 238, 255), hull, 2)
    pygame.draw.polygon(ship, (12, 28, 56), [(sx, 26), (sx + 22, 94), (sx, 120), (sx - 22, 94)])
    pygame.draw.ellipse(ship, (160, 238, 255), (sx - 13, 38, 26, 38))
    pygame.draw.ellipse(ship, (238, 254, 255), (sx - 7, 46, 14, 22))
    flame_len = 20 + int(8 * pulse)
    for nozzle_x in (sx - 18, sx + 18):
        pygame.draw.rect(ship, (42, 52, 84), (nozzle_x - 6, 136, 12, 12), border_radius=4)
        pygame.draw.polygon(
            ship,
            (255, 160, 70, 180),
            [(nozzle_x - 6, 147), (nozzle_x + 6, 147), (nozzle_x, 147 + flame_len)],
        )
        pygame.draw.polygon(
            ship,
            (255, 238, 176, 220),
            [(nozzle_x - 2, 147), (nozzle_x + 2, 147), (nozzle_x, 143 + flame_len)],
        )
    bob = int(math.sin(now * 0.0022) * 5)
    bay_surf.blit(ship, (cx - ship.get_width() // 2, 58 + bob))

    status_font = pygame.font.SysFont(None, 22)
    small = pygame.font.SysFont(None, 18)
    status = [
        ("LOCAL PROFILE", (116, 206, 255)),
        (f"{settings.DIFFICULTY} difficulty", (228, 238, 255)),
        (f"{settings.VISUAL_QUALITY} render mode", (190, 214, 244)),
    ]
    y = bay.height - 82
    for text, color in status:
        img = small.render(text, True, color)
        bay_surf.blit(img, (18, y))
        y += 19

    launch = status_font.render("ARCADE RUN READY", True, (255, 222, 146))
    bay_surf.blit(launch, (bay.width - launch.get_width() - 18, bay.height - 38))
    screen.blit(bay_surf, bay.topleft)


def draw_menu(screen, font, title, items, selected_idx, dt=16, subtitle="", descriptions=None, footer_hint=None):
    stars = _ensure_menu_stars()
    draw_background(screen, stars, max(1, int(dt * 0.5)))

    now = pygame.time.get_ticks()
    pulse = 0.5 + 0.5 * math.sin(now * 0.0035)
    breathe = 0.5 + 0.5 * math.sin(now * 0.0017)
    sw = screen.get_width()
    sh = screen.get_height()
    is_title = title == "Blaster"

    panel_w = min(1040 if is_title else 700, max(840 if is_title else 480, sw - 140 if is_title else sw - 110))
    panel_h = min(590 if is_title else 560, max(500 if is_title else 420, sh - 130 if is_title else sh - 106))
    panel = pygame.Rect(sw // 2 - panel_w // 2, sh // 2 - panel_h // 2, panel_w, panel_h)

    shadow = pygame.Surface((panel.width + 26, panel.height + 26), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (4, 10, 24, 140), shadow.get_rect(), border_radius=20)
    screen.blit(shadow, (panel.x - 13, panel.y - 5))

    panel_surf = pygame.Surface((panel.width, panel.height), pygame.SRCALPHA)
    panel_surf.fill((8, 16, 34, 188))
    pygame.draw.rect(panel_surf, (90, 146, 226, 175), panel_surf.get_rect(), 2, border_radius=16)
    glow = pygame.Surface((panel.width, panel.height), pygame.SRCALPHA)
    glow_alpha = int(20 + 30 * pulse)
    pygame.draw.rect(glow, (82, 160, 255, glow_alpha), glow.get_rect(), 1, border_radius=16)
    panel_surf.blit(glow, (0, 0))
    header = pygame.Surface((panel.width - 20, 64), pygame.SRCALPHA)
    for y in range(header.get_height()):
        t = y / max(1, header.get_height() - 1)
        col = _blend((38, 78, 148), (16, 36, 78), t)
        pygame.draw.line(header, (*col, 104), (0, y), (header.get_width(), y))
    pygame.draw.rect(header, (126, 188, 255, 130), header.get_rect(), 1, border_radius=12)
    panel_surf.blit(header, (10, 10))
    screen.blit(panel_surf, panel.topleft)

    title_shadow = font.render(title, True, (10, 18, 36))
    title_col = (236, 245, min(255, 245 + int(8 * pulse)))
    title_surf = font.render(title, True, title_col)
    tx = panel.left + 42 if is_title else sw // 2 - title_surf.get_width() // 2
    title_y = panel.top + 24
    screen.blit(title_shadow, (tx + 3, title_y + 3))
    screen.blit(title_surf, (tx, title_y))
    pygame.draw.line(
        screen,
        (126, 190, 255, int(120 + 70 * breathe)),
        (panel.left + 40, title_y + 34),
        (panel.right - 40, title_y + 34),
        1,
    )

    if subtitle:
        subtitle_chip = pygame.Surface((min(panel.width - 80, 470), 28), pygame.SRCALPHA)
        subtitle_chip.fill((12, 26, 56, 166))
        pygame.draw.rect(subtitle_chip, (94, 150, 230, 120), subtitle_chip.get_rect(), 1, border_radius=8)
        sub = font.render(subtitle, True, (184, 208, 240))
        chip_x = panel.left + 42 if is_title else sw // 2 - subtitle_chip.get_width() // 2
        chip_y = title_y + 42
        screen.blit(subtitle_chip, (chip_x, chip_y))
        sub_x = chip_x + 14 if is_title else sw // 2 - sub.get_width() // 2
        screen.blit(sub, (sub_x, chip_y + 4))

    if is_title:
        _draw_title_showcase(screen, panel, now, pulse)

    btn_w = 348 if is_title else panel.width - 108
    btn_h = 54 if is_title else 48
    row_gap = 64 if is_title else 56
    base_y = panel.top + 164 if is_title else panel.top + 118
    rects = []
    for i, item in enumerate(items):
        is_selected = i == selected_idx
        row_pulse = 0.5 + 0.5 * math.sin(now * 0.004 + i * 0.8)
        lift = int(4 + 3 * row_pulse) if is_selected else 0
        if is_title:
            btn_x = panel.left + 42 - (7 if is_selected else 0)
        else:
            btn_x = panel.left + (panel.width - btn_w) // 2 - (7 if is_selected else 0)
        y = base_y + i * row_gap - lift
        btn_rect = pygame.Rect(btn_x, y, btn_w, btn_h)
        btn_shadow = pygame.Surface((btn_rect.width, btn_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(btn_shadow, (5, 10, 20, 118), btn_shadow.get_rect(), border_radius=10)
        screen.blit(btn_shadow, (btn_rect.x, btn_rect.y + 3))

        btn_surf = pygame.Surface((btn_rect.width, btn_rect.height), pygame.SRCALPHA)
        top_col = (26, 44, 82) if not is_selected else (48, 104, 206)
        bottom_col = (14, 25, 48) if not is_selected else (22, 54, 124)
        for py in range(btn_h):
            t = py / max(1, btn_h - 1)
            pygame.draw.line(btn_surf, (*_blend(top_col, bottom_col, t), 228), (0, py), (btn_w, py))
        border = (144, 206, 255, 236) if is_selected else (98, 136, 190, 128)
        pygame.draw.rect(btn_surf, border, btn_surf.get_rect(), 1, border_radius=10)
        if is_selected:
            pygame.draw.rect(btn_surf, (255, 214, 138, 210), pygame.Rect(0, 0, 5, btn_h), border_radius=3)
            shine_w = 56
            shine_x = int((now * 0.22 + i * 48) % (btn_w + shine_w)) - shine_w
            shine = pygame.Surface((shine_w, btn_h), pygame.SRCALPHA)
            for sx in range(shine_w):
                alpha = int(max(0, 28 - abs(sx - shine_w * 0.5) * 1.6))
                pygame.draw.line(shine, (196, 228, 255, alpha), (sx, 0), (sx, btn_h))
            btn_surf.blit(shine, (shine_x, 0), special_flags=pygame.BLEND_RGBA_ADD)
            glow_ring = pygame.Surface((btn_w + 8, btn_h + 8), pygame.SRCALPHA)
            pygame.draw.rect(
                glow_ring,
                (110, 186, 255, int(52 + 46 * row_pulse)),
                glow_ring.get_rect(),
                2,
                border_radius=12,
            )
            screen.blit(glow_ring, (btn_rect.x - 4, btn_rect.y - 4))
        screen.blit(btn_surf, btn_rect.topleft)

        txt_col = (255, 245, 220) if is_selected else (208, 220, 240)
        text = font.render(item, True, txt_col)
        screen.blit(text, (btn_rect.centerx - text.get_width() // 2, btn_rect.centery - text.get_height() // 2))
        rects.append(btn_rect)

    desc_text = ""
    if descriptions and 0 <= selected_idx < len(items):
        desc_text = descriptions.get(items[selected_idx], "")
    if desc_text:
        if is_title:
            desc_rect = pygame.Rect(panel.left + 42, panel.bottom - 112, 348, 50)
        else:
            desc_rect = pygame.Rect(panel.left + 22, panel.bottom - 96, panel.width - 44, 48)
        desc_surf = pygame.Surface((desc_rect.width, desc_rect.height), pygame.SRCALPHA)
        desc_surf.fill((14, 24, 48, 168))
        pygame.draw.rect(desc_surf, (112, 162, 232, 120), desc_surf.get_rect(), 1, border_radius=8)
        screen.blit(desc_surf, desc_rect.topleft)
        desc_font = pygame.font.SysFont(None, 22)
        desc_img = desc_font.render(desc_text, True, (186, 210, 240))
        screen.blit(
            desc_img,
            (desc_rect.centerx - desc_img.get_width() // 2, desc_rect.centery - desc_img.get_height() // 2),
        )

    if footer_hint is None:
        footer_hint = "W/S or arrows - Enter select - mouse click"
    hint_chip = pygame.Surface((min(panel.width - 76, 560), 30), pygame.SRCALPHA)
    hint_chip.fill((10, 22, 46, 160))
    pygame.draw.rect(hint_chip, (92, 146, 222, 108), hint_chip.get_rect(), 1, border_radius=9)
    hint = font.render(footer_hint, True, (158, 184, 216))
    chip_x = sw // 2 - hint_chip.get_width() // 2
    chip_y = panel.bottom - 40
    screen.blit(hint_chip, (chip_x, chip_y))
    screen.blit(hint, (sw // 2 - hint.get_width() // 2, chip_y + 5))
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
