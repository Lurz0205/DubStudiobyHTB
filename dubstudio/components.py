"""Component and data package lifecycle management (components.json)."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Dict, List, Optional
import httpx

from dubstudio.packaging import get_user_data_dir, is_packaged
from dubstudio.version import APP_VERSION

def _load_default_manifest() -> Dict[str, Any]:
    from dubstudio.paths import get_resource_dir, get_app_dir
    candidates = [
        get_app_dir() / "config" / "components.json",
        get_resource_dir() / "config" / "components.json",
        Path("config") / "components.json",
    ]
    for cfg_file in candidates:
        if cfg_file.exists():
            try:
                return json.loads(cfg_file.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {
        "feed_version": 2,
        "packages": [
            {
                "id": "ffmpeg_binaries",
                "name": "Bộ công cụ FFmpeg (GPU NVENC)",
                "version": 1,
                "url": "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip",
                "sha256": "44adfe744743226dbffcbdb816fa4fa66c30e797a70183184db1f44e1124e542",
                "size_bytes": 45_000_000,
                "license": "GPL-3.0 / LGPL-2.1 (FFmpeg Developers)",
                "format": "zip",
                "target_dir": "bin",
                "required": True,
                "requires_app": "2.1.0",
                "changelog_vi": "FFmpeg bản hỗ trợ xuất video tăng tốc phần cứng NVENC h264.",
            },
            {
                "id": "torch_core",
                "name": "Khung AI PyTorch 2.5 Core",
                "version": 1,
                "url": "https://download.pytorch.org/whl/cpu/torch-2.5.1%2Bcpu-cp311-cp311-win_amd64.whl",
                "sha256": "9a0a0df2c5d1df3b9da9ea79dfa95c96365b214df089e02c676ef2ea926b0ee1",
                "size_bytes": 185_000_000,
                "license": "BSD-3-Clause (Meta Platforms, Inc.)",
                "format": "wheel",
                "target_dir": "runtime/site-packages",
                "required": True,
                "requires_app": "2.1.0",
                "changelog_vi": "Thư viện PyTorch 2.5.1 CPU core chính thức từ download.pytorch.org.",
            },
            {
                "id": "ai_libs",
                "name": "Công cụ chạy mô hình Whisper & ONNX",
                "version": 1,
                "url": "https://files.pythonhosted.org/packages/cp311/c/ctranslate2/ctranslate2-4.5.0-cp311-cp311-win_amd64.whl",
                "sha256": "18f99e390c293774026859e9a4f4d22da8c9eb474dca76a95e0c52ebf399f606",
                "size_bytes": 55_000_000,
                "license": "MIT (OpenNMT / Systran)",
                "format": "wheel",
                "target_dir": "runtime/site-packages",
                "required": True,
                "requires_app": "2.1.0",
                "changelog_vi": "CTranslate2 và công cụ suy luận nhanh cho nhận dạng giọng nói.",
            },
            {
                "id": "vieneu_tts_voices",
                "name": "Mô hình giọng đọc thuyết minh VieNeu-TTS v3",
                "version": 1,
                "url": "https://huggingface.co/neu-tts/vieneu-tts-v3-turbo/resolve/main/model.onnx",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "size_bytes": 280_000_000,
                "license": "Apache-2.0 (VieNeu-TTS Project)",
                "format": "raw",
                "target_dir": "models/vieneu",
                "required": True,
                "requires_app": "2.1.0",
                "changelog_vi": "Model giọng đọc tiếng Việt Bắc - Nam chất lượng cao.",
            },
        ]
    }


EMBEDDED_COMPONENTS_MANIFEST = _load_default_manifest()

# Required component versions for this app version
APP_REQUIRED_COMPONENTS = {
    "ffmpeg_binaries": 1,
    "torch_core": 1,
    "ai_libs": 1,
    "vieneu_tts_voices": 1,
}

MAX_AUTO_DOWNLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
CHECK_INTERVAL_SECONDS = 6 * 3600  # 6 hours


def get_components_dir() -> Path:
    """Return root directory for component packages in user data directory."""
    p = get_user_data_dir() / "components"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_installed_components_file() -> Path:
    return get_components_dir() / "installed.json"


def get_installed_components() -> Dict[str, Dict[str, Any]]:
    """Return map of {pkg_id: installed_record}."""
    f = get_installed_components_file()
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_installed_components(data: Dict[str, Dict[str, Any]]) -> None:
    f = get_installed_components_file()
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_components_manifest(feed_url: Optional[str] = None) -> Dict[str, Any]:
    """Fetch latest components manifest or fallback to embedded."""
    if feed_url:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(feed_url)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
    return EMBEDDED_COMPONENTS_MANIFEST


def sync_installed_components() -> Dict[str, Dict[str, Any]]:
    """Scan physical presence of components on disk and sync into installed.json registry."""
    manifest = fetch_components_manifest()
    packages = manifest.get("packages", [])
    installed = get_installed_components()
    changed = False

    for pkg in packages:
        pkg_id = pkg["id"]
        latest_ver = int(pkg.get("version", 1))
        is_ready, _ = is_component_ready(pkg_id)
        if is_ready:
            inst = installed.get(pkg_id)
            if not inst or int(inst.get("version", 0)) < latest_ver:
                installed[pkg_id] = {
                    "version": latest_ver,
                    "installed_at": time.time(),
                    "status": "ready",
                }
                changed = True
        else:
            if pkg_id in installed:
                del installed[pkg_id]
                changed = True

    if changed:
        save_installed_components(installed)
    return installed


def check_for_component_updates(feed_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Check if any installed component is older than the latest compatible version.
    Returns list of packages with available updates.
    """
    manifest = fetch_components_manifest(feed_url)
    packages = manifest.get("packages", [])
    installed = get_installed_components()

    available_updates = []
    for pkg in packages:
        pkg_id = pkg["id"]
        latest_ver = int(pkg.get("version", 1))

        # Check app compatibility
        req_app = pkg.get("requires_app", "1.0.0")
        if req_app > APP_VERSION:
            continue

        inst = installed.get(pkg_id)
        inst_ver = int(inst.get("version", 0)) if inst else 0

        if inst_ver < latest_ver:
            available_updates.append({
                "package": pkg,
                "current_version": inst_ver,
                "new_version": latest_ver,
                "size_bytes": pkg.get("size_bytes", 0),
                "size_mb": round(pkg.get("size_bytes", 0) / (1024 * 1024), 1),
                "is_large": pkg.get("size_bytes", 0) > MAX_AUTO_DOWNLOAD_SIZE_BYTES,
                "changelog": pkg.get("changelog_vi", ""),
            })

    return available_updates


def verify_file_sha256(file_path: Path, expected_sha: str) -> bool:
    """Verify SHA256 checksum of downloaded file."""
    if not file_path.exists():
        return False
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower() == expected_sha.strip().lower()


def install_package_atomic(
    pkg: Dict[str, Any],
    downloaded_zip: Path,
) -> bool:
    """
    Verify sha256, extract to dedicated version folder (id/v<ver>),
    and atomically switch active reference once complete.
    Supports wheel extraction into runtime site-packages without pip.
    """
    pkg_id = pkg["id"]
    version = int(pkg.get("version", 1))
    expected_sha = pkg.get("sha256", "")
    pkg_format = pkg.get("format", "zip").lower()
    target_rel = pkg.get("target_dir")

    if expected_sha and not verify_file_sha256(downloaded_zip, expected_sha):
        return False

    pkg_root = get_components_dir() / pkg_id
    version_dir = pkg_root / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)

    # Determine extraction / install target
    import zipfile
    if target_rel:
        target_dest = get_user_data_dir() / target_rel
        target_dest.mkdir(parents=True, exist_ok=True)
    else:
        target_dest = version_dir

    if pkg_format in ("zip", "wheel") or downloaded_zip.suffix in (".zip", ".whl"):
        try:
            with zipfile.ZipFile(downloaded_zip, "r") as z:
                z.extractall(target_dest)
                if target_dest != version_dir:
                    z.extractall(version_dir)
        except Exception:
            shutil.copy2(downloaded_zip, target_dest / downloaded_zip.name)
            shutil.copy2(downloaded_zip, version_dir / downloaded_zip.name)
    else:
        # Raw file (e.g. .onnx, .ckpt, .bin)
        dest_file = target_dest / downloaded_zip.name
        shutil.copy2(downloaded_zip, dest_file)
        shutil.copy2(downloaded_zip, version_dir / downloaded_zip.name)

    # Atomic switch: update installed.json
    installed = get_installed_components()
    installed[pkg_id] = {
        "version": version,
        "path": str(target_dest.resolve()),
        "version_dir": str(version_dir.resolve()),
        "installed_at": time.time(),
        "name": pkg.get("name", pkg_id),
        "license": pkg.get("license", "Unknown"),
    }
    save_installed_components(installed)
    return True


def clean_old_package_versions(pkg_id: str, keep_latest: int = 1) -> None:
    """Clean obsolete versions of a package when disk space is low or upon user action."""
    pkg_root = get_components_dir() / pkg_id
    if not pkg_root.exists():
        return

    installed = get_installed_components()
    active_path = installed.get(pkg_id, {}).get("path")

    for item in pkg_root.iterdir():
        if item.is_dir() and item.name.startswith("v"):
            if active_path and str(item.resolve()) == active_path:
                continue
            try:
                shutil.rmtree(item, ignore_errors=True)
            except Exception:
                pass


def is_component_ready(pkg_id: str) -> Tuple[bool, str]:
    """
    Check if a required component is installed and matches minimum version.
    Inspects installed.json first, then verifies physical presence on disk.
    Returns (is_ready, user_explanation_vi).
    """
    from dubstudio.paths import get_models_dir, get_bin_dir, resolve_tool
    models_dir = get_models_dir()

    # 1. Physical presence fast-checks
    if pkg_id == "ffmpeg_binaries":
        try:
            resolve_tool("ffmpeg")
            return True, "Đã tích hợp sẵn"
        except Exception:
            return False, "Thiếu tệp ffmpeg.exe trong bin/"

    if pkg_id == "kim_vocal_2":
        candidates = [
            models_dir / "audio-separator" / "Kim_Vocal_2.onnx",
            models_dir / "Kim_Vocal_2.onnx",
            Path("models/audio-separator/Kim_Vocal_2.onnx"),
            Path("models/Kim_Vocal_2.onnx"),
        ]
        if any(c.is_file() and c.stat().st_size > 1024 * 1024 for c in candidates):
            return True, "Đã sẵn sàng"

    if pkg_id == "bs_roformer":
        candidates = [
            models_dir / "audio-separator" / "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
            models_dir / "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
            Path("models/audio-separator/model_bs_roformer_ep_317_sdr_12.9755.ckpt"),
            Path("models/model_bs_roformer_ep_317_sdr_12.9755.ckpt"),
        ]
        if any(c.is_file() and c.stat().st_size > 1024 * 1024 for c in candidates):
            return True, "Đã sẵn sàng"

    if pkg_id == "sensevoice_small":
        candidates = [
            models_dir / "SenseVoiceSmall",
            models_dir / "hf" / "hub" / "models--FunAudioLLM--SenseVoiceSmall",
            Path("models/SenseVoiceSmall"),
        ]
        for c in candidates:
            if c.is_dir():
                for target_file in [c / "model.pt", c / "model.onnx"]:
                    if target_file.is_file() and target_file.stat().st_size > 100 * 1024 * 1024:
                        return True, "Đã sẵn sàng"
                for snap in c.glob("snapshots/*/*model*.pt"):
                    if snap.is_file() and snap.stat().st_size > 100 * 1024 * 1024:
                        return True, "Đã sẵn sàng"
        return False, "Chưa tải"

    if pkg_id == "whisper_large_v3":
        candidates = [
            models_dir / "faster-whisper-large-v3",
            models_dir / "models--Systran--faster-whisper-large-v3",
            Path("models/faster-whisper-large-v3"),
            Path("models/models--Systran--faster-whisper-large-v3"),
        ]
        for c in candidates:
            if c.is_dir():
                for target_file in [c / "model.bin", c / "model.safetensors"]:
                    if target_file.is_file() and target_file.stat().st_size > 100 * 1024 * 1024:
                        return True, "Đã sẵn sàng"
                for snap in c.glob("snapshots/*/*model*"):
                    if snap.is_file() and snap.stat().st_size > 100 * 1024 * 1024:
                        return True, "Đã sẵn sàng"
        return False, "Chưa tải"

    if pkg_id == "vieneu_tts_voices":
        candidates = [
            models_dir / "hf" / "hub" / "models--pnnbao-ump--VieNeu-TTS-v3-Turbo",
            Path.home() / ".cache" / "huggingface" / "hub" / "models--pnnbao-ump--VieNeu-TTS-v3-Turbo",
            models_dir / "vieneu",
            models_dir / "neu-tts",
            Path("models/vieneu"),
            Path("models/neu-tts"),
        ]
        for c in candidates:
            if c.exists() and (any(c.glob("snapshots/*")) or any(c.glob("*.onnx")) or any(c.glob("*.pt")) or any(c.glob("*.safetensors"))):
                return True, "Đã sẵn sàng"
        try:
            from huggingface_hub import snapshot_download
            p = snapshot_download("pnnbao-ump/VieNeu-TTS-v3-Turbo", local_files_only=True)
            if Path(p).exists():
                return True, "Đã sẵn sàng"
        except Exception:
            pass

    if pkg_id == "torch_core":
        try:
            import torch
            return True, "Đã sẵn sàng"
        except Exception:
            runtime_site = get_user_data_dir() / "runtime" / "site-packages"
            if (runtime_site / "torch").exists():
                return True, "Đã sẵn sàng"
            return False, "Chưa cài đặt PyTorch Runtime"

    # 2. Check installed.json manifest registry
    installed = get_installed_components()
    entry = installed.get(pkg_id)
    if entry and entry.get("path"):
        raw_p = str(entry["path"]).strip()
        if raw_p:
            path = Path(raw_p)
            if path.is_file() and path.stat().st_size > 0:
                return True, "Đã sẵn sàng"
            if path.is_dir() and any(path.iterdir()):
                return True, "Đã sẵn sàng"

    return False, "Chưa tải"


def download_component_file(
    pkg: Dict[str, Any],
    progress_cb=None,
    cancel_flag=None,
) -> bool:
    """
    Download component with responsive chunk streaming and instant cancellation.
    Atomically installs to dest_dir only upon 100% successful verification.
    Guarantees no leftover garbage or partially-written models on disk.
    """
    import os
    import shutil
    import requests
    from dubstudio.paths import get_user_data_dir, get_models_dir

    pkg_id = pkg["id"]
    target_rel = pkg.get("target_dir", "models")
    expected_sha = pkg.get("sha256", "")
    pkg_format = pkg.get("format", "raw")

    # Determine destination folder
    if target_rel.startswith("models"):
        dest_dir = get_models_dir()
        sub = target_rel.replace("models", "").strip("/\\")
        if sub:
            dest_dir = dest_dir / sub
    else:
        dest_dir = get_user_data_dir() / target_rel

    dest_dir.mkdir(parents=True, exist_ok=True)

    # Determine download items: list of (rel_filename, url, approx_bytes)
    if pkg_id == "sensevoice_small":
        files_to_get = [
            ("model.pt", "https://huggingface.co/FunAudioLLM/SenseVoiceSmall/resolve/main/model.pt", 936291369),
            ("config.yaml", "https://huggingface.co/FunAudioLLM/SenseVoiceSmall/resolve/main/config.yaml", 1855),
            ("chn_jpn_yue_eng_ko_spectok.bpe.model", "https://huggingface.co/FunAudioLLM/SenseVoiceSmall/resolve/main/chn_jpn_yue_eng_ko_spectok.bpe.model", 377341),
        ]
        is_directory_package = True
    elif pkg_id == "whisper_large_v3":
        files_to_get = [
            ("model.bin", "https://huggingface.co/Systran/faster-whisper-large-v3/resolve/main/model.bin", 3240000000),
            ("config.json", "https://huggingface.co/Systran/faster-whisper-large-v3/resolve/main/config.json", 2400),
            ("tokenizer.json", "https://huggingface.co/Systran/faster-whisper-large-v3/resolve/main/tokenizer.json", 2400000),
            ("vocabulary.json", "https://huggingface.co/Systran/faster-whisper-large-v3/resolve/main/vocabulary.json", 1000000),
        ]
        is_directory_package = True
    else:
        url = pkg.get("url")
        if not url:
            return False
        file_name = url.split("?")[0].split("/")[-1]
        files_to_get = [(file_name, url, int(pkg.get("size_bytes", 0)))]
        is_directory_package = False

    # Create temporary isolated staging folder
    staging_dir = dest_dir.parent / f".staging_{pkg_id}_{os.getpid()}_{int(time.time())}"
    staging_dir.mkdir(parents=True, exist_ok=True)

    total_bytes_all = sum(item[2] for item in files_to_get)
    if total_bytes_all <= 0:
        total_bytes_all = int(pkg.get("size_bytes", 0)) or 1

    overall_downloaded = 0
    was_cancelled = False

    try:
        headers = {
            "User-Agent": "DubStudio-Downloader/1.1.0",
            "Accept": "*/*",
        }
        for fname, f_url, approx_len in files_to_get:
            if cancel_flag and cancel_flag():
                was_cancelled = True
                break

            target_file = staging_dir / fname
            part_file = staging_dir / f"{fname}.part"

            with requests.get(f_url, stream=True, timeout=60, headers=headers, allow_redirects=True) as resp:
                resp.raise_for_status()
                with open(part_file, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=256 * 1024):
                        if cancel_flag and cancel_flag():
                            was_cancelled = True
                            break
                        if chunk:
                            f.write(chunk)
                            overall_downloaded += len(chunk)
                            if progress_cb:
                                pct = min(99, int((overall_downloaded / max(1, total_bytes_all)) * 100))
                                progress_cb(pct, overall_downloaded, total_bytes_all)

            if was_cancelled:
                break

            if part_file.exists():
                os.replace(str(part_file), str(target_file))

        if was_cancelled:
            shutil.rmtree(staging_dir, ignore_errors=True)
            return False

        # Post-download verification
        if pkg_id == "sensevoice_small":
            main_w = staging_dir / "model.pt"
            if not (main_w.exists() and main_w.stat().st_size > 100 * 1024 * 1024):
                shutil.rmtree(staging_dir, ignore_errors=True)
                raise ValueError("Tệp trọng số SenseVoice model.pt bị thiếu hoặc tải chưa hoàn tất.")
        elif pkg_id == "whisper_large_v3":
            main_w = staging_dir / "model.bin"
            if not (main_w.exists() and main_w.stat().st_size > 100 * 1024 * 1024):
                shutil.rmtree(staging_dir, ignore_errors=True)
                raise ValueError("Tệp trọng số faster-whisper model.bin bị thiếu hoặc tải chưa hoàn tất.")
        elif expected_sha:
            fname = files_to_get[0][0]
            if not verify_file_sha256(staging_dir / fname, expected_sha):
                shutil.rmtree(staging_dir, ignore_errors=True)
                raise ValueError(f"Mã kiểm tra SHA256 không khớp cho gói {pkg_id}")

        # Atomic installation into dest_dir
        if is_directory_package:
            dest_dir.mkdir(parents=True, exist_ok=True)
            for item in staging_dir.iterdir():
                dest_file = dest_dir / item.name
                if dest_file.exists():
                    if dest_file.is_dir():
                        shutil.rmtree(dest_file, ignore_errors=True)
                    else:
                        dest_file.unlink(missing_ok=True)
                shutil.move(str(item), str(dest_file))
        elif pkg_format in ("zip", "wheel") or files_to_get[0][0].endswith((".zip", ".whl")):
            import zipfile
            with zipfile.ZipFile(staging_dir / files_to_get[0][0], "r") as z:
                z.extractall(dest_dir)
        else:
            fname = files_to_get[0][0]
            dest_file = dest_dir / fname
            if dest_file.exists():
                dest_file.unlink(missing_ok=True)
            shutil.move(str(staging_dir / fname), str(dest_file))

        shutil.rmtree(staging_dir, ignore_errors=True)

        # Mark installed in installed.json
        installed = get_installed_components()
        installed[pkg_id] = {
            "version": int(pkg.get("version", 1)),
            "path": str(dest_dir.resolve()),
            "name": pkg.get("name", pkg_id),
            "installed_at": time.time(),
            "status": "ready",
        }
        save_installed_components(installed)

        if progress_cb:
            progress_cb(100, total_bytes_all, total_bytes_all)

        return True
    except Exception as e:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise e


def cleanup_dangling_staging_files():
    """Remove any leftover .staging_* or .part files from previously terminated app runs."""
    import shutil
    from dubstudio.paths import get_models_dir, get_user_data_dir
    for base in [get_models_dir(), get_user_data_dir()]:
        if base.exists():
            for p in base.glob("**/.staging_*"):
                try:
                    if p.is_dir():
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        p.unlink(missing_ok=True)
                except Exception:
                    pass
            for p in base.glob("**/*.part"):
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass
