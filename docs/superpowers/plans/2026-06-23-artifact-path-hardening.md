# Artifact Path Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden manifest-based artifact reads so corrupt `relative_path` values cannot read files outside a job directory.

**Architecture:** Add a single `LocalArtifactStore` path containment helper and route analysis, render, and export artifact read paths through it. Cover corrupt manifest escape, absolute path, and symlink escape cases with store-level tests while preserving existing API response shapes.

**Tech Stack:** Python 3.11, FastAPI `HTTPException`, Pydantic models, pytest, local filesystem artifact store.

---

## Source Spec

- Design spec: `docs/superpowers/specs/2026-06-23-artifact-path-hardening-design.md`

## File Map

- Modify: `apps/api/cleansolve_api/artifacts.py`
  - Add `_artifact_path_inside_job()`.
  - Use it in `read_latest_analysis_payload()`.
  - Use it in `rendered_preview_response()`.
  - Use it in `latest_render_artifact()`.
  - Refactor `_export_artifact_path()` to reuse the helper without changing behavior.
- Modify: `apps/api/tests/test_jobs_api.py`
  - Add corrupt analysis artifact path escape test.
  - Add corrupt analysis artifact symlink escape test.
  - Add corrupt render artifact path escape test.
  - Keep existing export escape and normal artifact tests passing.

## Contracts To Preserve

- No new artifact type.
- No manifest schema change.
- No SSE endpoint.
- No web UI changes.
- No OpenAI/GPT/image generation changes.
- No image upload write-path change.
- Existing successful job/run/render/export API tests remain green.
- Error details must not include escaped path strings.

---

### Task 1: Store-Level Regression Tests For Escaped Artifact Paths

**Files:**
- Modify: `apps/api/tests/test_jobs_api.py`

- [ ] **Step 1: Add a helper for source ids near existing store tests**

In `apps/api/tests/test_jobs_api.py`, after `assert_error()` add:

```python
def source_ids():
    return {
        "problem": "img_problem_123",
        "teacher_solution": "img_teacher_456",
    }
```

Then replace only newly added test code references with `source_ids()`. Do not refactor existing tests in this task.

- [ ] **Step 2: Add corrupt analysis path escape test**

Append this test near `test_store_saves_analysis_outputs_and_updates_manifest`:

```python
def test_read_latest_analysis_payload_rejects_path_escape_from_corrupt_manifest(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    manifest.latest_image_artifact_ids = ids
    store.save_manifest(manifest)

    updated = store.save_analysis_outputs(
        job_id=manifest.job_id,
        status_value="APPROVED",
        revision_attempts=1,
        review_items=[],
        candidate_spec_payload={"job_id": manifest.job_id, "version": 1},
        validation_report_payload={"report_id": "report_1", "passed": True, "issues": []},
        correction_plan_payload={
            "job_id": manifest.job_id,
            "revision_attempts": 1,
            "correction_plans": [],
        },
        source_image_artifact_ids=ids,
    )

    artifact = updated.analysis_artifacts["candidate_spec"][0]
    artifact.relative_path = "../escape.json"
    store.save_manifest(updated)
    (tmp_path / "jobs" / "escape.json").write_text(
        '{"escaped": true}',
        encoding="utf-8",
    )

    with pytest.raises(HTTPException) as exc_info:
        store.read_latest_analysis_payload(manifest.job_id, "candidate_spec")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "ANALYSIS_ARTIFACT_NOT_FOUND"
    assert "escape.json" not in str(exc_info.value.detail)

    absolute_path = tmp_path / "escape-absolute.json"
    absolute_path.write_text('{"escaped": true}', encoding="utf-8")
    artifact.relative_path = str(absolute_path)
    store.save_manifest(updated)

    with pytest.raises(HTTPException) as exc_info:
        store.read_latest_analysis_payload(manifest.job_id, "candidate_spec")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "ANALYSIS_ARTIFACT_NOT_FOUND"
    assert str(absolute_path) not in str(exc_info.value.detail)
```

- [ ] **Step 3: Add corrupt analysis symlink escape test**

Append this test after the path escape test:

```python
def test_read_latest_analysis_payload_rejects_symlink_escape_from_corrupt_manifest(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    manifest.latest_image_artifact_ids = ids
    store.save_manifest(manifest)

    updated = store.save_analysis_outputs(
        job_id=manifest.job_id,
        status_value="APPROVED",
        revision_attempts=1,
        review_items=[],
        candidate_spec_payload={"job_id": manifest.job_id, "version": 1},
        validation_report_payload={"report_id": "report_1", "passed": True, "issues": []},
        correction_plan_payload={
            "job_id": manifest.job_id,
            "revision_attempts": 1,
            "correction_plans": [],
        },
        source_image_artifact_ids=ids,
    )

    outside_path = tmp_path / "outside.json"
    outside_path.write_text('{"escaped": true}', encoding="utf-8")
    link_path = (
        tmp_path
        / "jobs"
        / manifest.job_id
        / "artifacts"
        / "specs"
        / "spec_escape.json"
    )
    link_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        link_path.symlink_to(outside_path)
    except OSError as exc:
        pytest.skip(f"symlink creation is not available: {exc}")

    artifact = updated.analysis_artifacts["candidate_spec"][0]
    artifact.relative_path = "artifacts/specs/spec_escape.json"
    store.save_manifest(updated)

    with pytest.raises(HTTPException) as exc_info:
        store.read_latest_analysis_payload(manifest.job_id, "candidate_spec")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "ANALYSIS_ARTIFACT_NOT_FOUND"
    assert "outside.json" not in str(exc_info.value.detail)
```

- [ ] **Step 4: Add corrupt render path escape test**

Append this test near `test_store_saves_and_reads_rendered_preview_artifact`:

```python
def test_render_artifact_reads_reject_path_escape_from_corrupt_manifest(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    _, artifact = store.save_render_artifact(
        job_id=manifest.job_id,
        svg='<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        candidate_spec_artifact_id="spec_123",
        source_image_artifact_ids=ids,
    )

    current_manifest = store.get_job(manifest.job_id)
    current_manifest.render_artifacts[0].relative_path = "../escape.svg"
    store.save_manifest(current_manifest)
    (tmp_path / "jobs" / "escape.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text>escaped</text></svg>',
        encoding="utf-8",
    )

    for call in (
        lambda: store.rendered_preview_response(manifest.job_id),
        lambda: store.latest_render_artifact(manifest.job_id),
    ):
        with pytest.raises(HTTPException) as exc_info:
            call()
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "RENDER_ARTIFACT_NOT_FOUND"
        assert "escape.svg" not in str(exc_info.value.detail)

    assert artifact.artifact_id == current_manifest.latest_render_artifact_id
```

- [ ] **Step 5: Run tests and verify RED**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest apps/api/tests/test_jobs_api.py::test_read_latest_analysis_payload_rejects_path_escape_from_corrupt_manifest apps/api/tests/test_jobs_api.py::test_read_latest_analysis_payload_rejects_symlink_escape_from_corrupt_manifest apps/api/tests/test_jobs_api.py::test_render_artifact_reads_reject_path_escape_from_corrupt_manifest -q
```

Expected:

- The analysis escape test fails because `read_latest_analysis_payload()` reads the escaped file or raises a different result.
- The symlink test fails because symlink target is read or not rejected as `ANALYSIS_ARTIFACT_NOT_FOUND`.
- The render escape test fails because escaped SVG is read or not rejected as `RENDER_ARTIFACT_NOT_FOUND`.

Do not proceed until these tests fail for the expected reason.

- [ ] **Step 6: Commit only if instructed by controller**

Do not commit after RED tests. The implementation task will commit test and code together.

---

### Task 2: Path Containment Helper And Reader Integration

**Files:**
- Modify: `apps/api/cleansolve_api/artifacts.py`
- Modify: `apps/api/tests/test_jobs_api.py`

- [ ] **Step 1: Add `_artifact_path_inside_job()`**

In `apps/api/cleansolve_api/artifacts.py`, inside `class LocalArtifactStore`, place this helper immediately before `_export_artifact_path()`:

```python
    def _artifact_path_inside_job(
        self,
        job_id: str,
        relative_path_value: str,
        not_found_error: HTTPException,
    ) -> Path:
        relative_path = Path(relative_path_value)
        if relative_path.is_absolute():
            raise not_found_error

        job_root = self._job_root(job_id).resolve()
        artifact_path = (job_root / relative_path).resolve()
        try:
            artifact_path.relative_to(job_root)
        except ValueError:
            raise not_found_error from None
        return artifact_path
```

Do not add path values to `not_found_error.detail`.

- [ ] **Step 2: Use helper in `read_latest_analysis_payload()`**

Replace:

```python
        artifact_path = self._job_root(job_id) / artifact.relative_path
        if not artifact_path.exists():
            raise analysis_artifact_not_found_error(artifact_type)
        return json.loads(artifact_path.read_text(encoding="utf-8"))
```

with:

```python
        artifact_path = self._artifact_path_inside_job(
            job_id,
            artifact.relative_path,
            analysis_artifact_not_found_error(artifact_type),
        )
        if not artifact_path.exists():
            raise analysis_artifact_not_found_error(artifact_type)
        return json.loads(artifact_path.read_text(encoding="utf-8"))
```

- [ ] **Step 3: Use helper in render readers**

In both `rendered_preview_response()` and `latest_render_artifact()`, replace:

```python
        artifact_path = self._job_root(job_id) / artifact.relative_path
        if not artifact_path.exists():
            raise render_artifact_not_found_error()
```

with:

```python
        artifact_path = self._artifact_path_inside_job(
            job_id,
            artifact.relative_path,
            render_artifact_not_found_error(),
        )
        if not artifact_path.exists():
            raise render_artifact_not_found_error()
```

Keep the returned payloads unchanged.

- [ ] **Step 4: Refactor `_export_artifact_path()` to use the helper**

Replace the full body of `_export_artifact_path()` with:

```python
    def _export_artifact_path(self, job_id: str, artifact: ExportArtifact) -> Path:
        return self._artifact_path_inside_job(
            job_id,
            artifact.relative_path,
            export_artifact_not_found_error(),
        )
```

This must preserve existing export tests.

- [ ] **Step 5: Run targeted tests and verify GREEN**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest apps/api/tests/test_jobs_api.py::test_read_latest_analysis_payload_rejects_path_escape_from_corrupt_manifest apps/api/tests/test_jobs_api.py::test_read_latest_analysis_payload_rejects_symlink_escape_from_corrupt_manifest apps/api/tests/test_jobs_api.py::test_render_artifact_reads_reject_path_escape_from_corrupt_manifest apps/api/tests/test_jobs_api.py::test_store_rejects_export_download_path_escape_from_corrupt_manifest -q
```

Expected: all selected tests pass. If symlink creation is unavailable, only the symlink test may be skipped.

- [ ] **Step 6: Run full API tests**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest apps/api/tests -q
```

Expected: all API tests pass.

- [ ] **Step 7: Run diff check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 8: Commit Task 2**

Run:

```bash
git add apps/api/cleansolve_api/artifacts.py apps/api/tests/test_jobs_api.py
git commit -m "fix(api): harden artifact read paths"
```

---

### Task 3: Final Verification, Review, Push, And PR

**Files:**
- No planned production edits.

- [ ] **Step 1: Verify no scope creep**

Run:

```bash
git diff --name-only main..HEAD
rg -n "EventSource|text/event-stream|gpt-image-2|Images API|OPENAI_API_KEY" apps/api apps/web packages docs/product docs/superpowers/specs docs/superpowers/plans
```

Expected:

- No files under `apps/web`.
- No `EventSource` or `text/event-stream`.
- No runtime `gpt-image-2` or image generation call added.
- `OPENAI_API_KEY` matches, if any, are existing settings/tests/docs and unrelated to this branch.

- [ ] **Step 2: Run final API verification**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest apps/api/tests -q
```

Expected: all API tests pass.

- [ ] **Step 3: Run broader smoke verification**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/tmp/cleansolve-no-env python -m pytest apps/api/tests packages/harness/tests -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run diff check**

Run:

```bash
git diff --check
git status --short --branch
```

Expected:

- `git diff --check` prints no output.
- status shows only committed branch state, no unstaged files.

- [ ] **Step 5: Request final reviews**

Use `superpowers:requesting-code-review` with two reviewers:

- Spec compliance reviewer:
  - Compare against `docs/superpowers/specs/2026-06-23-artifact-path-hardening-design.md`.
  - Verify analysis/render/export manifest read path containment.
  - Verify no SSE/web/OpenAI/image generation scope creep.
- Code quality reviewer:
  - Review helper placement, error mapping, path containment correctness, test robustness, and backward compatibility.

- [ ] **Step 6: Address review findings**

For each Critical or Important finding:

1. Reproduce with a failing test or exact command.
2. Patch only relevant files.
3. Run targeted tests.
4. Run `CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest apps/api/tests -q`.
5. Commit with:

```bash
git commit -m "fix(api): address artifact path review finding"
```

- [ ] **Step 7: Push branch**

Run:

```bash
git status --short
git push -u origin feat/artifact-path-hardening
```

Expected: branch pushes to origin.

- [ ] **Step 8: Create PR**

PR title:

```text
fix(api): harden artifact read paths
```

PR body:

```markdown
## 요약
- manifest에 저장된 artifact `relative_path`를 읽기 전에 job root containment를 검증하는 공통 helper를 추가했습니다.
- analysis artifact, rendered preview, latest render artifact, export artifact read path가 같은 containment 규칙을 사용하도록 정리했습니다.
- corrupt manifest의 path escape, absolute path, symlink escape 회귀 테스트를 추가했습니다.

## 검증
- [ ] `CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest apps/api/tests -q`
- [ ] `CLEANSOLVE_API_ENV_FILE=/tmp/cleansolve-no-env python -m pytest apps/api/tests packages/harness/tests -q`
- [ ] `git diff --check`

## 참고
- 이번 PR은 SSE endpoint, web UI, GPT/OpenAI/image generation 동작을 변경하지 않습니다.
- 다음 작업은 `job progress SSE stream과 web progress UI`입니다.
```
