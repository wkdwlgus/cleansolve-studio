# CleanSolve Studio — Source of Truth

> CleanSolve Studio의 초기 Source of Truth(SoT) 문서이다.  
> Codex CLI + GPT-5.5 + Superpowers 기반 프로젝트 세팅 시 제품 원칙, 워크플로우, 검증/수정 루프, HITL 정책의 기준으로 사용한다.  
> 원본 문제 이미지와 선생님 손풀이 이미지를 최상위 기준으로 두고, 시스템 내장 손글씨 스타일 프리셋을 활용해 정서된 풀이 이미지를 생성하는 방향을 정의한다.  
> 이 문서는 구현 세부를 고정하기보다, Superpowers가 스캐폴딩과 기술 선택을 할 때 깨지면 안 되는 제품/품질 경계를 명시한다.

## 목차
- [CleanSolve Studio — Source of Truth](#cleansolve-studio--source-of-truth)
  - [목차](#목차)
  - [0. 문서 목적](#0-문서-목적)
  - [0.1 Codex/Superpowers 사용 방식](#01-codexsuperpowers-사용-방식)
- [1. 프로젝트 개요](#1-프로젝트-개요)
  - [1.1 프로젝트명](#11-프로젝트명)
  - [1.2 한국어 설명](#12-한국어-설명)
  - [1.3 한 줄 정의](#13-한-줄-정의)
  - [1.4 핵심 문제](#14-핵심-문제)
- [2. 제품 목표](#2-제품-목표)
  - [2.1 사용자가 원하는 결과](#21-사용자가-원하는-결과)
  - [2.2 제품의 본질](#22-제품의-본질)
- [3. 핵심 설계 원칙](#3-핵심-설계-원칙)
  - [3.1 원본 이미지는 최상위 SoT이다](#31-원본-이미지는-최상위-sot이다)
  - [3.2 원샷 생성에 의존하지 않는다](#32-원샷-생성에-의존하지-않는다)
  - [3.3 사용자는 수학적 명령어를 입력하지 않는다](#33-사용자는-수학적-명령어를-입력하지-않는다)
  - [3.4 수학 의미보다 먼저 시각 annotation primitive를 안정적으로 다룬다](#34-수학-의미보다-먼저-시각-annotation-primitive를-안정적으로-다룬다)
  - [3.5 자동 self-revision loop는 기본 품질 장치이다](#35-자동-self-revision-loop는-기본-품질-장치이다)
- [4. 대상 범위](#4-대상-범위)
  - [4.1 과목 범위](#41-과목-범위)
  - [4.2 MVP 범위](#42-mvp-범위)
  - [4.3 MVP에서 제외할 것](#43-mvp에서-제외할-것)
- [5. 핵심 워크플로우](#5-핵심-워크플로우)
  - [5.1 기본 처리 흐름](#51-기본-처리-흐름)
  - [5.2 Workflow orchestrator](#52-workflow-orchestrator)
  - [5.3 AI 호출의 역할](#53-ai-호출의-역할)
  - [5.4 코드/렌더러의 역할](#54-코드렌더러의-역할)
  - [5.5 Automatic Self-Revision Loop](#55-automatic-self-revision-loop)
- [6. Annotation Primitive Registry](#6-annotation-primitive-registry)
  - [6.1 기본 원칙](#61-기본-원칙)
  - [6.2 MVP core primitive](#62-mvp-core-primitive)
  - [6.3 장기 확장 primitive 후보](#63-장기-확장-primitive-후보)
- [7. Candidate Spec 설계](#7-candidate-spec-설계)
  - [7.1 Candidate spec의 역할](#71-candidate-spec의-역할)
  - [7.2 공통 element 필드](#72-공통-element-필드)
  - [7.3 치수선 계열 element 규칙](#73-치수선-계열-element-규칙)
    - [7.3.1 dimension\_line](#731-dimension_line)
    - [7.3.2 dimension\_curve](#732-dimension_curve)
    - [7.3.3 freehand\_dimension\_marker](#733-freehand_dimension_marker)
    - [7.3.4 target anchor와 visible stroke의 차이](#734-target-anchor와-visible-stroke의-차이)
  - [7.4 치수선 검증 규칙](#74-치수선-검증-규칙)
    - [7.4.1 의미 범위 검증](#741-의미-범위-검증)
    - [7.4.2 시각 위치 검증](#742-시각-위치-검증)
    - [7.4.3 원본 대비 검증](#743-원본-대비-검증)
    - [7.4.4 허용 오차](#744-허용-오차)
  - [7.5 Correction Plan 설계](#75-correction-plan-설계)
  - [7.6 예시 spec](#76-예시-spec)
- [8. HITL 설계](#8-hitl-설계)
  - [8.1 목표](#81-목표)
  - [8.1.1 HITL은 예외 경로이다](#811-hitl은-예외-경로이다)
  - [8.2 Atomic review unit](#82-atomic-review-unit)
  - [8.3 Interaction policy by element type](#83-interaction-policy-by-element-type)
    - [formula\_line](#formula_line)
    - [text\_note](#text_note)
    - [highlight\_line](#highlight_line)
    - [highlight\_curve](#highlight_curve)
    - [dimension\_line](#dimension_line)
    - [dimension\_curve](#dimension_curve)
    - [freehand\_dimension\_marker](#freehand_dimension_marker)
    - [arrow](#arrow)
    - [box / circle](#box--circle)
    - [angle\_mark](#angle_mark)
    - [graph\_point](#graph_point)
    - [graph\_curve / graph\_tangent](#graph_curve--graph_tangent)
    - [shaded\_area](#shaded_area)
    - [freehand\_annotation](#freehand_annotation)
    - [unsupported\_annotation](#unsupported_annotation)
  - [8.4 Snapping 규칙](#84-snapping-규칙)
  - [8.5 검수 UI 원칙](#85-검수-ui-원칙)
  - [8.6 수정 방식](#86-수정-방식)
  - [8.7 AI 재호출이 필요한 경우](#87-ai-재호출이-필요한-경우)
  - [8.8 HITL Escalation Policy](#88-hitl-escalation-policy)
    - [8.8.1 자동 통과](#881-자동-통과)
    - [8.8.2 내부 재검증](#882-내부-재검증)
    - [8.8.3 자동 수정 우선 조건](#883-자동-수정-우선-조건)
    - [8.8.4 사용자 노출 조건](#884-사용자-노출-조건)
    - [8.8.5 Review item budget](#885-review-item-budget)
    - [8.8.6 Review 우선순위](#886-review-우선순위)
- [9. 검증 설계](#9-검증-설계)
  - [9.1 Spec validation](#91-spec-validation)
  - [9.2 Source-to-spec validation](#92-source-to-spec-validation)
  - [9.3 Render-to-source validation](#93-render-to-source-validation)
  - [9.4 Auto-revision validation](#94-auto-revision-validation)
- [10. 렌더링 전략](#10-렌더링-전략)
  - [10.1 원칙](#101-원칙)
  - [10.2 렌더링 방식 선택](#102-렌더링-방식-선택)
  - [10.3 AI 이미지 생성과 렌더링의 차이](#103-ai-이미지-생성과-렌더링의-차이)
  - [10.4 손글씨 스타일 처리](#104-손글씨-스타일-처리)
  - [10.5 재렌더링과 재생성의 우선순위](#105-재렌더링과-재생성의-우선순위)
- [11. OpenAI API 사용 원칙](#11-openai-api-사용-원칙)
  - [11.1 Responses API 용도](#111-responses-api-용도)
  - [11.2 Images API 또는 image generation tool 용도](#112-images-api-또는-image-generation-tool-용도)
  - [11.3 모델 호출 원칙](#113-모델-호출-원칙)
- [12. 상태 관리](#12-상태-관리)
  - [12.1 Job 상태](#121-job-상태)
  - [12.2 저장해야 할 산출물](#122-저장해야-할-산출물)
  - [12.3 Revision 기록](#123-revision-기록)
- [13. Quality Harness / Evaluation Harness](#13-quality-harness--evaluation-harness)
- [14. 권장 기술 방향](#14-권장-기술-방향)
  - [14.1 기본 방향](#141-기본-방향)
  - [14.2 Codex/Superpowers가 결정해야 할 것](#142-codexsuperpowers가-결정해야-할-것)
  - [14.3 초기에는 과한 도입을 피할 것](#143-초기에는-과한-도입을-피할-것)
- [15. Repository 산출물 요구사항](#15-repository-산출물-요구사항)
- [16. Codex/Superpowers 작업 원칙](#16-codexsuperpowers-작업-원칙)
- [17. 금지 사항](#17-금지-사항)
- [18. MVP 성공 기준](#18-mvp-성공-기준)
- [19. 최종 제품 방향](#19-최종-제품-방향)



## 0. 문서 목적

이 문서는 `CleanSolve Studio` 프로젝트의 초기 SoT(Source of Truth)이다.

Codex CLI 기반 GPT-5.5 및 Superpowers 플러그인을 사용하여 프로젝트 구조, 아키텍처, 핵심 워크플로우, API 설계, 검수 루프, UI 방향성, MVP 범위를 세팅하기 위한 기준 문서로 사용한다.

이 문서에 명시된 내용은 초기 구현의 우선 기준이다. 구현 중 불명확한 부분이 발생하면 임의로 확장하지 말고, `ASSUMPTIONS.md` 또는 `DECISIONS.md`에 가정과 결정을 기록한 뒤 최소 단위로 구현한다.

<a id="section-0-1"></a>
## 0.1 Codex/Superpowers 사용 방식

이 문서는 Superpowers가 수행할 개발 절차를 세부 파일 단위로 강제하기 위한 문서가 아니다.

이 문서는 다음을 정의한다.

1. 제품이 해결해야 하는 문제
2. 절대 깨지면 안 되는 설계 원칙
3. 사용자 경험의 핵심 규칙
4. AI와 deterministic renderer의 역할 분리
5. 한국 고등수학 전체를 다루기 위한 확장 가능한 annotation model
6. HITL 검수 규칙
7. 자동 검수 및 자동 수정 루프
8. 초기 MVP의 경계와 금지사항

Codex/Superpowers는 이 SoT를 기반으로 다음을 판단한다.

1. 최종 프로젝트 폴더명과 초기 scaffold
2. 구체적인 기술 스택
3. LangGraph 또는 유사 workflow orchestrator 도입 방식
4. repository 구조
5. 테스트/harness 구조
6. 구현 계획과 작업 순서

단, Codex/Superpowers가 제안하는 구현은 이 SoT의 제품 원칙과 충돌하면 안 된다.

---

<a id="section-1"></a>
# 1. 프로젝트 개요

<a id="section-1-1"></a>
## 1.1 프로젝트명

**CleanSolve Studio**

기본 repository slug는 `cleansolve-studio`로 한다.

Codex/Superpowers가 brainstorming 과정에서 더 적절한 이름을 제안할 수는 있으나, 별도 결정이 없다면 이 이름을 사용한다.

<a id="section-1-2"></a>
## 1.2 한국어 설명

**수학 손풀이 정서 AI 편집기**

<a id="section-1-3"></a>
## 1.3 한 줄 정의

선생님이 직접 작성한 수학 손글씨 풀이 이미지를 원본 문제 이미지 위에 더 깔끔하고 예쁜 손글씨 스타일로 재구성하되, 내용·수식·도형 주석·색상·풀이 순서를 최대한 보존하는 AI 기반 편집 서비스.

<a id="section-1-4"></a>
## 1.4 핵심 문제

현재 많은 선생님은 학생들에게 손글씨 풀이를 제공한다. 그러나 선생님마다 글씨체와 가독성이 다르며, 악필인 경우 학생 입장에서 풀이 이해도가 낮아질 수 있다.

기존에는 선생님이 작성한 손글씨 풀이를 사람이 다시 예쁘게 써주는 외주 방식으로 해결했다.

CleanSolve Studio는 이 과정을 AI와 편집 시스템으로 대체하거나 보조한다.

---

<a id="section-2"></a>
# 2. 제품 목표

<a id="section-2-1"></a>
## 2.1 사용자가 원하는 결과

입력:

1. 원본 문제 이미지
2. 선생님이 직접 작성한 손글씨 풀이 이미지

시스템 내부 기준:

1. 예쁜 손글씨 스타일은 초기 MVP에서 사용자가 업로드하지 않는다.
2. 예쁜 손글씨 스타일 기준은 서비스 운영자가 사전에 등록한 **시스템 내장 스타일 프리셋**을 사용한다.
3. 이 시스템 내장 스타일 프리셋은 AI 분석/렌더링 단계에서 스타일 기준 컨텍스트로 활용한다.
4. 장기적으로는 여러 스타일 프리셋 선택 또는 사용자 지정 스타일 업로드를 검토할 수 있으나, 초기 MVP 범위에는 포함하지 않는다.

출력:

1. 원본 문제의 인쇄 영역은 최대한 그대로 유지
2. 선생님 풀이의 내용, 수식, 도형 주석, 색상, 강조, 풀이 순서를 보존
3. 글씨만 시스템 내장 예쁜 손글씨 스타일로 정리
4. 필요 시 도형 위 보조선, 색상 강조, 라벨을 더 가독성 좋게 재배치
5. 최종 결과는 이미지 또는 PDF로 export 가능

<a id="section-2-2"></a>
## 2.2 제품의 본질

이 프로젝트는 단순 이미지 생성기가 아니다.

잘못된 방향:

```text
원본 문제 이미지 + 손풀이 이미지
→ AI에게 한 번에 요청
→ 최종 이미지 생성
```

올바른 방향:

```text
원본 이미지
+ 선생님 손풀이 이미지
+ 시스템 내장 손글씨 스타일 기준
→ 시각 요소 분석
→ 구조화된 작업 명세 생성
→ 불확실 항목 내부 검증
→ 렌더링/합성
→ 결과 이미지 자동 검수
→ 오류 발견 시 자동 수정/재렌더링 또는 부분 재생성
→ 그래도 해결되지 않는 경우에만 HITL
→ 최종 export
```

즉, CleanSolve Studio는 **수학 손풀이 전용 AI 편집기**이다.

---

<a id="section-3"></a>
# 3. 핵심 설계 원칙

<a id="section-3-1"></a>
## 3.1 원본 이미지는 최상위 SoT이다

진짜 SoT는 JSON이 아니라 원본 이미지이다.

SoT 우선순위:

```text
1순위: 원본 문제 이미지
2순위: 선생님 손글씨 풀이 이미지
3순위: 시스템 내장 예쁜 손글씨 스타일 프리셋
4순위: AI가 추출한 candidate spec JSON
5순위: 생성/렌더링된 결과 이미지
```

JSON은 원본을 대체하는 정답지가 아니다.
JSON은 원본 이미지에서 추출한 **검증 대상 중간 명세(candidate rendering spec)** 이다.

시스템 내장 예쁜 손글씨 스타일 프리셋은 사용자 입력이 아니다.
운영자가 사전에 등록한 기준 스타일이며, 초기 MVP에서는 모든 작업이 이 기본 스타일을 기준으로 렌더링된다.

<a id="section-3-2"></a>
## 3.2 원샷 생성에 의존하지 않는다

프론티어 모델의 원샷 이미지 생성은 데모 수준에서는 매우 좋은 결과를 낼 수 있다.

하지만 다음 오류가 발생할 수 있다.

* 선분 표시 범위 오류
* 도형 주석 누락
* 색상 강조 누락
* 수식 지수 오인식
* 아래 풀이와 도형 주석의 불일치
* 원본에 없는 내용을 그럴듯하게 보완하는 과잉추론
* 치수선의 양 끝이 실제 타겟 범위와 어긋나는 오류
* 라벨은 맞지만 라벨이 가리키는 시각 범위가 틀리는 오류
* 길이 표시선이 타겟 구간의 양 끝을 정확히 가리키지 못하는 오류
* 곡선 치수선이 타겟 선분/구간 전체가 아니라 일부만 표시하는 오류
* 치수선의 label은 맞지만, 실제 표시선의 span이 잘못되어 다른 길이를 의미하게 되는 오류
* 원본 손풀이의 freehand-style 치수선이 단순 highlight로 잘못 분류되는 오류

따라서 제품은 다음 구조를 따른다.

```text
인식
→ 구조화
→ 검증
→ 렌더링
→ 결과 검수
→ 자동 수정/재렌더링
→ 필요 시 HITL
```

치수선과 강조선은 다르다.

`highlight`는 특정 선, 영역, 수식, 점을 시각적으로 강조하는 표시이다.
`dimension marker`는 특정 길이, 구간, 호, 거리, 각도 범위를 나타내는 표시이다.

특히 수학 손풀이에서는 타겟 선분 위에 직접 치수선을 긋지 않고, 선분 옆에 떨어진 곡선, 괄호, 분절된 손필기 stroke, label을 조합하여 길이를 표시하는 경우가 많다. 이런 요소는 `highlight_curve`가 아니라 `dimension_curve` 또는 `freehand_dimension_marker`로 분류해야 한다.

<a id="section-3-3"></a>
## 3.3 사용자는 수학적 명령어를 입력하지 않는다

사용자에게 다음과 같은 입력을 요구하면 안 된다.

```text
secθ의 표시 범위를 OQ로 수정하세요.
OR인지 QR인지 입력하세요.
```

이런 방식은 사용성이 낮다.

사용자는 개발자가 아니다.
선생님은 눈으로 보고 클릭, 선택, 드래그, 승인할 수 있어야 한다.

좋은 UX:

```text
AI가 복원한 표시선을 보여준다.
사용자는 끝점을 드래그한다.
사용자는 A/B 후보 중 하나를 선택한다.
사용자는 [맞음], [수정], [추가], [추가 안 함]을 누른다.
```

<a id="section-3-4"></a>
## 3.4 수학 의미보다 먼저 시각 annotation primitive를 안정적으로 다룬다

한국 고등수학 전체를 대상으로 하기 때문에 특정 문제 하나의 수학 의미에 과적합하면 안 된다.

서비스의 기본 단위는 수학 개념이 아니라 **시각적 풀이 구성요소(annotation primitive)** 이다.

수학 의미는 보조 정보로 활용하되, UI와 렌더링의 기본은 좌표·anchor·geometry 기반 시각 요소여야 한다.

<a id="section-3-5"></a>
## 3.5 자동 self-revision loop는 기본 품질 장치이다

결과 이미지 또는 렌더링 preview가 생성된 뒤에는 곧바로 사용자에게 보여주지 않는다.

시스템은 먼저 결과를 원본 손풀이 이미지 및 candidate spec과 비교하여 자동 검수한다.
오류가 발견되면, 곧바로 HITL로 넘기지 않고 자동 수정 가능 여부를 판단한다.

자동 수정 가능한 오류는 correction plan을 생성한 뒤 다음 중 하나로 처리한다.

1. candidate spec patch 적용 후 deterministic re-render
2. 해당 overlay element만 재렌더링
3. 해당 text/formula handwriting asset만 부분 재생성
4. 복잡한 경우 제한된 범위의 이미지 재편집

자동 self-revision loop를 1~2회 수행한 뒤에도 해결되지 않는 경우에만 HITL로 escalte한다.

---

<a id="section-4"></a>
# 4. 대상 범위

<a id="section-4-1"></a>
## 4.1 과목 범위

장기 범위는 한국 고등수학 전체이다.

* 공통수학
* 수학 I
* 수학 II
* 미적분
* 확률과 통계
* 기하

<a id="section-4-2"></a>
## 4.2 MVP 범위

MVP에서는 전체 고등수학을 모두 완벽히 처리하려 하지 않는다.

우선순위:

1. 원본 문제 이미지와 손풀이 이미지 업로드
2. 손풀이 내 수식/텍스트 라인 추출
3. 색상별 필기 요소 추출
4. 도형/그래프 위 주요 annotation 추출
5. 하단 풀이 영역을 시스템 내장 예쁜 손글씨 스타일로 재렌더링
6. 원본 문제 위에 오버레이 합성
7. 결과 이미지 자동 검수
8. 자동 수정/재렌더링 루프
9. 불확실 항목을 사용자에게 시각적으로 제시
10. 클릭/선택/드래그 기반 수정
11. 결과 이미지 export
12. 핵심 작업 흐름을 LangGraph 또는 Codex/Superpowers가 추천한 유사 workflow orchestrator로 구성

<a id="section-4-3"></a>
## 4.3 MVP에서 제외할 것

초기 버전에서 제외한다.

* 완전 자동 100% 무검수 보장
* 모든 문제 유형에 대한 수학적 정답 검증
* 개인별 손글씨 스타일 학습 모델 학습
* 사용자 지정 손글씨 스타일 이미지 업로드
* 복잡한 벡터 에디터 수준의 자유 편집
* 대량 채점/성적 관리
* LMS 연동
* 결제/구독 시스템
* 모바일 앱

---

<a id="section-5"></a>
# 5. 핵심 워크플로우

<a id="section-5-1"></a>
## 5.1 기본 처리 흐름

```text
START
  ↓
Upload problem image
  ↓
Upload teacher solution image
  ↓
Load system built-in handwriting style preset
  ↓
Analyze source images
  ↓
Extract candidate spec JSON
  ↓
Validate spec
  ↓
Render preview v1
  ↓
Inspect preview v1 against source images and candidate spec
  ↓
If issues are auto-correctable:
    Create correction plan
    Apply spec patch or partial regeneration
    Render preview v2
    Inspect preview v2
  ↓
If still failed and user-visible impact is high:
    Show HITL review UI
  ↓
User confirms/edits uncertain items
  ↓
Re-render deterministic overlay
  ↓
Final inspection
  ↓
Final preview
  ↓
Export image/PDF
END
```

초기 MVP에서는 사용자가 손글씨 스타일 예시 이미지를 업로드하거나 선택하지 않는다.
시스템은 운영자가 사전에 등록한 기본 손글씨 스타일 프리셋을 자동으로 로드하여 분석/렌더링 컨텍스트로 사용한다.

<a id="section-5-2"></a>
## 5.2 Workflow orchestrator

초기 구현부터 workflow orchestrator를 사용한다.

기본 후보는 LangGraph이다.

다만 Codex/Superpowers가 SoT 전체를 검토한 뒤 LangGraph보다 적절한 대안을 제안할 수 있다. 그 경우 반드시 `DECISIONS.md`에 다음을 기록해야 한다.

1. 선택한 orchestrator
2. LangGraph를 선택하지 않은 이유
3. 상태 관리 방식
4. 실패/재시도 방식
5. 자동 self-revision loop 방식
6. HITL interrupt/resume 방식
7. 테스트 전략

Superpowers는 개발 작업 절차를 지원하는 도구이다.
LangGraph 또는 유사 orchestrator는 CleanSolve Studio 서비스 내부의 job workflow를 실행하는 runtime 구성요소이다.
둘의 역할을 혼동하지 않는다.

<a id="section-5-3"></a>
## 5.3 AI 호출의 역할

AI는 다음을 담당한다.

1. 원본 문제 이미지의 영역 이해
2. 선생님 손풀이 이미지의 필기 요소 추출
3. 수식/텍스트 OCR 및 구조화
4. 도형/그래프/표 위 annotation 추출
5. 불확실 항목 탐지
6. 렌더링 spec 후보 생성
7. 시스템 내장 스타일 프리셋을 기준으로 한 스타일 적용 지시 생성
8. 생성 결과와 원본 손풀이 비교 검수
9. 오류 발견 시 correction plan 생성
10. 자동 수정 후 재검수
11. 사용자 수정 후 필요 시 재해석

AI는 최종 렌더링의 단일 SoT가 아니다.

<a id="section-5-4"></a>
## 5.4 코드/렌더러의 역할

서비스 코드는 다음을 담당한다.

1. 파일 저장
2. 작업 상태 관리
3. candidate spec 버전 관리
4. validation report 저장
5. correction plan 저장
6. user patch 저장
7. 사용자 수정사항 반영
8. 시스템 내장 스타일 프리셋 로드 및 버전 관리
9. overlay primitive 렌더링
10. 이미지 합성
11. 부분 재렌더링
12. export
13. retry 및 failure handling

<a id="section-5-5"></a>
## 5.5 Automatic Self-Revision Loop

자동 self-revision loop는 HITL 이전에 실행되는 기본 품질 보정 단계이다.

목표:

```text
사용자에게 묻기 전에,
시스템이 스스로 발견 가능한 오류를 먼저 수정한다.
```

기본 루프:

```text
Render or generate preview
  ↓
Visual inspection with AI
  ↓
Validation report
  ↓
If pass:
    Continue
If fail and auto-correctable:
    Create correction plan
    Apply correction
    Re-render or regenerate affected asset
    Re-inspect
If fail and not auto-correctable:
    Escalate to HITL only if user-visible impact is high
```

자동 수정 대상 예시:

1. 수식 OCR 후보가 명확한 경우
2. 색상 오인식이 명확한 경우
3. 치수선 endpoint가 source crop 비교로 자동 보정 가능한 경우
4. 라벨 위치가 치수선 group과 떨어진 경우
5. 누락된 강조선이 원본에서 명확히 발견되는 경우
6. 생성 결과에서 원본 문제 인쇄 영역이 훼손된 경우
7. candidate spec에는 있으나 렌더링 결과에서 누락된 overlay가 있는 경우

자동 수정 방식:

1. spec patch
2. render parameter update
3. partial overlay re-render
4. handwriting asset regeneration
5. limited image edit
6. full regeneration only as last resort

제한:

```text
- 자동 수정 루프는 무한 반복하지 않는다.
- MVP 기본 max_revision_attempts는 2로 둔다.
- 2회 이후에도 해결되지 않으면 internal warning 또는 HITL로 전환한다.
- 자동 수정은 원본 손풀이에 없는 내용을 새로 창작하면 안 된다.
```

---

<a id="section-6"></a>
# 6. Annotation Primitive Registry

<a id="section-6-1"></a>
## 6.1 기본 원칙

기존의 element type 목록은 전체 고등수학을 보장할 수 없다.
따라서 CleanSolve Studio는 고정 enum만으로 모든 풀이 요소를 표현하지 않는다.

원칙:

1. element type은 확장 가능한 registry로 관리한다.
2. MVP core primitive는 작게 시작한다.
3. 지원하지 못하는 요소는 버리지 않고 `unsupported_annotation` 또는 `freehand_annotation`으로 보존한다.
4. 모든 element는 source evidence를 가진다.
5. 모든 element는 bbox 또는 geometry를 가진다.
6. 모든 element는 confidence를 가진다.
7. 불명확하면 unknown/null을 허용한다.
8. 불명확하면 needs_review=true로 둔다.
9. 모델이 모르는 것을 추측해 채우면 안 된다.
10. 적용된 스타일은 사용자 업로드 파일이 아니라 시스템 내장 style preset id/version으로 기록한다.

<a id="section-6-2"></a>
## 6.2 MVP core primitive

초기 구현에서 반드시 지원할 core primitive:

```text
formula_line
text_note
highlight_line
highlight_curve
dimension_line
dimension_curve
freehand_dimension_marker
arrow
box
circle
angle_mark
point_label
segment_label
graph_point
graph_curve
graph_tangent
shaded_area
choice_mark
freehand_annotation
unsupported_annotation
```

<a id="section-6-3"></a>
## 6.3 장기 확장 primitive 후보

장기적으로 추가할 수 있는 primitive:

```text
table
matrix
case_tree
probability_tree
venn_diagram
number_line
coordinate_axis
integral_area
sequence_diagram
transformation_arrow
brace
bracket
tick_mark
eraser_region
layout_spacer
```

이 목록은 전체 목록이 아니다.
새로운 문제 유형이나 필기 관습이 발견되면 registry를 확장한다.

---

<a id="section-7"></a>
# 7. Candidate Spec 설계

<a id="section-7-1"></a>
## 7.1 Candidate spec의 역할

Candidate spec은 원본 손풀이를 재현하기 위한 중간 명세이다.

Candidate spec은 정답지가 아니다.
Candidate spec은 renderer와 HITL UI가 다룰 수 있도록 원본 필기 요소를 구조화한 작업 명세이다.

<a id="section-7-2"></a>
## 7.2 공통 element 필드

모든 element는 가능한 한 다음 필드를 가진다.

```json
{
  "id": "el_001",
  "type": "dimension_curve",
  "source_region": "diagram",
  "color": "blue",
  "confidence": 0.82,
  "needs_review": false,
  "requires_human_review": false,
  "auto_correctable": false,
  "evidence": {
    "source": "teacher_solution_image",
    "bbox": [100, 200, 500, 260]
  },
  "bbox": [100, 200, 500, 260],
  "geometry": {},
  "style": {},
  "interaction": {},
  "validation": {},
  "revision_history": []
}
```

<a id="section-7-3"></a>
## 7.3 치수선 계열 element 규칙

선분 길이, 호의 길이, 구간 길이, 그래프 구간, 높이, 거리, 각도 등을 나타내는 표시선은 일반 highlight와 구분한다.

치수선 계열 element는 다음을 표현한다.

```text
이 표시가 어느 범위의 길이/구간/거리/각도를 의미하는가?
그 범위의 실제 시작점과 끝점은 어디인가?
실제로 화면에 그려지는 stroke는 어디에 위치하는가?
label은 해당 범위를 오해 없이 설명하는 위치에 있는가?
```

치수선은 반드시 타겟 선분 위에 직접 놓일 필요가 없다.
수학 손풀이에서는 치수선이 타겟 선분 옆에 떨어져 있고, 곡선·괄호·분절된 freehand stroke 형태로 그려지는 경우가 많다.

예시:

```text
점 O에서 점 S까지의 길이가 1임을 표시하기 위해,
선분 OS 위를 직접 칠하지 않고,
OS 왼쪽에 빨간 곡선 stroke 여러 개와 label “1”을 배치하는 경우
```

이 경우 해당 element는 highlight가 아니라 `dimension_curve` 또는 `freehand_dimension_marker`로 처리한다.

### 7.3.1 dimension_line

직선 형태의 치수선이다.

예:

```text
- 축 위의 구간 표시
- 선분과 평행하게 떨어진 직선 치수 표시
- 높이, 거리, 수평/수직 길이 표시
```

권장 geometry:

```json
{
  "kind": "dimension_line",
  "target_anchor_start": [0, 0],
  "target_anchor_end": [100, 0],
  "visible_start": [0, 12],
  "visible_end": [100, 12],
  "label_anchor": [50, 24],
  "endpoint_style": "none | tick | dot | arrow | bracket",
  "offset_side": "above | below | left | right | inside | outside | unknown"
}
```

### 7.3.2 dimension_curve

곡선 형태의 치수선이다.

예:

```text
- 선분 옆에 떨어져 있는 곡선 길이 표시
- 호의 길이 표시
- 구간 전체를 괄호처럼 감싸는 곡선 표시
- 기준선 아래/위로 휘어진 범위 표시
```

권장 geometry:

```json
{
  "kind": "dimension_curve",
  "target_anchor_start": [0, 0],
  "target_anchor_end": [100, 0],
  "visible_start": [0, 12],
  "visible_end": [100, 12],
  "control_points": [[50, 35]],
  "label_anchor": [50, 48],
  "endpoint_style": "none | tick | dot | arrow | bracket",
  "offset_side": "above | below | left | right | inside | outside | unknown",
  "curvature_direction": "clockwise | counterclockwise | inward | outward | unknown",
  "stroke_continuity": "continuous | fragmented | unknown"
}
```

### 7.3.3 freehand_dimension_marker

손풀이에서 흔히 나오는 분절형 길이 표시이다.

첨부 예시처럼 한 개의 매끈한 곡선이 아니라, 여러 개의 짧은 red stroke와 label이 함께 특정 길이를 나타내는 경우 사용한다.

예:

```text
- 빨간 곡선 stroke 2~3개 + label “1”
- 선분 옆에 떨어진 손필기 괄호 표시
- 정확한 단일 곡선으로 fitting하기 어려운 길이 표시
```

권장 geometry:

```json
{
  "kind": "freehand_dimension_marker",
  "target_anchor_start": [0, 0],
  "target_anchor_end": [100, 0],
  "visible_strokes": [
    {
      "stroke_id": "s1",
      "points": [[10, 20], [20, 35], [30, 45]]
    },
    {
      "stroke_id": "s2",
      "points": [[45, 55], [58, 70], [70, 82]]
    }
  ],
  "label": "1",
  "label_anchor": [40, 52],
  "offset_side": "above | below | left | right | inside | outside | unknown",
  "stroke_continuity": "fragmented"
}
```

### 7.3.4 target anchor와 visible stroke의 차이

치수선 계열 element에서는 다음을 반드시 구분한다.

```text
target_anchor_start / target_anchor_end
= 의미상 타겟 구간의 실제 양 끝

visible_start / visible_end / visible_strokes
= 화면에 실제로 그려지는 치수선 stroke

label_anchor
= 길이, 값, 기호가 배치되는 위치
```

치수선이 타겟 선분에서 떨어져 그려져도 된다.
그러나 `target_anchor_start`와 `target_anchor_end`는 반드시 표시하려는 실제 구간의 양 끝과 대응되어야 한다.

예를 들어 O에서 S까지의 길이를 표시하는 빨간 곡선 치수선이라면:

```text
target_anchor_start ≈ O
target_anchor_end ≈ S
visible_strokes는 OS 옆에 떨어진 곡선/분절 stroke
label_anchor는 “1”이 적힌 위치
```

로 표현한다.

<a id="section-7-4"></a>
## 7.4 치수선 검증 규칙

`dimension_line`, `dimension_curve`, `freehand_dimension_marker`는 다음을 검증한다.

### 7.4.1 의미 범위 검증

```text
1. target_anchor_start와 target_anchor_end가 실제 타겟 구간의 양 끝과 대응되는가?
2. label이 의미하는 길이/값이 target_anchor_start~target_anchor_end 범위와 충돌하지 않는가?
3. 치수선이 타겟보다 짧거나 길게 표시되어 다른 범위를 의미하게 만들지 않는가?
4. 원본 손풀이에서 의도한 길이 표시를 highlight로 잘못 분류하지 않았는가?
```

### 7.4.2 시각 위치 검증

```text
1. visible stroke가 target anchor들과 시각적으로 대응되는 위치에 있는가?
2. 곡선 또는 분절 stroke의 시작/끝 방향이 target range의 양 끝을 암시하는가?
3. visible stroke가 중간에서 끊겨 target range 일부만 표시하는 것처럼 보이지 않는가?
4. 치수선이 타겟 선분, 축, 그래프, 보조선, 음영 영역과 겹쳐 잘못된 의미를 만들지 않는가?
5. label_anchor가 치수선의 범위를 오해하게 만드는 위치에 있지 않은가?
```

### 7.4.3 원본 대비 검증

```text
1. 원본 손풀이의 치수선이 어느 쪽에 놓였는지 보존했는가?
   예: 선분의 왼쪽, 아래쪽, 바깥쪽, 내부 등

2. 원본 손풀이의 stroke continuity를 보존했는가?
   예: continuous curve인지 fragmented freehand stroke인지

3. 원본 손풀이의 label 위치를 지나치게 바꾸지 않았는가?

4. 원본에서 치수선이 label과 함께 하나의 시각 단위로 작동했다면,
   결과에서도 치수선과 label을 group으로 유지했는가?
```

### 7.4.4 허용 오차

허용 오차는 이미지 해상도와 element type에 따라 달라진다.

MVP에서는 다음을 원칙으로 한다.

```text
- printed geometry endpoint에 snap 가능한 경우: 엄격한 pixel tolerance 적용
- 손필기 freehand endpoint만 존재하는 경우: 더 넓은 tolerance 적용
- target anchor는 정확성을 우선
- visible stroke는 자연스러움과 원본 유사성을 함께 고려
```

tolerance 값은 fixture 기반 harness에서 조정 가능해야 한다.

<a id="section-7-5"></a>
## 7.5 Correction Plan 설계

자동 검수에서 오류가 발견되면, 시스템은 바로 재생성하지 않고 correction plan을 먼저 생성한다.

Correction plan은 다음을 포함한다.

```json
{
  "revision_id": "rev_001",
  "source_preview_id": "rendered_preview_v1",
  "issues": [
    {
      "issue_id": "issue_001",
      "type": "dimension_endpoint_mismatch",
      "severity": "high",
      "expected": "freehand dimension marker should represent target range from O to S",
      "actual": "visible marker appears to cover only partial range",
      "auto_correctable": true,
      "correction_action": "patch_candidate_spec_geometry"
    }
  ],
  "actions": [
    {
      "action_id": "act_001",
      "type": "spec_patch",
      "element_id": "el_002",
      "patch": {
        "geometry.target_anchor_end": [520, 470]
      }
    }
  ],
  "requires_human_review": false
}
```

Correction action 후보:

```text
spec_patch
partial_overlay_rerender
handwriting_asset_regeneration
limited_image_edit
full_regeneration
escalate_to_human_review
```

원칙:

1. 가능한 경우 `spec_patch`와 `partial_overlay_rerender`를 우선한다.
2. 전체 이미지 재생성은 최후 수단이다.
3. correction plan은 반드시 저장되어야 한다.
4. 자동 수정 후에는 반드시 재검수를 수행한다.

<a id="section-7-6"></a>
## 7.6 예시 spec

```json
{
  "job_id": "uuid",
  "version": 1,
  "source_images": {
    "problem_image_id": "uuid",
    "teacher_solution_image_id": "uuid"
  },
  "style": {
    "source": "system_builtin",
    "preset_id": "default_pretty_handwriting",
    "preset_version": "v1",
    "description": "운영자가 사전에 등록한 기본 예쁜 손글씨 스타일"
  },
  "page": {
    "width": 1080,
    "height": 1920
  },
  "regions": [
    {
      "id": "region_problem_text",
      "type": "printed_problem",
      "bbox": [0, 0, 1080, 420],
      "preserve_original": true
    },
    {
      "id": "region_diagram",
      "type": "diagram",
      "bbox": [120, 420, 960, 980],
      "preserve_original": true
    },
    {
      "id": "region_solution",
      "type": "solution_area",
      "bbox": [80, 1080, 1000, 1800],
      "preserve_original": false
    }
  ],
  "elements": [
    {
      "id": "el_001",
      "type": "formula_line",
      "text": "\\overline{PQ}=\\tan\\theta, \\overline{PR}=\\tan^2\\theta",
      "display_text": "PQ = tanθ, PR = tan²θ",
      "color": "red",
      "bbox": [80, 1120, 900, 1170],
      "confidence": 0.93,
      "needs_review": false,
      "requires_human_review": false,
      "auto_correctable": false,
      "evidence": {
        "source": "teacher_solution_image",
        "bbox": [75, 1115, 905, 1175]
      }
    },
    {
      "id": "el_002",
      "type": "freehand_dimension_marker",
      "label": "1",
      "color": "red",
      "geometry": {
        "kind": "freehand_dimension_marker",
        "target_anchor_start": [180, 820],
        "target_anchor_end": [520, 470],
        "visible_strokes": [
          {
            "stroke_id": "s1",
            "points": [[190, 805], [210, 720], [250, 650]]
          },
          {
            "stroke_id": "s2",
            "points": [[305, 580], [370, 510], [500, 455]]
          }
        ],
        "label": "1",
        "label_anchor": [280, 610],
        "offset_side": "left",
        "stroke_continuity": "fragmented"
      },
      "confidence": 0.74,
      "needs_review": true,
      "requires_human_review": false,
      "auto_correctable": true,
      "review_reason": "치수선의 target endpoint가 원본에서 의도한 길이 범위와 정확히 일치하는지 내부 검증 필요",
      "evidence": {
        "source": "teacher_solution_image",
        "bbox": [160, 430, 540, 850]
      },
      "interaction": {
        "allowed": [
          "drag_target_anchor_start",
          "drag_target_anchor_end",
          "drag_visible_stroke",
          "drag_label"
        ]
      },
      "revision_history": []
    }
  ],
  "uncertainties": [
    {
      "id": "unc_001",
      "element_id": "el_002",
      "type": "dimension_endpoint_uncertain",
      "message": "빨간 치수선의 target endpoint가 원본과 정확히 일치하는지 확인 필요",
      "review_ui": "drag_dimension_endpoint",
      "user_visible_by_default": false
    }
  ]
}
```

---

<a id="section-8"></a>
# 8. HITL 설계

<a id="section-8-1"></a>
## 8.1 목표

HITL은 사용자가 수학 기호나 점 이름을 키보드로 설명하게 만드는 구조가 아니다.

목표는 다음과 같다.

```text
AI가 거의 다 작업
→ 불확실한 부분은 먼저 내부 검증/자동 수정
→ 그래도 해결되지 않는 항목만 사용자에게 보여줌
→ 사용자는 클릭/선택/드래그로 확인
→ 시스템이 spec을 수정
→ deterministic re-render
```

<a id="section-8-1-1"></a>
## 8.1.1 HITL은 예외 경로이다

HITL은 기본 경로가 아니다.
CleanSolve Studio의 목표는 사용자가 매번 검수 질문을 받는 서비스가 아니다.

제품 목표:

```text
일반적인 문제 처리에서 대부분의 작업은 자동으로 통과해야 한다.
사용자에게 질문하는 것은 불확실성이 실제 결과 품질에 영향을 줄 때만 허용한다.
```

초기 품질 목표:

```text
- 사용자에게 HITL 검수가 노출되는 job 비율: 20% 이하를 목표로 한다.
- 즉, 대략 5개 작업 중 1개 이하만 사용자 확인이 필요해야 한다.
- review가 필요한 job에서도 사용자에게 보여주는 항목은 기본적으로 1~3개 이하로 제한한다.
- 모든 low-confidence 요소를 사용자에게 보여주면 안 된다.
```

중요 원칙:

```text
needs_review=true는 곧바로 사용자에게 물어보라는 뜻이 아니다.

needs_review=true
= 내부 추가 검증 또는 후보 생성이 필요한 상태

requires_human_review=true
= 자동 검증과 자동 수정 후보 생성 이후에도 해결되지 않아 사용자에게 노출해야 하는 상태
```

<a id="section-8-2"></a>
## 8.2 Atomic review unit

HITL에서 검수 단위는 element 하나가 기본이다.

단, 다음 요소들은 group으로 묶어 검수한다.

1. 치수선 + 라벨
2. 화살표 + 라벨
3. 박스 + 박스 안 수식
4. 그래프 점 + 점 라벨
5. 음영 영역 + 영역 라벨
6. 각도 표시 + 각도 라벨

검수 단위는 사용자가 “이 표시가 맞는지” 눈으로 판단할 수 있는 최소 단위여야 한다.

<a id="section-8-3"></a>
## 8.3 Interaction policy by element type

element type별 허용 조작은 명시적으로 제한한다.

### formula_line

허용:

* 후보 선택
* 직접 수식 수정
* 위치 이동
* 줄 간격 조정
* 색상 선택

비허용:

* 수식 의미 자동 변경
* 원본에 없는 전개 추가

### text_note

허용:

* 후보 선택
* 직접 텍스트 수정
* 위치 이동
* 색상 선택

### highlight_line

허용:

* start/end handle drag
* 전체 이동
* 색상 변경
* 두께 조정

### highlight_curve

허용:

* start/end handle drag
* control point drag
* 전체 이동
* 색상 변경
* 두께 조정

### dimension_line

허용:

* target_anchor_start drag
* target_anchor_end drag
* visible offset drag
* label drag
* endpoint style 선택
* 색상 변경

검증:

* target_anchor_start/end가 타겟 구간 양 끝과 대응되어야 한다.
* visible_start/end가 target anchor와 시각적으로 정렬되어야 한다.

### dimension_curve

허용:

* target_anchor_start drag
* target_anchor_end drag
* curve control point drag
* curve offset drag
* label drag
* endpoint style 선택
* 색상 변경

검증:

* 곡선의 양 끝이 타겟 구간 양 끝을 정확히 가리켜야 한다.
* 곡선이 중간에서 끊겨 타겟 범위를 짧게 보이게 하면 안 된다.
* 라벨 위치가 타겟 범위를 오해하게 만들면 안 된다.

### freehand_dimension_marker

허용:

* target_anchor_start drag
* target_anchor_end drag
* visible stroke group 이동
* 개별 stroke point 조정
* label drag
* 색상 변경
* 원본 stroke continuity 유지/정리 선택

검증:

* 분절 stroke가 하나의 치수 표시 group으로 유지되어야 한다.
* label이 해당 group과 함께 움직여야 한다.
* target_anchor_start/end가 의미상 길이 범위의 양 끝과 대응되어야 한다.
* 단순 highlight_curve로 자동 변환하면 안 된다.

### arrow

허용:

* start/end handle drag
* arrow head 방향 선택
* label drag
* 색상 변경

### box / circle

허용:

* resize
* move
* 색상 변경
* 두께 조정

### angle_mark

허용:

* vertex drag
* start ray/end ray handle drag
* radius 조정
* label drag
* 색상 변경

### graph_point

허용:

* point drag
* label drag
* 그래프 곡선/축으로 snap
* 색상 변경

### graph_curve / graph_tangent

허용:

* control point drag
* endpoint drag
* tangent point drag
* 색상 변경

### shaded_area

허용:

* polygon handle drag
* opacity 조정
* 색상 변경
* label drag

### freehand_annotation

허용:

* move
* scale
* opacity 조정
* needs_review 유지
* 사용자가 직접 redraw

### unsupported_annotation

허용:

* source crop 확인
* 사용자에게 “원본 필기 그대로 유지” 또는 “수동 편집” 선택 제공

<a id="section-8-4"></a>
## 8.4 Snapping 규칙

사용자가 endpoint나 anchor를 드래그할 때 가능한 경우 자동 snap을 제공한다.

snap 후보:

1. 인쇄 도형의 점
2. 손풀이에서 감지된 점
3. 선분의 endpoint
4. 축 눈금
5. 그래프 교점
6. 원/호 위의 점
7. 기존 annotation의 endpoint
8. bbox corner
9. 수식 라인의 baseline

단, snap은 강제하지 않는다.
사용자는 Alt/Option 또는 별도 toggle로 free drag를 사용할 수 있어야 한다.

<a id="section-8-5"></a>
## 8.5 검수 UI 원칙

사용자에게 보여줄 항목은 최대한 적게 유지한다.

좋은 예:

```text
검토 필요 2개

1. 이 파란 치수선의 끝점이 맞나요?
   [원본 확대] [결과 확대]
   [맞음] [끝점 조정]

2. 이 수식이 맞나요?
   AI 인식: g(θ)=1/2×tan³θ
   후보 A: g(θ)=1/2×tan²θ
   후보 B: g(θ)=1/2×tan³θ
   [A 선택] [B 선택] [직접 수정]
```

나쁜 예:

```text
secθ의 대응 선분을 입력하세요.
```

<a id="section-8-6"></a>
## 8.6 수정 방식

수정은 기본적으로 spec 수정이다.

* 표시선 범위 수정 → geometry endpoint 변경
* 치수선 범위 수정 → target_anchor_start/target_anchor_end 변경
* 치수선 위치 수정 → visible_start/visible_end/control_points/visible_strokes 변경
* 강조선 추가/삭제 → element 추가/삭제
* 수식 수정 → formula_line text 변경
* 색상 변경 → color 변경
* 위치 조정 → bbox 또는 geometry 변경

단순 수정은 AI 이미지 재생성 없이 deterministic renderer로 반영한다.

<a id="section-8-7"></a>
## 8.7 AI 재호출이 필요한 경우

다음 경우에만 AI 재호출을 고려한다.

* 손풀이 인식 자체가 불확실한 경우
* 사용자가 “다시 분석”을 요청한 경우
* 레이아웃 충돌이 심한 경우
* 시스템 내장 스타일 프리셋 적용 품질이 낮은 경우
* 하단 풀이 전체 재배치가 필요한 경우
* unsupported_annotation을 구조화 primitive로 다시 분해하려는 경우
* 자동 self-revision loop에서 부분 재생성이 필요하다고 판단한 경우

<a id="section-8-8"></a>
## 8.8 HITL Escalation Policy

HITL 노출은 다음 단계 이후에만 발생한다.

```text
1. Candidate spec 추출
2. Spec validation
3. Source-to-spec validation
4. Render preview
5. Render-to-source validation
6. 자동 보정 가능 여부 판단
7. 필요 시 second-pass AI validation
8. correction plan 생성
9. 자동 수정/재렌더링 또는 부분 재생성
10. 재검수
11. 그래도 불확실성이 남고, 결과 품질에 큰 영향을 줄 때만 사용자에게 노출
```

### 8.8.1 자동 통과

다음 조건을 만족하면 사용자에게 묻지 않는다.

```text
- confidence가 충분히 높다.
- source-to-spec validation에서 충돌이 없다.
- render-to-source validation에서 큰 차이가 없다.
- 해당 element가 결과 품질에 중대한 영향을 주지 않는다.
```

### 8.8.2 내부 재검증

다음 경우에는 사용자에게 바로 묻지 말고 내부 재검증을 수행한다.

```text
- OCR 후보가 2개 이상이지만 하나가 명확히 우세한 경우
- 치수선 endpoint가 약간 애매하지만 source crop과 render crop 비교로 해결 가능한 경우
- 색상이나 stroke continuity가 애매하지만 결과 의미에는 영향이 작은 경우
```

### 8.8.3 자동 수정 우선 조건

다음 경우는 HITL보다 자동 수정이 우선이다.

```text
- candidate spec에는 존재하지만 preview에서 누락된 element
- label 위치가 group과 분리된 경우
- 치수선 visible stroke가 target anchor와 명백히 어긋난 경우
- 색상 또는 stroke thickness가 원본과 명백히 다른 경우
- 수식 OCR 후보 중 하나가 source crop 검증에서 명확히 우세한 경우
- 원본 문제 인쇄 영역이 preview에서 훼손된 경우
```

### 8.8.4 사용자 노출 조건

다음 경우에만 사용자에게 노출한다.

```text
- 수식 값, 지수, 부호, 분모/분자 등 의미가 바뀔 수 있는 경우
- 치수선 target_anchor_start/end가 틀리면 풀이 의미가 바뀌는 경우
- 도형 주석의 범위가 잘못되어 학생이 다른 선분/구간으로 이해할 가능성이 큰 경우
- 원본 손풀이의 핵심 annotation이 누락되었는데 자동 복원이 불확실한 경우
- 자동 수정 후보들이 서로 충돌하고 confidence 차이가 작을 경우
- 자동 self-revision loop를 max_revision_attempts만큼 수행해도 통과하지 못한 경우
```

### 8.8.5 Review item budget

한 job에서 사용자에게 노출하는 review item 수는 제한한다.

```text
- 기본 목표: 0개
- 일반 허용: 최대 3개
- 3개를 초과하면 개별 질문을 모두 보여주지 말고 “정밀 검수 모드”로 묶는다.
```

정밀 검수 모드는 MVP 필수 기능이 아니다.
MVP에서는 3개 초과 시 우선순위가 높은 항목만 보여주고 나머지는 internal warning으로 남긴다.

### 8.8.6 Review 우선순위

우선순위는 다음 순서로 높다.

```text
1. 수식 의미 오류 가능성
2. 치수선 target range 오류 가능성
3. 도형/그래프 핵심 주석 누락
4. 선분/화살표 endpoint 오류
5. 라벨 위치로 인한 의미 오해
6. 색상 차이
7. 미학적 품질 이슈
```

---

<a id="section-9"></a>
# 9. 검증 설계

<a id="section-9-1"></a>
## 9.1 Spec validation

Spec 생성 후 바로 렌더링하지 않는다.

검증 단계에서 다음을 확인한다.

* 필수 필드 존재 여부
* bbox가 이미지 범위를 벗어나지 않는지
* confidence가 낮은 항목이 needs_review로 표시되었는지
* formula_line의 text와 display_text가 충돌하지 않는지
* 색상값이 허용 목록에 있는지
* geometry가 유효한지
* source evidence가 존재하는지
* unknown 필드가 있는 경우 사용자 검수 대상으로 올라갔는지
* style.source가 초기 MVP 기준 `system_builtin`인지
* style.preset_id와 style.preset_version이 존재하는지
* dimension_line/dimension_curve/freehand_dimension_marker의 target_anchor_start/end가 존재하는지
* dimension 계열 element에 label이 있는 경우 label_anchor가 존재하는지
* unsupported_annotation이 버려지지 않고 HITL 또는 internal warning으로 올라가는지

<a id="section-9-2"></a>
## 9.2 Source-to-spec validation

원본 손풀이 이미지와 candidate spec을 다시 비교한다.

질문 예시:

```text
이 candidate spec은 teacher_solution_image의 필기 요소를 충실히 반영하는가?
누락된 수식, 잘못된 색상, 잘못된 표시선 범위, 과잉추론된 annotation이 있는가?
치수선의 양 끝은 원본 필기에서 의도한 범위의 양 끝과 대응되는가?
```

출력은 validation report JSON으로 저장한다.

<a id="section-9-3"></a>
## 9.3 Render-to-source validation

렌더링 결과와 원본 손풀이 이미지를 비교한다.

검수 항목:

* 수식 텍스트 일치
* 수식 줄 순서 일치
* 색상 일치
* 도형 annotation 누락 여부
* 강조선/화살표 위치의 큰 오류
* 치수선 endpoint와 target range 정합성
* 곡선 치수선의 양 끝 alignment
* 라벨과 표시 범위의 의미 불일치
* 원본 문제 인쇄 영역 훼손 여부
* 시스템 내장 스타일 프리셋과의 유사성
* 사용자가 승인한 수정사항 반영 여부
* freehand_dimension_marker가 highlight_curve로 잘못 렌더링되지 않았는지
* 치수선의 target_anchor_start/end가 원본에서 의도한 구간 양 끝과 대응되는지
* visible stroke가 target range 전체를 암시하는지
* 곡선 치수선이 타겟 구간의 중간 일부만 표시하는 것처럼 보이지 않는지
* label이 치수선 group에 포함되어 원본과 같은 의미 단위를 형성하는지
* fragmented stroke 형태의 치수선을 지나치게 매끈한 단일 곡선으로 바꿔 의미나 위치가 변하지 않았는지

치수선 검수는 label 텍스트 일치만으로 통과할 수 없다.
label이 맞아도 치수선의 span과 endpoint가 틀리면 실패로 처리한다.

<a id="section-9-4"></a>
## 9.4 Auto-revision validation

자동 수정/재렌더링 후에는 반드시 재검수를 수행한다.

검증 기준:

```text
1. 이전 validation report의 high severity issue가 해결되었는가?
2. correction plan이 의도한 element만 수정했는가?
3. 수정하지 않은 element가 흔들리거나 바뀌지 않았는가?
4. 원본 문제 이미지가 훼손되지 않았는가?
5. 사용자 승인 사항이 덮어써지지 않았는가?
6. 새 오류가 발생하지 않았는가?
```

자동 수정이 기존 정상 요소를 악화시키면 해당 revision은 실패로 처리한다.

---

<a id="section-10"></a>
# 10. 렌더링 전략

<a id="section-10-1"></a>
## 10.1 원칙

최종 이미지를 매번 통째로 AI 이미지 생성 모델에 맡기지 않는다.

기본 전략:

```text
원본 문제 이미지는 그대로 보존
+ 확정된 overlay elements를 렌더링
+ 시스템 내장 예쁜 손글씨 스타일 텍스트를 합성
+ 최종 이미지 export
```

<a id="section-10-2"></a>
## 10.2 렌더링 방식 선택

초기 구현의 기본 방향은 다음이다.

```text
Client editor:
React + TypeScript + Konva 또는 Fabric.js 계열 canvas editor

Canonical overlay model:
JSON candidate spec + SVG-compatible geometry model

Server export:
SVG/Canvas composition을 PNG/PDF로 export
구체 구현은 Codex/Superpowers가 검토하여 Sharp, Playwright, Pillow 중 선택
```

이 선택의 이유:

1. HITL에서 endpoint drag, anchor drag, control point drag가 필요하다.
2. 치수선, 곡선, 화살표, 박스, 그래프 annotation은 interactive handle이 필요하다.
3. deterministic re-render가 가능해야 한다.
4. 사용자가 수정한 geometry가 spec에 정확히 반영되어야 한다.
5. 전체 이미지를 AI로 재생성하면 수정하지 않은 부분이 흔들릴 수 있다.

<a id="section-10-3"></a>
## 10.3 AI 이미지 생성과 렌더링의 차이

이전 원샷 테스트에서 얻은 예쁜 글씨체는 **이미지 생성 모델이 스타일을 반영해 전체 이미지를 새로 그린 결과**에 가깝다.

이 문서에서 말하는 renderer는 그와 다르다.

Renderer의 역할:

```text
확정된 spec을 기반으로
원본 이미지 위에
오버레이 요소를 정확한 위치에
재현 가능하게 합성하는 것
```

AI 이미지 생성의 역할:

```text
시스템 내장 스타일 프리셋을 참고하여
손글씨 스타일 초안 또는 텍스트/수식 스타일 asset을 생성하는 것
```

따라서 CleanSolve Studio는 다음 하이브리드 전략을 사용한다.

1. geometry, endpoint, 치수선, 화살표, 박스, 라벨 위치는 deterministic renderer가 담당한다.
2. 예쁜 손글씨 스타일은 시스템 내장 스타일 프리셋과 AI handwriting/style renderer가 담당한다.
3. 최종 합성은 spec 기반 renderer가 담당한다.
4. 단순 수정 시 전체 AI 이미지 재생성을 하지 않는다.
5. AI 생성 결과는 style asset 또는 preview로 활용할 수 있으나, 최종 위치 정합성의 기준은 candidate spec이다.

AI 원샷 이미지 생성이 보여준 예쁜 글씨체는 중요한 스타일 기준이다.
그러나 위치 정합성, 치수선 endpoint, 라벨 group, 도형 annotation의 정확성은 deterministic spec renderer가 담당해야 한다.

따라서 손글씨 스타일 품질을 얻기 위해 전체 이미지를 매번 AI로 재생성하는 구조를 기본값으로 삼지 않는다.

권장 구조:

1. AI는 예쁜 손글씨 스타일 asset 또는 preview를 생성한다.
2. Candidate spec은 수식, 라벨, 치수선, 화살표, box, curve의 위치와 의미를 관리한다.
3. Renderer는 확정된 spec을 원본 이미지 위에 합성한다.
4. 단순 수정은 spec patch + deterministic re-render로 처리한다.
5. 스타일 품질이 낮은 경우에만 해당 text/formula asset 단위로 AI 재생성을 고려한다.

<a id="section-10-4"></a>
## 10.4 손글씨 스타일 처리

초기 MVP에서는 완전한 개인화 필기체 학습을 목표로 하지 않는다.

초기 MVP의 스타일 기준은 사용자가 업로드하는 이미지가 아니다.
서비스 운영자가 사전에 등록한 **시스템 내장 손글씨 스타일 프리셋**을 사용한다.

가능한 방식:

1. 시스템 내장 예쁜 손글씨 스타일 폰트 또는 handwriting-like font
2. 운영자가 등록한 스타일 기준 이미지를 내부 asset으로 보관하고, 이미지 생성 API 호출 시 컨텍스트로 사용
3. 이미지 생성 API를 이용한 시스템 내장 스타일 참고 기반 텍스트/수식 asset 렌더링
4. 수식은 LaTeX/KaTeX 기반으로 정확히 렌더링하고, 주변 주석만 손글씨 스타일 적용
5. 장기적으로 여러 시스템 스타일 preset 도입
6. 장기적으로 사용자 지정 스타일 업로드 또는 개인별 스타일 학습 검토

정확도가 필요한 수식은 미학보다 정확성을 우선한다.

<a id="section-10-5"></a>
## 10.5 재렌더링과 재생성의 우선순위

오류 수정 시 우선순위는 다음이다.

```text
1. spec patch
2. deterministic partial re-render
3. handwriting asset partial regeneration
4. limited image edit
5. full image regeneration
6. HITL
```

전체 이미지 재생성은 비용이 크고, 멀쩡한 영역이 흔들릴 수 있으므로 기본 경로가 아니다.

---

<a id="section-11"></a>
# 11. OpenAI API 사용 원칙

<a id="section-11-1"></a>
## 11.1 Responses API 용도

Responses API는 다음에 사용한다.

* 이미지 분석
* 손글씨 OCR 보조
* 수식/텍스트 추출
* candidate spec JSON 생성
* validation report 생성
* correction plan 생성
* 자동 수정 후 재검수
* 사용자 수정 후 재검수
* 생성 결과 검수

<a id="section-11-2"></a>
## 11.2 Images API 또는 image generation tool 용도

이미지 생성/편집 API는 다음에 사용한다.

* 초기 고품질 미리보기 생성
* 시스템 내장 스타일 프리셋을 반영한 시각적 초안 생성
* 복잡한 손글씨 스타일 변환
* deterministic renderer로 처리하기 어려운 자연스러운 필기 재배치
* 텍스트/수식 블록의 손글씨 스타일 asset 생성
* 자동 self-revision loop에서 필요한 부분 재생성 또는 제한적 재편집

단, 단순 수정마다 전체 이미지를 재생성하지 않는다.

초기 MVP에서는 이미지 생성/편집 API 호출에 사용되는 스타일 기준이 사용자 업로드 이미지가 아니라, 시스템 내부 asset 또는 preset id로 관리되는 기본 스타일이다.

<a id="section-11-3"></a>
## 11.3 모델 호출 원칙

* 분석 결과는 가능하면 JSON schema로 제한한다.
* 불명확하면 추측하지 말고 unknown/null과 needs_review=true를 사용한다.
* 모델 출력은 항상 서버 검증을 통과해야 한다.
* 검증 실패 시 먼저 correction plan을 생성한다.
* 자동 수정 가능한 오류는 HITL 전에 자동 수정/재렌더링한다.
* 모델이 생성한 결과는 원본 이미지와 다시 비교한다.
* 스타일 기준은 초기 MVP에서 `system_builtin` 프리셋만 사용한다.
* 자동 self-revision loop는 무한 반복하지 않는다.

---

<a id="section-12"></a>
# 12. 상태 관리

<a id="section-12-1"></a>
## 12.1 Job 상태

작업 단위는 `Job`이다.

상태 예시:

```text
CREATED
IMAGES_UPLOADED
STYLE_PRESET_LOADED
ANALYZING
SPEC_EXTRACTED
SPEC_VALIDATING
RENDERING
RENDERED
INSPECTING
CORRECTION_PLANNING
AUTO_REVISING
RE_RENDERING
RE_INSPECTING
NEEDS_REVIEW
REVISION_REQUIRED
APPROVED
EXPORTED
FAILED
```

<a id="section-12-2"></a>
## 12.2 저장해야 할 산출물

각 Job은 다음을 저장한다.

```text
original_problem_image
teacher_solution_image
system_style_preset_id
system_style_preset_version
candidate_spec_v1.json
spec_validation_report_v1.json
rendered_preview_v1.png
image_validation_report_v1.json
correction_plan_v1.json
candidate_spec_v2.json
rendered_preview_v2.png
image_validation_report_v2.json
user_edits_v1.json
candidate_spec_v3.json
rendered_preview_v3.png
final_output.png
final_output.pdf
```

원본 이미지는 절대 덮어쓰지 않는다.

시스템 내장 스타일 프리셋 자체는 Job마다 업로드 파일로 저장하지 않는다.
Job에는 해당 작업에 사용된 `system_style_preset_id`와 `system_style_preset_version`을 기록한다.

<a id="section-12-3"></a>
## 12.3 Revision 기록

모든 자동 수정과 사용자 수정은 revision으로 기록한다.

Revision에는 다음을 저장한다.

```text
revision_id
revision_type: auto | human
source_preview_id
input_validation_report_id
correction_plan_id
changed_elements
before_spec_version
after_spec_version
result_preview_id
result_validation_report_id
pass_or_fail
```

이 기록은 나중에 품질 분석과 오류 재현에 사용한다.

---

<a id="section-13"></a>
# 13. Quality Harness / Evaluation Harness

Codex/Superpowers는 초기 scaffold 과정에서 테스트와 검증 harness를 반드시 고려한다.

초기 harness는 다음 목적을 가진다.

1. candidate spec schema validation
2. primitive별 renderer validation
3. dimension_line/dimension_curve/freehand_dimension_marker endpoint validation
4. user patch 적용 검증
5. deterministic re-render 결과 검증
6. source-to-spec validation mock 테스트
7. render-to-source validation mock 테스트
8. visual regression snapshot 테스트
9. fixture 기반 오류 재현 테스트
10. freehand_dimension_marker 분류 검증
11. dimension_curve와 highlight_curve 구분 검증
12. 치수선 target_anchor_start/end 정합성 검증
13. visible stroke와 target anchor alignment 검증
14. HITL 노출률 측정
15. review item 개수 budget 검증
16. correction plan 생성 검증
17. automatic self-revision loop 검증
18. auto-revision 후 regression 검증
19. max_revision_attempts 제한 검증

초기 fixture는 소수의 샘플로 시작한다.

fixture 구성 예시:

```text
problem_image
teacher_solution_image
expected_partial_spec.json
expected_review_items.json
expected_render_constraints.json
expected_correction_plan.json
expected_final_constraints.json
```

이 harness는 완전한 수학 정답 검증기가 아니다.
목표는 손풀이 시각 요소의 추출·검수·렌더링·자동수정 파이프라인이 깨지지 않게 하는 것이다.

초기 fixture set에서 사용자 검수 노출률을 측정한다.

목표:

```text
- requires_human_review=true job 비율 ≤ 20%
- job당 노출 review item 평균 ≤ 1
- review item 3개 초과 job은 실패 또는 warning 처리
- auto-correctable issue의 자동 수정 성공률 측정
- auto-revision 후 기존 정상 element regression 발생률 측정
```

단, 이 수치는 MVP의 품질 방향을 잡기 위한 목표이다.
초기 fixture 수가 적을 때는 절대 지표로 과신하지 않는다.

---

<a id="section-14"></a>
# 14. 권장 기술 방향

<a id="section-14-1"></a>
## 14.1 기본 방향

Frontend:

```text
React
TypeScript
Konva 또는 Fabric.js 계열 canvas editor
Tailwind CSS or equivalent
```

Backend:

```text
Python FastAPI 또는 Node.js/NestJS
OpenAI API client
PostgreSQL
Object storage compatible file storage
```

Rendering/export:

```text
Client-side interactive canvas editor
Canonical JSON/SVG-compatible geometry model
Server-side export to PNG/PDF
```

Workflow:

```text
초기부터 LangGraph 또는 Codex/Superpowers가 추천한 유사 workflow orchestrator 사용
```

<a id="section-14-2"></a>
## 14.2 Codex/Superpowers가 결정해야 할 것

다음은 이 SoT가 강제하지 않는다.

1. FastAPI와 NestJS 중 최종 선택
2. Konva와 Fabric.js 중 최종 선택
3. Sharp, Playwright, Pillow 중 export 구현 선택
4. LangGraph와 유사 orchestrator 중 최종 선택
5. 실제 repository 디렉터리 구조
6. test runner와 lint 도구
7. 세부 implementation plan

단, 결정 이유는 `DECISIONS.md`에 기록한다.

<a id="section-14-3"></a>
## 14.3 초기에는 과한 도입을 피할 것

초기부터 다음을 과도하게 도입하지 않는다.

* Temporal
* 복잡한 multi-agent runtime
* 자체 학습 모델
* 대규모 분산 처리
* 완전한 Figma 수준 에디터
* 결제/계정/권한 시스템

---

<a id="section-15"></a>
# 15. Repository 산출물 요구사항

Codex/Superpowers가 repository 구조를 자유롭게 제안할 수 있다.

단, 초기 repository에는 최소한 다음 범주의 산출물이 있어야 한다.

```text
README
SoT 문서
ASSUMPTIONS 문서
DECISIONS 문서
Workflow 설계 문서
HITL UX 설계 문서
Candidate spec schema
Validation report schema
Correction plan schema
Style preset asset 저장 위치
Sample image fixture 저장 위치
Renderer prototype
OpenAI adapter interface
Mock analysis client
Workflow orchestrator prototype
테스트/harness
```

초기 MVP에서는 사용자 지정 style upload directory를 만들지 않는다.
시스템 내장 style preset asset만 둔다.

---

<a id="section-16"></a>
# 16. Codex/Superpowers 작업 원칙

Codex는 이 SoT를 새 세션의 최상위 요구사항으로 받아 프로젝트를 세팅한다.

작업 원칙:

1. 먼저 Superpowers의 brainstorming/planning 흐름을 사용한다.
2. 바로 대규모 코드를 생성하지 않는다.
3. 이 SoT를 읽고 제품/아키텍처 이해를 정리한다.
4. 불명확한 점은 `ASSUMPTIONS.md`에 기록한다.
5. 구현 결정은 `DECISIONS.md`에 기록한다.
6. scaffold는 Superpowers가 제안한 계획에 따라 만든다.
7. 테스트 가능한 작은 단위로 구현한다.
8. HITL과 renderer는 제품 핵심이므로 mock이라도 동작하는 골격을 먼저 만든다.
9. 자동 self-revision loop는 제품 품질의 핵심이므로 mock이라도 workflow에 포함한다.
10. SoT와 충돌하는 기능은 구현하지 않는다.
11. 사용자가 요청하지 않은 결제/로그인/대량 처리 기능을 추가하지 않는다.

---

<a id="section-17"></a>
# 17. 금지 사항

Codex는 다음을 하지 않는다.

1. 원본 이미지를 덮어쓰기
2. JSON을 진짜 SoT처럼 취급하기
3. 불확실한 내용을 확정값처럼 저장하기
4. 모든 수학 문제를 완벽히 푸는 엔진을 만들려고 하기
5. 처음부터 전체 고등수학 범위를 완전 자동화하려 하기
6. 사용자에게 수학적 점 이름이나 선분명을 직접 입력하게 하는 UX를 기본으로 설계하기
7. 수정할 때마다 전체 이미지를 무조건 AI로 재생성하는 구조로 만들기
8. 이미지 생성 모델만으로 최종 품질을 보장하려 하기
9. 샘플 하나에 과적합한 데이터 구조 만들기
10. 임의로 결제, 로그인, 배포, 대량 처리 기능을 추가하기
11. 초기 MVP에서 사용자 지정 손글씨 스타일 이미지 업로드 기능을 구현하기
12. 시스템 내장 스타일 프리셋을 Job별 사용자 업로드 파일처럼 취급하기
13. element type 목록을 완전한 전체 목록처럼 취급하기
14. 치수선 endpoint 정합성 검증 없이 preview를 통과시키기
15. 클릭/드래그 UX를 element별 interaction policy 없이 뭉뚱그려 구현하기
16. needs_review=true인 모든 항목을 무조건 사용자에게 노출하기
17. 치수선과 highlight를 구분하지 않고 하나의 curve annotation으로 처리하기
18. label만 맞으면 치수선 검수를 통과시키기
19. 사용자 검수 질문이 과도하게 발생하는 UX를 기본 경로로 설계하기
20. HITL을 품질 보증의 주된 수단으로 삼기
21. 자동 수정 가능한 오류를 곧바로 HITL로 넘기기
22. 자동 수정 루프를 무한 반복하기
23. correction plan 없이 임의로 재생성하기
24. 자동 수정 과정에서 사용자 승인 사항을 덮어쓰기
25. 전체 이미지 재생성을 기본 수정 전략으로 삼기

---

<a id="section-18"></a>
# 18. MVP 성공 기준

MVP 성공 기준:

1. 사용자가 원본 문제 이미지와 손풀이 이미지를 업로드할 수 있다.
2. 시스템이 기본 내장 손글씨 스타일 프리셋을 자동으로 로드할 수 있다.
3. 시스템이 candidate spec을 생성하거나 mock spec으로 처리할 수 있다.
4. candidate spec에 따라 원본 위에 overlay preview를 렌더링할 수 있다.
5. 하단 풀이 수식/텍스트를 재배치할 수 있다.
6. 도형 위 highlight/arrow/box/label을 표시할 수 있다.
7. dimension_line/dimension_curve의 endpoint와 anchor를 표현할 수 있다.
8. needs_review 항목을 내부 검증 대상으로 관리할 수 있다.
9. requires_human_review 항목만 사용자에게 노출할 수 있다.
10. 사용자가 element type별 허용된 클릭/드래그/선택 방식으로 수정할 수 있다.
11. 수정사항이 spec patch로 저장된다.
12. 수정 후 deterministic re-render가 된다.
13. 최종 이미지를 export할 수 있다.
14. 최소 fixture 기반 harness가 통과한다.
15. freehand-style 치수선을 dimension_curve 또는 freehand_dimension_marker로 표현할 수 있다.
16. 치수선의 target_anchor_start/end와 visible stroke를 분리해서 저장할 수 있다.
17. 치수선 label을 치수선 group의 일부로 관리할 수 있다.
18. 치수선 endpoint와 span 검증을 수행할 수 있다.
19. HITL은 기본 경로가 아니라 예외 경로로 동작한다.
20. fixture 기준 사용자 검수 노출률과 review item 개수를 측정할 수 있다.
21. 생성/렌더링 결과를 자동 검수할 수 있다.
22. 오류 발견 시 correction plan을 생성할 수 있다.
23. 자동 수정 가능한 오류는 spec patch 또는 부분 재렌더링으로 해결할 수 있다.
24. 자동 self-revision loop를 max_revision_attempts 내에서 수행할 수 있다.
25. 자동 수정 후 재검수를 수행할 수 있다.
26. 자동 수정 후 기존 정상 element가 흔들리지 않았는지 검증할 수 있다.

---

<a id="section-19"></a>
# 19. 최종 제품 방향

CleanSolve Studio는 장기적으로 다음 형태를 목표로 한다.

```text
수학 손풀이 전용 Canva
+ Math OCR
+ AI handwriting beautification
+ 시스템 내장 손글씨 스타일 프리셋
+ 구조화된 annotation editor
+ automatic self-revision loop
+ human-in-the-loop 검수
+ 원본 보존형 렌더링
```

핵심 경쟁력은 “AI가 예쁜 이미지를 한 번에 만들어주는 것”이 아니다.

핵심 경쟁력은 다음이다.

```text
수학 손풀이를 시각 요소 단위로 분해하고,
치수선·강조선·화살표·수식·라벨을 정확한 primitive로 관리하며,
결과를 스스로 검수하고,
자동 수정 가능한 오류는 사람에게 묻기 전에 고치고,
정말 필요한 경우에만 사용자에게 보여주며,
수정은 쉽고,
결과는 안정적으로 재렌더링하는 것.
```

특히 CleanSolve Studio는 치수선, 곡선 길이 표시, 분절 손필기 stroke, 라벨을 하나의 의미 group으로 다루어야 한다.

길이 표시선의 목적은 단순히 예쁜 선을 그리는 것이 아니라, 학생이 “어느 구간의 길이인지” 즉시 오해 없이 이해하도록 만드는 것이다.

따라서 치수선의 target endpoint, visible stroke, label 위치, group 관계는 최종 품질의 핵심 검증 대상이다.

이 원칙을 모든 구현의 기준으로 삼는다.
