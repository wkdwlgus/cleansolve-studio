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
RenderArtifactType = Literal["overlay_svg"]
ExportFormat = Literal["png"]
ExportMimeType = Literal["image/png"]
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
    "ANALYSIS_ADAPTER_FAILED": "analysis adapter 실행에 실패했습니다.",
    "ANALYSIS_SOURCE_CHANGED": "분석 실행 중 입력 이미지가 변경되었습니다.",
    "UNSUPPORTED_IMAGE_TYPE": "지원하지 않는 이미지 형식입니다.",
    "INVALID_IMAGE_BYTES": "이미지 파일 내용이 MIME 형식과 일치하지 않습니다.",
    "EMPTY_IMAGE": "빈 이미지 파일은 업로드할 수 없습니다.",
    "IMAGE_TOO_LARGE": "이미지 파일 크기가 허용 범위를 초과했습니다.",
    "MISSING_REQUIRED_IMAGES": "workflow 실행에 필요한 이미지가 아직 업로드되지 않았습니다.",
    "SPEC_NOT_READY": "수정할 candidate spec이 아직 없습니다.",
    "SPEC_PATCH_REJECTED": "허용되지 않는 spec 수정입니다.",
    "SPEC_VERSION_CONFLICT": "화면의 spec version이 최신이 아닙니다.",
    "RENDER_ARTIFACT_NOT_FOUND": "렌더링 preview artifact를 찾을 수 없습니다.",
    "UNSUPPORTED_EXPORT_FORMAT": "지원하지 않는 export 형식입니다.",
    "EXPORT_JOB_NOT_READY": "승인된 job만 export할 수 있습니다.",
    "EXPORT_SPEC_NOT_READY": "export할 candidate spec이 아직 없습니다.",
    "EXPORT_RENDER_NOT_READY": "export할 render artifact가 최신 상태가 아닙니다.",
    "EXPORT_SOURCE_CHANGED": "export 생성 중 입력 artifact가 변경되었습니다.",
    "EXPORT_ARTIFACT_NOT_FOUND": "export artifact를 찾을 수 없습니다.",
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


class RenderArtifact(BaseModel):
    artifact_id: str
    type: RenderArtifactType
    relative_path: str
    size_bytes: int = Field(ge=1)
    sha256: str = Field(min_length=64, max_length=64)
    created_at: str
    candidate_spec_artifact_id: str
    source_image_artifact_ids: dict[ImageRole, str]


class ExportArtifact(BaseModel):
    artifact_id: str
    format: ExportFormat
    mime_type: ExportMimeType
    relative_path: str
    size_bytes: int = Field(ge=1)
    sha256: str = Field(min_length=64, max_length=64)
    created_at: str
    candidate_spec_artifact_id: str
    render_artifact_id: str
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
    render_artifacts: list[RenderArtifact] = Field(default_factory=list)
    latest_render_artifact_id: str | None = None
    export_artifacts: list[ExportArtifact] = Field(default_factory=list)
    latest_export_artifact_id: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_job_id() -> str:
    return f"job_{uuid4().hex}"


def _new_artifact_id() -> str:
    return f"img_{uuid4().hex}"


def _new_analysis_artifact_id(artifact_type: AnalysisArtifactType) -> str:
    prefix = ANALYSIS_ARTIFACT_PREFIXES[artifact_type]
    return f"{prefix}_{uuid4().hex}"


def _new_render_artifact_id() -> str:
    return f"render_{uuid4().hex}"


def _new_export_artifact_id() -> str:
    return f"export_{uuid4().hex}"


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


def analysis_adapter_failed_error(client: str, reason: str) -> HTTPException:
    return _error(
        "ANALYSIS_ADAPTER_FAILED",
        status.HTTP_502_BAD_GATEWAY,
        {"client": client, "reason": reason},
    )


def render_artifact_not_found_error() -> HTTPException:
    return _error("RENDER_ARTIFACT_NOT_FOUND", status.HTTP_404_NOT_FOUND)


def unsupported_export_format_error(received: str) -> HTTPException:
    return _error(
        "UNSUPPORTED_EXPORT_FORMAT",
        status.HTTP_400_BAD_REQUEST,
        {"allowed": ["png"], "received": received},
    )


def export_job_not_ready_error(status_value: str) -> HTTPException:
    return _error("EXPORT_JOB_NOT_READY", status.HTTP_409_CONFLICT, {"status": status_value})


def export_spec_not_ready_error() -> HTTPException:
    return _error("EXPORT_SPEC_NOT_READY", status.HTTP_409_CONFLICT)


def export_render_not_ready_error(fields: dict[str, Any] | None = None) -> HTTPException:
    return _error("EXPORT_RENDER_NOT_READY", status.HTTP_409_CONFLICT, fields)


def export_source_changed_error(fields: dict[str, Any]) -> HTTPException:
    return _error("EXPORT_SOURCE_CHANGED", status.HTTP_409_CONFLICT, fields)


def export_artifact_not_found_error() -> HTTPException:
    return _error("EXPORT_ARTIFACT_NOT_FOUND", status.HTTP_404_NOT_FOUND)


def spec_not_ready_error() -> HTTPException:
    return _error("SPEC_NOT_READY", status.HTTP_409_CONFLICT)


def spec_patch_rejected_error(fields: dict[str, Any]) -> HTTPException:
    return _error("SPEC_PATCH_REJECTED", status.HTTP_400_BAD_REQUEST, fields)


def spec_version_conflict_error(
    *,
    client_spec_version: int,
    server_spec_version: int,
) -> HTTPException:
    return _error(
        "SPEC_VERSION_CONFLICT",
        status.HTTP_409_CONFLICT,
        {
            "client_spec_version": client_spec_version,
            "server_spec_version": server_spec_version,
        },
    )


def spec_artifact_conflict_error(
    *,
    expected_candidate_spec_artifact_id: str | None,
    latest_candidate_spec_artifact_id: str | None,
) -> HTTPException:
    return _error(
        "SPEC_VERSION_CONFLICT",
        status.HTTP_409_CONFLICT,
        {
            "expected_candidate_spec_artifact_id": expected_candidate_spec_artifact_id,
            "latest_candidate_spec_artifact_id": latest_candidate_spec_artifact_id,
        },
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
        "render_artifacts": [
            artifact.model_dump(mode="json") for artifact in manifest.render_artifacts
        ],
        "latest_render_artifact_id": manifest.latest_render_artifact_id,
        "export_artifacts": [
            artifact.model_dump(mode="json") for artifact in manifest.export_artifacts
        ],
        "latest_export_artifact_id": manifest.latest_export_artifact_id,
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

    def save_failed_analysis_run(
        self,
        job_id: str,
        *,
        client: str,
        reason: str,
    ) -> JobManifest:
        _validate_job_id(job_id)
        with self._job_lock(job_id):
            manifest = self.get_job(job_id)
            failed_item = {
                "type": "analysis_adapter_failed",
                "client": client,
                "retryable": True,
                "review_reason": None,
                "safe_reason": reason,
            }
            updated_manifest = JobManifest.model_validate(
                {
                    **manifest.model_dump(mode="python"),
                    "status": "FAILED",
                    "review_items": [*manifest.review_items, failed_item],
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

    def save_spec_patch_outputs(
        self,
        job_id: str,
        *,
        candidate_spec_payload: dict[str, Any],
        validation_report_payload: dict[str, Any],
        source_image_artifact_ids: dict[ImageRole, str],
        expected_candidate_spec_artifact_id: str | None,
    ) -> JobManifest:
        _validate_job_id(job_id)
        payloads: dict[AnalysisArtifactType, dict[str, Any]] = {
            "candidate_spec": candidate_spec_payload,
            "validation_report": validation_report_payload,
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
            latest_candidate_spec_artifact_id = manifest.latest_analysis_artifact_ids[
                "candidate_spec"
            ]
            if latest_candidate_spec_artifact_id != expected_candidate_spec_artifact_id:
                raise spec_artifact_conflict_error(
                    expected_candidate_spec_artifact_id=expected_candidate_spec_artifact_id,
                    latest_candidate_spec_artifact_id=latest_candidate_spec_artifact_id,
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
                    "analysis_artifacts": analysis_artifacts,
                    "latest_analysis_artifact_ids": latest_analysis_artifact_ids,
                    "updated_at": _utc_now(),
                }
            )
            self.save_manifest(updated_manifest)
            return updated_manifest

    def save_render_artifact(
        self,
        job_id: str,
        *,
        svg: str,
        candidate_spec_artifact_id: str,
        source_image_artifact_ids: dict[ImageRole, str],
    ) -> tuple[JobManifest, RenderArtifact]:
        _validate_job_id(job_id)
        with self._job_lock(job_id):
            manifest = self.get_job(job_id)
            latest_candidate_spec_artifact_id = manifest.latest_analysis_artifact_ids[
                "candidate_spec"
            ]
            if (
                latest_candidate_spec_artifact_id is not None
                and candidate_spec_artifact_id != latest_candidate_spec_artifact_id
            ):
                raise _error(
                    "ANALYSIS_SOURCE_CHANGED",
                    status.HTTP_409_CONFLICT,
                    {
                        "candidate_spec_artifact_id": candidate_spec_artifact_id,
                        "latest_candidate_spec_artifact_id": latest_candidate_spec_artifact_id,
                    },
                )
            artifact = self._write_render_artifact(
                job_id,
                svg,
                candidate_spec_artifact_id,
                source_image_artifact_ids,
            )
            updated_manifest = JobManifest.model_validate(
                {
                    **manifest.model_dump(mode="python"),
                    "render_artifacts": [*manifest.render_artifacts, artifact],
                    "latest_render_artifact_id": artifact.artifact_id,
                    "updated_at": _utc_now(),
                }
            )
            self.save_manifest(updated_manifest)
            return updated_manifest, artifact

    def rendered_preview_response(self, job_id: str) -> dict[str, Any]:
        manifest = self.get_job(job_id)
        artifact_id = manifest.latest_render_artifact_id
        if artifact_id is None:
            raise render_artifact_not_found_error()

        artifact = next(
            (
                candidate
                for candidate in manifest.render_artifacts
                if candidate.artifact_id == artifact_id
            ),
            None,
        )
        if artifact is None:
            raise render_artifact_not_found_error()

        artifact_path = self._job_root(job_id) / artifact.relative_path
        if not artifact_path.exists():
            raise render_artifact_not_found_error()
        return {
            "job_id": manifest.job_id,
            "artifact": artifact.model_dump(mode="json"),
            "svg": artifact_path.read_text(encoding="utf-8"),
        }

    def latest_render_artifact(self, job_id: str) -> tuple[JobManifest, RenderArtifact, str]:
        manifest = self.get_job(job_id)
        artifact_id = manifest.latest_render_artifact_id
        if artifact_id is None:
            raise render_artifact_not_found_error()

        artifact = next(
            (
                candidate
                for candidate in manifest.render_artifacts
                if candidate.artifact_id == artifact_id
            ),
            None,
        )
        if artifact is None:
            raise render_artifact_not_found_error()

        artifact_path = self._job_root(job_id) / artifact.relative_path
        if not artifact_path.exists():
            raise render_artifact_not_found_error()
        return manifest, artifact, artifact_path.read_text(encoding="utf-8")

    def save_export_artifact(
        self,
        job_id: str,
        *,
        png_bytes: bytes,
        candidate_spec_artifact_id: str,
        render_artifact_id: str,
        source_image_artifact_ids: dict[ImageRole, str],
    ) -> tuple[JobManifest, ExportArtifact]:
        _validate_job_id(job_id)
        with self._job_lock(job_id):
            manifest = self.get_job(job_id)
            latest_candidate_spec_artifact_id = manifest.latest_analysis_artifact_ids[
                "candidate_spec"
            ]
            if latest_candidate_spec_artifact_id != candidate_spec_artifact_id:
                raise export_source_changed_error(
                    {
                        "candidate_spec_artifact_id": candidate_spec_artifact_id,
                        "latest_candidate_spec_artifact_id": latest_candidate_spec_artifact_id,
                    }
                )
            if manifest.latest_render_artifact_id != render_artifact_id:
                raise export_source_changed_error(
                    {
                        "render_artifact_id": render_artifact_id,
                        "latest_render_artifact_id": manifest.latest_render_artifact_id,
                    }
                )
            if manifest.latest_image_artifact_ids != source_image_artifact_ids:
                raise export_source_changed_error(
                    {
                        "source_image_artifact_ids": source_image_artifact_ids,
                        "latest_image_artifact_ids": manifest.latest_image_artifact_ids,
                    }
                )

            artifact = self._write_export_artifact(
                job_id,
                png_bytes,
                candidate_spec_artifact_id,
                render_artifact_id,
                source_image_artifact_ids,
            )
            updated_manifest = JobManifest.model_validate(
                {
                    **manifest.model_dump(mode="python"),
                    "export_artifacts": [*manifest.export_artifacts, artifact],
                    "latest_export_artifact_id": artifact.artifact_id,
                    "updated_at": _utc_now(),
                }
            )
            self.save_manifest(updated_manifest)
            return updated_manifest, artifact

    def export_artifacts_response(self, job_id: str) -> dict[str, Any]:
        manifest = self.get_job(job_id)
        return {
            "job_id": manifest.job_id,
            "export_artifacts": [
                artifact.model_dump(mode="json") for artifact in manifest.export_artifacts
            ],
            "latest_export_artifact_id": manifest.latest_export_artifact_id,
        }

    def latest_export_response(self, job_id: str) -> dict[str, Any]:
        manifest = self.get_job(job_id)
        artifact_id = manifest.latest_export_artifact_id
        if artifact_id is None:
            raise export_artifact_not_found_error()
        artifact = self._find_export_artifact(manifest, artifact_id)
        artifact_path = self._export_artifact_path(job_id, artifact)
        if not artifact_path.exists():
            raise export_artifact_not_found_error()
        return {
            "job_id": manifest.job_id,
            "artifact": artifact.model_dump(mode="json"),
        }

    def export_download(self, job_id: str, export_id: str) -> tuple[ExportArtifact, Path]:
        manifest = self.get_job(job_id)
        artifact = self._find_export_artifact(manifest, export_id)
        artifact_path = self._export_artifact_path(job_id, artifact)
        if not artifact_path.exists():
            raise export_artifact_not_found_error()
        return artifact, artifact_path

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

    def latest_image_artifact_paths(self, job_id: str) -> dict[ImageRole, Path]:
        manifest = self.get_job(job_id)
        paths: dict[ImageRole, Path] = {}
        job_root = self._job_root(job_id).resolve()
        for role, artifact_id in manifest.latest_image_artifact_ids.items():
            if artifact_id is None:
                continue
            artifact = next(
                (
                    candidate
                    for candidate in manifest.image_artifacts[role]
                    if candidate.artifact_id == artifact_id
                ),
                None,
            )
            if artifact is None:
                raise job_not_found_error(job_id)
            path = (self._job_root(job_id) / artifact.relative_path).resolve()
            try:
                path.relative_to(job_root)
            except ValueError:
                raise job_not_found_error(job_id) from None
            paths[role] = path
        return paths

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

    def _write_render_artifact(
        self,
        job_id: str,
        svg: str,
        candidate_spec_artifact_id: str,
        source_image_artifact_ids: dict[ImageRole, str],
    ) -> RenderArtifact:
        artifact_id = _new_render_artifact_id()
        relative_path = f"artifacts/renders/{artifact_id}.svg"
        final_path = self._job_root(job_id) / relative_path
        temp_path = final_path.with_name(f"{artifact_id}.svg.tmp")
        payload_bytes = svg.encode("utf-8")

        try:
            final_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(payload_bytes)
            temp_path.replace(final_path)
        except OSError as exc:
            temp_path.unlink(missing_ok=True)
            raise _error("STORAGE_WRITE_FAILED", status.HTTP_500_INTERNAL_SERVER_ERROR) from exc

        return RenderArtifact(
            artifact_id=artifact_id,
            type="overlay_svg",
            relative_path=relative_path,
            size_bytes=len(payload_bytes),
            sha256=hashlib.sha256(payload_bytes).hexdigest(),
            created_at=_utc_now(),
            candidate_spec_artifact_id=candidate_spec_artifact_id,
            source_image_artifact_ids=source_image_artifact_ids,
        )

    def _write_export_artifact(
        self,
        job_id: str,
        png_bytes: bytes,
        candidate_spec_artifact_id: str,
        render_artifact_id: str,
        source_image_artifact_ids: dict[ImageRole, str],
    ) -> ExportArtifact:
        if not png_bytes:
            raise _error("STORAGE_WRITE_FAILED", status.HTTP_500_INTERNAL_SERVER_ERROR)

        artifact_id = _new_export_artifact_id()
        relative_path = f"artifacts/exports/{artifact_id}.png"
        final_path = self._job_root(job_id) / relative_path
        temp_path = final_path.with_name(f"{artifact_id}.png.tmp")

        try:
            final_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(png_bytes)
            temp_path.replace(final_path)
        except OSError as exc:
            temp_path.unlink(missing_ok=True)
            raise _error("STORAGE_WRITE_FAILED", status.HTTP_500_INTERNAL_SERVER_ERROR) from exc

        return ExportArtifact(
            artifact_id=artifact_id,
            format="png",
            mime_type="image/png",
            relative_path=relative_path,
            size_bytes=len(png_bytes),
            sha256=hashlib.sha256(png_bytes).hexdigest(),
            created_at=_utc_now(),
            candidate_spec_artifact_id=candidate_spec_artifact_id,
            render_artifact_id=render_artifact_id,
            source_image_artifact_ids=source_image_artifact_ids,
        )

    def _find_export_artifact(self, manifest: JobManifest, export_id: str) -> ExportArtifact:
        artifact = next(
            (
                candidate
                for candidate in manifest.export_artifacts
                if candidate.artifact_id == export_id
            ),
            None,
        )
        if artifact is None:
            raise export_artifact_not_found_error()
        return artifact

    def _export_artifact_path(self, job_id: str, artifact: ExportArtifact) -> Path:
        relative_path = Path(artifact.relative_path)
        if relative_path.is_absolute():
            raise export_artifact_not_found_error()

        job_root = self._job_root(job_id).resolve()
        artifact_path = (job_root / relative_path).resolve()
        try:
            artifact_path.relative_to(job_root)
        except ValueError:
            raise export_artifact_not_found_error() from None
        return artifact_path

    def _job_lock(self, job_id: str) -> Lock:
        key = (str(self.storage_root), job_id)
        with self._job_locks_guard:
            if key not in self._job_locks:
                self._job_locks[key] = Lock()
            return self._job_locks[key]
