# Changelog

## Unreleased

## 1.1.1 - 2026-05-10

### Added
- Added a custom Blaster app icon for the Windows executable and game window.

## 1.1.0 - 2026-05-10

### Changed
- Runtime settings and high scores now use the user's app data directory instead of writing active saves into the source tree.
- Legacy `data/settings.json` and `data/highscores.json` files are migrated on first run when no app-data save exists.
- Combat collision handling now lives in `blaster/combat.py`, reducing the size and responsibility of `blaster/main.py`.
- README media previews were refreshed to match the current menu, combat HUD, ship frames, and boss telegraph systems.
- README screenshots are now PNG captures from the actual Pygame renderer and can be regenerated with `tools/capture_readme_screenshots.py`.
- In-game rendering was tuned toward the refreshed preview style with brighter space backdrops, stronger HUD glass panels, richer combat particles, and a more dramatic boss telegraph.
- Background composition was refined to remove the bright center glow, keep nebula detail near the edges, and lower the perspective grid for better gameplay readability.
- The player ship is now slightly larger and sits higher above the bottom edge for better visibility.

### Fixed
- Added strict boolean sanitization for persisted settings such as fullscreen and FPS display.
- Capped the high-score name prompt loop to the configured FPS limit.
- Added short post-hit player invulnerability to prevent rapid multi-hit life loss.
- Menu, HUD, options, selection, replay, and end-screen labels now fit inside their panels and use brighter text where contrast was weak.
- UI text now renders with a consistent dark outline/shadow, and upgrade cards have darker text zones so labels stay readable over colored glows.

## 1.0.0 - 2026-03-06

### Added
- Visual quality presets: `Performance`, `Balanced`, `Cinematic`, `Enhanced`.
- Fullscreen toggle with `F11` and options menu switch.
- FPS cap selection and optional FPS counter.
- Wave progression system with scaling enemy pressure.
- Mini-boss every 4 waves with dedicated HP bar and phase behavior.
- Persistent user settings in `data/settings.json`.
- Death replay (5 seconds) with skip controls.
- Shooter enemies and elite enemy variants.
- GitHub-ready media previews in `docs/media/`.

### Changed
- Main menu, pause menu, and options menu visuals/UX refreshed.
- `Esc` in gameplay now opens pause menu (same behavior as `P`).
- HUD hints and accessibility details updated.
- Power-up visuals redesigned for clearer type recognition.
- General combat feedback and readability improved.

### Fixed
- Shield and double-shot behavior consistency.
- Safer highscore and settings data sanitization and persistence.
