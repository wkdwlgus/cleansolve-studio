# Handwriting Style Lab Design

## 목적

Handwriting Style Lab은 `default_pretty_handwriting v1`을 실제 renderer 튜닝과 GPT-5.5 스타일 분석에 사용할 수 있도록, 승인된 손글씨 레퍼런스 세트를 소프트웨어 계약과 deterministic 산출물로 고정하는 개발 공간이다.

이번 milestone은 스타일을 완성하거나 AI 호출을 실행하지 않는다. 이번 milestone의 완료 기준은 다음 작업자가 같은 입력, 같은 출력 경로, 같은 manifest schema, 같은 sample sheet 생성 규칙을 사용하도록 만드는 것이다.

## 배경

`docs/product/handwriting-style-reference-set.md`에서 core 19개와 extended 26개 샘플이 승인되었다.

Core set:

`GT_024`, `GT_036`, `GT_043`, `GT_049`, `GT_058`, `GT_067`, `GT_073`, `GT_079`, `GT_082`, `GT_086`, `GT_090`, `GT_099`, `GT_102`, `GT_116`, `GT_132`, `GT_135`, `GT_141`, `GT_146`, `GT_147`

Extended set:

`GT_001`, `GT_003`, `GT_009`, `GT_010`, `GT_019`, `GT_023`, `GT_028`, `GT_037`, `GT_056`, `GT_063`, `GT_075`, `GT_080`, `GT_088`, `GT_091`, `GT_094`, `GT_101`, `GT_104`, `GT_117`, `GT_122`, `GT_129`, `GT_131`, `GT_134`, `GT_137`, `GT_140`, `GT_142`, `GT_145`

원본 레퍼런스 이미지는 로컬 `/image/clean_solutions`에 있고 `/image`는 gitignore 대상이다. 저장소에는 이미지 원본을 커밋하지 않는다.

## 범위

### 포함

1. `tools/style_lab/` Python package와 CLI entrypoint를 만든다.
2. 승인된 core/extended sample ID를 코드 상수와 JSON manifest로 고정한다.
3. 로컬 이미지 root를 입력받아 sample file 존재 여부와 이미지 metadata를 검증한다.
4. deterministic하게 core contact sheet와 extended contact sheet를 생성한다.
5. deterministic하게 style token skeleton JSON을 생성한다.
6. deterministic하게 calibration manifest JSON을 생성한다.
7. `assets/style-presets/default_pretty_handwriting/preset.json`에 calibration 상태와 산출물 계약을 기록한다.
8. fixture 기반 pytest로 `/image`가 없어도 검증 가능하게 만든다.
9. README류 문서는 한국어로 작성한다.

### 제외

1. GPT-5.5 API 호출 실행.
2. `gpt-image-2` asset 생성.
3. renderer의 실제 손글씨 품질 튜닝.
4. style similarity model 또는 image diff model 구현.
5. Web UI 연결.
6. Job runtime workflow 연결.
7. 사용자 지정 손글씨 style upload.

## 디렉터리와 파일

### 새 파일

- `tools/style_lab/__init__.py`
- `tools/style_lab/reference_set.py`
- `tools/style_lab/models.py`
- `tools/style_lab/image_metrics.py`
- `tools/style_lab/contact_sheet.py`
- `tools/style_lab/tokens.py`
- `tools/style_lab/manifest.py`
- `tools/style_lab/cli.py`
- `tools/style_lab/README.md`
- `tools/style_lab/tests/test_reference_set.py`
- `tools/style_lab/tests/test_image_metrics.py`
- `tools/style_lab/tests/test_contact_sheet.py`
- `tools/style_lab/tests/test_manifest.py`
- `tools/style_lab/tests/test_cli.py`

### 수정 파일

- `assets/style-presets/default_pretty_handwriting/preset.json`
- `docs/product/handwriting-style-reference-set.md`
- `pyproject.toml`
- `pytest.ini`

### 생성되지만 커밋하지 않는 파일

CLI 기본 실행 시 output root는 `/image/style-lab/default_pretty_handwriting/v1`이다.

생성 파일:

- `/image/style-lab/default_pretty_handwriting/v1/core_contact_sheet.jpg`
- `/image/style-lab/default_pretty_handwriting/v1/extended_contact_sheet.jpg`
- `/image/style-lab/default_pretty_handwriting/v1/calibration_manifest.json`
- `/image/style-lab/default_pretty_handwriting/v1/style_tokens.skeleton.json`
- `/image/style-lab/default_pretty_handwriting/v1/metrics.csv`

`/image`는 gitignore 대상이므로 이 산출물은 커밋하지 않는다.

## CLI 계약

명령:

```bash
python -m tools.style_lab.cli build \
  --image-root image/clean_solutions \
  --output-root image/style-lab/default_pretty_handwriting/v1
```

옵션:

- `--image-root`: `GT_024.png` 같은 레퍼런스 이미지가 들어 있는 directory. 기본값은 `image/clean_solutions`.
- `--output-root`: 산출물을 저장할 directory. 기본값은 `image/style-lab/default_pretty_handwriting/v1`.
- `--preset-id`: 기본값 `default_pretty_handwriting`.
- `--preset-version`: 기본값 `v1`.
- `--contact-sheet-width`: thumbnail cell width. 기본값 `320`.
- `--contact-sheet-height`: thumbnail cell height. 기본값 `460`.
- `--columns`: contact sheet column 수. 기본값 `5`.

성공 시 stdout은 한 줄 JSON이다.

```json
{
  "status": "ok",
  "preset_id": "default_pretty_handwriting",
  "preset_version": "v1",
  "core_count": 19,
  "extended_count": 26,
  "output_root": "image/style-lab/default_pretty_handwriting/v1",
  "artifacts": {
    "core_contact_sheet": "image/style-lab/default_pretty_handwriting/v1/core_contact_sheet.jpg",
    "extended_contact_sheet": "image/style-lab/default_pretty_handwriting/v1/extended_contact_sheet.jpg",
    "calibration_manifest": "image/style-lab/default_pretty_handwriting/v1/calibration_manifest.json",
    "style_tokens": "image/style-lab/default_pretty_handwriting/v1/style_tokens.skeleton.json",
    "metrics": "image/style-lab/default_pretty_handwriting/v1/metrics.csv"
  }
}
```

실패 시 exit code는 `2`이고 stderr에 사람이 읽을 수 있는 한 줄 오류를 출력한다.

오류 형식:

```text
Style Lab input error: missing reference images: GT_024.png, GT_036.png
```

예상하지 못한 내부 오류는 Python traceback을 숨기지 않는다. 이유는 이 CLI가 운영 사용자용 UI가 아니라 개발자 도구이기 때문이다.

## 데이터 모델

`tools/style_lab/models.py`는 dataclass를 사용한다. Pydantic을 새로 도입하지 않는다.

### ReferenceSample

필드:

- `sample_id: str`
- `tier: Literal["core", "extended"]`
- `role: str`
- `filename: str`

규칙:

- `sample_id`는 `GT_` + 세 자리 숫자 형식이다.
- `filename`은 `{sample_id}.png`이다.
- `tier`는 `core` 또는 `extended`만 허용한다.
- `role`은 빈 문자열이면 안 된다.

### ImageMetric

필드:

- `sample_id: str`
- `path: str`
- `width: int`
- `height: int`
- `aspect_ratio: float`
- `ink_ratio: float`
- `dark_ratio: float`
- `red_ratio: float`
- `blue_ratio: float`

계산 규칙:

- 이미지는 PIL로 `RGB` 변환한다.
- `aspect_ratio = width / height`이고 소수점 6자리로 반올림한다.
- `ink_ratio`: 흰 배경이 아닌 픽셀 비율. 조건은 `r < 245 or g < 245 or b < 245`.
- `dark_ratio`: 검정/회색 필기 픽셀 비율. 조건은 `r < 120 and g < 120 and b < 120`.
- `red_ratio`: 빨강/주황 필기 픽셀 비율. 조건은 `r > 150 and g < 130 and b < 130`.
- `blue_ratio`: 파랑/보라 필기 픽셀 비율. 조건은 `b > 130 and r < 150 and g < 170`.
- 비율은 전체 픽셀 수로 나누고 소수점 6자리로 반올림한다.

### CalibrationManifest

JSON field:

```json
{
  "preset_id": "default_pretty_handwriting",
  "preset_version": "v1",
  "source": "system_builtin",
  "calibration_status": "reference_contract_ready",
  "created_by": "tools.style_lab",
  "reference_set_doc": "docs/product/handwriting-style-reference-set.md",
  "core_samples": [],
  "extended_samples": [],
  "artifacts": {},
  "metrics_summary": {}
}
```

`core_samples`와 `extended_samples`는 `ReferenceSample` 배열이다.

`artifacts`는 CLI stdout의 `artifacts`와 같은 key를 가진다.

`metrics_summary` 필드:

- `core_count`
- `extended_count`
- `mean_ink_ratio`
- `mean_dark_ratio`
- `mean_red_ratio`
- `mean_blue_ratio`
- `max_ink_sample_id`
- `max_color_sample_id`

평균은 core+extended 전체 45개 기준으로 계산하고 소수점 6자리로 반올림한다.

## Style Token Skeleton

`style_tokens.skeleton.json`은 실제 AI 분석 결과가 아니라 다음 milestone의 출력 schema 초안이다.

파일 내용:

```json
{
  "preset_id": "default_pretty_handwriting",
  "preset_version": "v1",
  "schema_version": "style_tokens.v0",
  "status": "skeleton_pending_ai_calibration",
  "reference_contract": {
    "core_count": 19,
    "extended_count": 26,
    "reference_set_doc": "docs/product/handwriting-style-reference-set.md"
  },
  "tokens": {
    "stroke": {
      "black_width_px": null,
      "blue_width_px": null,
      "red_width_px": null,
      "jitter_px": null,
      "opacity": null
    },
    "text": {
      "korean_baseline_jitter_px": null,
      "letter_spacing_px": null,
      "line_height_ratio": null,
      "size_ratio_to_formula": null
    },
    "formula": {
      "baseline_jitter_px": null,
      "fraction_bar_width_px": null,
      "symbol_slant_deg": null,
      "vertical_compactness": null
    },
    "diagram": {
      "label_offset_px": null,
      "annotation_line_width_px": null,
      "hatching_gap_px": null,
      "hatching_angle_jitter_deg": null
    },
    "palette": {
      "black": null,
      "blue": null,
      "red_orange": null
    }
  }
}
```

`null` 값은 의도적이다. 이번 milestone에서는 값을 임의로 채우지 않는다.

## Contact Sheet 생성 규칙

구현은 `tools/style_lab/contact_sheet.py`에 둔다.

입력:

- `samples: list[ReferenceSample]`
- `image_root: Path`
- `output_path: Path`
- `title: str`
- `cell_width: int`
- `cell_height: int`
- `columns: int`

출력:

- JPEG RGB image.

레이아웃:

- 배경은 흰색.
- 전체 padding은 16px.
- title 영역 높이는 48px.
- label 영역 높이는 30px.
- cell 간격은 14px.
- label은 왼쪽 상단에 sample id를 검정색으로 표시한다.
- 각 이미지는 원본 비율을 유지하고 `cell_width x cell_height` 안에 contain 방식으로 맞춘다.
- 이미지는 셀 중앙에 배치한다.
- 셀 테두리는 `#d0d0d0` 1px이다.
- title font는 시스템 font를 시도하되 없으면 PIL default font를 사용한다.
- font fallback 차이로 pixel-perfect test를 하지 않는다.

Determinism:

- sample list 순서를 그대로 사용한다.
- EXIF orientation이 있으면 `ImageOps.exif_transpose`를 적용한다.
- JPEG quality는 `92`로 고정한다.

## Preset JSON 수정

`assets/style-presets/default_pretty_handwriting/preset.json`에 아래 field를 추가한다.

```json
{
  "calibration_status": "reference_contract_ready",
  "reference_set": {
    "doc": "docs/product/handwriting-style-reference-set.md",
    "core_count": 19,
    "extended_count": 26
  },
  "style_lab": {
    "default_image_root": "image/clean_solutions",
    "default_output_root": "image/style-lab/default_pretty_handwriting/v1",
    "manifest_filename": "calibration_manifest.json",
    "style_tokens_filename": "style_tokens.skeleton.json"
  }
}
```

기존 field는 삭제하지 않는다.

## Dependency and pytest 설정

`pyproject.toml`은 아래처럼 명시적으로 수정한다.

1. `[project].dependencies` 배열에 `"Pillow"`를 추가한다.

새 runtime dependency는 `Pillow`만 허용한다. Pillow가 이미 dev/test 환경에 설치되어 있어도 `pyproject.toml` dependency에 명시한다.

`pytest.ini`는 아래처럼 명시적으로 수정한다. 이 저장소는 `pytest.ini`가 pytest 설정의 기준 파일이므로, `pyproject.toml`에 `[tool.pytest.ini_options]`를 추가하지 않는다.

1. `[pytest].testpaths`에 `tools/style_lab/tests`를 추가한다.
2. `[pytest].pythonpath`에 `.`를 추가한다.

## 문서

`tools/style_lab/README.md`는 한국어로 작성한다.

포함 내용:

- 목적
- 입력 이미지 위치
- 기본 명령
- 산출물 목록
- OpenAI API를 호출하지 않는다는 점
- 산출물은 `/image` 아래에 생성되므로 git에 커밋되지 않는다는 점

`docs/product/handwriting-style-reference-set.md`에는 Style Lab 실행 명령과 산출물 경로를 추가한다.

## 테스트 전략

모든 테스트는 실제 `/image` 없이 동작해야 한다.

테스트 fixture는 pytest `tmp_path` 아래에서 PNG를 생성한다. fixture는 두 층으로 나눈다.

### Metric unit fixture

색상/잉크 비율 계산을 분리 검증하기 위한 작은 PNG다.

1. `blank_white.png`: 흰 배경만 있는 80x60 RGB 이미지.
2. `black_line.png`: 흰 배경에 검정 선 1개가 있는 80x60 RGB 이미지.
3. `red_orange_line.png`: 흰 배경에 빨강/주황 선 1개가 있는 80x60 RGB 이미지.
4. `blue_purple_line.png`: 흰 배경에 파랑/보라 선 1개가 있는 80x60 RGB 이미지.

### Composite solution fixture

Style Lab 산출물 생성은 실제 풀이 이미지에 더 가까운 합성 fixture로 검증한다. 이 fixture는 외부 파일을 커밋하지 않고, 테스트 안에서 PIL로 생성한다.

각 합성 이미지는 최소 640x900 RGB 이미지여야 한다. 배경은 흰색이고 아래 요소를 모두 포함한다.

1. 상단 문제 영역: 옅은 회색 인쇄문처럼 보이는 여러 줄의 작은 텍스트형 stroke.
2. 검정 풀이 영역: 8줄 이상의 수식형 stroke, 분수선, 등호, 괄호형 곡선.
3. 한글 설명 대체 영역: 실제 한글 OCR을 테스트하지 않으므로 짧은 검정 stroke 묶음과 spacing이 있는 문단 블록.
4. 기하/그래프 영역: 삼각형 또는 좌표축, 원호, 점 라벨 위치를 가진 도형.
5. 파란색 주석: 도형 라벨, 핵심 식 밑줄, 결론 표시 중 2개 이상.
6. 빨강/주황 주석: 보조선, 치환식, 박스 강조 중 2개 이상.
7. 해칭 영역: 같은 방향의 짧은 선 8개 이상.
8. 충분한 여백: contact sheet가 contain 방식으로 축소해도 레이아웃이 깨지지 않도록 바깥 여백 24px 이상.

`tools/style_lab/tests`는 합성 fixture 5개를 만든다.

- `GT_024.png`: 기하 도형과 높은 잉크 밀도 중심.
- `GT_049.png`: 좌표 그래프와 해칭 중심.
- `GT_079.png`: 큰 적분/분수형 stroke 중심.
- `GT_086.png`: 문단형 설명과 수식 혼합 중심.
- `GT_147.png`: 단계형 풀이와 색상별 결론 정리 중심.

CLI 통합 테스트에서 승인된 45개 전체 파일이 필요할 때는 위 5개 패턴을 sample id별로 순환 적용해 `GT_001.png`부터 필요한 sample id 파일을 모두 생성한다. 단, 파일명과 sample id 목록은 실제 core/extended 계약을 그대로 따라야 한다.

### 필수 테스트

`tools/style_lab/tests/test_reference_set.py`

- core sample 수가 19개인지 검증한다.
- extended sample 수가 26개인지 검증한다.
- 모든 sample id가 `GT_000` 형식인지 검증한다.
- core와 extended 사이에 중복 sample id가 없는지 검증한다.

`tools/style_lab/tests/test_image_metrics.py`

- 흰 배경만 있는 이미지는 `ink_ratio == 0`이다.
- 검정 선이 있는 이미지는 `dark_ratio > 0`이다.
- 빨강 선이 있는 이미지는 `red_ratio > 0`이다.
- 파랑 선이 있는 이미지는 `blue_ratio > 0`이다.
- aspect ratio는 소수점 6자리로 계산된다.

`tools/style_lab/tests/test_contact_sheet.py`

- contact sheet 파일이 생성된다.
- output image mode는 `RGB`이다.
- output image width와 height가 입력 sample 수, column 수, cell 크기 기준으로 기대값과 일치한다.
- 합성 풀이 fixture 5개를 contact sheet에 넣어도 파일이 생성된다.
- contact sheet의 첫 번째 cell label 영역에는 첫 번째 sample id의 어두운 픽셀이 존재한다.
- 누락된 이미지가 있으면 `StyleLabInputError`를 발생시킨다.

`tools/style_lab/tests/test_manifest.py`

- manifest JSON에 preset id/version/source/status가 들어간다.
- manifest의 core/extended count가 승인된 값과 일치한다.
- metrics summary의 평균과 max sample id가 deterministic하게 계산된다.
- style token skeleton의 모든 token leaf 값은 `None`이다.

`tools/style_lab/tests/test_cli.py`

- fixture image root와 tmp output root로 `build` command가 exit code 0을 반환한다.
- stdout JSON의 artifact path들이 실제 파일로 존재한다.
- CLI 성공 테스트는 승인된 core/extended sample id 45개에 해당하는 합성 풀이 fixture 파일을 모두 생성한 뒤 실행한다.
- 생성된 `core_contact_sheet.jpg`와 `extended_contact_sheet.jpg`의 크기가 0보다 크고 PIL로 열 수 있다.
- 이미지가 누락된 경우 exit code 2를 반환하고 stderr가 `Style Lab input error:`로 시작한다.

## 완료 기준

1. `python -m pytest tools/style_lab/tests -q`가 통과한다.
2. 기존 Python 테스트가 통과한다.
3. `python -m tools.style_lab.cli build --image-root image/clean_solutions --output-root image/style-lab/default_pretty_handwriting/v1`가 로컬 이미지가 있을 때 성공한다.
4. 생성된 core contact sheet를 사용자가 열어볼 수 있다.
5. git diff에는 `/image` 산출물이 포함되지 않는다.
6. `preset.json`은 reference contract 상태를 명확히 표현한다.

## 다음 milestone

이 milestone 이후 다음 milestone은 GPT-5.5 style profile extraction이다.

그 milestone은 이번 산출물 중 다음 파일을 입력으로 사용한다.

- `calibration_manifest.json`
- `style_tokens.skeleton.json`
- `core_contact_sheet.jpg`
- core sample 원본 이미지 19개

다음 milestone도 사용자 승인 없이는 core set을 변경하지 않는다.
