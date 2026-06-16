from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, ClassVar, Literal
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from pydantic import BaseModel, Field

ImageRole = Literal["problem", "teacher_solution"]
ImageMimeType = Literal["image/png", "image/jpeg"]
ImageExtension = Literal["png", "jpg"]
AnalysisArtifactType = Literal["candidate_spec", "validation_report", "correction_plan"]
JobStatus = Literal["CREATED", "APPROVED", "NEEDS_REVIEW", "FAILED", "REVISION_REQUIRED"]

ALLOWED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg"}
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024
JOB_ID_PATTERN = re.compile(r"^job_[0-9a-f]{32}$")
ANALYSIS_ARTIFACT_TYPES: tuple[AnalysisArtifactType, ...] = (
    "candidate_spec",
    "validation_report",
    "correction_plan",
)
ANALYSIS_ARTIFACT_PREFIXES: dict[AnalysisArtifactType, str] = {
    "candidate_spec": "spec",
    "validation_report": "report",
    "correction_plan": "correction",
}
ANALYSIS_ARTIFACT_DIRECTORIES: dict[AnalysisArtifactType, str] = {
    "candidate_spec": "specs",
    "validation_report": "reports",
    "correction_plan": "corrections",
}

ERROR_MESSAGES = {
    "JOB_NOT_FOUND": "작업을 찾을 수 없습니다.",
    "ANALYSIS_ARTIFACT_NOT_FOUND": "분석 artifact를 찾을 수 없습니다.",
    "ANALYSIS_SOURCE_CHANGED": "분석 실행 중 입력 이미지가 변경되었습니다.",
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


class AnalysisArtifact(BaseModel):
    artifact_id: str
    type: AnalysisArtifactType
    relative_path: str
    size_bytes: int = Field(ge=1)
    sha256: str = Field(min_length=64, max_length=64)
    created_at: str
    source_image_artifact_ids: dict[ImageRole, str]


def _empty_analysis_artifacts() -> dict[AnalysisArtifactType, list[AnalysisArtifact]]:
    return {artifact_type: [] for artifact_type in ANALYSIS_ARTIFACT_TYPES}


def _empty_latest_analysis_artifact_ids() -> dict[AnalysisArtifactType, str | None]:
    return {artifact_type: None for artifact_type in ANALYSIS_ARTIFACT_TYPES}


class JobManifest(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    revision_attempts: int = Field(ge=0)
    review_items: list[dict[str, Any]]
    image_artifacts: dict[ImageRole, list[ImageArtifact]]
    latest_image_artifact_ids: dict[ImageRole, str | None]
    analysis_artifacts: dict[AnalysisArtifactType, list[AnalysisArtifact]] = Field(
        default_factory=_empty_analysis_artifacts
    )
    latest_analysis_artifact_ids: dict[AnalysisArtifactType, str | None] = Field(
        default_factory=_empty_latest_analysis_artifact_ids
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_job_id() -> str:
    return f"job_{uuid4().hex}"


def _new_artifact_id() -> str:
    return f"img_{uuid4().hex}"


def _new_analysis_artifact_id(artifact_type: AnalysisArtifactType) -> str:
    prefix = ANALYSIS_ARTIFACT_PREFIXES[artifact_type]
    return f"{prefix}_{uuid4().hex}"


def _detect_magic_type(data_prefix: bytes) -> str | None:
    if data_prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data_prefix.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


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


def analysis_artifact_not_found_error(artifact_type: AnalysisArtifactType) -> HTTPException:
    return _error(
        "ANALYSIS_ARTIFACT_NOT_FOUND",
        status.HTTP_404_NOT_FOUND,
        {"artifact_type": artifact_type},
    )


def _validate_job_id(job_id: str) -> None:
    if not JOB_ID_PATTERN.fullmatch(job_id):
        raise job_not_found_error(job_id)


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
        "analysis_artifacts": {
            artifact_type: [artifact.model_dump(mode="json") for artifact in artifacts]
            for artifact_type, artifacts in manifest.analysis_artifacts.items()
        },
        "latest_analysis_artifact_ids": manifest.latest_analysis_artifact_ids,
    }


class LocalArtifactStore:
    _job_locks: ClassVar[dict[tuple[str, str], Lock]] = {}
    _job_locks_guard: ClassVar[Lock] = Lock()

    def __init__(self, storage_root: Path):
        self.storage_root = storage_root

    def create_job(self, job_id: str | None = None) -> JobManifest:
        resolved_job_id = job_id or _new_job_id()
        _validate_job_id(resolved_job_id)
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
        _validate_job_id(job_id)
        manifest_path = self._manifest_path(job_id)
        if not manifest_path.exists():
            raise job_not_found_error(job_id)
        return JobManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    def save_manifest(self, manifest: JobManifest) -> None:
        _validate_job_id(manifest.job_id)
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
        _validate_job_id(job_id)
        with self._job_lock(job_id):
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

    def save_analysis_outputs(
        self,
        job_id: str,
        *,
        status_value: JobStatus,
        revision_attempts: int,
        review_items: list[dict[str, Any]],
        candidate_spec_payload: dict[str, Any],
        validation_report_payload: dict[str, Any],
        correction_plan_payload: dict[str, Any],
        source_image_artifact_ids: dict[ImageRole, str],
    ) -> JobManifest:
        _validate_job_id(job_id)
        payloads: dict[AnalysisArtifactType, dict[str, Any]] = {
            "candidate_spec": candidate_spec_payload,
            "validation_report": validation_report_payload,
            "correction_plan": correction_plan_payload,
        }

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

            for artifact_type, payload in payloads.items():
                artifact = self._write_analysis_artifact(
                    job_id,
                    artifact_type,
                    payload,
                    source_image_artifact_ids,
                )
                analysis_artifacts[artifact_type].append(artifact)
                latest_analysis_artifact_ids[artifact_type] = artifact.artifact_id

            updated_manifest = JobManifest.model_validate(
                {
                    **manifest.model_dump(mode="python"),
                    "status": status_value,
                    "revision_attempts": revision_attempts,
                    "review_items": review_items,
                    "analysis_artifacts": analysis_artifacts,
                    "latest_analysis_artifact_ids": latest_analysis_artifact_ids,
                    "updated_at": _utc_now(),
                }
            )
            self.save_manifest(updated_manifest)
            return updated_manifest

    def analysis_artifacts_response(self, job_id: str) -> dict[str, Any]:
        manifest = self.get_job(job_id)
        return {
            "job_id": manifest.job_id,
            "analysis_artifacts": {
                artifact_type: [
                    artifact.model_dump(mode="json")
                    for artifact in artifacts
                ]
                for artifact_type, artifacts in manifest.analysis_artifacts.items()
            },
            "latest_analysis_artifact_ids": manifest.latest_analysis_artifact_ids,
        }

    def read_latest_analysis_payload(
        self,
        job_id: str,
        artifact_type: AnalysisArtifactType,
    ) -> dict[str, Any]:
        if artifact_type not in ANALYSIS_ARTIFACT_TYPES:
            raise ValueError(f"Unsupported analysis artifact type: {artifact_type}")

        manifest = self.get_job(job_id)
        artifact_id = manifest.latest_analysis_artifact_ids[artifact_type]
        if artifact_id is None:
            raise analysis_artifact_not_found_error(artifact_type)

        artifact = next(
            (
                candidate
                for candidate in manifest.analysis_artifacts[artifact_type]
                if candidate.artifact_id == artifact_id
            ),
            None,
        )
        if artifact is None:
            raise analysis_artifact_not_found_error(artifact_type)

        artifact_path = self._job_root(job_id) / artifact.relative_path
        if not artifact_path.exists():
            raise analysis_artifact_not_found_error(artifact_type)
        return json.loads(artifact_path.read_text(encoding="utf-8"))

    async def save_image(
        self,
        job_id: str,
        role: ImageRole,
        upload: UploadFile,
    ) -> tuple[JobManifest, ImageArtifact]:
        temp_path: Path | None = None

        try:
            _validate_job_id(job_id)
            manifest = self.get_job(job_id)
            content_type = upload.content_type
            if content_type not in ALLOWED_IMAGE_MIME_TYPES:
                raise _error(
                    "UNSUPPORTED_IMAGE_TYPE",
                    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    {
                        "allowed": sorted(ALLOWED_IMAGE_MIME_TYPES),
                        "received": content_type,
                    },
                )

            artifact_id = _new_artifact_id()
            extension: ImageExtension = "png" if content_type == "image/png" else "jpg"
            role_directory = self._role_directory(job_id, role)
            relative_path = f"artifacts/images/{role}/{artifact_id}.{extension}"
            final_path = self._job_root(job_id) / relative_path
            temp_path = final_path.with_name(f"{artifact_id}.{extension}.tmp")
            digest = hashlib.sha256()
            size_bytes = 0
            first_chunk = b""

            role_directory.mkdir(parents=True, exist_ok=True)
            with temp_path.open("wb") as output:
                while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
                    if not first_chunk:
                        first_chunk = chunk
                    size_bytes += len(chunk)
                    if size_bytes > MAX_IMAGE_UPLOAD_BYTES:
                        output.close()
                        temp_path.unlink(missing_ok=True)
                        raise _error(
                            "IMAGE_TOO_LARGE",
                            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            {"max_size_bytes": MAX_IMAGE_UPLOAD_BYTES},
                        )
                    digest.update(chunk)
                    output.write(chunk)

            if size_bytes == 0:
                temp_path.unlink(missing_ok=True)
                raise _error("EMPTY_IMAGE", status.HTTP_400_BAD_REQUEST)

            if _detect_magic_type(first_chunk) != content_type:
                temp_path.unlink(missing_ok=True)
                raise _error(
                    "INVALID_IMAGE_BYTES",
                    status.HTTP_400_BAD_REQUEST,
                    {"reason": "mime_magic_mismatch"},
                )

            artifact = ImageArtifact(
                artifact_id=artifact_id,
                role=role,
                mime_type=content_type,
                extension=extension,
                size_bytes=size_bytes,
                sha256=digest.hexdigest(),
                relative_path=relative_path,
                created_at=_utc_now(),
            )
            final_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.replace(final_path)
            with self._job_lock(job_id):
                current_manifest = self.get_job(job_id)
                current_manifest.image_artifacts[role].append(artifact)
                current_manifest.latest_image_artifact_ids[role] = artifact.artifact_id
                current_manifest.updated_at = _utc_now()
                self.save_manifest(current_manifest)
                return current_manifest, artifact
        except HTTPException:
            raise
        except OSError as exc:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise _error("STORAGE_WRITE_FAILED", status.HTTP_500_INTERNAL_SERVER_ERROR) from exc
        finally:
            await upload.close()

    def _job_root(self, job_id: str) -> Path:
        return self.storage_root / job_id

    def _manifest_path(self, job_id: str) -> Path:
        return self._job_root(job_id) / "manifest.json"

    def _role_directory(self, job_id: str, role: ImageRole) -> Path:
        return self._job_root(job_id) / "artifacts" / "images" / role

    def _write_analysis_artifact(
        self,
        job_id: str,
        artifact_type: AnalysisArtifactType,
        payload: dict[str, Any],
        source_image_artifact_ids: dict[ImageRole, str],
    ) -> AnalysisArtifact:
        artifact_id = _new_analysis_artifact_id(artifact_type)
        relative_path = (
            f"artifacts/{ANALYSIS_ARTIFACT_DIRECTORIES[artifact_type]}/{artifact_id}.json"
        )
        final_path = self._job_root(job_id) / relative_path
        temp_path = final_path.with_name(f"{artifact_id}.json.tmp")
        payload_bytes = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")

        try:
            final_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(payload_bytes)
            temp_path.replace(final_path)
        except OSError as exc:
            temp_path.unlink(missing_ok=True)
            raise _error("STORAGE_WRITE_FAILED", status.HTTP_500_INTERNAL_SERVER_ERROR) from exc

        return AnalysisArtifact(
            artifact_id=artifact_id,
            type=artifact_type,
            relative_path=relative_path,
            size_bytes=len(payload_bytes),
            sha256=hashlib.sha256(payload_bytes).hexdigest(),
            created_at=_utc_now(),
            source_image_artifact_ids=source_image_artifact_ids,
        )

    def _job_lock(self, job_id: str) -> Lock:
        key = (str(self.storage_root), job_id)
        with self._job_locks_guard:
            if key not in self._job_locks:
                self._job_locks[key] = Lock()
            return self._job_locks[key]
