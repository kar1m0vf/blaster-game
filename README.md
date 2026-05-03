# Blaster

Arcade 2D shooter built with Pygame.

## What Is In This Build

- Polished animated main menu and pause menu
- Adaptive options UI with mouse + keyboard support
- 16:9 scaled playfield (`1280x720`) for modern displays
- Visual quality presets: `Performance`, `Balanced`, `Cinematic`, `Enhanced`
- Default borderless fullscreen with preserved 16:9 aspect ratio (`F11` or Options)
- FPS cap control and optional FPS counter
- Local ship frame selection: `Interceptor`, `Vanguard`, `Lancer`
- Distinct local weapon profiles: twin pulse, plasma caster, rail lance
- Local Run Mode foundation: 8-wave offline operation split into visual sectors
- 2.5D visual pass with depth stars, orbital backdrop, perspective grid, and sprite shadows
- Wave progression with special enemies and boss phases
- Death replay (5 seconds, skippable)
- Local high scores (`data/highscores.json`)
- Persistent user settings (`data/settings.json`)

## Screenshots

![Menu](docs/media/preview-menu.svg)
![Battle](docs/media/preview-battle.svg)
![Boss](docs/media/preview-boss.svg)

## Controls

- `A / D` or `Left / Right` - move
- `Space` - shoot
- `P` or `Esc` - pause/resume
- `F11` - fullscreen toggle
- `F3` - FPS counter on/off
- `1 / 2 / 3` - switch difficulty during gameplay

## Download Ready Build (Windows)

Use the **Releases** page and download the latest `Blaster-windows-x64.zip`.

Inside archive:

- `Blaster.exe`
- `README.md`
- `LICENSE`
- `COPYRIGHT`
- `CHANGELOG.md`

## Run From Source

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_game.py
```

## Tests

```powershell
pytest -q
```

## Build Release (.exe + .zip)

Use script:

```powershell
.\scripts\build_release.ps1
```

It will:

1. install build dependencies
2. run tests
3. build `Blaster.exe` with PyInstaller
4. assemble release files
5. create `release/Blaster-windows-x64.zip`

## Notes

- Main entrypoint is `run_game.py`.
- `blaster_game.py` is an old prototype file and is not used for current gameplay.

## Legal

This project is proprietary. All rights reserved.

See `LICENSE` and `COPYRIGHT` for terms.
