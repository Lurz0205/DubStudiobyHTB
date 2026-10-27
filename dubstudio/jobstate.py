"""Job state tracking, stage hashes, and resume logic."""
from datetime import datetime, timezone
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from dubstudio.errors import DubError

_json_write_lock = threading.Lock()


def atomic_write_json(path: Path | str, data: Any, indent: int = 2) -> None:
    """Safely write data to a JSON file atomically using a temporary file and atomic replace.
    
    Includes Windows-resilient retry loop and fallback for locked file handles.
    """
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = p.with_suffix(f"{p.suffix}.tmp_{os.getpid()}_{id(data)}_{time.time_ns()}")
    
    with _json_write_lock:
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
                f.flush()
                os.fsync(f.fileno())

            # Windows retry loop for os.replace when destination might be temporarily locked for reading
            replaced = False
            for attempt in range(10):
                try:
                    os.replace(tmp_path, p)
                    replaced = True
                    break
                except PermissionError:
                    time.sleep(0.02 * (attempt + 1))
                except Exception:
                    break

            if not replaced:
                # Fallback: direct overwrite if os.replace is blocked by Windows lock
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=indent)
                    f.flush()
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass


def compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file's contents in chunks."""
    if not path.exists():
        raise DubError(
            code="FILE_NOT_FOUND",
            user_message_vi=f"Không tìm thấy tệp để tính hash: {path.name}",
            hint_vi="Kiểm tra lại đường dẫn tệp nguồn.",
            details={"path": str(path)},
        )
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class JobContext:
    """Represents a processing job with a dedicated workspace and state.json."""

    def __init__(
        self,
        workspace_path: Optional[Path] = None,
        job_id: str = "",
        input_path: Optional[Path] = None,
        workspace: Optional[Path] = None,
    ) -> None:
        target_ws = workspace_path or workspace
        if target_ws is None:
            from dubstudio.paths import resolve_job_workspace
            target_ws = resolve_job_workspace(job_id)
        self.workspace = Path(target_ws).resolve()
        self.job_id = job_id
        self.input_path = input_path
        self.state_file = self.workspace / "state.json"
        self.state_data: Dict[str, Any] = {"stages": {}}
        self._ensure_workspace()
        self.load_state()

    def _ensure_workspace(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / "audio").mkdir(parents=True, exist_ok=True)
        (self.workspace / "out").mkdir(parents=True, exist_ok=True)

    def load_state(self) -> None:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self.state_data = json.load(f)
            except Exception:
                self.state_data = {"stages": {}}
        else:
            self.state_data = {"stages": {}}

    def save_state(self) -> None:
        atomic_write_json(self.state_file, self.state_data, indent=2)

    def is_stage_done(self, stage_name: str, input_hash: str) -> bool:
        """Check if stage was already completed with identical input hash and existing outputs."""
        stage_info = self.state_data.get("stages", {}).get(stage_name)
        if not stage_info:
            return False
        if stage_info.get("status") != "done":
            return False
        if stage_info.get("input_hash") != input_hash:
            return False

        # Verify that recorded output files actually exist on disk
        outputs = stage_info.get("outputs", [])
        for rel_path in outputs:
            if not (self.workspace / rel_path).exists():
                return False

        return True

    def start_stage(self, stage_name: str, input_hash: str) -> None:
        stages = self.state_data.setdefault("stages", {})
        stages[stage_name] = {
            "status": "running",
            "input_hash": input_hash,
            "outputs": [],
            "started": datetime.now(timezone.utc).isoformat(),
            "finished": None,
            "error": None,
        }
        self.save_state()

    def finish_stage(self, stage_name: str, outputs: List[str]) -> None:
        stages = self.state_data.setdefault("stages", {})
        stage_info = stages.get(stage_name, {})
        stage_info["status"] = "done"
        stage_info["outputs"] = outputs
        stage_info["finished"] = datetime.now(timezone.utc).isoformat()
        stage_info["error"] = None
        stages[stage_name] = stage_info
        self.save_state()

    def fail_stage(self, stage_name: str, error_msg: str) -> None:
        stages = self.state_data.setdefault("stages", {})
        stage_info = stages.get(stage_name, {})
        stage_info["status"] = "failed"
        stage_info["finished"] = datetime.now(timezone.utc).isoformat()
        stage_info["error"] = error_msg
        stages[stage_name] = stage_info
        self.save_state()
