# Candidate Spec Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store mock workflow outputs as job analysis artifacts and expose them through API endpoints.

**Architecture:** Extend the existing local artifact store and job manifest with analysis artifact metadata. Pass uploaded image artifact ids into the mock workflow so candidate specs reference actual stored inputs, then persist candidate spec, validation report, and correction plan JSON files under each job.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, pytest, existing LangGraph mock workflow.

---

## Source Documents

- Spec: `docs/superpowers/specs/2026-06-16-candidate-spec-pipeline-design.md`
- Roadmap: `docs/product/mvp-roadmap.md`

## Files

- Modify: `packages/ai/cleansolve_ai/mock_client.py`
- Modify: `packages/ai/tests/test_mock_client.py`
- Modify: `packages/workflow/cleansolve_workflow/graph.py`
- Modify: `packages/workflow/cleansolve_workflow/nodes.py`
- Modify: `packages/workflow/cleansolve_workflow/state.py`
- Modify: `packages/workflow/tests/test_graph.py`
- Modify: `apps/api/cleansolve_api/artifacts.py`
- Modify: `apps/api/cleansolve_api/routes/jobs.py`
- Modify: `apps/api/tests/test_jobs_api.py`

Do not modify web UI, renderer, OpenAI adapter, export, or dataset scripts.

## Task 1: Source Image Artifact IDs In Mock Workflow

**Files:**

- Modify: `packages/ai/tests/test_mock_client.py`
- Modify: `packages/ai/cleansolve_ai/mock_client.py`
- Modify: `packages/workflow/tests/test_graph.py`
- Modify: `packages/workflow/cleansolve_workflow/state.py`
- Modify: `packages/workflow/cleansolve_workflow/graph.py`
- Modify: `packages/workflow/cleansolve_workflow/nodes.py`

- [ ] **Step 1: Add failing mock client test**

Append this test to `packages/ai/tests/test_mock_client.py`:

```python
def test_mock_client_uses_uploaded_image_artifact_ids_when_provided():
    spec = MockAnalysisClient().extract_candidate_spec(
        "job_abc",
        problem_image_artifact_id="img_problem_123",
        teacher_solution_image_artifact_id="img_teacher_456",
    )

    assert spec.source_images == {
        "problem_image_id": "img_problem_123",
        "teacher_solution_image_id": "img_teacher_456",
    }
```

Run:

```bash
python -m pytest packages/ai/tests/test_mock_client.py::test_mock_client_uses_uploaded_image_artifact_ids_when_provided -q
```

Expected: fail with `TypeError` because the keyword arguments do not exist.

- [ ] **Step 2: Implement mock client signature**

In `packages/ai/cleansolve_ai/mock_client.py`, change the function signature to:

```python
def extract_candidate_spec(
    self,
    job_id: str,
    *,
    problem_image_artifact_id: str | None = None,
    teacher_solution_image_artifact_id: str | None = None,
) -> CandidateSpec:
```

Change `source_images` to:

```python
source_images={
    "problem_image_id": problem_image_artifact_id or f"{job_id}_problem",
    "teacher_solution_image_id": (
        teacher_solution_image_artifact_id or f"{job_id}_teacher_solution"
    ),
},
```

Run:

```bash
python -m pytest packages/ai/tests/test_mock_client.py -q
```

Expected: all mock client tests pass.

- [ ] **Step 3: Add failing workflow source id test**

Append this test to `packages/workflow/tests/test_graph.py`:

```python
def test_mock_workflow_passes_source_image_artifact_ids_to_candidate_spec():
    state = run_mock_workflow(
        "job_abc",
        source_image_artifact_ids={
            "problem": "img_problem_123",
            "teacher_solution": "img_teacher_456",
        },
    )

    assert state["candidate_spec"].source_images == {
        "problem_image_id": "img_problem_123",
        "teacher_solution_image_id": "img_teacher_456",
    }
```

Run:

```bash
python -m pytest packages/workflow/tests/test_graph.py::test_mock_workflow_passes_source_image_artifact_ids_to_candidate_spec -q
```

Expected: fail with `TypeError` because `run_mock_workflow` does not accept `source_image_artifact_ids`.

- [ ] **Step 4: Extend workflow state and graph**

In `packages/workflow/cleansolve_workflow/state.py`, add optional key:

```python
source_image_artifact_ids: NotRequired[dict[str, str | None]]
```

In `packages/workflow/cleansolve_workflow/graph.py`, add parameter to `run_mock_workflow`:

```python
source_image_artifact_ids: dict[str, str | None] | None = None,
```

If provided, set:

```python
initial_state["source_image_artifact_ids"] = source_image_artifact_ids
```

In `packages/workflow/cleansolve_workflow/nodes.py`, update `analyze_sources`:

```python
source_ids = state.get("source_image_artifact_ids") or {}
state["candidate_spec"] = MockAnalysisClient().extract_candidate_spec(
    state["job_id"],
    problem_image_artifact_id=source_ids.get("problem"),
    teacher_solution_image_artifact_id=source_ids.get("teacher_solution"),
)
```

Run:

```bash
python -m pytest packages/ai/tests/test_mock_client.py packages/workflow/tests/test_graph.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add packages/ai/cleansolve_ai/mock_client.py packages/ai/tests/test_mock_client.py packages/workflow/cleansolve_workflow/state.py packages/workflow/cleansolve_workflow/graph.py packages/workflow/cleansolve_workflow/nodes.py packages/workflow/tests/test_graph.py
git commit -m "feat(workflow): pass uploaded image artifact ids to mock spec"
```

## Task 2: Persist Analysis Artifacts In Local Store

**Files:**

- Modify: `apps/api/tests/test_jobs_api.py`
- Modify: `apps/api/cleansolve_api/artifacts.py`

- [ ] **Step 1: Add failing manifest defaults test**

Append this test to `apps/api/tests/test_jobs_api.py`:

```python
def test_old_manifest_json_defaults_analysis_artifact_fields(tmp_path):
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

    assert manifest.analysis_artifacts == {
        "candidate_spec": [],
        "validation_report": [],
        "correction_plan": [],
    }
    assert manifest.latest_analysis_artifact_ids == {
        "candidate_spec": None,
        "validation_report": None,
        "correction_plan": None,
    }
```

Run:

```bash
python -m pytest apps/api/tests/test_jobs_api.py::test_old_manifest_json_defaults_analysis_artifact_fields -q
```

Expected: fail because `JobManifest` has no analysis fields.

- [ ] **Step 2: Implement analysis artifact models and defaults**

In `apps/api/cleansolve_api/artifacts.py`:

Add type alias:

```python
AnalysisArtifactType = Literal[
    "candidate_spec",
    "validation_report",
    "correction_plan",
]
```

Add constants:

```python
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
```

Add model:

```python
class AnalysisArtifact(BaseModel):
    artifact_id: str
    type: AnalysisArtifactType
    relative_path: str
    size_bytes: int = Field(ge=1)
    sha256: str = Field(min_length=64, max_length=64)
    created_at: str
    source_image_artifact_ids: dict[ImageRole, str]
```

Add default helpers:

```python
def _empty_analysis_artifacts() -> dict[AnalysisArtifactType, list[AnalysisArtifact]]:
    return {artifact_type: [] for artifact_type in ANALYSIS_ARTIFACT_TYPES}


def _empty_latest_analysis_artifact_ids() -> dict[AnalysisArtifactType, str | None]:
    return {artifact_type: None for artifact_type in ANALYSIS_ARTIFACT_TYPES}
```

Add fields to `JobManifest`:

```python
analysis_artifacts: dict[AnalysisArtifactType, list[AnalysisArtifact]] = Field(
    default_factory=_empty_analysis_artifacts
)
latest_analysis_artifact_ids: dict[AnalysisArtifactType, str | None] = Field(
    default_factory=_empty_latest_analysis_artifact_ids
)
```

Extend `job_response()` with:

```python
"analysis_artifacts": {
    artifact_type: [artifact.model_dump(mode="json") for artifact in artifacts]
    for artifact_type, artifacts in manifest.analysis_artifacts.items()
},
"latest_analysis_artifact_ids": manifest.latest_analysis_artifact_ids,
```

Run:

```bash
python -m pytest apps/api/tests/test_jobs_api.py::test_old_manifest_json_defaults_analysis_artifact_fields -q
```

Expected: pass.

- [ ] **Step 3: Add failing store persistence test**

Append this test to `apps/api/tests/test_jobs_api.py`:

```python
def test_store_saves_analysis_outputs_and_updates_manifest(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    source_ids = {
        "problem": "img_problem_123",
        "teacher_solution": "img_teacher_456",
    }

    updated = store.save_analysis_outputs(
        job_id=manifest.job_id,
        status_value="APPROVED",
        revision_attempts=1,
        review_items=[],
        candidate_spec_payload={
            "job_id": manifest.job_id,
            "version": 1,
            "source_images": {
                "problem_image_id": "img_problem_123",
                "teacher_solution_image_id": "img_teacher_456",
            },
        },
        validation_report_payload={
            "report_id": "report_1",
            "passed": True,
            "issues": [],
        },
        correction_plan_payload={
            "job_id": manifest.job_id,
            "revision_attempts": 1,
            "correction_plans": [],
        },
        source_image_artifact_ids=source_ids,
    )

    assert updated.latest_analysis_artifact_ids["candidate_spec"].startswith("spec_")
    assert updated.latest_analysis_artifact_ids["validation_report"].startswith("report_")
    assert updated.latest_analysis_artifact_ids["correction_plan"].startswith("correction_")

    for artifact_type, artifacts in updated.analysis_artifacts.items():
        assert len(artifacts) == 1
        artifact = artifacts[0]
        artifact_path = tmp_path / "jobs" / manifest.job_id / artifact.relative_path
        assert artifact_path.exists()
        assert artifact.size_bytes == len(artifact_path.read_bytes())
        assert artifact.source_image_artifact_ids == source_ids
```

Run:

```bash
python -m pytest apps/api/tests/test_jobs_api.py::test_store_saves_analysis_outputs_and_updates_manifest -q
```

Expected: fail because `save_analysis_outputs` does not exist.

- [ ] **Step 4: Implement analysis output persistence**

In `apps/api/cleansolve_api/artifacts.py`:

Add helper:

```python
def _new_analysis_artifact_id(artifact_type: AnalysisArtifactType) -> str:
    prefix = ANALYSIS_ARTIFACT_PREFIXES[artifact_type]
    return f"{prefix}_{uuid4().hex}"
```

Add method on `LocalArtifactStore`:

```python
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
```

Inside the method:

1. validate job id
2. acquire `self._job_lock(job_id)`
3. load current manifest
4. write three JSON files with `json.dumps(..., ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")`
5. write temp file then replace final file
6. create `AnalysisArtifact` metadata for each payload
7. append metadata to `manifest.analysis_artifacts[artifact_type]`
8. update `manifest.latest_analysis_artifact_ids[artifact_type]`
9. update status, revision_attempts, review_items, updated_at
10. save manifest
11. return updated manifest

Use these directories exactly:

```python
relative_path = (
    f"artifacts/{ANALYSIS_ARTIFACT_DIRECTORIES[artifact_type]}/{artifact_id}.json"
)
```

Run:

```bash
python -m pytest apps/api/tests/test_jobs_api.py::test_store_saves_analysis_outputs_and_updates_manifest -q
```

Expected: pass.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add apps/api/cleansolve_api/artifacts.py apps/api/tests/test_jobs_api.py
git commit -m "feat(api): persist analysis artifacts in job manifest"
```

## Task 3: Analysis Artifact API Routes

**Files:**

- Modify: `apps/api/tests/test_jobs_api.py`
- Modify: `apps/api/cleansolve_api/artifacts.py`
- Modify: `apps/api/cleansolve_api/routes/jobs.py`

- [ ] **Step 1: Add failing API route tests**

Append these tests to `apps/api/tests/test_jobs_api.py`:

```python
def test_analysis_artifact_routes_return_structured_404_before_run():
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]

    for path, artifact_type in [
        ("candidate-spec", "candidate_spec"),
        ("validation-report", "validation_report"),
        ("correction-plan", "correction_plan"),
    ]:
        response = client.get(f"/jobs/{job_id}/{path}")

        assert response.status_code == 404
        assert_error(response, "ANALYSIS_ARTIFACT_NOT_FOUND")
        assert response.json()["detail"]["fields"] == {
            "artifact_type": artifact_type,
        }


def test_run_persists_analysis_artifacts_and_routes_return_latest_payloads():
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)

    job_before_run = client.get(f"/jobs/{job_id}").json()
    expected_source_ids = job_before_run["latest_image_artifact_ids"]
    run_response = client.post(f"/jobs/{job_id}/run")
    run_payload = run_response.json()

    assert run_response.status_code == 200
    assert set(run_payload["analysis_artifacts"]) == {
        "candidate_spec",
        "validation_report",
        "correction_plan",
    }
    assert all(run_payload["latest_analysis_artifact_ids"].values())
    assert len(run_payload["analysis_artifacts"]["candidate_spec"]) == 1
    assert len(run_payload["analysis_artifacts"]["validation_report"]) == 1
    assert len(run_payload["analysis_artifacts"]["correction_plan"]) == 1

    artifacts_response = client.get(f"/jobs/{job_id}/artifacts")
    candidate_response = client.get(f"/jobs/{job_id}/candidate-spec")
    validation_response = client.get(f"/jobs/{job_id}/validation-report")
    correction_response = client.get(f"/jobs/{job_id}/correction-plan")

    assert artifacts_response.status_code == 200
    assert artifacts_response.json()["latest_analysis_artifact_ids"] == run_payload[
        "latest_analysis_artifact_ids"
    ]
    assert candidate_response.status_code == 200
    assert candidate_response.json()["source_images"] == {
        "problem_image_id": expected_source_ids["problem"],
        "teacher_solution_image_id": expected_source_ids["teacher_solution"],
    }
    assert validation_response.status_code == 200
    assert validation_response.json()["passed"] is True
    assert correction_response.status_code == 200
    assert correction_response.json()["job_id"] == job_id
    assert correction_response.json()["revision_attempts"] == 1
    assert isinstance(correction_response.json()["correction_plans"], list)
```

Run:

```bash
python -m pytest apps/api/tests/test_jobs_api.py::test_analysis_artifact_routes_return_structured_404_before_run apps/api/tests/test_jobs_api.py::test_run_persists_analysis_artifacts_and_routes_return_latest_payloads -q
```

Expected: fail because routes and error code do not exist.

- [ ] **Step 2: Add artifact not found error and read helpers**

In `apps/api/cleansolve_api/artifacts.py`, add to `ERROR_MESSAGES`:

```python
"ANALYSIS_ARTIFACT_NOT_FOUND": "분석 artifact를 찾을 수 없습니다.",
```

Add helper:

```python
def analysis_artifact_not_found_error(artifact_type: AnalysisArtifactType) -> HTTPException:
    return _error(
        "ANALYSIS_ARTIFACT_NOT_FOUND",
        status.HTTP_404_NOT_FOUND,
        {"artifact_type": artifact_type},
    )
```

Add `LocalArtifactStore.analysis_artifacts_response(job_id)`:

```python
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
```

Add `LocalArtifactStore.read_latest_analysis_payload(job_id, artifact_type)`:

```python
def read_latest_analysis_payload(
    self,
    job_id: str,
    artifact_type: AnalysisArtifactType,
) -> dict[str, Any]:
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
```

- [ ] **Step 3: Update run route and add GET routes**

In `apps/api/cleansolve_api/routes/jobs.py`:

Update imports to include `AnalysisArtifactType`.

In `run_job`, replace `store.update_after_run(...)` with:

```python
source_image_artifact_ids = {
    "problem": manifest.latest_image_artifact_ids["problem"],
    "teacher_solution": manifest.latest_image_artifact_ids["teacher_solution"],
}
state = run_mock_workflow(
    job_id=job_id,
    source_image_artifact_ids=source_image_artifact_ids,
)
updated_manifest = store.save_analysis_outputs(
    job_id=job_id,
    status_value=state["status"],
    revision_attempts=state["revision_attempts"],
    review_items=list(state.get("review_items", [])),
    candidate_spec_payload=state["candidate_spec"].model_dump(mode="json"),
    validation_report_payload=state["validation_reports"][-1].model_dump(mode="json"),
    correction_plan_payload={
        "job_id": job_id,
        "revision_attempts": state["revision_attempts"],
        "correction_plans": state.get("correction_plans", []),
    },
    source_image_artifact_ids=source_image_artifact_ids,
)
```

Add routes:

```python
@router.get("/{job_id}/artifacts")
def get_analysis_artifacts(job_id: str) -> dict[str, object]:
    return _store().analysis_artifacts_response(job_id)


@router.get("/{job_id}/candidate-spec")
def get_candidate_spec(job_id: str) -> dict[str, object]:
    return _store().read_latest_analysis_payload(job_id, "candidate_spec")


@router.get("/{job_id}/validation-report")
def get_validation_report(job_id: str) -> dict[str, object]:
    return _store().read_latest_analysis_payload(job_id, "validation_report")


@router.get("/{job_id}/correction-plan")
def get_correction_plan(job_id: str) -> dict[str, object]:
    return _store().read_latest_analysis_payload(job_id, "correction_plan")
```

Run:

```bash
python -m pytest apps/api/tests/test_jobs_api.py -q
```

Expected: all job API tests pass.

- [ ] **Step 4: Commit Task 3**

Run:

```bash
git add apps/api/cleansolve_api/artifacts.py apps/api/cleansolve_api/routes/jobs.py apps/api/tests/test_jobs_api.py
git commit -m "feat(api): expose candidate spec pipeline artifacts"
```

## Task 4: Verification, Review, Push

**Files:**

- No production changes unless review finds defects.

- [ ] **Step 1: Run full test suite**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run diff checks**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 3: Run Superpowers reviews**

Dispatch spec compliance and code quality reviewers with:

- Design spec: `docs/superpowers/specs/2026-06-16-candidate-spec-pipeline-design.md`
- Plan: `docs/superpowers/plans/2026-06-16-candidate-spec-pipeline.md`
- Changed files from this milestone.

Fix Critical and Important findings, then re-run relevant tests.

- [ ] **Step 4: Push branch**

Run:

```bash
git status --short --branch
git push origin feat/mvp-roadmap
```

Expected: branch pushes to `origin/feat/mvp-roadmap`.

## Plan Self-Review

- Spec coverage:
  - Uploaded image artifact ids flow into mock spec: Task 1 and Task 3.
  - Candidate spec, validation report, correction plan storage: Task 2 and Task 3.
  - Manifest metadata and latest ids: Task 2.
  - API retrieval endpoints: Task 3.
  - Backward-compatible manifest defaults: Task 2.
  - No OpenAI/web/renderer/export scope creep: Files section and tasks.
- Placeholder scan:
  - No placeholder markers or copy-forward instructions.
- Type consistency:
  - `AnalysisArtifactType`, `AnalysisArtifact`, `analysis_artifacts`, `latest_analysis_artifact_ids`, and route names match the design spec.
