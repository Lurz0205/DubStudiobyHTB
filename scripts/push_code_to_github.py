"""Safely push source code to GitHub main branch via GitHub Git Data API."""
import base64
import hashlib
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import time
from pathlib import Path
import dotenv
import requests

dotenv.load_dotenv()
token = os.getenv("GITHUB_TOKEN")
repo_url = os.getenv("GITHUB_REPO_URL")

if not token or not repo_url:
    print("Error: GITHUB_TOKEN or GITHUB_REPO_URL missing in .env")
    exit(1)

parts = repo_url.rstrip("/").split("/")
owner = parts[-2]
repo = parts[-1]

api_base = f"https://api.github.com/repos/{owner}/{repo}"
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "DubStudio-Sync",
}

session = requests.Session()
session.headers.update(headers)

# Parse requested tag and commit message from CLI arguments
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dubstudio.version import APP_VERSION

requested_tag = None
custom_msg = None
for i, arg in enumerate(sys.argv):
    if arg == "--tag" and i + 1 < len(sys.argv):
        requested_tag = sys.argv[i + 1]
    elif arg.startswith("--tag="):
        requested_tag = arg.split("=", 1)[1]
    elif arg == "--msg" and i + 1 < len(sys.argv):
        custom_msg = sys.argv[i + 1]
    elif arg.startswith("--msg="):
        custom_msg = arg.split("=", 1)[1]

if custom_msg:
    commit_msg = custom_msg
elif requested_tag:
    tag_clean = requested_tag if requested_tag.startswith("v") else f"v{requested_tag}"
    commit_msg = f"Release {tag_clean}: Next-Gen Studio UI (React/Tailwind + PyWebView), Dynamic Ports, Zero PyQt6, and Syllable-Aware LLM Fit"
else:
    commit_msg = f"Update DubStudio v{APP_VERSION}: Next-Gen Studio UI, Dynamic Ports, and Syllable-Aware LLM Fit"

# 0a. Pre-Release Cleanup on Remote:
# ONLY if a new release tag is requested (--tag vX.X.X):
# Delete existing Release and Tag for requested_tag on GitHub before auditing/pushing.
# This guarantees that the latest release on GitHub is strictly < CURRENT_VERSION (e.g. v1.1.2),
# ensuring Velopack and the audit tool anchor 100% to the previous official release!
if requested_tag:
    target_clean_tag = requested_tag if requested_tag.startswith("v") else f"v{requested_tag}"
    print(f"Checking pre-existing release/tag for {target_clean_tag} on GitHub...", flush=True)
    try:
        rel_resp = session.get(f"{api_base}/releases/tags/{target_clean_tag}")
        if rel_resp.status_code == 200:
            rel_id = rel_resp.json().get("id")
            if rel_id:
                del_rel = session.delete(f"{api_base}/releases/{rel_id}")
                if del_rel.status_code in (200, 204):
                    print(f"[PRE-CLEAN] Deleted existing GitHub Release object for {target_clean_tag} (ID: {rel_id}) to restore clean base.", flush=True)
                    time.sleep(1.0)
        del_tag = session.delete(f"{api_base}/git/refs/tags/{target_clean_tag}")
        if del_tag.status_code in (200, 204):
            print(f"[PRE-CLEAN] Deleted existing remote Git Tag ref {target_clean_tag}.", flush=True)
            time.sleep(1.0)
    except Exception as e:
        print(f"Notice: Pre-cleanup error: {e}", flush=True)

# 0b. Mandatory Pre-Push Audit: Compare against last official release (< CURRENT_VERSION)
try:
    from scripts.audit_release_diff import run_audit
    run_audit(pending_commit_msg=commit_msg)
except Exception as e:
    print(f"Warning: Pre-push audit encountered error: {e}", flush=True)

# 1. Get latest commit SHA on main
ref_resp = session.get(f"{api_base}/git/ref/heads/main")
if ref_resp.status_code != 200:
    print("Failed to get ref:", ref_resp.status_code, ref_resp.text, flush=True)
    exit(1)

parent_commit_sha = ref_resp.json()["object"]["sha"]
print(f"Current main commit: {parent_commit_sha[:7]}", flush=True)

# 2. Get tree of current commit to identify unchanged files
commit_resp = session.get(f"{api_base}/git/commits/{parent_commit_sha}")
base_tree_sha = commit_resp.json()["tree"]["sha"]

tree_fetch_resp = session.get(f"{api_base}/git/trees/{base_tree_sha}?recursive=1")
remote_files_map = {}
if tree_fetch_resp.status_code == 200:
    for item in tree_fetch_resp.json().get("tree", []):
        if item.get("type") == "blob":
            remote_files_map[item["path"]] = item["sha"]

# 3. Collect ALL local project files and calculate Git SHA-1 for every file
excluded_dirs = {'.venv', 'models', 'workspace', 'out', 'samples', '__pycache__', 'dist', 'build', 'bin', '.pytest_cache', '.git', 'node_modules'}
excluded_files = {'.env', 'scratch_analyze.py', 'release_manifest.json'}

def calc_git_sha(content_bytes: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content_bytes)).encode("ascii") + b"\x00" + content_bytes).hexdigest()

local_files_map = {}
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in excluded_dirs]
    for f in files:
        if f in excluded_files or f.endswith(('.pyc', '.pyo', '.pyd')):
            continue
        p = Path(root) / f
        rel = p.relative_to('.').as_posix()
        content = p.read_bytes()
        local_files_map[rel] = (p, content, calc_git_sha(content))

# 4. Compare Local vs Remote Tree (Deterministic 1:1 Snapshot Audit)
identical_files = []
modified_files = []
added_files = []
deleted_files = []

for rel, (p, content, local_sha) in local_files_map.items():
    if rel in remote_files_map:
        if remote_files_map[rel] == local_sha:
            identical_files.append((rel, local_sha))
        else:
            modified_files.append((rel, p, content, remote_files_map[rel], local_sha))
    else:
        added_files.append((rel, p, content, local_sha))

for rel, remote_sha in remote_files_map.items():
    if rel not in local_files_map:
        deleted_files.append((rel, remote_sha))

print("=" * 65, flush=True)
print("       BANG DOI CHIEU MÃ NGUON LOCAL VA GITHUB TREE SNAPSHOT", flush=True)
print("=" * 65, flush=True)
print(f"Tong so file ma nguon tren may: {len(local_files_map)}", flush=True)
print(f"Tong so file tren GitHub tree:  {len(remote_files_map)}", flush=True)
print(f"  * Giu nguyen (khop 100% SHA): {len(identical_files)}", flush=True)
print(f"  * Thay doi noi dung:         {len(modified_files)}", flush=True)
print(f"  * File moi them:              {len(added_files)}", flush=True)
print(f"  * File da xoa:                {len(deleted_files)}", flush=True)
print("-" * 65, flush=True)

if modified_files:
    print("Cac file thay doi (Modified):", flush=True)
    for rel, _, _, old_sha, new_sha in modified_files:
        print(f"  [M] {rel} ({old_sha[:7]} -> {new_sha[:7]})", flush=True)

if added_files:
    print("Cac file moi them (Added):", flush=True)
    for rel, _, _, sha in added_files:
        print(f"  [+] {rel} ({sha[:7]})", flush=True)

if deleted_files:
    print("Cac file da xoa tren local (Deleted from tree):", flush=True)
    for rel, sha in deleted_files:
        print(f"  [-] {rel} ({sha[:7]})", flush=True)

print("=" * 65, flush=True)

# 5. Upload blobs for new / modified files
files_to_upload = [(rel, p, c, sha) for (rel, p, c, _, sha) in modified_files] + [(rel, p, c, sha) for (rel, p, c, sha) in added_files]

full_tree_items = []
# Re-use existing blob SHAs for identical files (zero network transfer!)
for rel, sha in identical_files:
    full_tree_items.append({
        "path": rel,
        "mode": "100644",
        "type": "blob",
        "sha": sha,
    })

if files_to_upload:
    print(f"\nDang tai len {len(files_to_upload)} blob moi len GitHub...", flush=True)
    for idx, (rel_path, local_path, content_bytes, expected_sha) in enumerate(files_to_upload, 1):
        b64_content = base64.b64encode(content_bytes).decode("utf-8")
        blob_sha = None
        for attempt in range(3):
            blob_resp = session.post(
                f"{api_base}/git/blobs",
                json={"content": b64_content, "encoding": "base64"},
            )
            if blob_resp.status_code == 201:
                blob_sha = blob_resp.json()["sha"]
                break
            time.sleep(1.0)
            
        if not blob_sha:
            print(f"Failed to create blob for {rel_path}: {blob_resp.status_code} {blob_resp.text}", flush=True)
            exit(1)
            
        full_tree_items.append({
            "path": rel_path,
            "mode": "100644",
            "type": "blob",
            "sha": blob_sha,
        })
        print(f"  -> Uploaded blob: {rel_path} ({idx}/{len(files_to_upload)}) [SHA: {blob_sha[:7]}]", flush=True)

# 6. Create Full Tree Snapshot (Contains 100% of all local files, NO base_tree overlay!)
assert len(full_tree_items) == len(local_files_map), f"Tree size mismatch: {len(full_tree_items)} vs {len(local_files_map)}"

tree_resp = session.post(
    f"{api_base}/git/trees",
    json={"tree": full_tree_items},
)
if tree_resp.status_code != 201:
    print("Failed to create tree:", tree_resp.status_code, tree_resp.text, flush=True)
    exit(1)
new_tree_sha = tree_resp.json()["sha"]
print(f"\n[XAC NHAN] Da tao Full Tree Snapshot hoan hao tren GitHub: {new_tree_sha[:7]} (Chua dung {len(full_tree_items)} file).", flush=True)


# 7. Create commit if tree changed, or reuse current commit if identical
if new_tree_sha == base_tree_sha:
    print(f"\n[HOAN TOAN DONG BO] 100% Cay thu muc GitHub va Local hoan toan trung khop (Tree: {new_tree_sha[:7]}). Khong can tao commit moi.", flush=True)
    new_commit_sha = parent_commit_sha
else:
    print(f"Commit message: {commit_msg}", flush=True)
    commit_payload = {
        "message": commit_msg,
        "tree": new_tree_sha,
        "parents": [parent_commit_sha],
    }
    new_commit_resp = session.post(
        f"{api_base}/git/commits",
        json=commit_payload,
    )
    if new_commit_resp.status_code != 201:
        print("Failed to create commit:", new_commit_resp.status_code, new_commit_resp.text, flush=True)
        exit(1)

    new_commit_sha = new_commit_resp.json()["sha"]
    print(f"Created commit: {new_commit_sha[:7]}", flush=True)

    # 8. Update ref
    ref_update = session.patch(
        f"{api_base}/git/refs/heads/main",
        json={"sha": new_commit_sha},
    )
    if ref_update.status_code != 200:
        print("Failed to update ref:", ref_update.status_code, ref_update.text, flush=True)
        exit(1)

    print(f"\n[THANH CONG] Toan bo ma nguon da duoc dong bo len branch main (Commit: {new_commit_sha[:7]})!", flush=True)

# 8. Create tag ONLY if explicitly requested via command line (e.g. --tag v1.1.1)
if requested_tag:
    tag_name = requested_tag if requested_tag.startswith("v") else f"v{requested_tag}"
    tag_ref = f"refs/tags/{tag_name}"
    tag_payload = {"ref": tag_ref, "sha": new_commit_sha}

    # Delete existing GitHub Release for this tag if present to ensure clean overwrite
    rel_resp = session.get(f"{api_base}/releases/tags/{tag_name}")
    if rel_resp.status_code == 200:
        rel_id = rel_resp.json().get("id")
        if rel_id:
            del_rel = session.delete(f"{api_base}/releases/{rel_id}")
            if del_rel.status_code in (204, 200):
                print(f"Deleted existing GitHub Release object for {tag_name} (ID: {rel_id}) to overwrite cleanly.", flush=True)
                time.sleep(1.0)

    del_resp = session.delete(f"{api_base}/git/refs/tags/{tag_name}")
    if del_resp.status_code in (204, 200):
        print(f"Deleted existing Git Tag {tag_name} ref on remote to prepare for fresh trigger.", flush=True)
        time.sleep(1.0)

    tag_resp = session.post(f"{api_base}/git/refs", json=tag_payload)
    if tag_resp.status_code == 201:
        print(f"[THANH CONG] Da tao Git Tag {tag_name} tren GitHub! GitHub Actions se tu dong build va release.", flush=True)
    else:
        patch_resp = session.patch(f"{api_base}/git/refs/tags/{tag_name}", json={"sha": new_commit_sha, "force": True})
        if patch_resp.status_code == 200:
            print(f"[THANH CONG] Da cap nhat Git Tag {tag_name} ve commit {new_commit_sha[:7]}!", flush=True)
        else:
            print(f"Notice: Khong the tao hoac cap nhat tag {tag_name}: {tag_resp.status_code} {tag_resp.text}", flush=True)
else:
    print("[THONG BAO] Ma nguon da cap nhat len branch main. KHONG tao tag release moi (dung co --tag <ver> neu muon phat hanh).", flush=True)


