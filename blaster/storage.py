import json
import os
from typing import Dict, List, Optional

from . import settings

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(ROOT, 'data')
HIGHSCORES_FILE = os.path.join(DATA_DIR, 'highscores.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
DEFAULT_PLAYER_NAME = "Player"
MAX_NAME_LEN = 16

def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def normalize_player_name(name: str) -> str:
    raw = '' if name is None else str(name)
    cleaned = ''.join(ch for ch in raw if ch.isprintable()).strip()
    if not cleaned:
        return DEFAULT_PLAYER_NAME
    return cleaned[:MAX_NAME_LEN]


def normalize_score(score) -> int:
    try:
        return max(0, int(score))
    except (TypeError, ValueError):
        return 0


def _sanitize_scores(scores: List[Dict], max_entries: Optional[int] = None) -> List[Dict]:
    sanitized = []
    for entry in scores if isinstance(scores, list) else []:
        if not isinstance(entry, dict):
            continue
        sanitized.append(
            {
                'name': normalize_player_name(entry.get('name')),
                'score': normalize_score(entry.get('score')),
            }
        )

    sanitized.sort(key=lambda x: x['score'], reverse=True)
    if max_entries is not None:
        sanitized = sanitized[:max_entries]
    return sanitized


def load_highscores() -> List[Dict]:
    _ensure_dir()
    if not os.path.exists(HIGHSCORES_FILE):
        return []
    try:
        with open(HIGHSCORES_FILE, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        return _sanitize_scores(raw)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return []


def save_highscores(scores: List[Dict]):
    _ensure_dir()
    cleaned = _sanitize_scores(scores)
    try:
        with open(HIGHSCORES_FILE, 'w', encoding='utf-8') as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def add_highscore(name: str, score: int, max_entries: int = 10):
    scores = load_highscores()
    scores.append({'name': normalize_player_name(name), 'score': normalize_score(score)})
    scores = _sanitize_scores(scores, max_entries=max_entries)
    save_highscores(scores)
    return scores


def _default_user_settings() -> Dict:
    return {
        "difficulty": "Normal",
        "visual_quality": "Balanced",
        "master_volume": 0.6,
        "fullscreen": False,
        "fps_cap": settings.FPS,
        "show_fps": True,
    }


def _sanitize_user_settings(raw: Dict) -> Dict:
    defaults = _default_user_settings()
    payload = raw if isinstance(raw, dict) else {}

    difficulty = payload.get("difficulty", defaults["difficulty"])
    if difficulty not in settings.DIFFICULTY_PRESETS:
        difficulty = defaults["difficulty"]

    visual_quality = payload.get("visual_quality", defaults["visual_quality"])
    if visual_quality not in settings.VISUAL_PRESETS:
        visual_quality = defaults["visual_quality"]

    try:
        master_volume = float(payload.get("master_volume", defaults["master_volume"]))
    except (TypeError, ValueError):
        master_volume = defaults["master_volume"]
    master_volume = max(0.0, min(1.0, master_volume))

    fullscreen = bool(payload.get("fullscreen", defaults["fullscreen"]))

    try:
        fps_cap = int(payload.get("fps_cap", defaults["fps_cap"]))
    except (TypeError, ValueError):
        fps_cap = defaults["fps_cap"]
    if fps_cap not in settings.FPS_OPTIONS:
        fps_cap = defaults["fps_cap"]

    show_fps = bool(payload.get("show_fps", defaults["show_fps"]))

    return {
        "difficulty": difficulty,
        "visual_quality": visual_quality,
        "master_volume": master_volume,
        "fullscreen": fullscreen,
        "fps_cap": fps_cap,
        "show_fps": show_fps,
    }


def load_user_settings() -> Dict:
    _ensure_dir()
    if not os.path.exists(SETTINGS_FILE):
        return _default_user_settings()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return _sanitize_user_settings(raw)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return _default_user_settings()


def save_user_settings(user_settings: Dict) -> Dict:
    _ensure_dir()
    cleaned = _sanitize_user_settings(user_settings)
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
    return cleaned
