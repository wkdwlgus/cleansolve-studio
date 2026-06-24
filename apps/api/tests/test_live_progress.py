import json

import pytest

from cleansolve_api.live_progress import (
    LiveProgressStore,
    cursor_sequence,
    progress_event_payload,
)
from cleansolve_workflow import ProgressEvent


def make_event(sequence: int, *, job_id: str = "job_00000000000000000000000000000000") -> ProgressEvent:
    return ProgressEvent(
        event_id=f"evt_{sequence:04d}",
        job_id=job_id,
        sequence=sequence,
        phase="analysis",
        status="CREATED" if sequence == 0 else "SPEC_EXTRACTED",
        message="작업을 시작했습니다." if sequence == 0 else "원본 문제와 선생님 손풀이를 분석하고 있습니다.",
        attempt=0,
        max_attempts=2,
        scores=None,
        next_action="continue",
        created_at=f"2026-06-23T00:00:0{sequence}Z",
    )


def test_progress_event_payload_projects_public_fields_only():
    event = make_event(0)
    payload = progress_event_payload(event)

    assert payload == {
        "event_id": "evt_0000",
        "job_id": "job_00000000000000000000000000000000",
        "sequence": 0,
        "phase": "analysis",
        "status": "CREATED",
        "message": "작업을 시작했습니다.",
        "attempt": 0,
        "max_attempts": 2,
        "scores": None,
        "next_action": "continue",
        "created_at": "2026-06-23T00:00:00Z",
    }


def test_live_progress_store_appends_reads_and_dedupes_events(tmp_path):
    store = LiveProgressStore(tmp_path / "jobs")
    job_id = "job_00000000000000000000000000000000"
    ids = {"problem": "img_problem_123", "teacher_solution": "img_teacher_456"}

    store.initialize(job_id, ids)
    store.append(job_id, make_event(1, job_id=job_id))
    store.append(job_id, make_event(0, job_id=job_id))
    store.append(job_id, make_event(1, job_id=job_id))

    events = store.read_events(job_id)

    assert [event["event_id"] for event in events] == ["evt_0000", "evt_0001"]
    assert store.progress_events_payload(job_id) == {"job_id": job_id, "events": events}
    jsonl_path = tmp_path / "jobs" / job_id / "artifacts" / "events" / "live_progress.jsonl"
    assert jsonl_path.exists()
    assert len(jsonl_path.read_text(encoding="utf-8").splitlines()) == 2


def test_live_progress_store_reads_after_cursor(tmp_path):
    store = LiveProgressStore(tmp_path / "jobs")
    job_id = "job_00000000000000000000000000000000"
    ids = {"problem": "img_problem_123", "teacher_solution": "img_teacher_456"}
    store.initialize(job_id, ids)
    store.append(job_id, make_event(0, job_id=job_id))
    store.append(job_id, make_event(1, job_id=job_id))

    assert cursor_sequence("evt_0000") == 0
    assert cursor_sequence("evt_0100") == 100
    assert cursor_sequence("bad") is None
    assert [event["event_id"] for event in store.read_events(job_id, after="evt_0000")] == ["evt_0001"]
    assert [event["event_id"] for event in store.read_events(job_id, after="bad")] == ["evt_0000", "evt_0001"]


def test_live_progress_store_skips_malformed_lines_on_read(tmp_path):
    store = LiveProgressStore(tmp_path / "jobs")
    job_id = "job_00000000000000000000000000000000"
    ids = {"problem": "img_problem_123", "teacher_solution": "img_teacher_456"}
    store.initialize(job_id, ids)
    store.append(job_id, make_event(0, job_id=job_id))
    jsonl_path = tmp_path / "jobs" / job_id / "artifacts" / "events" / "live_progress.jsonl"
    with jsonl_path.open("a", encoding="utf-8") as handle:
        handle.write("{bad json\n")
        handle.write(json.dumps({"event_id": "evt_0002", "sequence": "bad"}, ensure_ascii=False) + "\n")

    events = store.read_events(job_id)

    assert [event["event_id"] for event in events] == ["evt_0000"]


def test_live_progress_store_rejects_unsafe_event_id(tmp_path):
    store = LiveProgressStore(tmp_path / "jobs")
    job_id = "job_00000000000000000000000000000000"
    ids = {"problem": "img_problem_123", "teacher_solution": "img_teacher_456"}
    store.initialize(job_id, ids)
    event = make_event(0, job_id=job_id).model_copy(update={"event_id": "evt_0000\nevent: injected"})

    with pytest.raises(ValueError, match="unsafe progress event id"):
        store.append(job_id, event)
