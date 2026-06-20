# AI Review & Correction Workflow

> 이 문서는 CleanSolve Studio의 다음 단계 workflow 방향을 한눈에 보기 위한 architecture note다. SoT의 원칙을 따른다.

## 핵심 요약

```text
Style Lab
= 이쁜 손글씨 스타일을 미리 분석하고 renderer를 튜닝하는 개발 공간

GPT-5.5
= 분석, 검수, 판단, ReAct correction agent

gpt-image-2
= 필요할 때만 특정 텍스트/수식 블록의 손글씨 asset 생성

deterministic renderer
= 확정된 spec과 asset을 원본 이미지 위에 정확히 합성

eval gate
= diff/score 기준으로 승인 여부를 결정

HITL
= 자동 해결 실패 또는 확신 낮은 항목만 사용자에게 노출

SSE progress stream
= 사용자가 긴 AI loop를 기다리는 동안 현재 단계와 안전한 진행 요약을 보여주는 UX 장치
```

## 전체 흐름

```text
[0] Style Lab / Renderer Calibration
    - 런타임 workflow 전에 따로 만드는 개발 공간이다.
    - 프로젝트에 저장된 이쁜 손글씨 이미지를 분석한다.
    - 한글, 숫자, 수식, 선, 화살표, 치수선의 스타일 특징을 뽑는다.
    - deterministic renderer가 사용할 style preset 파라미터를 만든다.
    - 결과물:
      - default_pretty_handwriting v1
      - style tokens
      - sample sheet
      - renderer tuning rules

        ↓

[1] load_style_preset
    - 시스템 내장 예쁜 손글씨 스타일을 로드한다.
    - 사용자가 매번 스타일 이미지를 올리는 구조가 아니다.
    - 예:
      - style.source = system_builtin
      - preset_id = default_pretty_handwriting
      - preset_version = v1

        ↓

[2] analyze_sources_ai
    - GPT-5.5가 원본 문제 이미지와 선생님 손풀이 이미지를 분석한다.
    - 무엇을 어디에 써야 하는지 candidate spec으로 만든다.
    - 추출 대상:
      - 풀이 텍스트
      - 수식
      - 도형 라벨
      - 화살표
      - 강조선
      - 치수선
      - 풀이 순서
      - 색상/강조 의도

        ↓

[3] validate_contract_deterministic
    - AI 판단이 아니라 시스템 안전 검사다.
    - JSON schema, 필수 필드, bbox 숫자 범위, artifact 존재 여부 등을 검사한다.
    - 이 단계는 계속 deterministic이어야 한다.
    - 목적:
      - 모델 출력이 깨진 상태로 renderer에 들어가지 않게 막기

        ↓

[4] render_deterministic
    - 우리가 개발/캘리브레이션한 renderer가 candidate spec을 렌더링한다.
    - 같은 spec + 같은 style preset이면 항상 같은 결과가 나와야 한다.
    - 담당:
      - 위치 정합성
      - bbox 반영
      - 선/화살표/치수선 렌더링
      - 한글/수식/주석의 기본 손글씨 스타일 적용
      - 원본 이미지 위 overlay 합성

        ↓

[5] review_and_correct_agent
    - 여기서 GPT-5.5가 ReAct 방식으로 동작한다.
    - 단순히 검사만 하는 게 아니라, 보고 → 판단하고 → tool을 선택하고 → 다시 보고 → 고친다.
    - 각 주요 단계는 SSE progress event로 사용자에게 안전한 요약만 전달한다.

    agent가 보는 입력:
      - 원본 문제 이미지
      - 선생님 손풀이 이미지
      - 현재 렌더 결과
      - candidate spec
      - style preset 정보
      - 이전 correction history
      - 현재 eval score

    agent가 사용할 수 있는 tool:
      1. inspect_content
         - 풀이 내용, 수식, 순서가 맞는지 확인

      2. inspect_layout
         - bbox, anchor, 라벨, 치수선 위치가 맞는지 확인

      3. inspect_style
         - 한글과 수식이 같은 손글씨 계열처럼 보이는지 확인

      4. compute_visual_diff
         - 원본 문제 이미지 기준의 보존 diff, 선생님 손풀이 이미지 기준의 content/layout diff,
           시스템 내장 style sample 기준의 style diff를 분리해 계산

      5. patch_candidate_spec
         - 위치, 크기, 색상, anchor, label position 등을 수정

      6. request_handwriting_asset
         - 특정 텍스트/수식 블록만 gpt-image-2로 손글씨 asset 생성

      7. rerender
         - deterministic renderer 다시 실행

      8. mark_approved
         - 기준을 통과하면 승인

      9. escalate_hitl
         - 자동 해결이 어렵거나 확신이 낮으면 사용자 검수로 넘김

        ↓

[6] correction loop
    - agent가 필요하면 여러 번 수정한다.
    - 수정 방식은 크게 두 가지다.

    A. spec patch
       - bbox 이동
       - 치수선 endpoint 수정
       - 라벨 위치 이동
       - 색상/크기/간격 조정
       - 수식 블록 위치 조정

    B. handwriting asset regeneration
       - 특정 텍스트/수식 블록의 손글씨 품질이 낮을 때만 사용
       - gpt-image-2가 해당 블록 asset만 생성
       - 전체 이미지를 재생성하지 않는다.

        ↓

[7] eval gate
    - 최종 결과를 그냥 모델 판단으로 통과시키지 않는다.
    - 여러 점수 기준을 통과해야 한다.
    - diff 비교 대상은 하나가 아니다.
      - 원본 문제 이미지: 인쇄 영역이 훼손되지 않았는지 확인
      - 선생님 손풀이 이미지: 풀이 내용, 순서, 주석 위치가 보존됐는지 확인
      - style sample sheet: 한글, 수식, 선이 같은 손글씨 계열처럼 보이는지 확인

    승인 조건 예시:
      - contract_valid = true
      - content_consistency_score >= threshold
      - layout_alignment_score >= threshold
      - style_similarity_score >= threshold
      - visual_diff_score <= threshold
      - visible_review_item_count <= budget
      - max_error_severity <= allowed_level

    통과하면:
      → APPROVED

    통과하지 못하면:
      → correction loop 재진입
      → 개선이 멈추면 HITL
      → 비용/횟수 초과 시 HITL

        ↓

[8] loop budget / safety guard
    - 반복 횟수는 작게 잡을 필요는 없지만 무한 루프는 금지한다.

    예:
      - max_revision_attempts = 10~12
      - max_asset_generation_attempts = 3
      - max_total_openai_calls_per_job = 별도 제한
      - min_improvement_delta = 0.02

    중단 조건:
      - 점수가 더 이상 개선되지 않음
      - 같은 element를 반복해서 고침
      - asset 재생성 후에도 style score가 개선되지 않음
      - 수식 정확도가 흔들림
      - 비용 budget 초과
      - 모델 confidence가 낮음

        ↓

[9] HITL
    - 자동으로 해결하기 어려운 항목만 사용자에게 노출한다.
    - 사용자는 수학 명령어를 입력하지 않고, 클릭/드래그/선택 중심으로 수정한다.

        ↓

[10] export
    - 승인된 spec + asset + 원본 이미지를 합성한다.
    - PNG/PDF로 export한다.
    - export는 deterministic renderer 결과를 기준으로 한다.
```

## 진행 상황 SSE side channel

SSE progress stream은 workflow의 순차 단계가 아니라, `[2] analyze_sources_ai`부터 `[8] loop budget / safety guard`까지 병렬로 흐르는 사용자-facing side channel이다.

서버는 다음 endpoint로 진행 상황을 stream한다.

```text
GET /jobs/{job_id}/events
```

UI는 모델이 어떤 큰 단계를 거치는지 보여준다.

표시 예:

- 원본/손풀이 분석 중
- candidate spec 생성 중
- 렌더 결과 검수 중
- 3/12번째 자동 보정 중
- 수식 블록 손글씨 asset 생성 중
- style score 개선 확인 중
- HITL 필요 여부 판단 중

이 stream은 latency 체감 완화용 UX 장치이며, 품질 승인 gate가 아니다. Chain-of-thought, 내부 prompt, raw tool observation, hidden reasoning summary, 내부 correction plan은 노출하지 않는다. 노출 가능한 값은 서버가 allowlist로 정의한 phase/status/message/action label과 aggregate score뿐이다.

## 결정론으로 남길 것

- renderer
- JSON schema 검사
- artifact 저장/조회
- bbox 숫자 범위 검사
- loop 횟수 제한
- review item budget 계산
- export/download

## AI가 맡을 것

- 풀이가 맞는지 판단
- 수식이 빠졌는지 판단
- 위치가 시각적으로 맞는지 판단
- 스타일이 예쁜 손글씨 기준과 맞는지 판단
- 어떤 tool로 어떻게 고치면 되는지 선택

## 다음 구현 순서

1. `tools/style-lab/` 또는 동등한 실험 공간을 만든다.
2. 이쁜 손글씨 reference corpus와 canonical sample sheet를 정의한다.
3. `default_pretty_handwriting v1` style token schema를 만든다.
4. renderer calibration snapshot/diff harness를 만든다.
5. LangGraph에 `review_and_correct_agent` 설계를 반영한다.
6. job progress SSE event contract와 web progress UI를 설계한다.
7. `gpt-image-2` block-level handwriting asset generation을 opt-in tool로 연결한다.
8. eval gate와 loop budget을 구현한다.
