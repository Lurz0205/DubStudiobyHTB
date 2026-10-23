"""Safely push source code to GitHub main branch via GitHub Git Data API."""
import base64
import os
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

# 2. Get tree of current commit
commit_resp = session.get(f"{api_base}/git/commits/{parent_commit_sha}")
base_tree_sha = commit_resp.json()["tree"]["sha"]

# 3. Collect files to upload
excluded_dirs = {'.venv', 'models', 'workspace', 'out', 'samples', '__pycache__', 'dist', 'build', 'bin', '.pytest_cache', '.git'}
excluded_files = {'.env', 'scratch_analyze.py', 'release_manifest.json'}

files_to_push = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in excluded_dirs]
    for f in files:
        if f in excluded_files or f.endswith(('.pyc', '.pyo', '.pyd')):
            continue
        p = Path(root) / f
        rel = p.relative_to('.').as_posix()
        files_to_push.append((rel, p))

print(f"Total files to push: {len(files_to_push)}", flush=True)

# 4. Create blobs
tree_items = []
for idx, (rel_path, local_path) in enumerate(files_to_push, 1):
    content_bytes = local_path.read_bytes()
    b64_content = base64.b64encode(content_bytes).decode("utf-8")
    
    blob_resp = session.post(
        f"{api_base}/git/blobs",
        json={"content": b64_content, "encoding": "base64"},
    )
    if blob_resp.status_code != 201:
        print(f"Failed to create blob for {rel_path}: {blob_resp.status_code} {blob_resp.text}", flush=True)
        exit(1)
        
    blob_sha = blob_resp.json()["sha"]
    tree_items.append({
        "path": rel_path,
        "mode": "100644",
        "type": "blob",
        "sha": blob_sha,
    })
    if idx % 10 == 0 or idx == len(files_to_push):
        print(f"  -> Uploaded: {idx}/{len(files_to_push)} files...", flush=True)

# 5. Create new tree
tree_resp = session.post(
    f"{api_base}/git/trees",
    json={"base_tree": base_tree_sha, "tree": tree_items},
)
if tree_resp.status_code != 201:
    print("Failed to create tree:", tree_resp.status_code, tree_resp.text, flush=True)
    exit(1)

new_tree_sha = tree_resp.json()["sha"]
print(f"Created new tree: {new_tree_sha[:7]}", flush=True)

# 6. Create commit
commit_payload = {
    "message": "Release v1.0.1: Sync complete DubStudio source code for CI/CD",
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
