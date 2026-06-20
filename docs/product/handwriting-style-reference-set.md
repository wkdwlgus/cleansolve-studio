# 손글씨 스타일 레퍼런스 세트

이 문서는 `default_pretty_handwriting v1` 스타일 캘리브레이션에 사용할 운영자 승인 레퍼런스 세트를 정의한다.

레퍼런스 이미지는 저장소에 커밋하지 않는다. 원본 파일은 로컬 `/image/clean_solutions` 아래에 있으며, `/image`는 용량 문제로 gitignore 대상이다.

## 확정 상태

- 상태: Approved
- 승인일: 2026-06-20
- 기준 corpus: `/image/clean_solutions/GT_001.png`부터 `/image/clean_solutions/GT_147.png`
- 분석 방식: 전체 contact sheet 검토, 잉크 밀도/색상 사용량 기초 지표, 스타일 축별 수동 검수
- 로컬 분석 산출물: `/image/style-reference-candidates`

## Core Reference Set

Core set은 스타일 분석 프롬프트, deterministic renderer 튜닝, style similarity gate의 기본 기준으로 사용한다.

| 샘플 | 역할 |
| --- | --- |
| `GT_024` | 빽빽한 기하 풀이, 도형 위 색상 보조선, 높은 잉크 밀도 기준 |
| `GT_036` | 여백이 큰 단일 적분 문제, 큰 수식 간격과 줄바꿈 기준 |
| `GT_043` | 긴 다단계 풀이, 작은 글씨와 색상 강조가 섞인 고밀도 레이아웃 |
| `GT_049` | 좌표 그래프, 면적 해칭, 파란색 주석 기준 |
| `GT_058` | 함수 그래프와 구간 표시, 그래프 아래 보조 도형 기준 |
| `GT_067` | 기하 도형 안 라벨, 보조선, 면적 계산 전개 기준 |
| `GT_073` | 곡선 그래프, 반복 해칭, 색상 곡선 주석 기준 |
| `GT_079` | 큰 적분 기호, 루트/분수 수식의 손글씨 질감 기준 |
| `GT_082` | 큰 좌표축 위 그래프, 도형과 옆 주석이 분리된 구성 기준 |
| `GT_086` | 한글 설명과 수식 전개가 섞인 문단형 풀이 기준 |
| `GT_090` | 점근선형 그래프, 그림 아래 compact 수식 전개 기준 |
| `GT_099` | 붉은 박스 강조, 색상별 수식 계층, 삼각함수 전개 기준 |
| `GT_102` | 원/삼각형 기하, 높은 파란색 사용량, 라벨 밀도 기준 |
| `GT_116` | 큰 기하 도형과 sparse 풀이의 균형 기준 |
| `GT_132` | 가장 높은 잉크 밀도 구간의 기하+수식 혼합 기준 |
| `GT_135` | 색상 보조선이 많은 기하 풀이, 빨강/파랑 교정 표기 기준 |
| `GT_141` | 긴 도형 풀이와 색상 수식 블록의 하단 배치 기준 |
| `GT_146` | 도형 없는 긴 기호 전개, 극한/함수식 줄맞춤 기준 |
| `GT_147` | 단계형 텍스트+수식 풀이, 색상별 결론 정리 기준 |

## Extended Calibration Set

Extended set은 core set으로 부족한 사례를 보완하거나, 스타일 튜닝 후 회귀 검사용으로 사용한다.

`GT_001`, `GT_003`, `GT_009`, `GT_010`, `GT_019`, `GT_023`, `GT_028`, `GT_037`, `GT_056`, `GT_063`, `GT_075`, `GT_080`, `GT_088`, `GT_091`, `GT_094`, `GT_101`, `GT_104`, `GT_117`, `GT_122`, `GT_129`, `GT_131`, `GT_134`, `GT_137`, `GT_140`, `GT_142`, `GT_145`

## 스타일 특징

- 기본 검정 필기는 얇지만 완전히 균일하지 않고, 획 끝에 약한 흔들림이 있다.
- 파란색은 핵심 계산, 도형 라벨, 결론 정리에 자주 쓰인다.
- 빨강/주황색은 보조선, 치환, 강조 식, 오류 방지용 주석에 쓰인다.
- 한글 설명은 정자체보다 약간 눌린 손글씨에 가깝고, 수식보다 과하게 크지 않다.
- 수식은 조판 수식처럼 완전히 정렬되지 않고, 기준선과 간격이 약간 흔들린다.
- 도형 주석은 원본 인쇄 선 위에 얇고 빠르게 얹은 느낌을 유지한다.
- 해칭은 촘촘하고 규칙적이지만, 간격과 기울기에 약한 변동이 있다.

## 다음 작업 입력 계약

Style Lab 작업은 이 문서의 core set을 기본 입력으로 사용해야 한다.

다음 작업자는 임의로 다른 샘플을 core set에 추가하거나 제외하지 않는다. 변경이 필요하면 별도 사유를 문서화하고 사용자 승인을 받은 뒤 이 문서를 갱신한다.

Style Lab은 다음 산출물을 만들어야 한다.

- `default_pretty_handwriting v1` style token schema
- core set 기반 canonical style sample sheet
- renderer가 사용할 색상, 획 두께, baseline, spacing, jitter 파라미터 초안
- 한글/수식/도형 주석이 같은 손글씨 계열처럼 보이는지 확인하는 style similarity gate 초안

## Style Lab 실행

승인된 레퍼런스 세트는 Style Lab의 기본 입력이다.

```bash
python -m tools.style_lab.cli build \
  --image-root image/clean_solutions \
  --output-root image/style-lab/default_pretty_handwriting/v1
```

생성되는 산출물은 다음과 같다.

- `image/style-lab/default_pretty_handwriting/v1/core_contact_sheet.jpg`
- `image/style-lab/default_pretty_handwriting/v1/extended_contact_sheet.jpg`
- `image/style-lab/default_pretty_handwriting/v1/calibration_manifest.json`
- `image/style-lab/default_pretty_handwriting/v1/style_tokens.skeleton.json`
- `image/style-lab/default_pretty_handwriting/v1/metrics.csv`

이 산출물은 `/image` 아래에 생성되므로 git에 커밋하지 않는다.
