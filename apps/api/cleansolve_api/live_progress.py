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
