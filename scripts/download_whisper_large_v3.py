"""Download faster-whisper large-v3 model to models/ directory."""
import sys
from pathlib import Path
from faster_whisper import WhisperModel

def main():
    models_dir = Path("models")
    models_dir.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("Bat dau tai mo hinh faster-whisper large-v3 (~3.09 GB)...")
    print("Thu muc luu: models/")
    print("=" * 60)
    try:
        # Initializing WhisperModel with cpu and download_root triggers snapshot download to models/
        model = WhisperModel("large-v3", device="cpu", compute_type="int8", download_root=str(models_dir))
        print("\n" + "=" * 60)
        print("✓ TAI MO HINH LARGE-V3 THANH CONG!")
        print("=" * 60)
    except Exception as e:
        print(f"\n[LOI TAI MO HINH]: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
