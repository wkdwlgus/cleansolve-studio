# M10 Background Job & Live SSE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make job runs asynchronous and stream durable live progress events over SSE while preserving the M9 replay UI contract.

**Architecture:** Keep the current local artifact store and add a process-local thread executor, a durable per-job JSONL progress file, and a polling SSE reader. `POST /jobs/{job_id}/run` becomes a `202 RUNNING` start endpoint, the worker writes terminal artifacts, and the web opens SSE immediately after run start.

**Tech Stack:** Python 3.11, FastAPI, `ThreadPoolExecutor`, local filesystem JSON/JSONL artifacts, pytest, React 19, TypeScript, Vite/Vitest, Playwright.

---

## Source Spec

- Design spec: `docs/superpowers/specs/2026-06-23-m10-background-job-live-sse-design.md`

## File Map

- Modify: `apps/api/cleansolve_api/artifacts.py`
  - Add `RUNNING` and `CANCELLED` job statuses.
  - Add job-run error helpers.
  - Add `start_analysis_run()` and `save_failed_background_run()`.
  - Constrain `save_analysis_outputs()` to `RUNNING` source state for worker completion.
- Modify: `apps/api/cleansolve_api/settings.py`
  - Add background worker and SSE timing settings.
- Modify: `packages/workflow/cleansolve_workflow/state.py`
  - Add optional `progress_event_sink`.
- Modify: `packages/workflow/cleansolve_workflow/review_contract.py`
  - Add `CANCELLED` progress status.
  - Add cancelled message allowlist entry.
  - Call optional progress event sink from `append_progress_event()`.
- Modify: `packages/workflow/cleansolve_workflow/graph.py`
  - Add `progress_event_sink` parameter to `run_mock_workflow()`.
- Create: `apps/api/cleansolve_api/live_progress.py`
  - Own durable live progress JSONL/meta file creation, append, read, cursor parsing, and terminal payload assembly.
- Create: `apps/api/cleansolve_api/background.py`
  - Own `JobRunRequest`, `JobRunExecutor`, and worker success/failure flow.
- Modify: `apps/api/cleansolve_api/routes/jobs.py`
  - Make `POST /run` asynchronous.
  - Add cursor-aware live SSE streaming.
  - Preserve public progress event projection and safe SSE serialization.
- Modify: `apps/api/tests/test_jobs_api.py`
  - Update run API tests.
  - Add async run, duplicate run, terminal rerun, live SSE, reconnect, failure, and sensitive-data tests.
- Create: `apps/api/tests/test_live_progress.py`
  - Test JSONL append/read/cursor/dedupe/sanitization behavior.
- Create: `apps/api/tests/test_background.py`
  - Test worker success and safe failure without route/SSE concerns.
- Modify: `packages/workflow/tests/test_graph.py`
  - Test progress sink callback and sink exception behavior.
- Modify: `apps/web/src/api/client.ts`
  - Add `getJob()`.
  - Treat `RUNNING` as valid run-start status.
  - Add `failed` and `cancelled` SSE terminal events.
  - Keep EventSource alive across transient reconnect errors.
  - Open SSE immediately after `POST /run`.
- Modify: `apps/web/src/api/client.test.ts`
  - Update upload-to-review flow expectations.
  - Add failed/cancelled/reconnect tests.
- Modify: `apps/web/src/app/workflowState.test.ts`
  - Verify reconnect duplicate events remain deduped and terminal errors mark items inactive.
- Modify: `apps/web/e2e/upload-review.spec.ts`
  - Mock `202 RUNNING` and live `progress-stream`.
- Modify: `packages/harness/cleansolve_harness/e2e.py`
  - Start run with `202`, drain SSE, then fetch final job state before artifact/export checks.
- Modify: `packages/harness/tests/test_e2e.py`
  - Keep existing E2E expectations green with async run.
- Modify: `docs/product/mvp-roadmap.md`
  - Mark M10 implementation result after code is complete.
- Modify: `docs/product/mvp-release-checklist.md`
  - Update the live SSE gap after code is complete.

## Contracts To Preserve

- `ProgressEventPayload` public fields remain unchanged.
- `event: progress` SSE frame shape remains unchanged.
- `event: complete` remains the success terminal event.
- `GET /jobs/{job_id}/progress-events` remains a terminal artifact replay endpoint.
- Deterministic renderer output and input ordering must not change.
- No external queue, Redis, Celery, RQ, retry system, cancel endpoint, or cancel button in M10.
- API, SSE, manifest review items, and web UI must not expose raw model output, prompt, local path, API key, or `source_image_paths`.

---

### Task 1: Job Status, Settings, And Store Transition Contracts

**Files:**
- Modify: `apps/api/cleansolve_api/artifacts.py`
- Modify: `apps/api/cleansolve_api/settings.py`
- Modify: `apps/api/tests/test_jobs_api.py`

- [ ] **Step 1: Add failing store/status tests**

In `apps/api/tests/test_jobs_api.py`, append these tests near existing manifest/store tests:

```python
def test_store_start_analysis_run_marks_job_running(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    manifest.latest_image_artifact_ids = ids
    store.save_manifest(manifest)

    updated = store.start_analysis_run(
        manifest.job_id,
        source_image_artifact_ids=ids,
    )

    assert updated.status == "RUNNING"
    assert updated.latest_analysis_artifact_ids["candidate_spec"] is None
    assert updated.latest_analysis_artifact_ids["progress_events"] is None


def test_store_start_analysis_run_rejects_terminal_job(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    manifest.latest_image_artifact_ids = ids
    manifest.status = "APPROVED"
    store.save_manifest(manifest)

    with pytest.raises(HTTPException) as exc_info:
        store.start_analysis_run(
            manifest.job_id,
            source_image_artifact_ids=ids,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "JOB_RUN_NOT_RESTARTABLE"
    assert exc_info.value.detail["fields"] == {
        "job_id": manifest.job_id,
        "status": "APPROVED",
    }


def test_store_start_analysis_run_rejects_running_job(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    manifest.latest_image_artifact_ids = ids
    manifest.status = "RUNNING"
    store.save_manifest(manifest)

    with pytest.raises(HTTPException) as exc_info:
        store.start_analysis_run(
            manifest.job_id,
            source_image_artifact_ids=ids,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "JOB_ALREADY_RUNNING"
    assert exc_info.value.detail["fields"] == {"job_id": manifest.job_id}


def test_store_save_failed_background_run_persists_only_safe_progress_events(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    manifest.latest_image_artifact_ids = ids
    manifest.status = "RUNNING"
    store.save_manifest(manifest)
    failed_event = {
        "event_id": "evt_0000",
        "job_id": manifest.job_id,
        "sequence": 0,
        "phase": "failed",
        "status": "FAILED",
        "message": "작업이 실패했습니다.",
        "attempt": 0,
        "max_attempts": 2,
        "scores": None,
        "next_action": "fail",
        "created_at": "2026-06-23T00:00:00Z",
    }

    updated = store.save_failed_background_run(
        manifest.job_id,
        reason="configuration_error",
        review_item={
            "type": "analysis_adapter_failed",
            "client": "openai",
            "retryable": True,
            "review_reason": None,
            "safe_reason": "configuration_error",
        },
        progress_events_payload={
            "job_id": manifest.job_id,
            "events": [failed_event],
        },
        source_image_artifact_ids=ids,
    )

    assert updated.status == "FAILED"
    assert updated.review_items[-1]["safe_reason"] == "configuration_error"
    assert updated.latest_analysis_artifact_ids["candidate_spec"] is None
    assert updated.latest_analysis_artifact_ids["validation_report"] is None
    assert updated.latest_analysis_artifact_ids["correction_plan"] is None
    assert updated.latest_analysis_artifact_ids["review_correction"] is None
    assert updated.latest_analysis_artifact_ids["progress_events"].startswith("events_")
    payload = store.read_latest_analysis_payload(manifest.job_id, "progress_events")
    assert payload == {"job_id": manifest.job_id, "events": [failed_event]}
```

- [ ] **Step 2: Run RED store/status tests**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest apps/api/tests/test_jobs_api.py::test_store_start_analysis_run_marks_job_running apps/api/tests/test_jobs_api.py::test_store_start_analysis_run_rejects_terminal_job apps/api/tests/test_jobs_api.py::test_store_start_analysis_run_rejects_running_job apps/api/tests/test_jobs_api.py::test_store_save_failed_background_run_persists_only_safe_progress_events -q
```

Expected: failures because `RUNNING`, `start_analysis_run()`, and `save_failed_background_run()` do not exist.

- [ ] **Step 3: Implement status literals and error helpers**

In `apps/api/cleansolve_api/artifacts.py`, change `JobStatus` to:

```python
JobStatus = Literal[
    "CREATED",
    "RUNNING",
    "APPROVED",
    "NEEDS_REVIEW",
    "FAILED",
    "REVISION_REQUIRED",
    "CANCELLED",
]
```

Add these entries to `ERROR_MESSAGES`:

```python
    "JOB_ALREADY_RUNNING": "이미 실행 중인 작업입니다.",
    "JOB_RUN_NOT_RESTARTABLE": "이 작업은 다시 실행할 수 없습니다.",
    "JOB_RUN_SUBMIT_FAILED": "background 작업을 시작하지 못했습니다.",
```

Add these helpers after `missing_required_images_error()`:

```python
def job_already_running_error(job_id: str) -> HTTPException:
    return _error("JOB_ALREADY_RUNNING", status.HTTP_409_CONFLICT, {"job_id": job_id})


def job_run_not_restartable_error(job_id: str, status_value: str) -> HTTPException:
    return _error(
        "JOB_RUN_NOT_RESTARTABLE",
        status.HTTP_409_CONFLICT,
        {"job_id": job_id, "status": status_value},
    )


def job_run_submit_failed_error(job_id: str) -> HTTPException:
    return _error("JOB_RUN_SUBMIT_FAILED", status.HTTP_503_SERVICE_UNAVAILABLE, {"job_id": job_id})
```

- [ ] **Step 4: Implement store transition methods**

In `LocalArtifactStore`, add this method after `update_after_run()`:

```python
    def start_analysis_run(
        self,
        job_id: str,
        *,
        source_image_artifact_ids: dict[ImageRole, str],
    ) -> JobManifest:
        _validate_job_id(job_id)
        with self._job_lock(job_id):
            manifest = self.get_job(job_id)
            if manifest.status == "RUNNING":
                raise job_already_running_error(job_id)
            if manifest.status != "CREATED":
                raise job_run_not_restartable_error(job_id, manifest.status)
            if manifest.latest_image_artifact_ids != source_image_artifact_ids:
                raise _error(
                    "ANALYSIS_SOURCE_CHANGED",
                    status.HTTP_409_CONFLICT,
                    {
                        "source_image_artifact_ids": source_image_artifact_ids,
                        "latest_image_artifact_ids": manifest.latest_image_artifact_ids,
                    },
                )
            updated_manifest = JobManifest.model_validate(
                {
                    **manifest.model_dump(mode="python"),
                    "status": "RUNNING",
                    "updated_at": _utc_now(),
                }
            )
            self.save_manifest(updated_manifest)
            return updated_manifest
```

Add this method after `save_failed_analysis_run()`:

```python
    def save_failed_background_run(
        self,
        job_id: str,
        *,
        reason: str,
        review_item: dict[str, Any],
        progress_events_payload: dict[str, Any],
        source_image_artifact_ids: dict[ImageRole, str],
    ) -> JobManifest:
        _validate_job_id(job_id)
        with self._job_lock(job_id):
            manifest = self.get_job(job_id)
            if manifest.latest_image_artifact_ids != source_image_artifact_ids:
                raise _error(
                    "ANALYSIS_SOURCE_CHANGED",
                    status.HTTP_409_CONFLICT,
                    {
                        "source_image_artifact_ids": source_image_artifact_ids,
                        "latest_image_artifact_ids": manifest.latest_image_artifact_ids,
                    },
                )
            analysis_artifacts = {
                artifact_type: list(manifest.analysis_artifacts.get(artifact_type, []))
                for artifact_type in ANALYSIS_ARTIFACT_TYPES
            }
            latest_analysis_artifact_ids = {
                artifact_type: manifest.latest_analysis_artifact_ids.get(artifact_type)
                for artifact_type in ANALYSIS_ARTIFACT_TYPES
            }
            progress_artifact = self._write_analysis_artifact(
                job_id,
                "progress_events",
                progress_events_payload,
                source_image_artifact_ids,
            )
            analysis_artifacts["progress_events"].append(progress_artifact)
            latest_analysis_artifact_ids["progress_events"] = progress_artifact.artifact_id
            safe_review_item = {
                **review_item,
                "safe_reason": reason,
            }
            updated_manifest = JobManifest.model_validate(
                {
                    **manifest.model_dump(mode="python"),
                    "status": "FAILED",
                    "review_items": [*manifest.review_items, safe_review_item],
                    "analysis_artifacts": analysis_artifacts,
                    "latest_analysis_artifact_ids": latest_analysis_artifact_ids,
                    "updated_at": _utc_now(),
                }
            )
            self.save_manifest(updated_manifest)
            return updated_manifest
```

In `save_analysis_outputs()`, immediately after `manifest = self.get_job(job_id)`, add:

```python
            if manifest.status != "RUNNING":
                raise job_run_not_restartable_error(job_id, manifest.status)
```

Task 5 updates existing synchronous-run route tests after the route starts each run before saving outputs.

- [ ] **Step 5: Add settings**

In `apps/api/cleansolve_api/settings.py`, add three fields to `Settings`:

```python
    background_max_workers: int = Field(
        default_factory=lambda: _env_value("CLEANSOLVE_BACKGROUND_MAX_WORKERS", "1"),
        ge=1,
    )
    progress_poll_interval_ms: int = Field(
        default_factory=lambda: _env_value("CLEANSOLVE_PROGRESS_POLL_INTERVAL_MS", "250"),
        ge=1,
    )
    progress_heartbeat_seconds: int = Field(
        default_factory=lambda: _env_value("CLEANSOLVE_PROGRESS_HEARTBEAT_SECONDS", "15"),
        ge=1,
    )
```

Add expectations to `test_settings_default_to_mock_analysis_client()`:

```python
    assert settings.background_max_workers == 1
    assert settings.progress_poll_interval_ms == 250
    assert settings.progress_heartbeat_seconds == 15
```

- [ ] **Step 6: Run GREEN store/status tests**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest apps/api/tests/test_jobs_api.py::test_store_start_analysis_run_marks_job_running apps/api/tests/test_jobs_api.py::test_store_start_analysis_run_rejects_terminal_job apps/api/tests/test_jobs_api.py::test_store_start_analysis_run_rejects_running_job apps/api/tests/test_jobs_api.py::test_store_save_failed_background_run_persists_only_safe_progress_events apps/api/tests/test_jobs_api.py::test_settings_default_to_mock_analysis_client -q
```

Expected: selected tests pass.

- [ ] **Step 7: Commit store contracts**

Run:

```bash
git add apps/api/cleansolve_api/artifacts.py apps/api/cleansolve_api/settings.py apps/api/tests/test_jobs_api.py
git commit -m "feat(api): add job run state contracts"
```

Expected: commit succeeds.

---

### Task 2: Workflow Progress Sink

**Files:**
- Modify: `packages/workflow/cleansolve_workflow/state.py`
- Modify: `packages/workflow/cleansolve_workflow/review_contract.py`
- Modify: `packages/workflow/cleansolve_workflow/graph.py`
- Modify: `packages/workflow/tests/test_graph.py`

- [ ] **Step 1: Add failing workflow sink tests**

In `packages/workflow/tests/test_graph.py`, append:

```python
def test_run_mock_workflow_calls_progress_event_sink():
    events = []

    state = run_mock_workflow(
        "job_sink_test",
        source_image_artifact_ids={
            "problem": "img_problem_123",
            "teacher_solution": "img_teacher_456",
        },
        progress_event_sink=events.append,
    )

    assert len(events) == len(state["progress_events"])
    assert [event.event_id for event in events] == [
        event.event_id for event in state["progress_events"]
    ]
    assert events[0].message == "작업을 시작했습니다."


def test_run_mock_workflow_fails_when_progress_event_sink_fails():
    def failing_sink(_event):
        raise RuntimeError("progress sink failed")

    with pytest.raises(RuntimeError, match="progress sink failed"):
        run_mock_workflow(
            "job_sink_failure",
            source_image_artifact_ids={
                "problem": "img_problem_123",
                "teacher_solution": "img_teacher_456",
            },
            progress_event_sink=failing_sink,
        )
```

If `pytest` is not already imported in this file, add:

```python
import pytest
```

- [ ] **Step 2: Run RED workflow sink tests**

Run:

```bash
pytest packages/workflow/tests/test_graph.py::test_run_mock_workflow_calls_progress_event_sink packages/workflow/tests/test_graph.py::test_run_mock_workflow_fails_when_progress_event_sink_fails -q
```

Expected: failure because `run_mock_workflow()` does not accept `progress_event_sink`.

- [ ] **Step 3: Add sink type and cancelled status**

In `packages/workflow/cleansolve_workflow/state.py`, add imports:

```python
from collections.abc import Callable
```

Add this field to `WorkflowState`:

```python
    progress_event_sink: NotRequired[Callable[[Any], None]]
```

In `packages/workflow/cleansolve_workflow/review_contract.py`, add `"CANCELLED"` to `ProgressStatus`:

```python
    "CANCELLED",
```

Add this string to `PROGRESS_MESSAGE_ALLOWLIST`:

```python
        "작업이 취소되었습니다.",
```

- [ ] **Step 4: Call sink from `append_progress_event()`**

In `append_progress_event()`, after:

```python
    state.setdefault("progress_events", []).append(event)
    state["review_event_sequence"] = sequence + 1
```

insert:

```python
    sink = state.get("progress_event_sink")
    if callable(sink):
        sink(event)
```

Keep `return event` as the final line.

- [ ] **Step 5: Thread sink through `run_mock_workflow()`**

In `packages/workflow/cleansolve_workflow/graph.py`, add this parameter to `run_mock_workflow()`:

```python
    progress_event_sink=None,
```

After optional `analysis_client_override`, add:

```python
    if progress_event_sink is not None:
        initial_state["progress_event_sink"] = progress_event_sink
```

- [ ] **Step 6: Run GREEN workflow sink tests**

Run:

```bash
pytest packages/workflow/tests/test_graph.py::test_run_mock_workflow_calls_progress_event_sink packages/workflow/tests/test_graph.py::test_run_mock_workflow_fails_when_progress_event_sink_fails -q
```

Expected: `2 passed`.

- [ ] **Step 7: Run workflow regression tests**

Run:

```bash
pytest packages/workflow/tests -q
```

Expected: all workflow tests pass.

- [ ] **Step 8: Commit workflow sink**

Run:

```bash
git add packages/workflow/cleansolve_workflow/state.py packages/workflow/cleansolve_workflow/review_contract.py packages/workflow/cleansolve_workflow/graph.py packages/workflow/tests/test_graph.py
git commit -m "feat(workflow): stream progress events through sink"
```

Expected: commit succeeds.

---

### Task 3: Durable Live Progress Store

**Files:**
- Create: `apps/api/cleansolve_api/live_progress.py`
- Create: `apps/api/tests/test_live_progress.py`

- [ ] **Step 1: Add failing live progress tests**

Create `apps/api/tests/test_live_progress.py` with:

```python
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
```

- [ ] **Step 2: Run RED live progress tests**

Run:

```bash
pytest apps/api/tests/test_live_progress.py -q
```

Expected: import failure because `cleansolve_api.live_progress` does not exist.

- [ ] **Step 3: Implement `live_progress.py`**

Create `apps/api/cleansolve_api/live_progress.py`:

```python
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from cleansolve_workflow import ProgressEvent

from .artifacts import ImageRole

SSE_EVENT_ID_PATTERN = re.compile(r"^evt_\d{4,}$")
PROGRESS_EVENT_PUBLIC_FIELDS = (
    "event_id",
    "job_id",
    "sequence",
    "phase",
    "status",
    "message",
    "attempt",
    "max_attempts",
    "scores",
    "next_action",
    "created_at",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cursor_sequence(value: str | None) -> int | None:
    if value is None or SSE_EVENT_ID_PATTERN.fullmatch(value) is None:
        return None
    return int(value.removeprefix("evt_"))


def progress_event_payload(event: ProgressEvent) -> dict[str, Any]:
    raw = event.model_dump(mode="json")
    payload = {field: raw.get(field) for field in PROGRESS_EVENT_PUBLIC_FIELDS}
    validated = ProgressEvent.model_validate(payload)
    if SSE_EVENT_ID_PATTERN.fullmatch(validated.event_id) is None:
        raise ValueError("unsafe progress event id")
    return validated.model_dump(mode="json")


class LiveProgressStore:
    def __init__(self, storage_root: Path):
        self.storage_root = storage_root

    def initialize(
        self,
        job_id: str,
        source_image_artifact_ids: dict[ImageRole, str],
    ) -> None:
        events_dir = self._events_dir(job_id)
        events_dir.mkdir(parents=True, exist_ok=True)
        self._jsonl_path(job_id).write_text("", encoding="utf-8")
        self._meta_path(job_id).write_text(
            json.dumps(
                {
                    "job_id": job_id,
                    "status": "RUNNING",
                    "started_at": utc_now(),
                    "finished_at": None,
                    "terminal_reason": None,
                    "source_image_artifact_ids": source_image_artifact_ids,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def exists(self, job_id: str) -> bool:
        return self._jsonl_path(job_id).exists()

    def append(self, job_id: str, event: ProgressEvent) -> None:
        payload = progress_event_payload(event)
        existing = self.read_events(job_id)
        if any(
            item["event_id"] == payload["event_id"] or item["sequence"] == payload["sequence"]
            for item in existing
        ):
            return
        path = self._jsonl_path(job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def read_events(self, job_id: str, after: str | None = None) -> list[dict[str, Any]]:
        path = self._jsonl_path(job_id)
        if not path.exists():
            return []
        after_sequence = cursor_sequence(after)
        events_by_sequence: dict[int, dict[str, Any]] = {}
        event_ids: set[str] = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                raw = json.loads(line)
                validated = ProgressEvent.model_validate(raw)
            except (json.JSONDecodeError, ValidationError, TypeError):
                continue
            if SSE_EVENT_ID_PATTERN.fullmatch(validated.event_id) is None:
                continue
            payload = validated.model_dump(mode="json")
            sequence = validated.sequence
            if after_sequence is not None and sequence <= after_sequence:
                continue
            if sequence in events_by_sequence or validated.event_id in event_ids:
                continue
            events_by_sequence[sequence] = payload
            event_ids.add(validated.event_id)
        return [events_by_sequence[key] for key in sorted(events_by_sequence)]

    def progress_events_payload(self, job_id: str) -> dict[str, Any]:
        return {"job_id": job_id, "events": self.read_events(job_id)}

    def _events_dir(self, job_id: str) -> Path:
        return self.storage_root / job_id / "artifacts" / "events"

    def _jsonl_path(self, job_id: str) -> Path:
        return self._events_dir(job_id) / "live_progress.jsonl"

    def _meta_path(self, job_id: str) -> Path:
        return self._events_dir(job_id) / "live_progress.meta.json"
```

- [ ] **Step 4: Run GREEN live progress tests**

Run:

```bash
pytest apps/api/tests/test_live_progress.py -q
```

Expected: `5 passed`.

- [ ] **Step 5: Commit live progress store**

Run:

```bash
git add apps/api/cleansolve_api/live_progress.py apps/api/tests/test_live_progress.py
git commit -m "feat(api): add durable live progress store"
```

Expected: commit succeeds.

---

### Task 4: Background Executor And Worker

**Files:**
- Create: `apps/api/cleansolve_api/background.py`
- Create: `apps/api/tests/test_background.py`
- Modify: `apps/api/cleansolve_api/artifacts.py`

- [ ] **Step 1: Add failing worker tests**

Create `apps/api/tests/test_background.py`:

```python
from pathlib import Path

import pytest

from cleansolve_api import background
from cleansolve_api.artifacts import LocalArtifactStore
from cleansolve_api.background import JobRunExecutor, JobRunRequest, run_job_worker
from cleansolve_api.live_progress import LiveProgressStore
from cleansolve_ai import OpenAIConfigurationError


def create_running_job(tmp_path: Path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = {"problem": "img_problem_123", "teacher_solution": "img_teacher_456"}
    manifest.latest_image_artifact_ids = ids
    manifest.status = "RUNNING"
    store.save_manifest(manifest)
    live_store = LiveProgressStore(tmp_path / "jobs")
    live_store.initialize(manifest.job_id, ids)
    return store, live_store, manifest, ids


def request_for(job_id: str, ids: dict[str, str]) -> JobRunRequest:
    return JobRunRequest(
        job_id=job_id,
        source_image_artifact_ids=ids,
        analysis_client_kind="mock",
        openai_model_analysis="gpt-5.5",
        openai_analysis_image_detail="auto",
        openai_analysis_timeout_seconds=60,
    )


def test_job_worker_success_persists_outputs_and_progress(monkeypatch, tmp_path):
    store, live_store, manifest, ids = create_running_job(tmp_path)
    image_paths = {
        "problem": tmp_path / "problem.png",
        "teacher_solution": tmp_path / "teacher.png",
    }
    monkeypatch.setattr(store, "latest_image_artifact_paths", lambda _job_id: image_paths)

    run_job_worker(
        request_for(manifest.job_id, ids),
        store=store,
        live_progress_store=live_store,
        openai_api_key=None,
    )

    updated = store.get_job(manifest.job_id)
    assert updated.status == "APPROVED"
    assert updated.latest_analysis_artifact_ids["candidate_spec"].startswith("spec_")
    assert updated.latest_analysis_artifact_ids["progress_events"].startswith("events_")
    events_payload = store.read_latest_analysis_payload(manifest.job_id, "progress_events")
    assert events_payload["events"][0]["message"] == "작업을 시작했습니다."
    assert "source_image_paths" not in str(events_payload)


def test_job_worker_openai_failure_persists_safe_failed_progress(monkeypatch, tmp_path):
    store, live_store, manifest, ids = create_running_job(tmp_path)
    monkeypatch.setattr(
        background,
        "run_mock_workflow",
        lambda **_kwargs: (_ for _ in ()).throw(OpenAIConfigurationError("sk-secret /private/problem.png")),
    )

    run_job_worker(
        request_for(manifest.job_id, ids).model_copy(update={"analysis_client_kind": "openai"}),
        store=store,
        live_progress_store=live_store,
        openai_api_key="sk-test",
    )

    updated = store.get_job(manifest.job_id)
    payload = store.read_latest_analysis_payload(manifest.job_id, "progress_events")
    assert updated.status == "FAILED"
    assert updated.review_items[-1]["safe_reason"] == "configuration_error"
    assert payload["events"][-1]["status"] == "FAILED"
    assert payload["events"][-1]["message"] == "작업이 실패했습니다."
    assert "sk-" not in str(updated.model_dump(mode="json"))
    assert "/private" not in str(updated.model_dump(mode="json"))
    assert "sk-" not in str(payload)
    assert "/private" not in str(payload)


def test_job_run_executor_tracks_active_jobs_until_worker_finishes():
    calls = []

    def worker(request: JobRunRequest):
        calls.append(request.job_id)

    executor = JobRunExecutor(max_workers=1, worker=worker)
    request = request_for(
        "job_00000000000000000000000000000000",
        {"problem": "img_problem_123", "teacher_solution": "img_teacher_456"},
    )

    executor.submit(request)
    executor.shutdown(wait=True)

    assert calls == [request.job_id]
    assert executor.is_active(request.job_id) is False
```

- [ ] **Step 2: Run RED worker tests**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null pytest apps/api/tests/test_background.py -q
```

Expected: import failure because `cleansolve_api.background` does not exist.

- [ ] **Step 3: Implement `background.py`**

Create `apps/api/cleansolve_api/background.py`:

```python
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Callable

from pydantic import BaseModel

from cleansolve_ai import OpenAIAdapterError, OpenAIConfigurationError
from cleansolve_workflow import ProgressEvent, run_mock_workflow

from .artifacts import ImageRole, LocalArtifactStore
from .live_progress import LiveProgressStore
from .settings import settings

SAFE_FAILURE_REASONS = {
    "configuration_error",
    "response_error",
    "internal_error",
    "progress_write_failed",
    "analysis_source_changed",
}


class JobRunRequest(BaseModel):
    job_id: str
    source_image_artifact_ids: dict[ImageRole, str]
    analysis_client_kind: str
    openai_model_analysis: str
    openai_analysis_image_detail: str
    openai_analysis_timeout_seconds: int


def safe_adapter_reason(exc: OpenAIAdapterError) -> str:
    if isinstance(exc, OpenAIConfigurationError):
        return "configuration_error"
    return "response_error"


def failed_progress_event(job_id: str) -> ProgressEvent:
    return ProgressEvent(
        event_id="evt_9999",
        job_id=job_id,
        sequence=9999,
        phase="failed",
        status="FAILED",
        message="작업이 실패했습니다.",
        attempt=0,
        max_attempts=2,
        scores=None,
        next_action="fail",
        created_at="2026-06-23T00:00:00Z",
    )


def run_job_worker(
    request: JobRunRequest,
    *,
    store: LocalArtifactStore | None = None,
    live_progress_store: LiveProgressStore | None = None,
    openai_api_key: str | None = None,
) -> None:
    resolved_store = store or LocalArtifactStore(settings.storage_root)
    resolved_live_store = live_progress_store or LiveProgressStore(settings.storage_root)
    reason = "internal_error"
    try:
        manifest = resolved_store.get_job(request.job_id)
        if manifest.status != "RUNNING":
            return
        source_image_paths = {
            role: str(path)
            for role, path in resolved_store.latest_image_artifact_paths(request.job_id).items()
        }
        state = run_mock_workflow(
            job_id=request.job_id,
            source_image_artifact_ids=request.source_image_artifact_ids,
            source_image_paths=source_image_paths,
            analysis_client_kind=request.analysis_client_kind,
            openai_api_key=openai_api_key,
            openai_model_analysis=request.openai_model_analysis,
            openai_analysis_image_detail=request.openai_analysis_image_detail,
            openai_analysis_timeout_seconds=request.openai_analysis_timeout_seconds,
            progress_event_sink=lambda event: resolved_live_store.append(request.job_id, event),
        )
        review_correction_payload = {
            "job_id": request.job_id,
            "review_attempts": [
                attempt.model_dump(mode="json") for attempt in state.get("review_attempts", [])
            ],
            "tool_decisions": [
                decision.model_dump(mode="json")
                for decision in state.get("review_tool_decisions", [])
            ],
            "latest_gate_result": (
                state["latest_gate_result"].model_dump(mode="json")
                if state.get("latest_gate_result") is not None
                else None
            ),
            "revision_attempts": state["revision_attempts"],
        }
        resolved_store.save_analysis_outputs(
            job_id=request.job_id,
            status_value=state["status"],
            revision_attempts=state["revision_attempts"],
            review_items=list(state.get("review_items", [])),
            candidate_spec_payload=state["candidate_spec"].model_dump(mode="json"),
            validation_report_payload=state["validation_reports"][-1].model_dump(mode="json"),
            correction_plan_payload={
                "job_id": request.job_id,
                "revision_attempts": state["revision_attempts"],
                "correction_plans": state.get("correction_plans", []),
            },
            review_correction_payload=review_correction_payload,
            progress_events_payload=resolved_live_store.progress_events_payload(request.job_id),
            source_image_artifact_ids=request.source_image_artifact_ids,
        )
        return
    except OpenAIAdapterError as exc:
        reason = safe_adapter_reason(exc)
    except Exception:
        reason = "internal_error"

    try:
        resolved_live_store.append(request.job_id, failed_progress_event(request.job_id))
    except Exception:
        reason = "progress_write_failed"
    resolved_store.save_failed_background_run(
        request.job_id,
        reason=reason if reason in SAFE_FAILURE_REASONS else "internal_error",
        review_item={
            "type": "analysis_adapter_failed",
            "client": request.analysis_client_kind,
            "retryable": True,
            "review_reason": None,
            "safe_reason": reason if reason in SAFE_FAILURE_REASONS else "internal_error",
        },
        progress_events_payload=resolved_live_store.progress_events_payload(request.job_id),
        source_image_artifact_ids=request.source_image_artifact_ids,
    )


class JobRunExecutor:
    def __init__(
        self,
        *,
        max_workers: int,
        worker: Callable[[JobRunRequest], None] | None = None,
    ):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._worker = worker or (lambda request: run_job_worker(request, openai_api_key=settings.openai_api_key))
        self._active: set[str] = set()
        self._lock = Lock()

    def submit(self, request: JobRunRequest) -> None:
        with self._lock:
            self._active.add(request.job_id)
        future = self._executor.submit(self._run_and_clear, request)
        future.add_done_callback(lambda completed: completed.exception())

    def is_active(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._active

    def shutdown(self, *, wait: bool) -> None:
        self._executor.shutdown(wait=wait)

    def _run_and_clear(self, request: JobRunRequest) -> None:
        try:
            self._worker(request)
        finally:
            with self._lock:
                self._active.discard(request.job_id)
```

- [ ] **Step 4: Run worker tests**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null pytest apps/api/tests/test_background.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit background worker**

Run:

```bash
git add apps/api/cleansolve_api/background.py apps/api/tests/test_background.py apps/api/cleansolve_api/artifacts.py
git commit -m "feat(api): add background job worker"
```

Expected: commit succeeds.

---

### Task 5: Async Run Route And Live SSE API

**Files:**
- Modify: `apps/api/cleansolve_api/routes/jobs.py`
- Modify: `apps/api/tests/test_jobs_api.py`

- [ ] **Step 1: Update and add failing API route tests**

In `apps/api/tests/test_jobs_api.py`, update `test_create_job_and_run_mock_workflow_after_required_images_uploaded()` to expect `202` and `RUNNING`:

```python
def test_create_job_and_run_mock_workflow_after_required_images_uploaded(monkeypatch):
    class CapturingExecutor:
        def __init__(self):
            self.requests = []

        def submit(self, request):
            self.requests.append(request)

        def is_active(self, job_id):
            return any(request.job_id == job_id for request in self.requests)

    executor = CapturingExecutor()
    monkeypatch.setattr(jobs, "job_run_executor", executor)
    client = TestClient(app)

    create_response = client.post("/jobs")
    job_id = create_response.json()["job_id"]
    upload_required_images(client, job_id)
    run_response = client.post(f"/jobs/{job_id}/run")
    job_payload = client.get(f"/jobs/{job_id}").json()

    assert create_response.status_code == 201
    assert run_response.status_code == 202
    assert run_response.json()["status"] == "RUNNING"
    assert job_payload["status"] == "RUNNING"
    assert len(executor.requests) == 1
    assert executor.requests[0].job_id == job_id
```

Append:

```python
def test_run_rejects_duplicate_running_job(monkeypatch):
    class CapturingExecutor:
        def submit(self, request):
            return None

        def is_active(self, job_id):
            return True

    monkeypatch.setattr(jobs, "job_run_executor", CapturingExecutor())
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)

    first = client.post(f"/jobs/{job_id}/run")
    second = client.post(f"/jobs/{job_id}/run")

    assert first.status_code == 202
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "JOB_ALREADY_RUNNING"


def test_progress_stream_reads_live_events_with_cursor(monkeypatch):
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)
    store = LocalArtifactStore(jobs.settings.storage_root)
    manifest = store.get_job(job_id)
    ids = {
        "problem": manifest.latest_image_artifact_ids["problem"],
        "teacher_solution": manifest.latest_image_artifact_ids["teacher_solution"],
    }
    store.start_analysis_run(job_id, source_image_artifact_ids=ids)
    live_store = jobs._live_progress_store()
    live_store.initialize(job_id, ids)
    live_store.append(
        job_id,
        jobs.ProgressEvent(
            event_id="evt_0000",
            job_id=job_id,
            sequence=0,
            phase="analysis",
            status="CREATED",
            message="작업을 시작했습니다.",
            attempt=0,
            max_attempts=2,
            scores=None,
            next_action="continue",
            created_at="2026-06-23T00:00:00Z",
        ),
    )
    live_store.append(
        job_id,
        jobs.ProgressEvent(
            event_id="evt_0001",
            job_id=job_id,
            sequence=1,
            phase="analysis",
            status="SPEC_EXTRACTED",
            message="원본 문제와 선생님 손풀이를 분석하고 있습니다.",
            attempt=0,
            max_attempts=2,
            scores=None,
            next_action="continue",
            created_at="2026-06-23T00:00:01Z",
        ),
    )

    response = client.get(f"/jobs/{job_id}/progress-stream?after=evt_0000")

    assert response.status_code == 200
    assert "id: evt_0000" not in response.text
    assert "id: evt_0001" in response.text
    assert "event: progress" in response.text
```

- [ ] **Step 2: Run RED async route tests**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null pytest apps/api/tests/test_jobs_api.py::test_create_job_and_run_mock_workflow_after_required_images_uploaded apps/api/tests/test_jobs_api.py::test_run_rejects_duplicate_running_job apps/api/tests/test_jobs_api.py::test_progress_stream_reads_live_events_with_cursor -q
```

Expected: failures because route remains synchronous and `_live_progress_store()`/executor are not wired.

- [ ] **Step 3: Wire imports and module globals in `jobs.py`**

In `apps/api/cleansolve_api/routes/jobs.py`, add imports:

```python
import time
from fastapi import Header, Query
from cleansolve_api.background import JobRunExecutor, JobRunRequest, failed_progress_event
from cleansolve_api.live_progress import LiveProgressStore, cursor_sequence
```

Keep the existing `ProgressEvent` import from `cleansolve_workflow`.

Add after `PROGRESS_EVENT_PUBLIC_FIELDS`:

```python
TERMINAL_SUCCESS_STATUSES = {"APPROVED", "NEEDS_REVIEW", "REVISION_REQUIRED"}
TERMINAL_STATUSES = TERMINAL_SUCCESS_STATUSES | {"FAILED", "CANCELLED"}

job_run_executor = JobRunExecutor(max_workers=settings.background_max_workers)
```

Add helper:

```python
def _live_progress_store() -> LiveProgressStore:
    return LiveProgressStore(settings.storage_root)
```

- [ ] **Step 4: Replace `run_job()` with async start behavior**

Replace the current body of `run_job()` with:

```python
def run_job(job_id: str) -> dict[str, object]:
    store = _store()
    manifest = store.get_job(job_id)
    missing_roles = [
        role
        for role, artifact_id in manifest.latest_image_artifact_ids.items()
        if artifact_id is None
    ]
    if missing_roles:
        raise missing_required_images_error(missing_roles)

    source_image_artifact_ids = {
        "problem": manifest.latest_image_artifact_ids["problem"],
        "teacher_solution": manifest.latest_image_artifact_ids["teacher_solution"],
    }
    running_manifest = store.start_analysis_run(
        job_id,
        source_image_artifact_ids=source_image_artifact_ids,
    )
    live_store = _live_progress_store()
    try:
        live_store.initialize(job_id, source_image_artifact_ids)
        job_run_executor.submit(
            JobRunRequest(
                job_id=job_id,
                source_image_artifact_ids=source_image_artifact_ids,
                analysis_client_kind=settings.analysis_client,
                openai_model_analysis=settings.openai_model_analysis,
                openai_analysis_image_detail=settings.openai_analysis_image_detail,
                openai_analysis_timeout_seconds=settings.openai_analysis_timeout_seconds,
            )
        )
    except OSError as exc:
        failed_event = failed_progress_event(job_id)
        store.save_failed_background_run(
            job_id,
            reason="progress_write_failed",
            review_item={
                "type": "analysis_adapter_failed",
                "client": settings.analysis_client,
                "retryable": True,
                "review_reason": None,
                "safe_reason": "progress_write_failed",
            },
            progress_events_payload={"job_id": job_id, "events": [failed_event.model_dump(mode="json")]},
            source_image_artifact_ids=source_image_artifact_ids,
        )
        raise
    except Exception as exc:
        failed_event = failed_progress_event(job_id)
        try:
            live_store.append(job_id, failed_event)
            progress_events_payload = live_store.progress_events_payload(job_id)
        except Exception:
            progress_events_payload = {"job_id": job_id, "events": [failed_event.model_dump(mode="json")]}
        store.save_failed_background_run(
            job_id,
            reason="internal_error",
            review_item={
                "type": "analysis_adapter_failed",
                "client": settings.analysis_client,
                "retryable": True,
                "review_reason": None,
                "safe_reason": "internal_error",
            },
            progress_events_payload=progress_events_payload,
            source_image_artifact_ids=source_image_artifact_ids,
        )
        raise job_run_submit_failed_error(job_id) from exc
    return job_response(running_manifest)
```

Add `status_code=status.HTTP_202_ACCEPTED` to the route decorator:

```python
@router.post("/{job_id}/run", status_code=status.HTTP_202_ACCEPTED)
```

Add `job_run_submit_failed_error` to the existing multi-line `from cleansolve_api.artifacts import` block.

- [ ] **Step 5: Implement cursor-aware SSE stream helpers**

Replace `_progress_event_stream()` with a function that accepts `after`:

```python
def _progress_event_stream(payload: dict[str, object], after: str | None = None) -> Iterable[str]:
    events = payload.get("events")
    if not isinstance(events, list):
        events = []
    after_sequence = cursor_sequence(after)
    projected_events = [
        projected
        for event in events
        if isinstance(event, dict)
        for projected in [_public_progress_event(event)]
        if projected is not None
        and (after_sequence is None or int(projected["sequence"]) > after_sequence)
    ]
    sorted_events = sorted(projected_events, key=lambda event: event["sequence"])
    for event in sorted_events:
        yield _sse_frame(
            event="progress",
            event_id=event["event_id"],
            data=event,
        )
    yield _sse_frame(
        event="complete",
        data={
            "job_id": payload.get("job_id") if isinstance(payload.get("job_id"), str) else "",
            "status": "APPROVED",
            "event_count": len(sorted_events),
        },
    )
```

Add:

```python
def _failed_terminal_reason(manifest_status: str, job_id: str) -> str:
    if manifest_status != "FAILED":
        return "cancelled" if manifest_status == "CANCELLED" else "complete"
    try:
        manifest = _store().get_job(job_id)
    except HTTPException:
        return "internal_error"
    for item in reversed(manifest.review_items):
        reason = item.get("safe_reason") if isinstance(item, dict) else None
        if reason in {
            "configuration_error",
            "response_error",
            "internal_error",
            "progress_write_failed",
            "analysis_source_changed",
        }:
            return reason
    return "internal_error"


def _terminal_sse_event(status_value: str) -> str:
    if status_value in TERMINAL_SUCCESS_STATUSES:
        return "complete"
    if status_value == "CANCELLED":
        return "cancelled"
    return "failed"


def _live_progress_event_stream(job_id: str, after: str | None = None) -> Iterable[str]:
    live_store = _live_progress_store()
    sent_ids: set[str] = set()
    last_heartbeat = time.monotonic()
    while True:
        manifest = _store().get_job(job_id)
        for event in live_store.read_events(job_id, after=after):
            if event["event_id"] in sent_ids:
                continue
            sent_ids.add(event["event_id"])
            yield _sse_frame(event="progress", event_id=event["event_id"], data=event)
        if manifest.status in TERMINAL_STATUSES:
            final_events = live_store.read_events(job_id, after=after)
            event_count = len(final_events)
            yield _sse_frame(
                event=_terminal_sse_event(manifest.status),
                data={
                    "job_id": job_id,
                    "status": manifest.status,
                    "reason": "cancelled" if manifest.status == "CANCELLED" else (
                        _failed_terminal_reason(manifest.status, job_id) if manifest.status == "FAILED" else None
                    ),
                    "event_count": event_count,
                },
            )
            return
        if time.monotonic() - last_heartbeat >= settings.progress_heartbeat_seconds:
            last_heartbeat = time.monotonic()
            yield ": keep-alive\n\n"
        time.sleep(settings.progress_poll_interval_ms / 1000)
```

This version reads the failed reason from manifest review items and falls back to `internal_error` without exposing exception details.

- [ ] **Step 6: Update route signature for cursor sources**

Replace `stream_progress_events()` route with:

```python
@router.get("/{job_id}/progress-stream")
def stream_progress_events(
    job_id: str,
    after: str | None = Query(default=None),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    cursor = after or last_event_id
    store = _store()
    manifest = store.get_job(job_id)
    live_store = _live_progress_store()
    if manifest.status == "RUNNING" and live_store.exists(job_id):
        stream = _live_progress_event_stream(job_id, cursor)
    elif live_store.exists(job_id) and manifest.status in TERMINAL_STATUSES:
        stream = _live_progress_event_stream(job_id, cursor)
    else:
        payload = store.read_latest_analysis_payload(job_id, "progress_events")
        stream = _progress_event_stream(payload, cursor)
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 7: Run selected API route tests**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null pytest apps/api/tests/test_jobs_api.py::test_create_job_and_run_mock_workflow_after_required_images_uploaded apps/api/tests/test_jobs_api.py::test_run_rejects_duplicate_running_job apps/api/tests/test_jobs_api.py::test_progress_stream_reads_live_events_with_cursor -q
```

Expected: selected tests pass.

- [ ] **Step 8: Update existing failure tests for async behavior**

Update `test_run_with_openai_without_key_returns_502_and_marks_job_failed` and `test_run_with_openai_sdk_failure_returns_502_without_analysis_artifacts` so they call the worker directly or use an inline executor. The expected route response is now `202 RUNNING`, and failure is observed after worker execution.

Use this inline executor inside each test:

```python
class InlineExecutor:
    def submit(self, request):
        jobs.run_job_worker(
            request,
            store=jobs._store(),
            live_progress_store=jobs._live_progress_store(),
            openai_api_key=jobs.settings.openai_api_key,
        )

    def is_active(self, job_id):
        return False
```

Monkeypatch it:

```python
monkeypatch.setattr(jobs, "job_run_executor", InlineExecutor())
```

Update assertions:

```python
assert response.status_code == 202
assert job_response_payload["status"] == "FAILED"
assert "sk-" not in str(job_response_payload)
assert "private" not in str(job_response_payload)
progress_payload = client.get(f"/jobs/{job_id}/progress-events").json()
assert progress_payload["events"][-1]["status"] == "FAILED"
assert "sk-" not in str(progress_payload)
assert "private" not in str(progress_payload)
```

- [ ] **Step 9: Run API tests**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null pytest apps/api/tests -q
```

Expected: all API tests pass.

- [ ] **Step 10: Commit async API and SSE**

Run:

```bash
git add apps/api/cleansolve_api/routes/jobs.py apps/api/tests/test_jobs_api.py
git commit -m "feat(api): run jobs asynchronously with live sse"
```

Expected: commit succeeds.

---

### Task 6: Web Client Live SSE Flow

**Files:**
- Modify: `apps/web/src/api/client.ts`
- Modify: `apps/web/src/api/client.test.ts`

- [ ] **Step 1: Add failing web client tests**

In `apps/web/src/api/client.test.ts`, update the upload workflow test so `/jobs/job_test/run` returns:

```ts
return Response.json({ job_id: 'job_test', status: 'RUNNING', revision_attempts: 0 }, { status: 202 });
```

Change the test `eventSourceFactory` to emit progress and complete:

```ts
let createdSource: FakeEventSource | null = null;
```

Pass:

```ts
eventSourceFactory: (url) => {
  expect(url).toBe('/jobs/job_test/progress-stream');
  createdSource = new FakeEventSource();
  queueMicrotask(() => {
    createdSource?.emit('progress', JSON.stringify(progressEventPayload));
    createdSource?.emit('complete', JSON.stringify({ job_id: 'job_test', status: 'APPROVED', event_count: 1 }));
  });
  return createdSource;
},
```

Add a fetch mock for final job:

```ts
if (url === '/jobs/job_test') {
  return Response.json({ job_id: 'job_test', status: 'APPROVED', revision_attempts: 1 });
}
```

Update expected call order to include:

```ts
{ url: '/jobs/job_test', method: 'GET', bodyType: 'none', fileName: undefined },
```

after the run call and before candidate spec.

Append:

```ts
it('rejects upload workflow when live stream sends failed terminal event', async () => {
  const problemFile = new File(['problem'], 'problem.png', { type: 'image/png' });
  const teacherFile = new File(['teacher'], 'teacher.png', { type: 'image/png' });
  const fetcher = async (url: string, init?: RequestInit): Promise<Response> => {
    if (url === '/jobs' && init?.method === 'POST') {
      return Response.json({ job_id: 'job_failed', status: 'CREATED' }, { status: 201 });
    }
    if (url === '/jobs/job_failed/images/problem' && init?.method === 'POST') {
      return Response.json({ ok: true }, { status: 201 });
    }
    if (url === '/jobs/job_failed/images/teacher-solution' && init?.method === 'POST') {
      return Response.json({ ok: true }, { status: 201 });
    }
    if (url === '/jobs/job_failed/run' && init?.method === 'POST') {
      return Response.json({ job_id: 'job_failed', status: 'RUNNING', revision_attempts: 0 }, { status: 202 });
    }
    return Response.json({ detail: 'unexpected' }, { status: 404 });
  };

  await expect(
    runUploadToReviewWorkflow(
      { problemFile, teacherSolutionFile: teacherFile },
      {
        fetcher,
        eventSourceFactory: () => {
          const source = new FakeEventSource();
          queueMicrotask(() => {
            source.emit('failed', JSON.stringify({ job_id: 'job_failed', status: 'FAILED', reason: 'response_error', event_count: 1 }));
          });
          return source;
        }
      }
    )
  ).rejects.toThrow('작업 실행 중 오류가 발생했습니다.');
});
```

- [ ] **Step 2: Run RED web client tests**

Run:

```bash
npm --prefix apps/web test -- src/api/client.test.ts
```

Expected: failures because the workflow still waits for replay after run and has no failed terminal event handling.

- [ ] **Step 3: Implement `getJob()`**

In `apps/web/src/api/client.ts`, add:

```ts
export async function getJob(jobId: string, baseUrl = '', fetcher: typeof fetch = fetch): Promise<JobResponse> {
  const response = await fetcher(`${baseUrl}/jobs/${jobId}`);
  return readJson<JobResponse>(response, '작업 상태를 불러오지 못했습니다.');
}
```

- [ ] **Step 4: Extend stream terminal handlers**

In `streamProgressEvents()` options, add:

```ts
    onFailed?: () => void;
    onCancelled?: () => void;
```

Register listeners:

```ts
  source.addEventListener('failed', () => {
    close();
    onFailed?.();
  });

  source.addEventListener('cancelled', () => {
    close();
    onCancelled?.();
  });
```

Keep malformed progress payload behavior unchanged.

- [ ] **Step 5: Add live stream wait helper**

Replace `collectProgressEvents()` with:

```ts
async function waitForLiveProgress(
  jobId: string,
  {
    baseUrl,
    eventSourceFactory,
    onProgress
  }: {
    baseUrl: string;
    eventSourceFactory?: (url: string) => EventSourceLike;
    onProgress?: (event: ProgressEventPayload) => void;
  }
): Promise<ProgressEventPayload[]> {
  return new Promise((resolve, reject) => {
    const events: ProgressEventPayload[] = [];
    streamProgressEvents(jobId, {
      baseUrl,
      eventSourceFactory,
      onProgress: (event) => {
        events.push(event);
        onProgress?.(event);
      },
      onComplete: () => resolve(events),
      onFailed: () => reject(new ProgressStreamError('작업 실행 중 오류가 발생했습니다.')),
      onCancelled: () => reject(new ProgressStreamError('작업이 취소되었습니다.')),
      onError: reject
    });
  });
}
```

- [ ] **Step 6: Update upload workflow order**

In `runUploadToReviewWorkflow()`, replace:

```ts
  const run = await runJob(created.job_id, baseUrl, fetcher);
  const progressEvents = await collectProgressEvents(created.job_id, {
    baseUrl,
    fetcher,
    eventSourceFactory,
    onProgress
  });
  const candidateSpec = await getCandidateSpec(created.job_id, baseUrl, fetcher);
  const reviewItems = await getReviewItems(created.job_id, baseUrl, fetcher);
```

with:

```ts
  const run = await runJob(created.job_id, baseUrl, fetcher);
  if (run.status !== 'RUNNING') {
    throw new Error('작업 실행을 시작하지 못했습니다.');
  }
  const progressEvents = await waitForLiveProgress(created.job_id, {
    baseUrl,
    eventSourceFactory,
    onProgress
  });
  const finalJob = await getJob(created.job_id, baseUrl, fetcher);
  const candidateSpec = await getCandidateSpec(created.job_id, baseUrl, fetcher);
  const reviewItems = await getReviewItems(created.job_id, baseUrl, fetcher);
```

Return:

```ts
    status: finalJob.status,
    revisionAttempts: finalJob.revision_attempts ?? 0,
```

instead of using `run`.

- [ ] **Step 7: Run web client tests**

Run:

```bash
npm --prefix apps/web test -- src/api/client.test.ts
```

Expected: client tests pass.

- [ ] **Step 8: Commit web client flow**

Run:

```bash
git add apps/web/src/api/client.ts apps/web/src/api/client.test.ts
git commit -m "feat(web): consume live job progress stream"
```

Expected: commit succeeds.

---

### Task 7: Web State And Playwright E2E

**Files:**
- Modify: `apps/web/src/app/workflowState.ts`
- Modify: `apps/web/src/app/workflowState.test.ts`
- Modify: `apps/web/e2e/upload-review.spec.ts`

- [ ] **Step 1: Add or update workflow state terminal tests**

In `apps/web/src/app/workflowState.test.ts`, append:

```ts
it('keeps reconnect replay duplicates deduped by event id', () => {
  const first = nextWorkflowState(initialWorkflowState, { type: 'progress-server', event: progressEvent });
  const replay = nextWorkflowState(first, { type: 'progress-server', event: { ...progressEvent, message: '작업을 시작했습니다.' } });

  expect(replay.progressItems).toHaveLength(1);
  expect(replay.progressItems[0]).toMatchObject({
    source: 'server',
    id: 'evt_0000',
    active: true
  });
});
```

No implementation change is needed if this passes.

- [ ] **Step 2: Update Playwright route mocks**

In `apps/web/e2e/upload-review.spec.ts`, change `/jobs/job_e2e/run` response to:

```ts
body: JSON.stringify({ job_id: 'job_e2e', status: 'RUNNING', revision_attempts: 0 })
```

Add a route for final job status after the run route:

```ts
await page.route('**/jobs/job_e2e', async (route) => {
  await route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ job_id: 'job_e2e', status: 'APPROVED', revision_attempts: 1 })
  });
});
```

Keep `/jobs/job_e2e/progress-stream` returning progress plus complete:

```ts
body:
  'id: evt_0000\n' +
  'event: progress\n' +
  'data: {"event_id":"evt_0000","job_id":"job_e2e","sequence":0,"phase":"analysis","status":"CREATED","message":"작업을 시작했습니다.","attempt":0,"max_attempts":2,"scores":null,"next_action":"continue","created_at":"2026-06-23T00:00:00Z"}\n\n' +
  'event: complete\n' +
  'data: {"job_id":"job_e2e","status":"APPROVED","event_count":1}\n\n'
```

- [ ] **Step 3: Run web state and E2E tests**

Run:

```bash
npm --prefix apps/web test -- src/app/workflowState.test.ts
npm --prefix apps/web run test:e2e
```

Expected: both commands pass.

- [ ] **Step 4: Commit web E2E updates**

Run:

```bash
git add apps/web/src/app/workflowState.test.ts apps/web/e2e/upload-review.spec.ts
git commit -m "test(web): cover live progress upload flow"
```

Expected: commit succeeds.

---

### Task 8: Harness Async Run Drain

**Files:**
- Modify: `packages/harness/cleansolve_harness/e2e.py`
- Modify: `packages/harness/tests/test_e2e.py`

- [ ] **Step 1: Add SSE drain helper in harness**

In `packages/harness/cleansolve_harness/e2e.py`, add:

```python
def _drain_progress_stream(client: TestClient, job_id: str) -> str:
    response = client.get(f"/jobs/{job_id}/progress-stream")
    if response.status_code != 200:
        raise AssertionError(
            f"Expected progress stream status 200, got {response.status_code}: {response.text}"
        )
    body = response.text
    if "event: complete" not in body:
        raise AssertionError(f"Progress stream did not complete: {body}")
    return body
```

- [ ] **Step 2: Update run flow**

In `run_api_upload_to_export_e2e()`, replace:

```python
    run_payload = _json_response(client.post(f"/jobs/{job_id}/run"), 200)
    status = _required_string(run_payload, "status")
```

with:

```python
    run_start_payload = _json_response(client.post(f"/jobs/{job_id}/run"), 202)
    if _required_string(run_start_payload, "status") != "RUNNING":
        raise AssertionError("run start response must be RUNNING")
    _drain_progress_stream(client, job_id)
    run_payload = _json_response(client.get(f"/jobs/{job_id}"), 200)
    status = _required_string(run_payload, "status")
```

- [ ] **Step 3: Run harness tests**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null pytest packages/harness/tests/test_e2e.py -q
```

Expected: harness tests pass.

- [ ] **Step 4: Commit harness update**

Run:

```bash
git add packages/harness/cleansolve_harness/e2e.py packages/harness/tests/test_e2e.py
git commit -m "test(harness): drain live progress before assertions"
```

Expected: commit succeeds.

---

### Task 9: Product Docs After Implementation

**Files:**
- Modify: `docs/product/mvp-roadmap.md`
- Modify: `docs/product/mvp-release-checklist.md`

- [ ] **Step 1: Update roadmap M10 section**

In `docs/product/mvp-roadmap.md`, change M10 state from:

```markdown
상태: Planned
```

to:

```markdown
상태: Done
```

Add an implementation result paragraph below the design link:

```markdown
구현 결과: `POST /jobs/{job_id}/run`은 `202 RUNNING`을 반환하는 비동기 시작 endpoint가 되었고, FastAPI process 내부 background worker가 workflow를 실행한다. 실행 중 progress event는 job별 durable JSONL 파일에 flush되며, `GET /jobs/{job_id}/progress-stream`은 live event, reconnect replay, success/failure/cancelled terminal event를 제공한다. 웹 upload flow는 run 시작 직후 SSE를 열어 M9 timeline UI와 같은 payload로 live progress를 표시한다.
```

- [ ] **Step 2: Update release checklist gap**

In `docs/product/mvp-release-checklist.md`, replace:

```markdown
- 저장된 progress event replay UI는 있으나, 긴 AI 분석/보정 loop 실행 중 live SSE는 아직 없다.
```

with:

```markdown
- live SSE는 구현됐지만, 외부 queue와 process crash 후 자동 재개는 MVP 이후 운영 hardening 범위다.
```

In the remaining gap list, replace:

```markdown
- Background job과 live SSE
```

with:

```markdown
- Background job의 외부 queue 전환과 crash recovery hardening
```

- [ ] **Step 3: Run docs diff check**

Run:

```bash
git diff --check docs/product/mvp-roadmap.md docs/product/mvp-release-checklist.md
```

Expected: no output.

- [ ] **Step 4: Commit docs update**

Run:

```bash
git add docs/product/mvp-roadmap.md docs/product/mvp-release-checklist.md
git commit -m "docs: update m10 live sse status"
```

Expected: commit succeeds.

---

### Task 10: Full Verification And Final Polish

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run Python tests**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest -q
```

Expected: all Python tests pass.

- [ ] **Step 2: Run web tests**

Run:

```bash
npm --prefix apps/web test
```

Expected: all Vitest tests pass.

- [ ] **Step 3: Run web build**

Run:

```bash
npm --prefix apps/web run build
```

Expected: build completes successfully.

- [ ] **Step 4: Run Playwright**

Run:

```bash
npm --prefix apps/web run test:e2e
```

Expected: Playwright upload-review test passes.

- [ ] **Step 5: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 6: Inspect sensitive-data constraints**

Run:

```bash
rg -n "source_image_paths|openai_api_key|sk-|/private|raw model output|prompt" apps/api apps/web packages docs/product
```

Expected:

- Matches in settings, internal worker parameters, design/docs, and test assertions are acceptable.
- No API response construction, SSE payload construction, web visible text, or progress event payload includes `source_image_paths`, raw exception messages, API keys, local paths, prompts, or raw model output.

- [ ] **Step 7: Final status check**

Run:

```bash
git status --short --branch
git log --oneline -8
```

Expected:

- Branch is `feat/m10-background-live-sse`.
- Working tree is clean.
- Recent commits show the M10 implementation slices.

## Plan Self-Review

- Spec coverage: covered async `POST /run`, background worker, job state transitions, live durable flush, live SSE, reconnect cursor, failure/cancelled contract, web immediate SSE open, M9 compatibility, harness/E2E, and M10 exclusions.
- Placeholder scan: no `TBD`, `TODO`, or open-ended "add validation" tasks. Each task names files, tests, commands, and expected outcomes.
- Type consistency: `JobRunRequest`, `LiveProgressStore`, `JobRunExecutor`, `progress_event_sink`, `getJob()`, and SSE terminal event names are introduced before dependent tasks use them.
