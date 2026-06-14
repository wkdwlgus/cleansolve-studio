from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

ImageRole = Literal["problem", "teacher_solution"]
ImageMimeType = Literal["image/png", "image/jpeg"]
ImageExtension = Literal["png", "jpg"]
JobStatus = Literal["CREATED", "APPROVED", "NEEDS_REVIEW", "FAILED"]

ALLOWED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg"}
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024

ERROR_MESSAGES = {
    "JOB_NOT_FOUND": "작업을 찾을 수 없습니다.",
    "UNSUPPORTED_IMAGE_TYPE": "지원하지 않는 이미지 형식입니다.",
    "INVALID_IMAGE_BYTES": "이미지 파일 내용이 MIME 형식과 일치하지 않습니다.",
    "EMPTY_IMAGE": "빈 이미지 파일은 업로드할 수 없습니다.",
    "IMAGE_TOO_LARGE": "이미지 파일 크기가 허용 범위를 초과했습니다.",
    "MISSING_REQUIRED_IMAGES": "workflow 실행에 필요한 이미지가 아직 업로드되지 않았습니다.",
    "STORAGE_WRITE_FAILED": "이미지 artifact 저장에 실패했습니다.",
}


class ImageArtifact(BaseModel):
    artifact_id: str
    role: ImageRole
    mime_type: ImageMimeType
    extension: ImageExtension
    size_bytes: int = Field(ge=1, le=MAX_IMAGE_UPLOAD_BYTES)
    sha256: str = Field(min_length=64, max_length=64)
    relative_path: str
    created_at: str


class JobManifest(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    revision_attempts: int = Field(ge=0)
    review_items: list[dict[str, Any]]
    image_artifacts: dict[ImageRole, list[ImageArtifact]]
    latest_image_artifact_ids: dict[ImageRole, str | None]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_job_id() -> str:
    return f"job_{uuid4().hex}"


def _new_artifact_id() -> str:
    return f"img_{uuid4().hex}"


def _error(code: str, status_code: int, fields: dict[str, Any] | None = None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": ERROR_MESSAGES[code],
            "fields": fields or {},
        },
    )


def job_not_found_error(job_id: str) -> HTTPException:
    return _error("JOB_NOT_FOUND", status.HTTP_404_NOT_FOUND, {"job_id": job_id})


def missing_required_images_error(missing_roles: list[ImageRole]) -> HTTPException:
    return _error(
        "MISSING_REQUIRED_IMAGES",
        status.HTTP_409_CONFLICT,
        {"missing_roles": missing_roles},
    )


def job_response(manifest: JobManifest) -> dict[str, Any]:
    return {
        "job_id": manifest.job_id,
        "status": manifest.status,
        "revision_attempts": manifest.revision_attempts,
        "review_items": manifest.review_items,
        "latest_image_artifact_ids": manifest.latest_image_artifact_ids,
        "image_artifacts": {
            role: [artifact.model_dump(mode="json") for artifact in artifacts]
            for role, artifacts in manifest.image_artifacts.items()
        },
    }


class LocalArtifactStore:
    def __init__(self, storage_root: Path):
        self.storage_root = storage_root

    def create_job(self, job_id: str | None = None) -> JobManifest:
        resolved_job_id = job_id or _new_job_id()
        now = _utc_now()
        manifest = JobManifest(
            job_id=resolved_job_id,
            status="CREATED",
            created_at=now,
            updated_at=now,
            revision_attempts=0,
            review_items=[],
            image_artifacts={"problem": [], "teacher_solution": []},
            latest_image_artifact_ids={"problem": None, "teacher_solution": None},
        )
        self.save_manifest(manifest)
        return manifest

    def get_job(self, job_id: str) -> JobManifest:
        manifest_path = self._manifest_path(job_id)
        if not manifest_path.exists():
            raise job_not_found_error(job_id)
        return JobManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    def save_manifest(self, manifest: JobManifest) -> None:
        job_root = self._job_root(manifest.job_id)
        try:
            job_root.mkdir(parents=True, exist_ok=True)
            manifest_path = self._manifest_path(manifest.job_id)
            temp_path = manifest_path.with_name("manifest.json.tmp")
            payload = json.dumps(
                manifest.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            temp_path.write_text(payload, encoding="utf-8")
            temp_path.replace(manifest_path)
        except OSError as exc:
            raise _error("STORAGE_WRITE_FAILED", status.HTTP_500_INTERNAL_SERVER_ERROR) from exc

    def update_after_run(
        self,
        job_id: str,
        status_value: JobStatus,
        revision_attempts: int,
        review_items: list[dict[str, Any]],
    ) -> JobManifest:
        manifest = self.get_job(job_id)
        updated_manifest = JobManifest.model_validate(
            {
                **manifest.model_dump(mode="python"),
                "status": status_value,
                "revision_attempts": revision_attempts,
                "review_items": review_items,
                "updated_at": _utc_now(),
            }
        )
        self.save_manifest(updated_manifest)
        return updated_manifest

    def _job_root(self, job_id: str) -> Path:
        return self.storage_root / job_id

    def _manifest_path(self, job_id: str) -> Path:
        return self._job_root(job_id) / "manifest.json"

    def _role_directory(self, job_id: str, role: ImageRole) -> Path:
        return self._job_root(job_id) / "artifacts" / "images" / role
