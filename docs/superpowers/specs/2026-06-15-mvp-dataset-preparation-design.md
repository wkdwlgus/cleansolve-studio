# M2 준비용 MVP 데이터셋 정리 상세 설계

Date: 2026-06-15
Status: Proposed

## 1. 목적

이 작업의 목적은 사용자가 로컬 `image/` 폴더에 넣은 대용량 원본 자료를 M2 Candidate Spec Pipeline에서 사용할 수 있는 문제 단위 샘플 구조로 정리하는 것이다.

이 작업은 제품 기능 구현이 아니라 **로컬 데이터셋 준비 도구와 산출물 구조**를 만드는 작업이다. 전체 147개 이미지 데이터는 용량이 크므로 git에 커밋하지 않는다. 저장소에는 스크립트, 문서, schema만 커밋한다. 대표 샘플 이미지도 이 milestone에서는 커밋하지 않는다.

## 2. 현재 입력 구조

입력 root는 프로젝트 루트의 `image/`다.

```text
image/
  original_pages/
  clean_solution_pages/
  teacher_solutions/
  clean_solutions/
```

현재 확인된 입력은 아래와 같다.

- `image/original_pages/`: 원본 문제 PDF 5개
- `image/clean_solution_pages/`: 이쁜 손글씨 풀이 페이지 PDF 5개
- `image/teacher_solutions/`: `B_001.png`부터 `B_147.png`까지 147개
- `image/clean_solutions/`: `GT_001.png`부터 `GT_147.png`까지 147개

`B_###`와 `GT_###`는 같은 번호끼리 한 문제 단위 쌍으로 본다.

## 3. git 관리 원칙

아래 경로는 커밋하지 않는다.

```text
image/
var/datasets/
.superpowers/
```

이 작업의 implementation plan 첫 단계는 `.gitignore`에 아래 항목을 추가하는 것이다.

```gitignore
/image/
/.superpowers/
```

`var/`는 기존 `.gitignore`에 이미 포함되어 있으므로 별도 추가하지 않는다.

## 4. 출력 구조

전체 147개 정리 결과는 로컬 전용 경로에 생성한다.

```text
var/datasets/mvp_samples/
  sample_001/
    original_page.png
    clean_solution_page.png
    problem_crop.png
    teacher_solution.png
    clean_solution.png
    metadata.json
  sample_002/
    ...

var/datasets/mvp_review_needed/
  candidate_001/
    original_page.png
    clean_solution_page.png
    problem_crop_candidate.png
    teacher_solution.png
    clean_solution.png
    metadata.json
```

`mvp_samples/`에는 자동 매칭 신뢰도가 높은 결과만 둔다.

`mvp_review_needed/`에는 자동 매칭이 애매한 결과를 둔다. 이 경로의 파일은 사람이 확인한 뒤에만 `mvp_samples/`로 승격할 수 있다.

## 5. metadata schema

각 샘플의 `metadata.json`은 아래 shape를 따른다.

```json
{
  "sample_id": "sample_001",
  "source_index": 1,
  "teacher_solution_file": "image/teacher_solutions/B_001.png",
  "clean_solution_file": "image/clean_solutions/GT_001.png",
  "matched_source_pdf": "image/clean_solution_pages/기말1.pdf",
  "matched_original_pdf": "image/original_pages/기말1 원본.pdf",
  "matched_page_index": 0,
  "problem_bbox": {
    "x": 120,
    "y": 240,
    "width": 900,
    "height": 1500
  },
  "matching": {
    "method": "clean_solution_template_match",
    "score": 0.94,
    "confidence": "high",
    "review_required": false,
    "reason": null
  }
}
```

`matched_page_index`는 0-based page index다.

`problem_bbox`는 rendered page image pixel coordinate 기준이다.

`problem_bbox`는 template matching bbox에 padding을 적용한 최종 crop bbox다. Padding은 모든 방향에 `24px`을 적용한다. Padding 적용 후 page boundary를 벗어나는 좌표는 page boundary로 clamp한다.

`confidence`는 정확히 아래 셋 중 하나다.

```text
high
medium
low
```

`review_required` 규칙은 아래와 같다.

- `high`: `false`
- `medium`: `true`
- `low`: `true`

## 6. 핵심 매칭 전략

순번만으로 원본 문제를 매칭하지 않는다.

이유:

- 원본 PDF에는 여러 문제가 한 페이지에 있다.
- 한두 문제씩 풀이가 없을 수 있다.
- `B_001~147`, `GT_001~147`의 번호는 실제 문제 번호가 아니라 crop 순번이다.

대신 아래 전략을 사용한다.

1. `clean_solution_pages/*.pdf`를 page image로 렌더링한다.
2. `clean_solutions/GT_###.png`를 template으로 사용한다.
3. 각 `GT_###.png`가 어느 clean solution page의 어느 bbox에 가장 잘 맞는지 찾는다.
4. clean solution PDF와 원본 PDF는 아래 고정 mapping과 page count로 1:1 매칭한다.
5. clean solution page에서 찾은 bbox를 같은 page index의 original page image에 적용한다.
6. 그 bbox로 `problem_crop.png`를 만든다.
7. `B_###.png`와 `GT_###.png`는 같은 번호끼리 그대로 복사한다.

이 전략은 원본 문제 페이지와 한 문제 풀이 crop의 순서가 중간에 어긋나도, `GT_###`가 clean solution page 안에서 직접 발견되면 매칭을 복구할 수 있다.

PDF pair mapping은 아래만 허용한다.

| clean solution PDF | original PDF |
| --- | --- |
| `기말1.pdf` | `기말1 원본.pdf` |
| `기말2.pdf` | `기말2 원본.pdf` |
| `기말3 .pdf` | `기말3 원본.pdf` |
| `미적분3단원.pdf` | `미적분3단원 원본.pdf` |
| `미적분4단원.pdf` | `미적분4단원 원본.pdf` |

## 7. PDF 렌더링 도구

PDF page 렌더링은 로컬 도구 스크립트에서 PyMuPDF를 사용한다.

프로젝트 runtime dependency에는 추가하지 않는다. 데이터셋 준비 전용 dependency로만 둔다.

구현 위치는 아래와 같다.

```text
tools/datasets/requirements.txt
tools/datasets/prepare_mvp_dataset.py
```

`tools/datasets/requirements.txt`는 아래 dependency를 포함한다.

```text
pymupdf
pillow
opencv-python
numpy
```

`prepare_mvp_dataset.py`는 위 dependency 중 하나라도 import할 수 없으면 아래 명령을 안내하고 종료한다.

```bash
python -m pip install -r tools/datasets/requirements.txt
```

PDF 렌더링 설정은 아래 고정값을 사용한다.

```text
render_dpi: 200
colorspace: RGB
output_format: PNG
```

## 8. Template matching 정책

Template matching은 clean solution page image와 `GT_###.png` 사이에서 수행한다.

절차:

1. PDF page를 `render_dpi=200`으로 렌더링한다.
2. page image와 template image를 grayscale로 변환한다.
3. template image는 아래 scale 후보로 resize해 각각 matching한다.
4. OpenCV `cv2.matchTemplate(..., cv2.TM_CCOEFF_NORMED)` score를 사용한다.
5. 모든 page와 scale 후보 중 score가 가장 높은 bbox를 후보로 채택한다.

Template scale 후보는 아래 순서로 고정한다.

```text
0.85
0.90
0.95
1.00
1.05
1.10
1.15
```

동일한 최고 score 후보가 2개 이상이고 score 차이가 `0.01` 미만이면 `review_required=true`로 처리한다.

초기 threshold는 아래 값으로 고정한다.

```text
high: score >= 0.86
medium: 0.72 <= score < 0.86
low: score < 0.72
```

threshold는 implementation 중 임의로 바꾸지 않는다. pilot 결과에서 부적합하면 별도 spec 수정으로 조정한다.

## 9. Pilot workflow

전체 147개를 한 번에 확정하지 않는다.

먼저 아래 subset만 처리한다.

```text
1, 2, 3, 10, 20, 30, 50, 80, 110, 147
```

pilot output은 아래 경로에 생성한다.

```text
var/datasets/pilot_mvp_samples/
var/datasets/pilot_review_needed/
```

pilot 완료 후 브라우저 companion으로 contact sheet를 생성해 확인한다.

contact sheet는 각 sample에 대해 아래를 나란히 보여준다.

```text
original_page thumbnail
problem_crop
teacher_solution
clean_solution
matching score/confidence
review_required
```

pilot에서 high confidence 결과가 눈으로도 맞는지 확인한 뒤에만 147개 전체 처리로 넘어간다.

## 10. 전체 처리 workflow

전체 처리 명령은 아래 형태로 둔다.

```bash
python tools/datasets/prepare_mvp_dataset.py --mode pilot
python tools/datasets/prepare_mvp_dataset.py --mode full
```

`--mode pilot`은 10개 subset만 처리한다.

`--mode full`은 147개 전체를 처리한다.

`--mode full`은 pilot 결과 review 없이 자동으로 실행하지 않는다. implementation plan에서는 pilot 검증을 별도 checkpoint로 둔다.

## 11. Error handling

아래 상황은 script가 실패하고 non-zero exit code를 반환한다.

- `image/`가 없다.
- 필수 하위 폴더가 없다.
- `B_001~B_147` 중 누락이 있다.
- `GT_001~GT_147` 중 누락이 있다.
- 원본 PDF 5개와 clean solution PDF 5개의 page count가 서로 맞지 않는다.
- PyMuPDF가 설치되어 있지 않다.

아래 상황은 실패가 아니라 `review_required=true`로 처리한다.

- template matching score가 `high` 미만이다.
- 최고 score와 2등 score의 차이가 `0.01` 미만이다.
- bbox가 page 경계 밖으로 보정되어야 한다.
- crop 결과가 비정상적으로 작거나 크다.

비정상 crop 기준은 아래와 같다.

- crop width가 page width의 `15%` 미만이다.
- crop height가 page height의 `8%` 미만이다.
- crop width가 page width의 `95%` 초과다.
- crop height가 page height의 `95%` 초과다.

## 12. Testing

자동 테스트는 실제 258MB `image/` 데이터에 의존하지 않는다.

테스트는 synthetic image를 사용해 아래를 검증한다.

- `B_001~B_147`, `GT_001~GT_147` 이름 검증
- PDF pair page count 검증 helper
- template matching helper가 page 안의 template 위치를 찾는지
- confidence threshold 분류
- metadata schema 생성
- `review_required` 분기

실제 `/image` 데이터 검증은 manual command로 분리한다.

## 13. Out of scope

이번 데이터셋 준비 작업에서 구현하지 않는 것:

- M2 candidate spec 생성
- OpenAI/OCR 기반 매칭
- 수학 문제 텍스트 이해
- web upload UI
- export 기능
- 전체 147개 결과 이미지 commit
- 대표 샘플 이미지 commit
- 사람이 검수한 결과를 자동으로 정답 처리하는 기능

## 14. Acceptance criteria

이 작업은 아래를 만족해야 완료로 본다.

- `/image/`와 `/.superpowers/`가 gitignore된다.
- `tools/datasets/prepare_mvp_dataset.py`가 있다.
- pilot mode가 지정된 10개 index를 처리한다.
- pilot 결과가 `var/datasets/pilot_mvp_samples/`와 `var/datasets/pilot_review_needed/`에 생성된다.
- 각 결과에는 `metadata.json`이 있다.
- browser companion으로 볼 수 있는 pilot contact sheet가 생성된다.
- 실제 대용량 `/image`와 `var/datasets` 결과는 git에 올라가지 않는다.
- unit test는 실제 `/image` 데이터 없이 통과한다.
- 전체 147개 처리는 pilot review 이후에만 수행한다.
