# Export Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build M6 export artifact foundations: deterministic PNG export prototype, export artifact persistence, export API routes, download support, tests, and Korean README usage docs.

**Architecture:** The renderer package owns deterministic PNG byte generation. The API artifact store owns export metadata, file persistence, stale source guards, and manifest defaults. Jobs routes enforce export preconditions, call the renderer, save export artifacts, and return/download metadata without exposing absolute filesystem paths.

**Tech Stack:** Python 3.13, FastAPI `FileResponse`, Pydantic, local filesystem artifacts, stdlib `zlib`/`struct`/`binascii`, pytest, existing FastAPI `TestClient`.

---

## File Structure

- Create `packages/renderer/cleansolve_renderer/export_png.py`
  - Owns deterministic PNG prototype byte generation.
- Create `packages/renderer/tests/test_export_png.py`
  - Verifies valid PNG structure, deterministic output, text metadata, and invalid dimensions.
- Modify `apps/api/cleansolve_api/artifacts.py`
  - Adds export artifact model, manifest fields, errors, store helpers, and file writers.
- Modify `apps/api/cleansolve_api/routes/jobs.py`
  - Adds export request model and export/list/latest/download routes.
- Modify `apps/api/tests/test_jobs_api.py`
  - Adds store and API export contract tests.
- Modify `README.md`
  - Adds Korean local export flow and PDF deferred note.

## Task 1: Deterministic PNG Writer

**Files:**
- Create: `packages/renderer/cleansolve_renderer/export_png.py`
- Create: `packages/renderer/tests/test_export_png.py`

- [ ] **Step 1: Write failing renderer tests**

Create `packages/renderer/tests/test_export_png.py`:

```py
import hashlib
import struct

import pytest

from cleansolve_renderer.export_png import render_export_png

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def chunk_payloads(png_bytes: bytes, chunk_type: bytes) -> list[bytes]:
    offset = len(PNG_SIGNATURE)
    payloads: list[bytes] = []
    while offset < len(png_bytes):
        length = struct.unpack(">I", png_bytes[offset : offset + 4])[0]
        current_type = png_bytes[offset + 4 : offset + 8]
        payload = png_bytes[offset + 8 : offset + 8 + length]
        if current_type == chunk_type:
            payloads.append(payload)
        offset += 12 + length
    return payloads


def text_chunks(png_bytes: bytes) -> dict[str, str]:
    chunks: dict[str, str] = {}
    for payload in chunk_payloads(png_bytes, b"tEXt"):
        key, value = payload.split(b"\x00", 1)
        chunks[key.decode("latin-1")] = value.decode("utf-8")
    return chunks


def test_render_export_png_writes_valid_signature_and_ihdr_dimensions():
    png = render_export_png(width=17, height=11, svg="<svg></svg>", metadata={})

    assert png.startswith(PNG_SIGNATURE)
    ihdr = chunk_payloads(png, b"IHDR")[0]
    width, height, bit_depth, color_type = struct.unpack(">IIBB", ihdr[:10])
    assert (width, height) == (17, 11)
    assert bit_depth == 8
    assert color_type == 2


def test_render_export_png_embeds_required_and_caller_metadata():
    svg = "<svg>overlay</svg>"
    png = render_export_png(
        width=2,
        height=2,
        svg=svg,
        metadata={"CleanSolve-Job-ID": "job_123"},
    )

    chunks = text_chunks(png)
    assert chunks["CleanSolve-Export-Version"] == "m6-png-prototype-v1"
    assert chunks["CleanSolve-SVG-SHA256"] == hashlib.sha256(svg.encode("utf-8")).hexdigest()
    assert chunks["CleanSolve-Source"] == "deterministic-overlay-svg"
    assert chunks["CleanSolve-Job-ID"] == "job_123"


def test_render_export_png_is_deterministic_for_same_input():
    kwargs = {
        "width": 3,
        "height": 4,
        "svg": "<svg><path /></svg>",
        "metadata": {"b": "2", "a": "1"},
    }

    assert render_export_png(**kwargs) == render_export_png(**kwargs)


@pytest.mark.parametrize(("width", "height"), [(0, 1), (1, 0), (-1, 1), (1, -1)])
def test_render_export_png_rejects_non_positive_dimensions(width, height):
    with pytest.raises(ValueError, match="width and height must be positive integers"):
        render_export_png(width=width, height=height, svg="<svg></svg>", metadata={})
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest packages/renderer/tests/test_export_png.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cleansolve_renderer.export_png'`.

- [ ] **Step 3: Implement PNG writer**

Create `packages/renderer/cleansolve_renderer/export_png.py`:

```py
from __future__ import annotations

import binascii
import hashlib
import struct
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
EXPORT_VERSION = "m6-png-prototype-v1"


def render_export_png(
    *,
    width: int,
    height: int,
    svg: str,
    metadata: dict[str, str],
) -> bytes:
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise ValueError("width and height must be positive integers")

    svg_bytes = svg.encode("utf-8")
    text_chunks = {
        "CleanSolve-Export-Version": EXPORT_VERSION,
        "CleanSolve-SVG-SHA256": hashlib.sha256(svg_bytes).hexdigest(),
        "CleanSolve-Source": "deterministic-overlay-svg",
        **metadata,
    }

    raw_row = b"\x00" + (b"\xff\xff\xff" * width)
    raw_image = raw_row * height
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunks = [_chunk(b"IHDR", ihdr)]
    chunks.extend(_text_chunk(key, value) for key, value in text_chunks.items() if key.startswith("CleanSolve-"))
    chunks.extend(
        _text_chunk(key, text_chunks[key])
        for key in sorted(key for key in text_chunks if not key.startswith("CleanSolve-"))
    )
    chunks.append(_chunk(b"IDAT", zlib.compress(raw_image, level=9)))
    chunks.append(_chunk(b"IEND", b""))
    return PNG_SIGNATURE + b"".join(chunks)


def _text_chunk(key: str, value: str) -> bytes:
    key_bytes = key.encode("latin-1")
    value_bytes = str(value).encode("utf-8")
    return _chunk(b"tEXt", key_bytes + b"\x00" + value_bytes)


def _chunk(chunk_type: bytes, payload: bytes) -> bytes:
    checksum = binascii.crc32(chunk_type)
    checksum = binascii.crc32(payload, checksum) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", checksum)
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
python -m pytest packages/renderer/tests/test_export_png.py -q
```

Expected: PASS.

## Task 2: Export Artifact Store

**Files:**
- Modify: `apps/api/cleansolve_api/artifacts.py`
- Modify: `apps/api/tests/test_jobs_api.py`

- [ ] **Step 1: Add failing store tests**

Append tests to `apps/api/tests/test_jobs_api.py` near existing artifact store tests:

```py
def test_old_manifest_json_defaults_export_artifact_fields(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    job_id = "job_00000000000000000000000000000000"
    job_root = tmp_path / "jobs" / job_id
    job_root.mkdir(parents=True)
    (job_root / "manifest.json").write_text(
        """
{
  "job_id": "job_00000000000000000000000000000000",
  "status": "CREATED",
  "created_at": "2026-06-16T00:00:00Z",
  "updated_at": "2026-06-16T00:00:00Z",
  "revision_attempts": 0,
  "review_items": [],
  "image_artifacts": {
    "problem": [],
    "teacher_solution": []
  },
  "latest_image_artifact_ids": {
    "problem": null,
    "teacher_solution": null
  }
}
""",
        encoding="utf-8",
    )

    manifest = store.get_job(job_id)

    assert manifest.export_artifacts == []
    assert manifest.latest_export_artifact_id is None


def test_store_saves_and_reads_export_artifact(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    manifest.latest_image_artifact_ids = {
        "problem": "img_problem_123",
        "teacher_solution": "img_teacher_456",
    }
    manifest.latest_analysis_artifact_ids["candidate_spec"] = "spec_123"
    manifest.latest_render_artifact_id = "render_123"
    store.save_manifest(manifest)

    updated, artifact = store.save_export_artifact(
        job_id=manifest.job_id,
        png_bytes=b"\x89PNG\r\n\x1a\nexport",
        candidate_spec_artifact_id="spec_123",
        render_artifact_id="render_123",
        source_image_artifact_ids={
            "problem": "img_problem_123",
            "teacher_solution": "img_teacher_456",
        },
    )

    assert artifact.artifact_id.startswith("export_")
    assert artifact.format == "png"
    assert artifact.mime_type == "image/png"
    assert artifact.relative_path == f"artifacts/exports/{artifact.artifact_id}.png"
    assert updated.latest_export_artifact_id == artifact.artifact_id
    assert store.export_artifacts_response(manifest.job_id)["latest_export_artifact_id"] == artifact.artifact_id
    assert store.latest_export_response(manifest.job_id) == {
        "job_id": manifest.job_id,
        "artifact": artifact.model_dump(mode="json"),
    }
    download_artifact, download_path = store.export_download(manifest.job_id, artifact.artifact_id)
    assert download_artifact == artifact
    assert download_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_store_rejects_export_when_candidate_or_render_or_source_changed(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    manifest.latest_image_artifact_ids = {
        "problem": "img_problem_latest",
        "teacher_solution": "img_teacher_latest",
    }
    manifest.latest_analysis_artifact_ids["candidate_spec"] = "spec_latest"
    manifest.latest_render_artifact_id = "render_latest"
    store.save_manifest(manifest)

    stale_cases = [
        {
            "candidate_spec_artifact_id": "spec_stale",
            "render_artifact_id": "render_latest",
            "source_image_artifact_ids": manifest.latest_image_artifact_ids,
        },
        {
            "candidate_spec_artifact_id": "spec_latest",
            "render_artifact_id": "render_stale",
            "source_image_artifact_ids": manifest.latest_image_artifact_ids,
        },
        {
            "candidate_spec_artifact_id": "spec_latest",
            "render_artifact_id": "render_latest",
            "source_image_artifact_ids": {
                "problem": "img_problem_old",
                "teacher_solution": "img_teacher_latest",
            },
        },
    ]

    for stale_case in stale_cases:
        with pytest.raises(HTTPException) as exc_info:
            store.save_export_artifact(job_id=manifest.job_id, png_bytes=b"png", **stale_case)
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "EXPORT_SOURCE_CHANGED"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest apps/api/tests/test_jobs_api.py -q
```

Expected: FAIL with missing `export_artifacts`, `save_export_artifact`, or export helper attributes.

- [ ] **Step 3: Implement store models, errors, and helpers**

Modify `apps/api/cleansolve_api/artifacts.py`:

- Add aliases:

```py
ExportFormat = Literal["png"]
ExportMimeType = Literal["image/png"]
```

- Add errors to `ERROR_MESSAGES`:

```py
"UNSUPPORTED_EXPORT_FORMAT": "지원하지 않는 export 형식입니다.",
"EXPORT_JOB_NOT_READY": "승인된 job만 export할 수 있습니다.",
"EXPORT_SPEC_NOT_READY": "export할 candidate spec이 아직 없습니다.",
"EXPORT_RENDER_NOT_READY": "export할 render artifact가 최신 상태가 아닙니다.",
"EXPORT_SOURCE_CHANGED": "export 생성 중 입력 artifact가 변경되었습니다.",
"EXPORT_ARTIFACT_NOT_FOUND": "export artifact를 찾을 수 없습니다.",
```

- Add model and manifest fields:

```py
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
```

```py
export_artifacts: list[ExportArtifact] = Field(default_factory=list)
latest_export_artifact_id: str | None = None
```

- Add helper ids/errors:

```py
def _new_export_artifact_id() -> str:
    return f"export_{uuid4().hex}"
```

```py
def export_source_changed_error(fields: dict[str, Any]) -> HTTPException:
    return _error("EXPORT_SOURCE_CHANGED", status.HTTP_409_CONFLICT, fields)


def export_artifact_not_found_error() -> HTTPException:
    return _error("EXPORT_ARTIFACT_NOT_FOUND", status.HTTP_404_NOT_FOUND)
```

- Add `job_response` fields:

```py
"export_artifacts": [
    artifact.model_dump(mode="json") for artifact in manifest.export_artifacts
],
"latest_export_artifact_id": manifest.latest_export_artifact_id,
```

- Add `latest_render_artifact(job_id: str) -> tuple[JobManifest, RenderArtifact, str]`.
- Add `save_export_artifact(job_id: str, *, png_bytes: bytes, candidate_spec_artifact_id: str, render_artifact_id: str, source_image_artifact_ids: dict[ImageRole, str]) -> tuple[JobManifest, ExportArtifact]`.
- Add `export_artifacts_response(job_id: str) -> dict[str, Any]`.
- Add `latest_export_response(job_id: str) -> dict[str, Any]`.
- Add `export_download(job_id: str, export_id: str) -> tuple[ExportArtifact, Path]`.
- Add `_write_export_artifact(job_id: str, png_bytes: bytes, candidate_spec_artifact_id: str, render_artifact_id: str, source_image_artifact_ids: dict[ImageRole, str]) -> ExportArtifact`.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
python -m pytest apps/api/tests/test_jobs_api.py -q
```

Expected: PASS for store tests and existing job tests.

## Task 3: Export API Routes

**Files:**
- Modify: `apps/api/cleansolve_api/routes/jobs.py`
- Modify: `apps/api/tests/test_jobs_api.py`

- [ ] **Step 1: Add failing API route tests**

Append route tests to `apps/api/tests/test_jobs_api.py`:

```py
def run_and_render_job(client: TestClient) -> tuple[str, dict]:
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)
    client.post(f"/jobs/{job_id}/run")
    render_payload = client.post(f"/jobs/{job_id}/render").json()
    return job_id, render_payload


def test_export_route_requires_approved_job():
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]

    response = client.post(f"/jobs/{job_id}/export", json={"format": "png"})

    assert response.status_code == 409
    assert_error(response, "EXPORT_JOB_NOT_READY")
    assert response.json()["detail"]["fields"] == {"status": "CREATED"}


def test_export_route_requires_latest_render_artifact():
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)
    client.post(f"/jobs/{job_id}/run")

    response = client.post(f"/jobs/{job_id}/export", json={"format": "png"})

    assert response.status_code == 409
    assert_error(response, "EXPORT_RENDER_NOT_READY")


def test_export_route_rejects_unsupported_format():
    client = TestClient(app)
    job_id, _ = run_and_render_job(client)

    response = client.post(f"/jobs/{job_id}/export", json={"format": "pdf"})

    assert response.status_code == 400
    assert_error(response, "UNSUPPORTED_EXPORT_FORMAT")
    assert response.json()["detail"]["fields"] == {
        "allowed": ["png"],
        "received": "pdf",
    }


def test_export_route_saves_png_artifact_and_downloads_it():
    client = TestClient(app)
    job_id, render_payload = run_and_render_job(client)

    response = client.post(f"/jobs/{job_id}/export", json={"format": "png"})

    assert response.status_code == 200
    payload = response.json()
    artifact = payload["artifact"]
    assert artifact["artifact_id"].startswith("export_")
    assert artifact["format"] == "png"
    assert artifact["mime_type"] == "image/png"
    assert artifact["render_artifact_id"] == render_payload["artifact"]["artifact_id"]
    assert artifact["candidate_spec_artifact_id"] == render_payload["artifact"]["candidate_spec_artifact_id"]
    assert payload["latest_export_artifact_id"] == artifact["artifact_id"]

    exports_response = client.get(f"/jobs/{job_id}/exports")
    latest_response = client.get(f"/jobs/{job_id}/exports/latest")
    download_response = client.get(f"/jobs/{job_id}/exports/{artifact['artifact_id']}/download")

    assert exports_response.status_code == 200
    assert exports_response.json()["latest_export_artifact_id"] == artifact["artifact_id"]
    assert latest_response.status_code == 200
    assert latest_response.json()["artifact"] == artifact
    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "image/png"
    assert download_response.content.startswith(PNG_BYTES[:8])


def test_latest_export_route_returns_404_before_export():
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]

    response = client.get(f"/jobs/{job_id}/exports/latest")

    assert response.status_code == 404
    assert_error(response, "EXPORT_ARTIFACT_NOT_FOUND")


def test_export_download_returns_404_for_unknown_export_id():
    client = TestClient(app)
    job_id, _ = run_and_render_job(client)

    response = client.get(f"/jobs/{job_id}/exports/export_unknown/download")

    assert response.status_code == 404
    assert_error(response, "EXPORT_ARTIFACT_NOT_FOUND")


def test_export_route_rejects_stale_render_candidate_spec():
    client = TestClient(app)
    job_id, _ = run_and_render_job(client)
    client.patch(
        f"/jobs/{job_id}/spec",
        json={
            "client_spec_version": 1,
            "element_id": "el_freehand_dimension_001",
            "operation": "update_element",
            "changes": {"geometry.target_anchor_end": [610, 380]},
        },
    )

    response = client.post(f"/jobs/{job_id}/export", json={"format": "png"})

    assert response.status_code == 409
    assert_error(response, "EXPORT_RENDER_NOT_READY")
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest apps/api/tests/test_jobs_api.py -q
```

Expected: FAIL with missing `/export`, `/exports`, `/exports/latest`, or download routes.

- [ ] **Step 3: Implement routes**

Modify `apps/api/cleansolve_api/routes/jobs.py`:

- Import:

```py
from fastapi.responses import FileResponse
from pydantic import BaseModel
from cleansolve_renderer.export_png import render_export_png
```

- Add request model:

```py
class ExportRequest(BaseModel):
    format: str = "png"
```

- Add public error functions in `artifacts.py` and import them in `routes/jobs.py`:

```py
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
```

- Add routes:

```py
@router.post("/{job_id}/export")
def export_job(job_id: str, request: ExportRequest | None = None) -> dict[str, object]:
    resolved_request = request or ExportRequest()
    if resolved_request.format != "png":
        raise unsupported_export_format_error(resolved_request.format)

    store = _store()
    manifest = store.get_job(job_id)
    if manifest.status != "APPROVED":
        raise export_job_not_ready_error(manifest.status)

    candidate_spec_artifact_id = manifest.latest_analysis_artifact_ids["candidate_spec"]
    if candidate_spec_artifact_id is None:
        raise export_spec_not_ready_error()

    _, render_artifact, svg = store.latest_render_artifact(job_id)
    if render_artifact.candidate_spec_artifact_id != candidate_spec_artifact_id:
        raise export_render_not_ready_error(
            {
                "latest_candidate_spec_artifact_id": candidate_spec_artifact_id,
                "render_candidate_spec_artifact_id": render_artifact.candidate_spec_artifact_id,
            }
        )
    if render_artifact.source_image_artifact_ids != manifest.latest_image_artifact_ids:
        raise export_source_changed_error(
            {
                "source_image_artifact_ids": render_artifact.source_image_artifact_ids,
                "latest_image_artifact_ids": manifest.latest_image_artifact_ids,
            }
        )

    spec = CandidateSpec.model_validate(store.read_latest_analysis_payload(job_id, "candidate_spec"))
    png_bytes = render_export_png(
        width=spec.page.width,
        height=spec.page.height,
        svg=svg,
        metadata={
            "CleanSolve-Job-ID": job_id,
            "CleanSolve-Candidate-Spec-Artifact-ID": candidate_spec_artifact_id,
            "CleanSolve-Render-Artifact-ID": render_artifact.artifact_id,
        },
    )
    updated_manifest, export_artifact = store.save_export_artifact(
        job_id=job_id,
        png_bytes=png_bytes,
        candidate_spec_artifact_id=candidate_spec_artifact_id,
        render_artifact_id=render_artifact.artifact_id,
        source_image_artifact_ids=render_artifact.source_image_artifact_ids,
    )
    return {
        "job_id": job_id,
        "artifact": export_artifact.model_dump(mode="json"),
        "latest_export_artifact_id": updated_manifest.latest_export_artifact_id,
    }


@router.get("/{job_id}/exports")
def get_exports(job_id: str) -> dict[str, object]:
    return _store().export_artifacts_response(job_id)


@router.get("/{job_id}/exports/latest")
def get_latest_export(job_id: str) -> dict[str, object]:
    return _store().latest_export_response(job_id)


@router.get("/{job_id}/exports/{export_id}/download")
def download_export(job_id: str, export_id: str) -> FileResponse:
    artifact, path = _store().export_download(job_id, export_id)
    return FileResponse(path, media_type=artifact.mime_type, filename=f"{artifact.artifact_id}.png")
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
python -m pytest apps/api/tests/test_jobs_api.py -q
```

Expected: PASS.

## Task 4: README Export Flow

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add README section**

Insert after “로컬 이미지 업로드 흐름”:

```md
## 로컬 export 흐름

M6 기준 export는 PNG artifact만 지원합니다. PDF export는 명시적으로 deferred 상태이며, `format: "pdf"` 요청은 `UNSUPPORTED_EXPORT_FORMAT`으로 거부됩니다.

기본 순서는 다음입니다.

1. `POST /jobs`로 job을 만듭니다.
2. `POST /jobs/{job_id}/images/problem`에 원본 문제 이미지를 업로드합니다.
3. `POST /jobs/{job_id}/images/teacher-solution`에 선생님 손풀이 이미지를 업로드합니다.
4. `POST /jobs/{job_id}/run`으로 mock workflow를 실행합니다.
5. `POST /jobs/{job_id}/render`로 최신 candidate spec의 deterministic SVG render artifact를 저장합니다.
6. `POST /jobs/{job_id}/export`에 `{ "format": "png" }`를 보내 PNG export artifact를 생성합니다.
7. `GET /jobs/{job_id}/exports/latest`로 최신 export metadata를 확인합니다.
8. `GET /jobs/{job_id}/exports/{export_id}/download`로 PNG bytes를 다운로드합니다.

M6 PNG export prototype은 latest render artifact와 candidate spec artifact를 참조하는 export 저장/다운로드 경로를 검증하기 위한 기반입니다. 상용 품질의 원본 이미지 + overlay raster compositing은 이후 milestone에서 다룹니다.
```

- [ ] **Step 2: Verify docs mention no absolute paths**

Run:

```bash
rg -n "absolute|/Users|/tmp|file://" README.md docs/superpowers/specs/2026-06-17-export-foundation-design.md
```

Expected: no new absolute local path examples. Existing text saying absolute paths are not exposed is allowed.

## Task 5: Full Verification and Reviews

**Files:**
- All changed files.

- [ ] **Step 1: Run full verification**

Run:

```bash
python -m pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
git diff --check
```

Expected:

- pytest passes.
- Vitest passes.
- web build exits 0. Existing Node/Vite version warning and chunk-size warning may appear.
- `git diff --check` has no output.

- [ ] **Step 2: Request spec compliance review**

Ask reviewer to compare implementation with:

- `docs/superpowers/specs/2026-06-17-export-foundation-design.md`
- this plan

Reviewer must inspect:

- PNG writer
- export store helpers
- export routes
- API tests
- README section

- [ ] **Step 3: Request code quality review**

Ask reviewer to focus on:

- invalid PNG bytes
- manifest stale-write races
- route ordering
- absolute path leakage
- brittle tests
- unsupported format handling

- [ ] **Step 4: Fix review findings and rerun verification**

Any Critical or Important finding must be fixed before commit.

- [ ] **Step 5: Commit and push**

Run:

```bash
git add packages/renderer/cleansolve_renderer/export_png.py packages/renderer/tests/test_export_png.py apps/api/cleansolve_api/artifacts.py apps/api/cleansolve_api/routes/jobs.py apps/api/tests/test_jobs_api.py README.md docs/superpowers/plans/2026-06-17-export-foundation.md
git commit -m "feat(export): add png export artifacts"
git push -u origin feat/export-foundation
```

Expected: branch pushed to GitHub.

## Self-Review Checklist

- Spec coverage: Tasks cover PNG writer, export artifact model, manifest defaults, store guards, API routes, download, README, tests, and verification.
- Placeholder scan: no TBD/TODO/fill-later instructions are present.
- Type consistency: artifact ids use `export_`, format uses `"png"`, mime type uses `"image/png"`, and route paths match the spec.
- Scope control: web export button, PDF generation, OpenAI calls, visual compositing, and review resolve are excluded.
