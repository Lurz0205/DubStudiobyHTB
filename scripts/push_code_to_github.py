"""Safely push source code to GitHub main branch via GitHub Git Data API."""
import base64
import hashlib
import os
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

# 3. Collect files and filter to ONLY changed files
excluded_dirs = {'.venv', 'models', 'workspace', 'out', 'samples', '__pycache__', 'dist', 'build', 'bin', '.pytest_cache', '.git'}
excluded_files = {'.env', 'scratch_analyze.py', 'release_manifest.json'}

def calc_git_sha(content_bytes: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content_bytes)).encode("ascii") + b"\x00" + content_bytes).hexdigest()

files_to_push = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in excluded_dirs]
    for f in files:
        if f in excluded_files or f.endswith(('.pyc', '.pyo', '.pyd')):
            continue
        p = Path(root) / f
        rel = p.relative_to('.').as_posix()
        content = p.read_bytes()
        local_sha = calc_git_sha(content)
        if remote_files_map.get(rel) != local_sha:
            files_to_push.append((rel, p, content, local_sha))

print(f"Total changed files to upload: {len(files_to_push)}", flush=True)
for rel, _, _, _ in files_to_push:
    print(f"  * {rel}", flush=True)

if not files_to_push:
    print("Khong co file nao thay doi so voi commit tren GitHub!", flush=True)

# 4. Create blobs for changed files only
tree_items = []
for idx, (rel_path, local_path, content_bytes, _) in enumerate(files_to_push, 1):
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
        
    tree_items.append({
        "path": rel_path,
        "mode": "100644",
        "type": "blob",
        "sha": blob_sha,
    })
    print(f"  -> Uploaded blob: {rel_path} ({idx}/{len(files_to_push)})", flush=True)

# 5. Create new tree (overlaying changes on top of base_tree)
if tree_items:
    tree_resp = session.post(
        f"{api_base}/git/trees",
        json={"base_tree": base_tree_sha, "tree": tree_items},
    )
    if tree_resp.status_code != 201:
        print("Failed to create tree:", tree_resp.status_code, tree_resp.text, flush=True)
        exit(1)
    new_tree_sha = tree_resp.json()["sha"]
    print(f"Created new tree: {new_tree_sha[:7]}", flush=True)
else:
    new_tree_sha = base_tree_sha

# 6. Create commit
commit_payload = {
    "message": "Fix(asr, diagnostics): Verify component readiness and prevent parallel download race conditions",
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

# 7. Update ref
ref_update = session.patch(
    f"{api_base}/git/refs/heads/main",
    json={"sha": new_commit_sha},
)
if ref_update.status_code != 200:
    print("Failed to update ref:", ref_update.status_code, ref_update.text, flush=True)
    exit(1)

print(f"\n[THANH CONG] Toan bo ma nguon da duoc dong bo len branch main (Commit: {new_commit_sha[:7]})!", flush=True)

# 8. Create or recreate tag v1.1.0 to trigger GitHub Actions build_release.yml
tag_name = "v1.1.0"
tag_ref = f"refs/tags/{tag_name}"
tag_payload = {"ref": tag_ref, "sha": new_commit_sha}

# Delete existing tag ref first if it exists to ensure a fresh tag creation event
del_resp = session.delete(f"{api_base}/git/refs/tags/{tag_name}")
if del_resp.status_code in (204, 200):
    print(f"Deleted existing Git Tag {tag_name} ref on remote to prepare for fresh trigger.", flush=True)
    time.sleep(1.0)

tag_resp = session.post(f"{api_base}/git/refs", json=tag_payload)
if tag_resp.status_code == 201:
    print(f"[THANH CONG] Da tao Git Tag {tag_name} tren GitHub! GitHub Actions se tu dong build va release.", flush=True)
else:
    # Fallback to force update if delete/create was delayed
    patch_resp = session.patch(f"{api_base}/git/refs/tags/{tag_name}", json={"sha": new_commit_sha, "force": True})
    if patch_resp.status_code == 200:
        print(f"[THANH CONG] Da cap nhat Git Tag {tag_name} ve commit {new_commit_sha[:7]}!", flush=True)
    else:
        print(f"Notice: Khong the tao hoac cap nhat tag {tag_name}: {tag_resp.status_code} {tag_resp.text}", flush=True)


