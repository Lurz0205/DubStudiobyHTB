"""Base interface and voice definitions for TTS engines."""

MALE_VOICES = {
    "Minh Đức", "Hải Đăng", "Quốc Tuấn", "Quang Sơn", "Thiện Minh",
    "Minh Triết", "Đức Trí", "Thái Sơn", "Xuân Vĩnh", "Thanh Bình",
    "Phạm Tuyên", "Thiền Tâm Đức", "Adam", "Adam bựa",
}

FEMALE_VOICES = {
    "Quỳnh Anh", "Mai Anh", "Trúc Ly", "Thùy Dung", "Ngọc Huyền",
    "Ngọc Trân", "Ngọc Linh", "Đoan Trang", "Thục Đoan", "Mỹ Duyên", "Kim Thanh",
}


def get_voice_gender(voice_name: str) -> str:
    """Return 'female' or 'male' for known VieNeu voices, or 'unknown'."""
    if voice_name in FEMALE_VOICES:
        return "female"
    if voice_name in MALE_VOICES:
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
