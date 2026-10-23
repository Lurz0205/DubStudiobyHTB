"""Script to download ASR models (SenseVoiceSmall and faster-whisper) directly into models/."""
import argparse
import sys
from pathlib import Path


def download_sensevoice(dest_dir: Path):
    dest = dest_dir / "SenseVoiceSmall"
    dest.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("Đang tải mô hình SenseVoiceSmall (~900 MB)...")
    print(f"Thư mục lưu: {dest.resolve()}")
    print("=" * 60)
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id="FunAudioLLM/SenseVoiceSmall",
            local_dir=str(dest.resolve()),
            local_dir_use_symlinks=False,
        )
        print("\n" + "=" * 60)
        print("✓ TẢI SENSEVOICE-SMALL THÀNH CÔNG!")
        print("=" * 60)
    except Exception as ex:
        print(f"Thử tải qua HuggingFace không thành công ({ex}), đang chuyển sang ModelScope...")
        try:
            from modelscope import snapshot_download as ms_download
            ms_dir = ms_download("iic/SenseVoiceSmall", cache_dir=str(dest_dir))
            # Move contents to SenseVoiceSmall if needed
            import shutil
            ms_path = Path(ms_dir)
            if ms_path.resolve() != dest.resolve():
                for item in ms_path.iterdir():
                    shutil.copy2(item, dest) if item.is_file() else shutil.copytree(item, dest / item.name, dirs_exist_ok=True)
            print("\n" + "=" * 60)
            print("✓ TẢI SENSEVOICE-SMALL THÀNH CÔNG TỪ MODELSCOPE!")
            print("=" * 60)
        except Exception as e:
            print(f"\n[LỖI TẢI SENSEVOICE]: {e}", file=sys.stderr)
            sys.exit(1)


def download_whisper(dest_dir: Path, model_size: str = "large-v3"):
    print("=" * 60)
    print(f"Đang tải mô hình faster-whisper {model_size} (~3.09 GB)...")
    print(f"Thư mục lưu: {dest_dir.resolve()}")
    print("=" * 60)
    try:
        from faster_whisper import WhisperModel
        WhisperModel(model_size, device="cpu", compute_type="int8", download_root=str(dest_dir.resolve()))
        print("\n" + "=" * 60)
        print(f"✓ TẢI FASTER-WHISPER {model_size.upper()} THÀNH CÔNG!")
        print("=" * 60)
    except Exception as e:
        print(f"\n[LỖI TẢI WHISPER]: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Tải mô hình ASR cho DubStudio")
    parser.add_argument("--model", choices=["sensevoice", "whisper", "all"], default="sensevoice", help="Mô hình cần tải")
    args = parser.parse_args()

    models_dir = Path("models").resolve()
    models_dir.mkdir(parents=True, exist_ok=True)

    if args.model in ("sensevoice", "all"):
        download_sensevoice(models_dir)

    if args.model in ("whisper", "all"):
        download_whisper(models_dir)


if __name__ == "__main__":
    main()
