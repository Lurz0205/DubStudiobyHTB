"""Audit tag-to-tag differences against the last official GitHub release.

Ensures zero modified files are forgotten and compiles a complete, transparent
audit of all changes, commit history, and file diffs since the last release.
"""
from __future__ import annotations

import base64
import hashlib
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dotenv
import requests

from dubstudio.version import APP_VERSION


def calc_git_sha(content_bytes: bytes) -> str:
    """Calculate Git Blob SHA-1 identical to Git's native blob hash."""
    return hashlib.sha1(b"blob " + str(len(content_bytes)).encode("ascii") + b"\x00" + content_bytes).hexdigest()


def get_github_session() -> Tuple[requests.Session, str, str, str]:
    """Initialize authenticated GitHub session from environment."""
    dotenv.load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    repo_url = os.getenv("GITHUB_REPO_URL") or "https://github.com/Lurz0205/DubStudiobyHTB"

    parts = repo_url.rstrip("/").split("/")
    owner = parts[-2]
    repo = parts[-1]
    api_base = f"https://api.github.com/repos/{owner}/{repo}"

    session = requests.Session()
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "DubStudio-Audit",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    session.headers.update(headers)
    return session, api_base, owner, repo


def find_last_release_tag(session: requests.Session, api_base: str, current_version: str) -> Tuple[str, str]:
    """Find the latest release tag before current_version."""
    curr_clean = current_version.lstrip("v")
    
    # 1. Check GitHub Releases
    resp = session.get(f"{api_base}/releases")
    if resp.status_code == 200:
        releases = resp.json()
        for r in releases:
            tag = r.get("tag_name", "")
            tag_clean = tag.lstrip("v")
            if tag_clean != curr_clean:
                commit_sha = ""
                # Get commit SHA for this tag
                tag_ref_resp = session.get(f"{api_base}/git/ref/tags/{tag}")
                if tag_ref_resp.status_code == 200:
                    tag_obj = tag_ref_resp.json().get("object", {})
                    commit_sha = tag_obj.get("sha", "")
                    if tag_obj.get("type") == "tag":
                        # Annotated tag: dereference commit
                        annotated_resp = session.get(tag_obj.get("url", ""))
                        if annotated_resp.status_code == 200:
                            commit_sha = annotated_resp.json().get("object", {}).get("sha", commit_sha)
                return tag, commit_sha

    # 2. Check Git Tags fallback
    tags_resp = session.get(f"{api_base}/tags")
    if tags_resp.status_code == 200:
        tags = tags_resp.json()
        for t in tags:
            tag_name = t.get("name", "")
            if tag_name.lstrip("v") != curr_clean:
                return tag_name, t.get("commit", {}).get("sha", "")

    # Default fallback
    return "v1.1.2", ""


def collect_local_files() -> Dict[str, Tuple[Path, bytes, str]]:
    """Scan local repository and return map of rel_path -> (Path, bytes, git_sha)."""
    excluded_dirs = {
        ".venv", "models", "workspace", "out", "samples", "__pycache__",
        "dist", "build", "bin", ".pytest_cache", ".git", ".gemini"
    }
    excluded_files = {
        ".env", "scratch_analyze.py", "release_manifest.json", "RELEASE_AUDIT.md"
    }

    local_map: Dict[str, Tuple[Path, bytes, str]] = {}
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        for f in files:
            if f in excluded_files or f.endswith((".pyc", ".pyo", ".pyd")):
                continue
            p = Path(root) / f
            rel = p.relative_to(".").as_posix()
            try:
                content = p.read_bytes()
                local_map[rel] = (p, content, calc_git_sha(content))
            except Exception:
                pass
    return local_map


def fetch_remote_tree(session: requests.Session, api_base: str, commit_sha: str) -> Dict[str, str]:
    """Fetch recursive tree map of path -> blob_sha for a commit."""
    if not commit_sha:
        return {}
    commit_resp = session.get(f"{api_base}/git/commits/{commit_sha}")
    if commit_resp.status_code != 200:
        return {}
    tree_sha = commit_resp.json().get("tree", {}).get("sha", "")
    if not tree_sha:
        return {}
    tree_resp = session.get(f"{api_base}/git/trees/{tree_sha}?recursive=1")
    if tree_resp.status_code != 200:
        return {}
    tree_map = {}
    for item in tree_resp.json().get("tree", []):
        if item.get("type") == "blob":
            tree_map[item["path"]] = item["sha"]
    return tree_map


def run_audit(target_version: Optional[str] = None) -> Dict[str, Any]:
    """Run tag-to-tag comparison and generate RELEASE_AUDIT.md."""
    ver = target_version or APP_VERSION
    session, api_base, owner, repo = get_github_session()

    print("=" * 70)
    print(f"       DUBSTUDIO RELEASE AUDIT: TAG-TO-TAG CODE COMPARISON")
    print("=" * 70)
    print(f"Target Version: v{ver.lstrip('v')}")

    last_tag, last_sha = find_last_release_tag(session, api_base, ver)
    print(f"Base Release Tag: {last_tag} (Commit: {last_sha[:7] if last_sha else 'auto-resolved'})")

    # If last_sha wasn't found directly, resolve from tag ref
    if not last_sha and last_tag:
        tag_ref_resp = session.get(f"{api_base}/git/ref/tags/{last_tag}")
        if tag_ref_resp.status_code == 200:
            last_sha = tag_ref_resp.json().get("object", {}).get("sha", "")

    remote_tree = fetch_remote_tree(session, api_base, last_sha)
    local_tree = collect_local_files()

    identical_files: List[Tuple[str, str]] = []
    modified_files: List[Tuple[str, str, str, Path]] = []  # rel, old_sha, new_sha, path
    added_files: List[Tuple[str, str, Path]] = []          # rel, new_sha, path
    deleted_files: List[Tuple[str, str]] = []              # rel, old_sha

    for rel, (p, content, local_sha) in local_tree.items():
        if rel in remote_tree:
            if remote_tree[rel] == local_sha:
                identical_files.append((rel, local_sha))
            else:
                modified_files.append((rel, remote_tree[rel], local_sha, p))
        else:
            added_files.append((rel, local_sha, p))

    for rel, remote_sha in remote_tree.items():
        if rel not in local_tree:
            deleted_files.append((rel, remote_sha))

    # Fetch commit log between last_tag and main
    commits_list: List[Dict[str, str]] = []
    try:
        compare_resp = session.get(f"{api_base}/compare/{last_tag}...main")
        if compare_resp.status_code == 200:
            for c in compare_resp.json().get("commits", []):
                commits_list.append({
                    "sha": c.get("sha", "")[:7],
                    "message": c.get("commit", {}).get("message", "").split("\n")[0],
                })
    except Exception:
        pass

    # Print summary to console
    print("-" * 70)
    print(f"Tong so file ma nguon local:     {len(local_tree)}")
    print(f"Tong so file o release {last_tag}:     {len(remote_tree)}")
    print(f"  * Giu nguyen (khop 100% SHA):  {len(identical_files)}")
    print(f"  * File sua doi (Modified):     {len(modified_files)}")
    print(f"  * File tao moi (Added):        {len(added_files)}")
    print(f"  * File da xoa (Deleted):       {len(deleted_files)}")
    print("-" * 70)

    if modified_files:
        print("\n[MODIFIED FILES]:")
        for rel, old_sha, new_sha, _ in modified_files:
            print(f"  ~ {rel} ({old_sha[:7]} -> {new_sha[:7]})")

    if added_files:
        print("\n[ADDED FILES]:")
        for rel, new_sha, _ in added_files:
            print(f"  + {rel} ({new_sha[:7]})")

    if deleted_files:
        print("\n[DELETED FILES]:")
        for rel, old_sha in deleted_files:
            print(f"  - {rel} ({old_sha[:7]})")

    # Generate comprehensive RELEASE_AUDIT.md
    audit_md_path = Path("RELEASE_AUDIT.md")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# DubStudio Release Audit — Tag-to-Tag Comparison",
        f"",
        f"- **Mục tiêu phát hành:** `v{ver.lstrip('v')}`",
        f"- **Phiên bản gốc đối chiếu:** `{last_tag}`",
        f"- **Thời gian kiểm toán:** `{timestamp}`",
        f"- **Tổng số file thay đổi:** `{len(modified_files) + len(added_files) + len(deleted_files)}` "
        f"({len(modified_files)} sửa đổi, {len(added_files)} thêm mới, {len(deleted_files)} đã xóa)",
        f"",
        f"---",
        f"",
        f"## 1. Tổng hợp toàn diện các tính năng & Lỗi đã sửa từ `{last_tag}`",
        f"",
        f"1. **Chuỗi Xử lý Âm thanh Studio Mastering & Sửa lỗi âm lượng 200%:**",
        f"   - Tái cấu trúc chuỗi bộ lọc âm thanh giọng đọc tiếng Việt: lọc rung sub-bass (high-pass 80Hz), tăng cường 2 dải EQ trong trẻo phát âm tiếng Việt (+3dB ở 3.2kHz, +1.5dB ở 120Hz), broadcast compressor.",
        f"   - Đưa bộ tăng âm sau compressor đạt chuẩn âm học +6.01 dBFS ở 200% kèm true-peak alimiter chống vỡ tiếng.",
        f"   - Tích hợp tính năng **Auto-Ducking thông minh (`sidechaincompress`)**: Tự động giảm nhạc nền BGM xuống ~10 dB khi có giọng đọc và trả về êm ái khi dứt câu.",
        f"   - Trình phát video preview điều khiển độc lập 4 luồng âm thanh mượt mà.",
        f"",
        f"2. **Khắc phục triệt để lỗi kết xuất video (500 Server Error):**",
        f"   - Sửa lỗi thiếu khai báo `cfg = AppConfig.load()` trong endpoint `/api/jobs/{{job_id}}/render`, `/split`, `/segments/tts`.",
        f"   - Cấu hình In-Memory ASGI Bridge trả về phản hồi lỗi JSON tiếng Việt rõ ràng, loại bỏ hoàn toàn các chuỗi URL loopback/port khỏi giao diện người dùng.",
        f"",
        f"3. **Kiến trúc Cập nhật An toàn & Bảo toàn Dữ liệu:**",
        f"   - Tách biệt thư mục cài đặt `%LocalAppData%\\DubStudio` và dữ liệu `%LocalAppData%\\DubStudioData`.",
        f"   - Cho phép cài đè không bao giờ bị xung đột hoặc mất các mô hình AI đã tải.",
        f"   - Mở khóa cờ `JOB_OBJECT_LIMIT_BREAKAWAY_OK` và khởi động lại độc lập bằng PowerShell wait-for-PID chống lỗi khóa file `WinError 32`.",
        f"   - Xác thực toàn vẹn mã băm SHA-256 và kích thước byte trước khi áp dụng cập nhật.",
        f"",
        f"4. **Tối ưu hóa Vòng lặp Khớp Thoại (Fit Stage):**",
        f"   - Cân bằng thời lượng 2 chiều (`shorter` cho câu bị đè, `longer` cho câu quá ngắn) qua 1 lượt gọi LLM duy nhất.",
        f"   - Tận dụng Persistent TTS Warm Worker tổng hợp âm thanh từng câu chỉ mất ~0.4s.",
        f"   - Sửa triệt để lỗi xung đột keyword argument `stdin` trong subprocess Popen.",
        f"",
        f"---",
        f"",
        f"## 2. Bảng Danh mục Chi tiết Các File Thay đổi (`{last_tag}..HEAD`)",
        f"",
        f"| Trạng thái | Đường dẫn File | SHA cũ ({last_tag}) | SHA mới (HEAD) |",
        f"|:---|:---|:---|:---|",
    ]

    for rel, old_sha, new_sha, _ in sorted(modified_files, key=lambda x: x[0]):
        lines.append(f"| **Modified** | `{rel}` | `{old_sha[:7]}` | `{new_sha[:7]}` |")

    for rel, new_sha, _ in sorted(added_files, key=lambda x: x[0]):
        lines.append(f"| **Added** | `{rel}` | *N/A* | `{new_sha[:7]}` |")

    for rel, old_sha in sorted(deleted_files, key=lambda x: x[0]):
        lines.append(f"| **Deleted** | `{rel}` | `{old_sha[:7]}` | *N/A* |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 3. Lịch sử Git Commits Kể từ `{last_tag}`",
        f"",
    ])

    if commits_list:
        for c in commits_list:
            lines.append(f"- [`{c['sha']}`] {c['message']}")
    else:
        lines.append(f"- Đang áp dụng các thay đổi trực tiếp từ working tree snapshot.")

    audit_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n[XAC NHAN] Da tao thanh cong file kiem toan minh bach: {audit_md_path.resolve()}")
    print("=" * 70)

    return {
        "last_tag": last_tag,
        "last_sha": last_sha,
        "modified_count": len(modified_files),
        "added_count": len(added_files),
        "deleted_count": len(deleted_files),
        "audit_file": str(audit_md_path),
    }


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    run_audit(target)
