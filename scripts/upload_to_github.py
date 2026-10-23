"""Upload release assets to GitHub Release with robust streaming and retry."""
import json
import os
from pathlib import Path
import time
import requests

def wait_for_internet(timeout=180):
    """Wait until internet connection and GitHub API are reachable again."""
    print("  [Wifi bi gian doan, dang cho ket noi hoi phuc...]")
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = requests.get("https://api.github.com", headers={"User-Agent": "DubStudio"}, timeout=5)
            if req.status_code in (200, 403):
                # Wait 3 extra seconds for Windows sockets to settle
                time.sleep(3)
                print("  [Wifi da ket noi lai on dinh! Bat dau chu ky an toan 15 phut.]")
                return True
        except Exception:
            time.sleep(2)
    return False
def upload_all():
    token = None
    repo_url = None
    for l in Path(".env").read_text(encoding="utf-8").splitlines():
        if l.startswith("GITHUB_TOKEN="):
            token = l.split("=", 1)[1].strip()
        elif l.startswith("GITHUB_REPO_URL="):
            repo_url = l.split("=", 1)[1].strip()

    if not token or not repo_url:
        print("Missing GITHUB_TOKEN or GITHUB_REPO_URL in .env")
        return False

    parts = repo_url.rstrip("/").split("/")
    owner = parts[-2]
    repo = parts[-1]
    release_id = 421419987

    api_base = f"https://api.github.com/repos/{owner}/{repo}/releases/{release_id}"
    upload_base = f"https://uploads.github.com/repos/{owner}/{repo}/releases/{release_id}/assets"

    headers_api = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "DubStudio-Agent",
    }

    # 1. Get existing assets
    resp = requests.get(api_base, headers=headers_api, timeout=30)
    if resp.status_code != 200:
        print(f"Failed to get release info: {resp.status_code}")
        return False

    rel_info = resp.json()
    existing_assets = {a["name"]: a["id"] for a in rel_info.get("assets", [])}
    print("Currently uploaded assets:", list(existing_assets.keys()))

    # Files to upload in priority order
    files = [
        Path("dist/releases/RELEASES"),
        Path("dist/releases/assets.win.json"),
        Path("dist/releases/DubStudio-1.0.1-delta.nupkg"),
        Path("dist/releases/DubStudio-1.0.1-full.nupkg"),
        Path("dist/releases/DubStudio-win-Setup.exe"),
    ]

    for fpath in files:
        if not fpath.exists():
            continue
        fname = fpath.name
        fsize = fpath.stat().st_size
        fsize_mb = fsize / (1024 * 1024)

        if fname in existing_assets:
            print(f"Skipping {fname} (already uploaded)")
            continue

        print(f"\nUploading {fname} ({fsize_mb:.1f} MB)...")
        headers_upload = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/octet-stream",
            "User-Agent": "DubStudio-Agent",
        }

        url = f"{upload_base}?name={fname}"
        success = False
        for attempt in range(1, 4):
            try:
                t0 = time.time()
                class ProgressReader:
                    def __init__(self, filename, total_size):
                        self._f = open(filename, "rb")
                        self._total = total_size
                        self._read_so_far = 0
                        self._last_pct = -1

                    def read(self, size=-1):
                        chunk = self._f.read(size)
                        if chunk:
                            self._read_so_far += len(chunk)
                            pct = int((self._read_so_far / self._total) * 100)
                            if pct != self._last_pct and pct % 10 == 0:
                                self._last_pct = pct
                                mb_done = self._read_so_far / (1024 * 1024)
                                dur = time.time() - t0
                                spd = (mb_done / dur) if dur > 0 else 0
                                print(f"  -> {pct}% ({mb_done:.1f}/{fsize_mb:.1f} MB) - {spd:.2f} MB/s")
                        return chunk

                    def __len__(self):
                        return self._total

                    def close(self):
                        self._f.close()

                reader = ProgressReader(fpath, fsize)
                headers_upload["Content-Length"] = str(fsize)
                r = requests.post(url, headers=headers_upload, data=reader, timeout=1800)
                reader.close()
                if r.status_code in (200, 201):
                    dur = time.time() - t0
                    speed = (fsize_mb / dur) if dur > 0 else 0
                    print(f"Uploaded {fname} successfully in {dur:.1f}s ({speed:.2f} MB/s)!")
                    success = True
                    break
                else:
                    print(f"Attempt {attempt} failed with status {r.status_code}: {r.text[:200]}")
            except Exception as e:
                print(f"Attempt {attempt} encountered error: {e}")
                wait_for_internet()

        if not success:
            print(f"FAILED to upload {fname} after 3 attempts.")
            return False

    # Publish release
    print("\nPublishing release v1.0.1 on GitHub...")
    r_pub = requests.patch(
        api_base,
        headers=headers_api,
        json={"draft": False, "prerelease": True},
        timeout=30,
    )
    if r_pub.status_code == 200:
        print("Release v1.0.1 PUBLISHED successfully!")
        return True
    else:
        print(f"Failed to publish release: {r_pub.status_code}: {r_pub.text}")
        return False

if __name__ == "__main__":
    upload_all()
