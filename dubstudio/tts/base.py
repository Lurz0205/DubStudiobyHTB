"""Base interface and voice definitions for TTS engines."""
from typing import Any

MALE_VOICES = {
    "Minh Đức", "Hải Đăng", "Quốc Tuấn", "Quang Sơn", "Thiện Minh",
    "Minh Triết", "Đức Trí", "Thái Sơn", "Xuân Vĩnh", "Thanh Bình",
    "Phạm Tuyên", "Thiền Tâm Đức", "Adam", "Adam bựa",
}

FEMALE_VOICES = {
    "Quỳnh Anh", "Mai Anh", "Trúc Ly", "Thùy Dung", "Ngọc Huyền",
    "Ngọc Trân", "Ngọc Linh", "Đoan Trang", "Thục Đoan", "Mỹ Duyên", "Kim Thanh",
}

ALL_VOICES = MALE_VOICES | FEMALE_VOICES


def clean_voice_name(voice: Any, default: str = "Minh Đức") -> str:
    """Clean and strip descriptive tags (like '(Nam - Tự nhiên)') to match valid VieNeu voice names."""
    if not voice:
        return default
    v = str(voice).strip()
    if v in ALL_VOICES:
        return v
    import re
    # Remove parenthesized phrases like (Nam - Tự nhiên) or (Nữ - Truyền cảm)
    cleaned = re.sub(r'\(.*?\)', '', v).strip()
    if cleaned in ALL_VOICES:
        return cleaned
    # Match longest substring against known voices
    for cand in sorted(ALL_VOICES, key=len, reverse=True):
        if cand.lower() in v.lower():
            return cand
    return default


def get_voice_gender(voice_name: str) -> str:
    """Return 'female' or 'male' for known VieNeu voices, or 'unknown'."""
    v = clean_voice_name(voice_name, "")
    if v in FEMALE_VOICES:
        return "female"
    if v in MALE_VOICES:
        return "male"
    return "unknown"


def resolve_vieneu_dirs() -> tuple[str, str]:
    """Resolve physical disk directories for VieNeu backbone and MOSS tokenizer 100% offline."""
    from pathlib import Path
    from dubstudio.paths import get_models_dir
    models_dir = get_models_dir()

    # 1. Search candidate locations for VieNeu-TTS-v3-Turbo backbone
    backbone_dir = None
    backbone_cands = [
        Path.home() / ".cache" / "huggingface" / "hub" / "models--pnnbao-ump--VieNeu-TTS-v3-Turbo" / "snapshots",
        models_dir / "hf" / "hub" / "models--pnnbao-ump--VieNeu-TTS-v3-Turbo" / "snapshots",
        models_dir / "vieneu",
        Path("models/vieneu"),
    ]
    for cand in backbone_cands:
        if cand.is_dir():
            if cand.name == "snapshots":
                snaps = [d for d in cand.iterdir() if d.is_dir()]
                if snaps:
                    backbone_dir = str(snaps[0].resolve())
                    break
            elif (cand / "config.json").exists():
                backbone_dir = str(cand.resolve())
                break

    # 2. Search candidate locations for MOSS Audio Tokenizer
    moss_dir = None
    moss_cands = [
        Path.home() / ".cache" / "huggingface" / "hub" / "models--OpenMOSS-Team--MOSS-Audio-Tokenizer-Nano" / "snapshots",
        models_dir / "hf" / "hub" / "models--OpenMOSS-Team--MOSS-Audio-Tokenizer-Nano" / "snapshots",
        models_dir / "moss",
        Path("models/moss"),
    ]
    for cand in moss_cands:
        if cand.is_dir():
            if cand.name == "snapshots":
                snaps = [d for d in cand.iterdir() if d.is_dir()]
                if snaps:
                    moss_dir = str(snaps[0].resolve())
                    break
            elif (cand / "config.json").exists():
                moss_dir = str(cand.resolve())
                break

    if not backbone_dir or not moss_dir:
        try:
            from huggingface_hub import snapshot_download
            if not backbone_dir:
                backbone_dir = snapshot_download("pnnbao-ump/VieNeu-TTS-v3-Turbo", local_files_only=True)
            if not moss_dir:
                moss_dir = snapshot_download("OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano", local_files_only=True)
        except Exception:
            pass

    return (
        backbone_dir or "pnnbao-ump/VieNeu-TTS-v3-Turbo",
        moss_dir or "OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano"
    )
