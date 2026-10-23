from pathlib import Path
from dubstudio.jobstate import JobContext, compute_file_hash


def test_jobstate_flow(tmp_path: Path):
    # Create sample dummy input file
    input_file = tmp_path / "sample.mp4"
    input_file.write_bytes(b"sample video bytes content")

    workspace = tmp_path / "workspace" / "job_01"
    job = JobContext(workspace_path=workspace, job_id="job_01", input_path=input_file)

    input_hash = compute_file_hash(input_file)
    assert not job.is_stage_done("stage_a", input_hash)

    # Start stage
    job.start_stage("stage_a", input_hash)
    assert job.state_data["stages"]["stage_a"]["status"] == "running"

    # Finish stage with output
    out_file = workspace / "out.txt"
    out_file.write_text("done output", encoding="utf-8")
    job.finish_stage("stage_a", ["out.txt"])

    # Reload from disk
    job2 = JobContext(workspace_path=workspace, job_id="job_01", input_path=input_file)
    assert job2.is_stage_done("stage_a", input_hash)

    # If hash changes, it is not done
    assert not job2.is_stage_done("stage_a", "different_hash")

    # If output file is removed, it is not considered done
    out_file.unlink()
    assert not job2.is_stage_done("stage_a", input_hash)
