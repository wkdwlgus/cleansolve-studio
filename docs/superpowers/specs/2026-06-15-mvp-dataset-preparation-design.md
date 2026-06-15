# 로컬 MVP 데이터 매칭 스크립트 설계

Date: 2026-06-15
Status: Approved

## 목적

`image/`에 들어 있는 로컬 대용량 자료를 빠르게 문제 단위 pilot 샘플로 맞춰본다. 이 작업은 제품 기능 개발이 아니라 M2 전에 데이터를 정리해보는 로컬 작업이다.

## 입력

```text
image/
  original_pages/          원본 PDF 5개
  clean_solution_pages/    이쁜 손글씨 풀이 페이지 PDF 5개
  teacher_solutions/       B_001.png ~ B_147.png
  clean_solutions/         GT_001.png ~ GT_147.png
```

`B_###`와 `GT_###`는 같은 번호끼리 한 문제 단위 쌍으로 본다. 이 번호는 실제 문제 번호가 아니라 crop 순번이다.

## git 관리

아래는 커밋하지 않는다.

```text
image/
var/datasets/
.superpowers/
```

구현 첫 단계에서 `.gitignore`에 아래를 추가한다.

```gitignore
/image/
/.superpowers/
```

`var/`는 이미 ignore되어 있다.

## 출력

pilot 결과만 먼저 만든다.

```text
var/datasets/pilot/
  samples/
    sample_001/
      original_page.png
      clean_solution_page.png
      problem_crop.png
      teacher_solution.png
      clean_solution.png
      metadata.json
  review_needed/
    sample_020/
      ...
  contact_sheet.html
```

`samples/`는 자동 매칭 신뢰도가 높은 결과다.

`review_needed/`는 사람이 확인해야 하는 결과다.

## 매칭 방식

원본 PDF에서 직접 문제를 찾지 않는다. 대신 `GT_###.png`를 clean solution page PDF 안에서 template matching으로 찾는다. clean solution PDF와 original PDF는 page count가 같으므로, clean solution page에서 찾은 bbox를 같은 page index의 original page에 적용해 `problem_crop.png`를 만든다.

고정 PDF mapping:

| clean solution PDF | original PDF |
| --- | --- |
| `기말1.pdf` | `기말1 원본.pdf` |
| `기말2.pdf` | `기말2 원본.pdf` |
| `기말3 .pdf` | `기말3 원본.pdf` |
| `미적분3단원.pdf` | `미적분3단원 원본.pdf` |
| `미적분4단원.pdf` | `미적분4단원 원본.pdf` |

## 구현 범위

커밋할 파일은 최소화한다.

```text
.gitignore
tools/datasets/local_match_dataset.py
docs/superpowers/specs/2026-06-15-mvp-dataset-preparation-design.md
docs/superpowers/plans/2026-06-15-mvp-dataset-preparation.md
```

별도 패키지, 테스트 패키지, schema 모듈은 만들지 않는다.

## 스크립트 정책

스크립트는 아래 모드를 지원한다.

```bash
python tools/datasets/local_match_dataset.py --mode pilot
python tools/datasets/local_match_dataset.py --mode full
```

이번 작업에서는 `--mode pilot`만 실행한다. `--mode full`은 pilot contact sheet를 사람이 확인한 뒤에만 실행한다.

Pilot index:

```text
1, 2, 3, 10, 20, 30, 50, 80, 110, 147
```

Template matching 설정:

```text
render_dpi: 200
search_dpi: 80
padding: 24px
scales: 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15
method: foreground mask + cv2.TM_CCOEFF_NORMED
high confidence: score >= 0.55
medium confidence: 0.35 <= score < 0.55
low confidence: score < 0.35
ambiguous score delta: 0.03
```

탐색은 `search_dpi`로 수행하고, 저장되는 `original_page.png`, `clean_solution_page.png`, `problem_crop.png`는 `render_dpi` 기준으로 만든다.

최고 score와 2등 score 차이가 `0.03` 미만이면 confidence가 `high`여도 `review_needed/`에 쓴다.

`high`이면서 ambiguous가 아닌 결과만 `samples/`에 쓰고, 나머지는 `review_needed/`에 쓴다.

출력 폴더는 임시 폴더에 먼저 생성하고, pilot 생성이 모두 성공한 뒤에만 `var/datasets/pilot`을 교체한다.

## metadata

각 샘플은 아래 형태의 `metadata.json`을 가진다.

```json
{
  "sample_id": "sample_001",
  "source_index": 1,
  "matched_clean_pdf": "image/clean_solution_pages/기말1.pdf",
  "matched_original_pdf": "image/original_pages/기말1 원본.pdf",
  "matched_page_index": 0,
  "problem_bbox": {
    "x": 120,
    "y": 240,
    "width": 900,
    "height": 1500
  },
  "score": 0.94,
  "runner_up_score": 0.76,
  "ambiguous": false,
  "confidence": "high",
  "review_required": false
}
```

## 완료 기준

- `/image/`와 `/.superpowers/`가 ignore된다.
- `tools/datasets/local_match_dataset.py`가 있다.
- `--mode pilot`로 10개 샘플 후보가 생성된다.
- `var/datasets/pilot/contact_sheet.html`이 생성된다.
- `image/`와 `var/datasets/`는 git에 잡히지 않는다.
- full 147개 생성은 실행하지 않는다.
