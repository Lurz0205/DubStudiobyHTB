"""Job state tracking, stage hashes, and resume logic."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from dubstudio.errors import DubError


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

    def __init__(self, workspace_path: Path, job_id: str, input_path: Optional[Path] = None) -> None:
        self.workspace = workspace_path
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
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state_data, f, ensure_ascii=False, indent=2)

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
