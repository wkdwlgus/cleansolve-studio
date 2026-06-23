# ReAct Review/Correction Workflow Contract 상세 설계

## 목적

이번 milestone의 목적은 GPT-5.5 기반 ReAct review/correction loop를 바로 production AI 호출로 붙이는 것이 아니라, 먼저 workflow 계약을 고정하는 것이다.

이 계약은 다음 PR들이 같은 상태, tool, eval gate, progress event를 재사용하게 만든다.

1. GPT-5.5 ReAct review/correction agent 구현.
2. job progress SSE stream 구현.
3. web progress UI 구현.
4. render-to-source validation과 visual diff eval gate 구현.
5. block-level handwriting asset regeneration 구현.

이번 milestone은 `SoT.md`의 10.5, 11.4, 12.4를 직접 반영한다.

## 현재 코드 기준

현재 workflow는 `packages/workflow/cleansolve_workflow` 아래 LangGraph 기반 prototype이다.

- `graph.py`는 `load_style_preset -> analyze_sources -> validate_spec -> render_preview -> inspect_render -> plan_correction -> apply_correction -> validate_spec` 흐름을 갖는다.
- `nodes.py`의 `inspect_render`와 `plan_correction`은 freehand dimension endpoint mismatch fixture를 deterministic하게 검사하고 spec patch를 만든다.
- `WorkflowState`는 `status_history`, `validation_reports`, `correction_plans`, `revision_attempts`, `rendered_preview`, `inspection_issue`를 가진다.
- API `POST /jobs/{job_id}/run`은 workflow 최종 상태만 저장한다.
- 아직 job progress event artifact, ReAct tool decision artifact, eval score artifact, SSE endpoint는 없다.

## 이번 milestone 범위

이번 milestone에서 구현할 범위는 mock/fixture 기반 ReAct workflow contract다.

1. ReAct review/correction 상태 모델을 추가한다.
2. 허용 tool allowlist와 tool decision schema를 추가한다.
3. eval score와 approval gate schema를 추가한다.
4. progress event schema와 deterministic event log를 추가한다.
5. 기존 workflow prototype이 이 contract를 사용해 기존 endpoint mismatch 자동 수정 경로를 실행하게 한다.
6. API는 run 결과에 progress event artifact와 review/correction artifact를 저장할 수 있게 한다.
7. 테스트는 실제 OpenAI 호출 없이 mock ReAct planner로 실행한다.
8. 문서는 이번 contract와 다음 SSE milestone의 연결 방식을 설명한다.

## 이번 milestone 제외 범위

다음 항목은 이번 milestone에서 구현하지 않는다.

1. 실제 GPT-5.5 ReAct model 호출.
2. 실제 `gpt-image-2` 또는 이미지 생성/편집 API 호출.
3. `GET /jobs/{job_id}/events` SSE endpoint.
4. web progress UI.
5. 실제 pixel 기반 visual diff 계산.
6. 실제 style similarity model.
7. PDF export.
8. full image regeneration.
9. raw model output 저장.
10. chain-of-thought, hidden reasoning, raw tool observation 노출.

이번 milestone은 위 항목이 후속 milestone에서 들어올 수 있도록 contract를 고정하지만, 동작 구현은 mock/deterministic fixture 수준으로 제한한다.

## 용어

### ReAct review/correction loop

렌더 결과, candidate spec, source image, style preset, validation report, 이전 correction history, eval score를 보고 다음 tool을 선택하는 반복 루프다.

이번 milestone에서는 실제 LLM이 아니라 deterministic mock planner가 tool을 선택한다.

### Tool decision

한 attempt에서 agent가 선택한 다음 행동이다. 예를 들어 `inspect_layout`, `patch_candidate_spec`, `rerender`, `mark_approved`, `escalate_hitl` 중 하나다.

### Eval gate

자동 승인 전에 통과해야 하는 점수와 상태 조건이다. 모델의 주관적 승인만으로 job을 승인하지 않는다.

### Progress event

사용자에게 노출 가능한 allowlist 이벤트다. 내부 reasoning이 아니라 현재 phase, status, 짧은 한국어 message, attempt, score, next_action만 포함한다.

## 파일 구조

이번 milestone에서 추가/수정할 파일은 다음으로 제한한다.

### 추가 파일

- `packages/workflow/cleansolve_workflow/review_contract.py`
- `packages/workflow/cleansolve_workflow/review_tools.py`
- `packages/workflow/tests/test_review_contract.py`
- `packages/workflow/tests/test_react_review_workflow.py`

### 수정 파일

- `packages/workflow/cleansolve_workflow/state.py`
- `packages/workflow/cleansolve_workflow/nodes.py`
- `packages/workflow/cleansolve_workflow/graph.py`
- `packages/workflow/cleansolve_workflow/__init__.py`
- `apps/api/cleansolve_api/artifacts.py`
- `apps/api/cleansolve_api/routes/jobs.py`
- `apps/api/tests/test_jobs_api.py`
- `packages/harness/tests/test_e2e.py`
- `docs/product/mvp-roadmap.md`
- `docs/product/mvp-release-checklist.md`

위 목록 밖 파일은 구현 중 필요해도 먼저 설계 변경을 문서화해야 한다.

## Public API

`packages/workflow/cleansolve_workflow/review_contract.py`는 아래 public API를 제공한다.

```python
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ReviewToolName = Literal[
    "inspect_content",
    "inspect_layout",
    "inspect_style",
    "compute_visual_diff",
    "patch_candidate_spec",
    "request_handwriting_asset",
    "rerender",
    "mark_approved",
    "escalate_hitl",
]

ReviewPhase = Literal[
    "analysis",
    "validation",
    "render",
    "review_and_correct",
    "hitl",
    "approval",
    "export",
    "failed",
]

ProgressStatus = Literal[
    "CREATED",
    "STYLE_PRESET_LOADED",
    "SPEC_EXTRACTED",
    "SPEC_VALIDATING",
    "RENDERING",
    "RENDERED",
    "INSPECTING_CONTENT",
    "INSPECTING_LAYOUT",
    "INSPECTING_STYLE",
    "COMPUTING_VISUAL_DIFF",
    "CORRECTION_PLANNING",
    "PATCHING_SPEC",
    "REQUESTING_HANDWRITING_ASSET",
    "RE_RENDERING",
    "RE_INSPECTING",
    "APPROVED",
    "NEEDS_REVIEW",
    "REVISION_REQUIRED",
    "FAILED",
]

NextAction = Literal[
    "continue",
    "content_check",
    "layout_check",
    "style_check",
    "visual_diff_check",
    "spec_patch",
    "handwriting_asset",
    "rerender",
    "approve",
    "hitl",
    "fail",
]
```

### ReviewScores

```python
class ReviewScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_consistency: float = Field(ge=0, le=1)
    layout_alignment: float = Field(ge=0, le=1)
    style_similarity: float = Field(ge=0, le=1)
    visual_diff: float = Field(ge=0, le=1)
```

의미:

- `content_consistency`: 선생님 풀이 내용, 수식, 풀이 순서와 candidate spec/render가 맞는 정도다. 높을수록 좋다.
- `layout_alignment`: bbox, anchor, 라벨, 치수선 endpoint가 원본 문제 위에서 맞는 정도다. 높을수록 좋다.
- `style_similarity`: 한글, 숫자, 수식, 선이 system style preset과 같은 계열처럼 보이는 정도다. 높을수록 좋다.
- `visual_diff`: render 결과와 목표 이미지 사이 차이다. 낮을수록 좋다.

이번 milestone의 mock score는 deterministic fixture 값만 사용한다.

### ApprovalGate

```python
class ApprovalGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_valid: bool
    content_consistency_threshold: float = Field(default=0.9, ge=0, le=1)
    layout_alignment_threshold: float = Field(default=0.85, ge=0, le=1)
    style_similarity_threshold: float = Field(default=0.7, ge=0, le=1)
    visual_diff_threshold: float = Field(default=0.25, ge=0, le=1)
    visible_review_item_budget: int = Field(default=0, ge=0)
    allowed_max_error_severity: Literal["none", "low", "medium", "high"] = "low"
```

기본 gate 통과 조건은 정확히 아래와 같다.

```text
contract_valid is True
content_consistency >= 0.9
layout_alignment >= 0.85
style_similarity >= 0.7
visual_diff <= 0.25
visible_review_item_count <= 0
max_error_severity in {"none", "low"}
```

이번 milestone에서 threshold는 코드 상수로 둔다. 환경변수로 조정하지 않는다.

### GateResult

```python
class GateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    failed_reasons: list[str]
    scores: ReviewScores
    contract_valid: bool
    visible_review_item_count: int = Field(ge=0)
    max_error_severity: Literal["none", "low", "medium", "high"]
```

`failed_reasons`의 allowed value는 아래 문자열만 사용한다.

```text
contract_invalid
content_consistency_below_threshold
layout_alignment_below_threshold
style_similarity_below_threshold
visual_diff_above_threshold
visible_review_item_budget_exceeded
max_error_severity_exceeded
```

### ReviewIssue

```python
class ReviewIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: str
    type: str
    severity: Literal["low", "medium", "high"]
    element_id: str | None = None
    message: str
    auto_correctable: bool
    evidence: dict[str, Any] = Field(default_factory=dict)
```

`message`는 내부 artifact에는 저장하지만 progress event에는 직접 넣지 않는다. 사용자 노출 문구는 progress event의 allowlist message만 사용한다.

### ToolDecision

```python
class ToolDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt: int = Field(ge=0)
    tool_name: ReviewToolName
    reason_code: str
    target_element_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
```

`reason_code` allowed value는 아래 문자열만 사용한다.

```text
initial_content_inspection
initial_layout_inspection
initial_style_inspection
initial_visual_diff
dimension_endpoint_mismatch
gate_passed
revision_budget_exceeded
repeated_element_patch
no_score_improvement
low_confidence
unsupported_tool_request
requires_handwriting_asset
validation_failed
```

### CorrectionAction

```python
class CorrectionAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    type: Literal["spec_patch", "handwriting_asset_request", "rerender", "hitl", "approve"]
    element_id: str | None = None
    patch: dict[str, Any] = Field(default_factory=dict)
    asset_request: dict[str, Any] = Field(default_factory=dict)
```

이번 milestone에서 실제로 실행 가능한 `CorrectionAction.type`은 `spec_patch`, `rerender`, `hitl`, `approve`다.

`handwriting_asset_request`는 contract와 event에만 남긴다. 실제 image API 호출은 하지 않는다.

### ReviewAttempt

```python
class ReviewAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt: int = Field(ge=0)
    tool_decisions: list[ToolDecision]
    issues: list[ReviewIssue]
    actions: list[CorrectionAction]
    scores_before: ReviewScores | None = None
    scores_after: ReviewScores | None = None
    gate_result: GateResult | None = None
```

한 attempt에는 여러 inspection decision이 들어갈 수 있지만, mutation action은 최대 1개만 허용한다.

mutation action은 아래 type이다.

- `spec_patch`
- `handwriting_asset_request`
- `rerender`
- `hitl`
- `approve`

### ProgressEvent

```python
class ProgressEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    job_id: str
    sequence: int = Field(ge=0)
    phase: ReviewPhase
    status: ProgressStatus
    message: str
    attempt: int = Field(ge=0)
    max_attempts: int = Field(ge=0)
    scores: ReviewScores | None = None
    next_action: NextAction
    created_at: str
```

`event_id`는 deterministic 테스트에서는 `evt_0001`, `evt_0002`처럼 생성한다. production에서는 UUID를 사용할 수 있지만 이번 milestone 구현은 deterministic sequence id를 사용한다.

`created_at`은 UTC ISO-8601 문자열이다. 테스트에서는 정규식으로 형태만 검증한다.

### ProgressEvent message allowlist

`message`는 아래 한국어 문자열 중 하나만 사용할 수 있다.

```text
작업을 시작했습니다.
기본 손글씨 스타일을 불러왔습니다.
원본 문제와 선생님 손풀이를 분석하고 있습니다.
candidate spec 계약을 검증하고 있습니다.
deterministic renderer로 preview를 만들고 있습니다.
렌더 결과의 풀이 내용을 확인하고 있습니다.
렌더 결과의 위치와 치수선 정합성을 확인하고 있습니다.
렌더 결과의 손글씨 스타일 일관성을 확인하고 있습니다.
렌더 결과의 시각적 차이를 계산하고 있습니다.
자동 수정 계획을 세우고 있습니다.
candidate spec patch를 적용하고 있습니다.
특정 손글씨 블록 asset 재생성이 필요합니다.
수정된 spec으로 preview를 다시 렌더링하고 있습니다.
자동 승인 기준을 통과했습니다.
사용자 검수가 필요합니다.
자동 수정 한도에 도달했습니다.
작업이 실패했습니다.
```

코드는 이 allowlist 밖 message를 만들지 않는다.

## Tool allowlist 계약

`packages/workflow/cleansolve_workflow/review_tools.py`는 tool registry를 제공한다.

```python
ALLOWED_REVIEW_TOOLS: tuple[ReviewToolName, ...] = (
    "inspect_content",
    "inspect_layout",
    "inspect_style",
    "compute_visual_diff",
    "patch_candidate_spec",
    "request_handwriting_asset",
    "rerender",
    "mark_approved",
    "escalate_hitl",
)
```

`ensure_allowed_tool(tool_name: str) -> ReviewToolName`은 allowlist 밖 문자열이면 `ReviewToolRejected`를 발생시킨다.

```python
class ReviewToolRejected(ValueError):
    pass
```

이번 milestone에서 tool 실행 함수는 아래 역할만 한다.

| tool | 이번 milestone 동작 |
| --- | --- |
| `inspect_content` | mock issue 없음, `content_consistency=0.95` |
| `inspect_layout` | 기존 freehand dimension endpoint mismatch를 감지 |
| `inspect_style` | mock style issue 없음, `style_similarity=0.78` |
| `compute_visual_diff` | mock `visual_diff=0.18` |
| `patch_candidate_spec` | 허용된 geometry patch만 적용 |
| `request_handwriting_asset` | 실행하지 않고 `CorrectionAction(type="handwriting_asset_request")` 기록만 허용 |
| `rerender` | deterministic renderer 재실행 |
| `mark_approved` | gate 통과 시에만 status `APPROVED` |
| `escalate_hitl` | status `REVISION_REQUIRED` 또는 `NEEDS_REVIEW` |

## Mock planner 계약

이번 milestone의 planner는 실제 GPT-5.5가 아니다. deterministic function으로 구현한다.

함수명:

```python
def plan_next_review_action(state: WorkflowState) -> ToolDecision:
    raise NotImplementedError("implementation must follow the output rules below")
```

입력은 `WorkflowState`다.

출력 규칙:

1. `candidate_spec`이 없으면 `tool_name="escalate_hitl"`, `reason_code="validation_failed"`.
2. 마지막 validation report가 없거나 실패했으면 `tool_name="escalate_hitl"`, `reason_code="validation_failed"`.
3. current attempt에서 content inspection이 없으면 `inspect_content`.
4. current attempt에서 layout inspection이 없으면 `inspect_layout`.
5. current attempt에서 style inspection이 없으면 `inspect_style`.
6. current attempt에서 visual diff가 없으면 `compute_visual_diff`.
7. gate가 통과하면 `mark_approved`, `reason_code="gate_passed"`.
8. layout issue가 auto-correctable이고 revision budget이 남아 있으면 `patch_candidate_spec`, `reason_code="dimension_endpoint_mismatch"`.
9. 같은 `element_id`에 같은 patch를 2회 연속 시도했으면 `escalate_hitl`, `reason_code="repeated_element_patch"`.
10. score 개선이 2회 연속 없으면 `escalate_hitl`, `reason_code="no_score_improvement"`.
11. revision budget이 없으면 `escalate_hitl`, `reason_code="revision_budget_exceeded"`.
12. 위 조건에 모두 해당하지 않으면 `escalate_hitl`, `reason_code="low_confidence"`.

이번 milestone의 기존 fixture 기준 정상 경로는 아래 순서여야 한다.

```text
CREATED
STYLE_PRESET_LOADED
SPEC_EXTRACTED
SPEC_VALIDATING
RENDERING
RENDERED
INSPECTING_CONTENT
INSPECTING_LAYOUT
INSPECTING_STYLE
COMPUTING_VISUAL_DIFF
CORRECTION_PLANNING
PATCHING_SPEC
RE_RENDERING
RENDERED
SPEC_REVALIDATING
INSPECTING_CONTENT
INSPECTING_LAYOUT
INSPECTING_STYLE
COMPUTING_VISUAL_DIFF
APPROVED
```

기존 `status_history`는 위 status를 반영하도록 갱신한다. 기존 테스트가 기대하던 `AUTO_REVISING`, `RE_INSPECTING`은 새 contract에서는 더 구체적인 `PATCHING_SPEC`, `RE_RENDERING`, inspection status로 대체한다.

## Score fixture 계약

이번 milestone의 deterministic score는 아래 표를 따른다.

### endpoint mismatch가 남아 있는 경우

```json
{
  "content_consistency": 0.95,
  "layout_alignment": 0.6,
  "style_similarity": 0.78,
  "visual_diff": 0.18
}
```

Gate 결과:

- `layout_alignment_below_threshold` 때문에 fail.
- `max_error_severity`는 `high`.

### endpoint mismatch가 수정된 경우

```json
{
  "content_consistency": 0.95,
  "layout_alignment": 0.9,
  "style_similarity": 0.78,
  "visual_diff": 0.18
}
```

Gate 결과:

- visible review item이 없고 validation이 통과하면 pass.
- `max_error_severity`는 `none`.

### validation failure가 있는 경우

```json
{
  "content_consistency": 0.0,
  "layout_alignment": 0.0,
  "style_similarity": 0.0,
  "visual_diff": 1.0
}
```

Gate 결과:

- `contract_invalid`.
- `max_error_severity`는 `high`.
- status는 `REVISION_REQUIRED`.

## WorkflowState 확장

`WorkflowState`에 아래 optional fields를 추가한다.

```python
review_attempts: list[Any]
progress_events: list[Any]
latest_scores: Any
latest_gate_result: Any
review_tool_decisions: list[Any]
review_event_sequence: int
```

TypedDict에는 `Any`를 사용해 circular import를 피한다. 실제 값은 `review_contract.py`의 Pydantic model을 사용한다.

## Progress event 생성 규칙

Progress event는 workflow 내부 helper로만 생성한다.

함수명:

```python
def append_progress_event(
    state: WorkflowState,
    *,
    phase: ReviewPhase,
    status: ProgressStatus,
    message: str,
    next_action: NextAction,
    scores: ReviewScores | None = None,
) -> None:
    raise NotImplementedError("implementation must follow the rules below")
```

규칙:

1. `sequence`는 `state["review_event_sequence"]`에서 시작하고 event마다 1 증가한다.
2. 첫 event sequence는 0이다.
3. `event_id`는 `evt_{sequence:04d}`다.
4. `job_id`는 `state["job_id"]`다.
5. `attempt`는 `state["revision_attempts"]`다.
6. `max_attempts`는 `state["max_revision_attempts"]`다.
7. `created_at`은 UTC ISO-8601 문자열이다.
8. `message`가 allowlist 밖이면 `ValueError`를 발생시킨다.
9. event는 `state.setdefault("progress_events", [])`에 `ProgressEvent` model instance로 append한다.

## Artifact 저장 계약

`apps/api/cleansolve_api/artifacts.py`의 `AnalysisArtifactType`에 아래 값을 추가한다.

```python
"review_correction"
"progress_events"
```

artifact prefix와 directory:

```python
"review_correction": "review"
"progress_events": "events"
```

```python
"review_correction": "reviews"
"progress_events": "events"
```

`LocalArtifactStore.save_analysis_outputs`는 아래 payload를 optional로 받는다.

```python
review_correction_payload: dict[str, Any] | None = None
progress_events_payload: dict[str, Any] | None = None
```

저장 payload 형식:

### review_correction artifact

```json
{
  "job_id": "job_123",
  "review_attempts": [],
  "tool_decisions": [],
  "latest_gate_result": {},
  "revision_attempts": 1
}
```

### progress_events artifact

```json
{
  "job_id": "job_123",
  "events": []
}
```

API response의 `latest_analysis_artifact_ids`에는 새 artifact id 두 개가 포함되어야 한다.

## API 계약

이번 milestone은 SSE endpoint를 추가하지 않는다.

대신 기존 artifact 조회 endpoint로 새 artifact를 볼 수 있어야 한다.

기존:

```text
GET /jobs/{job_id}/artifacts
```

기존 generic read endpoint:

```text
GET /jobs/{job_id}/correction-plan
```

이번 milestone에서 추가할 endpoint:

```text
GET /jobs/{job_id}/review-correction
GET /jobs/{job_id}/progress-events
```

응답:

- `GET /review-correction`은 latest `review_correction` payload를 반환한다.
- `GET /progress-events`는 latest `progress_events` payload를 반환한다.
- artifact가 없으면 기존 `analysis_artifact_not_found_error`와 같은 형식으로 404를 반환한다.

SSE endpoint `GET /jobs/{job_id}/events`는 다음 milestone에서 구현한다.

## 보안 및 노출 정책

Progress event에는 아래 항목을 절대 포함하지 않는다.

1. raw model output.
2. raw prompt.
3. chain-of-thought.
4. hidden reasoning summary.
5. raw tool observation.
6. source image path.
7. OpenAI API key.
8. unfiltered correction note.

`ToolDecision.arguments`와 `ReviewIssue.evidence`는 artifact에는 저장 가능하지만, progress event로 직접 복사하지 않는다.

## 기존 workflow와의 연결

기존 node는 아래처럼 바꾼다.

| 기존 node | 변경 |
| --- | --- |
| `load_style_preset` | status와 progress event `STYLE_PRESET_LOADED` 기록 |
| `analyze_sources` | progress event `SPEC_EXTRACTED` 기록 |
| `validate_spec` | validation 결과와 progress event `SPEC_VALIDATING` 또는 `SPEC_REVALIDATING` 기록 |
| `render_preview` | `RENDERING` event 후 render 실행, `RENDERED` event 기록 |
| `inspect_render` | 기존 단일 inspection 대신 ReAct inspection tools를 순서대로 실행 |
| `plan_correction` | `ToolDecision`과 `CorrectionAction` 생성 |
| `apply_correction` | `PATCHING_SPEC`, `RE_RENDERING`, `RENDERED` 기록 |
| `decide_human_review` | gate 통과와 visible review item budget 확인 후 `APPROVED` 또는 `NEEDS_REVIEW` |
| `require_revision` | `REVISION_REQUIRED` event 기록 |

`inspect_render`, `plan_correction`, `apply_correction` 함수명은 유지할 수 있다. 내부 동작만 contract model을 사용한다.

## Routing 계약

LangGraph routing은 아래 조건을 따른다.

### validate_spec 이후

```python
if latest validation report passed:
    return "render_preview"
return "require_revision"
```

### inspect_render 이후

```python
if latest_gate_result.passed:
    return "decide_human_review"
if latest tool decision is patch_candidate_spec:
    return "plan_correction"
if latest tool decision is request_handwriting_asset:
    return "require_revision"
if latest tool decision is escalate_hitl:
    return "require_revision"
return "require_revision"
```

### plan_correction 이후

`plan_correction`은 mutation action이 `spec_patch`면 `apply_correction`으로 이어진다.

이번 milestone에서 `handwriting_asset_request`는 실행하지 않고 `require_revision`으로 보낸다.

## Attempt와 budget

`revision_attempts`는 mutation action이 실제 candidate spec을 변경한 뒤 1 증가한다.

즉 inspection만 수행한 attempt는 `revision_attempts`를 증가시키지 않는다.

`max_revision_attempts`의 기본값은 기존과 동일하게 2다.

`max_revision_attempts=0`이면 layout mismatch를 발견하더라도 `patch_candidate_spec`을 실행하지 않고 `REVISION_REQUIRED`로 간다.

## 반복 patch 중단 규칙

같은 element에 같은 patch를 2회 연속 요청하면 `repeated_element_patch`로 HITL 전환한다.

동일 patch 판단:

```text
action.type == "spec_patch"
action.element_id 같음
action.patch JSON canonical dump 결과 같음
```

canonical dump는 `json.dumps(value, sort_keys=True, separators=(",", ":"))`를 사용한다.

## score 개선 중단 규칙

이번 milestone의 mock score에서는 score 개선 중단이 정상 경로에서 발생하지 않는다.

그래도 helper는 구현한다.

`has_score_improved(previous: ReviewScores, current: ReviewScores) -> bool` 규칙:

```text
content_consistency 증가 또는
layout_alignment 증가 또는
style_similarity 증가 또는
visual_diff 감소
```

2회 연속 improvement가 없으면 `no_score_improvement`로 HITL 전환한다.

이번 milestone tests는 helper 단위 테스트로만 검증한다.

## 문서 업데이트

`docs/product/mvp-roadmap.md`를 업데이트한다.

- `Workflow orchestrator` 메모에 ReAct contract/progress event artifact가 추가됐음을 반영한다.
- 다음 추천 작업에서 renderer calibration은 완료된 항목으로 내리고, 다음 후보는 `job progress SSE stream과 web progress UI`로 둔다.

`docs/product/mvp-release-checklist.md`를 업데이트한다.

- 아직 production ready가 아닌 이유에서 “GPT-5.5 기반 ReAct review/correction agent와 score 기반 eval gate가 없다”를 “contract와 mock path는 있으나 실제 GPT-5.5 agent/eval model은 없다”로 바꾼다.
- 남은 gap에서 `GPT-5.5 기반 ReAct review/correction workflow`를 `실제 GPT-5.5 기반 ReAct planner 연결`로 바꾼다.
- `job progress SSE stream과 web progress UI`는 그대로 남긴다.

## 테스트 계약

### `packages/workflow/tests/test_review_contract.py`

필수 테스트:

1. `test_progress_event_rejects_unapproved_message`
   - allowlist 밖 message로 `append_progress_event` 호출 시 `ValueError`.
2. `test_progress_event_sequence_is_deterministic`
   - sequence 0, 1.
   - event id `evt_0000`, `evt_0001`.
3. `test_gate_passes_when_all_thresholds_met`
   - approved score fixture로 pass.
4. `test_gate_fails_for_layout_score`
   - mismatch fixture로 `layout_alignment_below_threshold`.
5. `test_gate_fails_for_visual_diff`
   - `visual_diff=0.26`이면 fail.
6. `test_review_tool_allowlist_rejects_unknown_tool`
   - unknown tool은 `ReviewToolRejected`.
7. `test_score_improvement_helper_detects_improvement`
   - layout 증가와 visual diff 감소를 improvement로 본다.

### `packages/workflow/tests/test_react_review_workflow.py`

필수 테스트:

1. `test_react_workflow_auto_revises_with_progress_events`
   - final status `APPROVED`.
   - progress events status sequence가 설계의 정상 경로와 일치.
   - `review_attempts`가 2개 이상.
   - 첫 gate fail reason에 `layout_alignment_below_threshold`.
   - 마지막 gate passed.
2. `test_react_workflow_records_tool_decisions`
   - `inspect_content`, `inspect_layout`, `inspect_style`, `compute_visual_diff`, `patch_candidate_spec`, `mark_approved` decision이 기록됨.
3. `test_react_workflow_zero_revision_budget_escalates`
   - `max_revision_attempts=0`.
   - status `REVISION_REQUIRED`.
   - `progress_events` 마지막 status `REVISION_REQUIRED`.
   - no spec patch applied.
4. `test_react_workflow_rejects_repeated_unhelpful_patch`
   - `correction_patch_override={"geometry.label_anchor": [300, 620]}`.
   - status `REVISION_REQUIRED`.
   - reason_code가 `repeated_element_patch` 또는 `revision_budget_exceeded`.
5. `test_react_workflow_validation_failure_has_contract_invalid_gate`
   - invalid candidate spec override.
   - status `REVISION_REQUIRED`.
   - latest gate failed reason에 `contract_invalid`.

### `apps/api/tests/test_jobs_api.py`

필수 테스트:

1. `test_run_job_persists_review_correction_and_progress_events`
   - run 후 `latest_analysis_artifact_ids`에 `review_correction`, `progress_events`.
   - `GET /jobs/{job_id}/review-correction`이 payload 반환.
   - `GET /jobs/{job_id}/progress-events`가 event list 반환.
   - event message가 allowlist 값.
2. `test_progress_events_endpoint_returns_404_before_run`
   - job 생성 직후 progress events 조회는 404.
3. 기존 run/export/spec patch tests는 통과해야 한다.

### `packages/harness/tests/test_e2e.py`

필수 업데이트:

- E2E run artifact metric에 progress event count를 추가한다.
- fixture happy path에서 progress event count는 1 이상이어야 한다.

## Acceptance Criteria

이번 milestone 완료 기준:

1. `review_contract.py`가 ReAct tool, eval gate, progress event schema를 제공한다.
2. 기존 workflow happy path가 review contract model을 사용해 endpoint mismatch를 자동 수정한다.
3. workflow state에 `review_attempts`, `tool_decisions`, `latest_gate_result`, `progress_events`가 남는다.
4. API run이 `review_correction`과 `progress_events` artifact를 저장한다.
5. `GET /jobs/{job_id}/review-correction`과 `GET /jobs/{job_id}/progress-events`가 latest artifact를 반환한다.
6. progress event는 allowlist message만 포함한다.
7. raw model output, prompt, hidden reasoning, API key, source image path가 progress event에 포함되지 않는다.
8. 실제 OpenAI 호출 없이 모든 unit/E2E 테스트가 통과한다.
9. `docs/product/mvp-roadmap.md`와 `docs/product/mvp-release-checklist.md`가 최신 상태를 반영한다.

## Verification Commands

구현 후 반드시 실행한다.

```bash
pytest packages/workflow/tests -q
pytest apps/api/tests packages/harness/tests -q
CLEANSOLVE_API_ENV_FILE=/tmp/cleansolve-no-env python -m pytest apps/api/tests packages/ai/tests packages/harness/tests packages/spec/tests packages/workflow/tests -q
git diff --check
```

웹 코드는 이번 milestone에서 수정하지 않으므로 `npm --prefix apps/web test`는 필수 검증이 아니다.

## 다음 milestone

이번 milestone 다음 추천 작업은 `job progress SSE stream과 web progress UI`다.

다음 milestone은 이번 milestone의 `ProgressEvent` artifact를 그대로 사용한다.

다음 milestone에서 추가할 것:

1. `GET /jobs/{job_id}/events` SSE endpoint.
2. run 중 event append/storage strategy.
3. web client `EventSource` 또는 testable SSE adapter.
4. web progress panel.
5. Playwright smoke test.

이번 milestone에서 SSE endpoint를 만들지 않는 이유는 ReAct workflow/event contract가 먼저 고정되어야 UX가 재작업 없이 의미 있는 상태를 보여줄 수 있기 때문이다.
