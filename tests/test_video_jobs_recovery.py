import json
import time
from pathlib import Path
from uuid import uuid4

import pytest

from app.video_studio.engine import VideoError
from app.video_studio.jobs import VideoJobs


async def generate(_prompt):
    return json.dumps({"scenes": [{"layout": "orb", "text": "Ola"}]})


def manifest(root, **changes):
    job_id = uuid4().hex
    project = root / job_id
    project.mkdir()
    data = {"version": 1, "id": job_id, "owner": "org:a", "status": "done", "stage": "done",
            "progress": 1.0, "message": "Video pronto", "title": "Video", "duration": 1.0,
            "warnings": [], "error": None, "created_at": time.time(), **changes}
    (project / "job.json").write_text(json.dumps(data), encoding="utf-8")
    (project / "out").mkdir()
    (project / "out/video.mp4").write_bytes(b"mp4")
    return job_id, project


def test_completed_video_is_recovered_with_ownership_and_safe_public_contract(tmp_path):
    job_id, _ = manifest(tmp_path)
    jobs = VideoJobs(tmp_path, generate)
    result = jobs.status("org:a", job_id)
    assert result["status"] == "done"
    assert "owner" not in result and "path" not in result
    assert jobs.video("org:a", job_id).read_bytes() == b"mp4"
    result["warnings"].append("must not mutate the job")
    assert jobs.status("org:a", job_id)["warnings"] == []
    with pytest.raises(VideoError):
        jobs.video("org:b", job_id)
    with pytest.raises(VideoError):
        jobs.status("org:a", "../" + job_id)


@pytest.mark.parametrize("status", ["running", "queued"])
def test_interrupted_jobs_become_failed_and_do_not_generate_automatically(tmp_path, status):
    job_id, project = manifest(tmp_path, status=status, stage="render", progress=0.5)
    calls = []

    async def forbidden(_prompt):
        calls.append(True)
        raise AssertionError("Do not rerender automatically")

    jobs = VideoJobs(tmp_path, forbidden)
    assert jobs.status("org:a", job_id)["status"] == "failed"
    assert json.loads((project / "job.json").read_text(encoding="utf-8"))["status"] == "failed"
    assert calls == []


def test_failed_jobs_remain_available_after_restart(tmp_path):
    job_id, _ = manifest(tmp_path, status="failed", error="Interrupted")
    assert VideoJobs(tmp_path, generate).status("org:a", job_id)["error"] == "Interrupted"


@pytest.mark.parametrize("changes", [
    {"owner": ""}, {"owner": None}, {"status": "fake"}, {"progress": float("nan")},
    {"duration": float("inf")}, {"path": "../../secret.mp4"}, {"warnings": "wrong"},
    {"version": 2}, {"id": "../../secret"},
])
def test_malformed_manifest_cannot_restore_or_claim_a_video(tmp_path, changes):
    job_id, _ = manifest(tmp_path, **changes)
    jobs = VideoJobs(tmp_path, generate)
    with pytest.raises(VideoError):
        jobs.status("org:a", job_id)


def test_missing_completed_file_is_reported_as_failed(tmp_path):
    job_id, project = manifest(tmp_path)
    (project / "out/video.mp4").unlink()
    jobs = VideoJobs(tmp_path, generate)
    assert jobs.status("org:a", job_id)["status"] == "failed"


def test_corrupt_manifest_does_not_prevent_valid_job_recovery(tmp_path):
    bad_id, project = manifest(tmp_path)
    (project / "job.json").write_text("{invalid", encoding="utf-8")
    good_id, _ = manifest(tmp_path)
    jobs = VideoJobs(tmp_path, generate)
    assert jobs.status("org:a", good_id)["status"] == "done"
    with pytest.raises(VideoError):
        jobs.status("org:a", bad_id)


def test_symlinked_video_is_never_served(tmp_path):
    job_id, project = manifest(tmp_path)
    target = project / "out/video.mp4"
    target.unlink()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"private")
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip("Creating symlinks requires Windows developer mode or privileges")
    jobs = VideoJobs(tmp_path, generate)
    with pytest.raises(VideoError):
        jobs.video("org:a", job_id)


@pytest.mark.parametrize("relative", ["", "job.json", "out", "out/video.mp4"])
def test_recovery_refuses_symlink_boundaries_without_requiring_os_privileges(monkeypatch, tmp_path, relative):
    job_id, project = manifest(tmp_path)
    boundary = project / relative
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == boundary or original(path))
    jobs = VideoJobs(tmp_path, generate)
    with pytest.raises(VideoError):
        jobs.video("org:a", job_id)


def test_new_job_persists_finished_state_before_restart(monkeypatch, tmp_path):
    monkeypatch.setattr("app.video_studio.jobs.narrate", lambda *_args, **_kwargs: {"duration": 1, "warnings": []})

    def render(project, **_kwargs):
        output = project / "out/video.mp4"
        output.parent.mkdir()
        output.write_bytes(b"mp4")
        return output

    monkeypatch.setattr("app.video_studio.jobs.render", render)
    jobs = VideoJobs(tmp_path, generate)
    job = jobs.start("org:a", "Video", [])
    for _ in range(100):
        if jobs.status("org:a", job["id"])["status"] != "running":
            break
        time.sleep(0.02)
    assert jobs.status("org:a", job["id"])["status"] == "done"
    recovered = VideoJobs(tmp_path, generate)
    assert recovered.video("org:a", job["id"]).read_bytes() == b"mp4"
    assert not list((tmp_path / job["id"]).glob("*.tmp"))
