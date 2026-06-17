# M5 Spec Patch & Deterministic Re-render 구현 plan

작성일: 2026-06-17

상세 설계: `docs/superpowers/specs/2026-06-17-spec-patch-rerender-design.md`

## 목표

M5는 웹에서 제한된 candidate spec 수정을 저장하고, 수정된 spec을 deterministic renderer로 다시 렌더링해 SVG preview artifact로 보존/조회하는 milestone이다. OpenAI API는 사용하지 않는다.

## 공통 규칙

- README류 문서는 한국어로 작성한다.
- 새 production code는 먼저 실패하는 테스트를 만든 뒤 구현한다.
- 구현은 상세 설계의 allowlist, error code, response shape를 벗어나지 않는다.
- M5에서 element 추가/삭제, freehand stroke point 편집, generic JSON Patch, 최종 export, OpenAI adapter는 구현하지 않는다.
- 각 task 완료 후 spec compliance review와 code/UI quality review를 수행한다.

## Task 1. API patch validator와 request model

파일:

- `apps/api/cleansolve_api/spec_patch.py`
- `apps/api/tests/test_spec_patch.py`

구현:

1. `SpecPatchRequest` Pydantic model을 정의한다.
2. `operation`은 `"update_element"`만 허용한다.
3. `apply_spec_patch(spec: CandidateSpec, request: SpecPatchRequest) -> CandidateSpec`를 구현한다.
4. 함수는 입력 spec을 mutation하지 않고 deep copy를 반환한다.
5. `client_spec_version` 검사는 route가 담당하므로 이 함수에서는 수행하지 않는다.
6. target element가 없으면 patch rejected error를 발생시킬 수 있는 typed exception을 던진다.
7. primitive별 path allowlist는 상세 설계 5장의 표를 그대로 따른다.
8. point 값은 finite number 2개 배열이고 page bbox 내부여야 한다.
9. bbox 값은 finite number 4개 배열이고 width/height가 양수이며 page 내부여야 한다.
10. control point list는 길이 1 또는 2이며 모든 point가 page 내부여야 한다.
11. string 값은 non-empty string이어야 한다.
12. `freehand_dimension_marker.visible_strokes` 편집은 반드시 거부한다.
13. patch 성공 시 spec version을 1 증가시키고 수정 element `revision_history`에 `user_patch_v{result_spec_version}` 기록을 append한다.

테스트:

- allowed dimension target anchor patch가 version과 revision history를 갱신한다.
- 원본 spec object는 mutation되지 않는다.
- disallowed path는 `path_not_allowed` reason으로 거부된다.
- page 밖 point는 `invalid_point` reason으로 거부된다.
- 빈 label/color/text는 거부된다.
- unsupported operation은 거부된다.

검증:

```bash
python -m pytest apps/api/tests/test_spec_patch.py -q
```

## Task 2. Artifact store 확장

파일:

- `apps/api/cleansolve_api/artifacts.py`
- `apps/api/tests/test_jobs_api.py` 또는 `apps/api/tests/test_artifacts.py`

구현:

1. `RenderArtifact` model을 추가한다.
2. `JobManifest`에 `render_artifacts: list[RenderArtifact] = []`, `latest_render_artifact_id: str | None = None`을 추가한다.
3. 기존 manifest를 읽을 때 위 필드가 없어도 default로 동작하게 한다.
4. `save_spec_patch_outputs`를 추가해 candidate spec과 validation report artifact만 append한다.
5. `save_spec_patch_outputs`는 correction plan artifact와 latest id를 변경하지 않는다.
6. `save_render_artifact`를 추가해 `artifacts/renders/{artifact_id}.svg`에 UTF-8 SVG를 저장한다.
7. render artifact id prefix는 `render_`를 사용한다.
8. render artifact에는 size, sha256, created_at, candidate_spec_artifact_id, source_image_artifact_ids를 기록한다.
9. `rendered_preview_response`를 추가해 최신 render artifact metadata와 SVG 문자열을 반환한다.

테스트:

- old manifest JSON에 render fields가 없어도 default가 적용된다.
- spec patch 저장은 candidate spec/report latest id만 바꾸고 correction latest id는 유지한다.
- render artifact 저장 후 latest render id와 SVG 조회가 가능하다.

검증:

```bash
python -m pytest apps/api/tests/test_jobs_api.py -q
```

## Task 3. Jobs API route 연결

파일:

- `apps/api/cleansolve_api/routes/jobs.py`
- `apps/api/tests/test_jobs_api.py`

구현:

1. `PATCH /jobs/{job_id}/spec`를 추가한다.
2. latest candidate spec이 없으면 `SPEC_NOT_READY` 409를 반환한다.
3. stale `client_spec_version`은 `SPEC_VERSION_CONFLICT` 409와 client/server version field를 반환한다.
4. patch validator rejection은 `SPEC_PATCH_REJECTED` 400으로 반환한다.
5. patch 후 `validate_candidate_spec`를 실행하고 실패하면 artifact를 저장하지 않는다.
6. patch 성공 시 `save_spec_patch_outputs`로 candidate spec/report artifact를 저장한다.
7. response는 상세 설계 4.3 shape를 따른다.
8. `POST /jobs/{job_id}/render`를 추가한다.
9. latest candidate spec이 없으면 `SPEC_NOT_READY` 409를 반환한다.
10. `render_overlay_svg(spec)` 결과를 `save_render_artifact`로 저장한다.
11. `GET /jobs/{job_id}/rendered-preview`를 추가한다.
12. render artifact가 없으면 `RENDER_ARTIFACT_NOT_FOUND` 404를 반환한다.

테스트:

- run 후 allowed patch가 version 증가, artifact append, revision history 기록을 만든다.
- stale version은 409 conflict.
- disallowed path는 400 rejected이고 latest spec은 unchanged.
- run 전 patch는 409 spec not ready.
- render POST는 SVG artifact를 저장한다.
- rendered-preview GET은 최신 SVG를 반환한다.
- render 전 rendered-preview GET은 404.

검증:

```bash
python -m pytest apps/api/tests/test_jobs_api.py -q
```

## Task 4. Web API client와 edit draft helper

파일:

- `apps/web/src/api/client.ts`
- `apps/web/src/api/client.test.ts`
- `apps/web/src/editor/editDraft.ts`
- `apps/web/src/editor/editDraft.test.ts`

구현:

1. `SpecPatchRequest`, `SpecPatchResponse`, `RenderedPreviewResponse` type을 추가한다.
2. `patchCandidateSpec(jobId, request)`를 추가한다.
3. `renderJobPreview(jobId)`를 추가한다.
4. `getRenderedPreview(jobId)`를 추가한다.
5. client 실패 메시지는 상세 설계 11장의 한국어 문구를 사용한다.
6. `createTargetAnchorDraft(candidateSpec, reviewItem)`를 추가한다.
7. helper는 `freehand_dimension_marker`, `dimension_line`, `dimension_curve`만 지원한다.
8. helper는 element geometry에 target anchor start/end가 모두 있을 때만 draft를 반환한다.
9. `draftToSpecPatchRequest(draft)`는 target anchor start/end changes만 생성한다.

테스트:

- client 함수들이 올바른 endpoint/method/body를 사용한다.
- client 실패 시 한국어 오류를 throw한다.
- supported dimension review item은 draft를 생성한다.
- unsupported item은 null을 반환한다.
- draft는 상세 설계 12.3 changes shape로 변환된다.

검증:

```bash
npm --prefix apps/web test -- client.test.ts editDraft.test.ts
```

## Task 5. Web editor shell에 수정 UI 연결

파일:

- `apps/web/src/app/App.tsx`
- `apps/web/src/editor/ReviewPanel.tsx`
- `apps/web/src/app/App.css`
- 관련 test가 있으면 함께 수정

구현:

1. `ReviewPanel` row에 `수정` button을 추가한다.
2. `ReviewPanel`은 `onSelectItem` callback만 호출하고 API 호출은 하지 않는다.
3. `App`에 `selectedReviewItem`, `editDraft`, `editError`, `editPhase` state를 추가한다.
4. selected item이 unsupported이면 edit panel에 한국어 오류를 표시한다.
5. supported item이면 시작점 x/y, 끝점 x/y numeric input과 저장 button을 표시한다.
6. 저장 시 `patchCandidateSpec`를 호출한다.
7. patch 성공 후 candidate spec state를 response spec으로 갱신한다.
8. 이어서 `renderJobPreview`를 호출하고 response SVG를 state에 저장한다.
9. patch/render 실패 시 기존 candidate spec과 preview state는 변경하지 않는다.
10. canvas preview는 기존 candidate spec 기반 Konva preview를 유지한다.

테스트/검증:

```bash
npm --prefix apps/web test
npm --prefix apps/web run build
```

## Task 6. 전체 검증, 리뷰, push

수행:

1. 전체 test/build를 실행한다.
2. `git diff --check`를 실행한다.
3. spec compliance review를 수행한다.
4. code/UI quality review를 수행한다.
5. review 지적사항을 수정하고 재검증한다.
6. 커밋한다.
7. branch를 origin에 push한다.
8. PR 제목과 설명을 작성한다.

검증 명령:

```bash
npm --prefix apps/web test
npm --prefix apps/web run build
python -m pytest -q
git diff --check
```
