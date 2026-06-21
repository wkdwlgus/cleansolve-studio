# Style Profile Extraction Design

## 목적

Style Profile Extraction은 Style Lab의 deterministic 산출물을 GPT-5.5에 입력해 `default_pretty_handwriting v1`의 손글씨 스타일 프로필 초안을 생성하는 단계다.

이번 milestone은 renderer를 튜닝하지 않는다. 이번 milestone의 완료 기준은 다음과 같다.

1. GPT-5.5가 core reference sheet와 Style Lab manifest를 보고 style profile JSON을 생성할 수 있다.
2. 생성된 style profile은 schema 검증을 통과한다.
3. 실제 OpenAI 호출은 사용자가 명시적으로 opt-in할 때만 실행된다.
4. 실제 호출 결과는 `/image` 아래 ignored artifact로 저장하고 git에 커밋하지 않는다.
5. 기본 테스트는 mock client와 fixture만 사용해 비용 없이 통과한다.

## 공식 API 기준

이번 milestone은 OpenAI Responses API를 사용한다.

근거:

- OpenAI Responses API는 text, image, file input을 받을 수 있다.
- `input_image.image_url`은 URL 또는 base64 data URL을 받을 수 있다.
- image detail은 `low`, `high`, `auto` 중 하나다.
- Structured Outputs는 JSON Schema 기반 출력 검증에 사용한다.
- GPT-5.5는 최신 GPT-5 계열 작업에 적합하며, Responses API와 Structured Outputs를 사용할 수 있다.

참고 문서:

- `https://developers.openai.com/api/reference/resources/responses/methods/create/`
- `https://developers.openai.com/api/docs/guides/structured-outputs`
- `https://developers.openai.com/api/docs/guides/latest-model`

## 범위

### 포함

1. `tools/style_lab`에 style profile schema와 validator를 추가한다.
2. GPT-5.5용 style profile prompt를 추가한다.
3. OpenAI Responses API 기반 extractor를 추가한다.
4. mock extractor를 추가해 기본 테스트가 API key 없이 통과하게 한다.
5. CLI subcommand `extract-profile`을 추가한다.
6. opt-in OpenAI smoke test를 추가한다.
7. 한국어 README와 product doc을 업데이트한다.
8. 실제 GPT-5.5 호출 결과를 로컬 ignored artifact로 생성할 수 있게 한다.

### 제외

1. renderer parameter 자동 적용.
2. `assets/style-presets/default_pretty_handwriting/preset.json`의 실제 token 값 갱신.
3. style similarity gate 구현.
4. `gpt-image-2` asset 생성.
5. LangGraph runtime workflow 연결.
6. Web UI 연결.
7. API server endpoint 추가.

## 입력 산출물

기본 input root:

```text
image/style-lab/default_pretty_handwriting/v1
```

필수 입력 파일:

- `core_contact_sheet.jpg`
- `calibration_manifest.json`
- `style_tokens.skeleton.json`

선택 입력 directory:

```text
image/clean_solutions
```

이 directory가 제공되면 extractor는 아래 Image selection 규칙에 따라 core sample 원본 이미지를 추가 이미지 입력으로 첨부한다.
이 directory가 없으면 extractor는 원본 이미지를 0장 첨부하고 실패하지 않는다.
이 directory가 있지만 선택된 sample 파일이 없으면 해당 파일만 건너뛴다.
이 directory가 있고 선택된 sample 파일이 존재하지만 PNG/JPEG가 아니면 실패한다.

기본 출력 파일:

```text
image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json
```

이 파일은 `/image` 아래에 있으므로 git에 커밋하지 않는다.

## CLI 계약

기존 `tools.style_lab.cli`에 subcommand를 추가한다.

```bash
python -m tools.style_lab.cli extract-profile \
  --input-root image/style-lab/default_pretty_handwriting/v1 \
  --reference-image-root image/clean_solutions \
  --output-path image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json
```

옵션:

- `--input-root`: Style Lab deterministic 산출물 directory. 기본값은 `image/style-lab/default_pretty_handwriting/v1`.
- `--reference-image-root`: core sample 원본 이미지 directory. 기본값은 `image/clean_solutions`.
- `--output-path`: style profile JSON 저장 경로. 기본값은 `image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json`.
- `--client`: `mock` 또는 `openai`. 기본값은 `mock`.
- `--model`: 기본값은 `OPENAI_MODEL_ANALYSIS` env 또는 `gpt-5.5`.
- `--image-detail`: `low`, `high`, `auto`, `original` 중 하나. 기본값은 `OPENAI_STYLE_PROFILE_IMAGE_DETAIL` env 또는 `auto`. Responses API로 보낼 때 `original`은 `auto`로 변환한다.
- `--timeout-seconds`: 기본값은 `OPENAI_STYLE_PROFILE_TIMEOUT_SECONDS` env 또는 `90`. 1 이상 정수만 허용한다.
- `--max-reference-images`: core 원본 이미지를 추가 첨부할 최대 개수. 기본값은 `4`. 0 이상 6 이하 정수만 허용한다.

성공 stdout은 한 줄 JSON이다.

```json
{
  "status": "ok",
  "client": "mock",
  "model": "gpt-5.5",
  "preset_id": "default_pretty_handwriting",
  "preset_version": "v1",
  "output_path": "image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json",
  "core_sample_count": 19,
  "reference_image_count": 4
}
```

실패 시 exit code는 `2`이고 stderr는 한 줄이어야 한다.

```text
Style Lab input error: missing style lab artifacts: core_contact_sheet.jpg
```

예상하지 못한 OpenAI/SDK/네트워크 오류도 CLI에서는 traceback을 노출하지 않는다. 아래처럼 exit code `2`로 감싼다.

```text
Style Lab input error: OpenAI style profile request failed
```

## OpenAI 실행 정책

기본 CLI client는 `mock`이다. 실제 API 호출은 명시적으로 `--client openai`를 지정할 때만 발생한다.

OpenAI client는 다음 조건을 모두 만족해야 실행된다.

1. `--client openai`
2. `OPENAI_API_KEY` 존재
3. 필수 input artifact 존재
4. output path preflight 통과

API key는 출력 JSON, prompt, error message, 로그, 테스트 failure message에 포함하지 않는다.

## Opt-in smoke test

기본 pytest에서는 실제 OpenAI 호출을 절대 실행하지 않는다.

Smoke test는 아래 env가 있을 때만 실행한다.

```bash
CLEANSOLVE_RUN_OPENAI_STYLE_SMOKE=1 \
python -m pytest tools/style_lab/tests/test_openai_style_profile_smoke.py -q
```

추가 조건:

- `OPENAI_API_KEY`가 없으면 skip한다.
- `image/style-lab/default_pretty_handwriting/v1/core_contact_sheet.jpg`가 없으면 skip한다.
- `image/style-lab/default_pretty_handwriting/v1/calibration_manifest.json`이 없으면 skip한다.
- `image/style-lab/default_pretty_handwriting/v1/style_tokens.skeleton.json`이 없으면 skip한다.
- smoke test는 `--max-reference-images 0`에 준하는 입력으로 비용을 줄인다.
- smoke test output은 `image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json`에 저장한다.

## 파일 구조

### 새 파일

- `tools/style_lab/style_profile_schema.py`
- `tools/style_lab/style_profile_prompt.py`
- `tools/style_lab/style_profile_extractor.py`
- `tools/style_lab/tests/test_style_profile_schema.py`
- `tools/style_lab/tests/test_style_profile_extractor.py`
- `tools/style_lab/tests/test_extract_profile_cli.py`
- `tools/style_lab/tests/test_openai_style_profile_smoke.py`

### 수정 파일

- `tools/style_lab/cli.py`
- `tools/style_lab/README.md`
- `docs/product/handwriting-style-reference-set.md`
- `apps/api/.env.example`

`apps/api/.env.example`에는 아래 env를 추가한다.

```text
OPENAI_STYLE_PROFILE_IMAGE_DETAIL=auto
OPENAI_STYLE_PROFILE_TIMEOUT_SECONDS=90
CLEANSOLVE_RUN_OPENAI_STYLE_SMOKE=0
```

## Style Profile JSON schema

`tools/style_lab/style_profile_schema.py`에 JSON Schema와 Python validation helper를 둔다.

Schema name:

```text
style_profile_v1
```

Top-level required fields:

- `preset_id`
- `preset_version`
- `schema_version`
- `status`
- `source`
- `reference_summary`
- `style_description`
- `tokens`
- `renderer_recommendations`
- `quality_gates`
- `uncertainties`

Top-level fixed values:

- `preset_id`: `default_pretty_handwriting`
- `preset_version`: `v1`
- `schema_version`: `style_profile.v1`
- `source`: `gpt-5.5_style_profile_extraction`

`status` enum:

- `generated`
- `needs_review`

### reference_summary

Required fields:

- `core_sample_count`: integer, const `19`
- `extended_sample_count`: integer, const `26`
- `input_artifacts`: array of strings
- `visual_coverage_notes`: array of strings

### style_description

Required fields:

- `overall`: string
- `korean_text`: string
- `formula`: string
- `diagram_annotations`: string
- `color_usage`: string
- `spacing_and_layout`: string

각 string은 빈 문자열이면 안 된다.

### tokens

Required object structure:

```json
{
  "stroke": {
    "black_width_px": 1.0,
    "blue_width_px": 1.0,
    "red_width_px": 1.0,
    "jitter_px": 0.0,
    "opacity": 1.0
  },
  "text": {
    "korean_baseline_jitter_px": 0.0,
    "letter_spacing_px": 0.0,
    "line_height_ratio": 1.0,
    "size_ratio_to_formula": 1.0
  },
  "formula": {
    "baseline_jitter_px": 0.0,
    "fraction_bar_width_px": 1.0,
    "symbol_slant_deg": 0.0,
    "vertical_compactness": 1.0
  },
  "diagram": {
    "label_offset_px": 0.0,
    "annotation_line_width_px": 1.0,
    "hatching_gap_px": 8.0,
    "hatching_angle_jitter_deg": 0.0
  },
  "palette": {
    "black": "#222222",
    "blue": "#3448b8",
    "red_orange": "#d85a3a"
  }
}
```

Numeric constraints:

- widths: `0.5 <= value <= 8`
- jitter: `0 <= value <= 12`
- opacity: `0.1 <= value <= 1`
- ratio fields: `0.5 <= value <= 2`
- slant/angle jitter: `-20 <= value <= 20`
- hatching gap: `2 <= value <= 40`

Palette fields must match `^#[0-9a-fA-F]{6}$`.

### renderer_recommendations

Array of objects. Minimum 1 item, maximum 12 items.

Each object required fields:

- `target`: string enum `stroke`, `text`, `formula`, `diagram`, `palette`, `layout`
- `recommendation`: string
- `reason`: string
- `priority`: string enum `high`, `medium`, `low`

### quality_gates

Required fields:

- `style_similarity_threshold`: number `0 <= value <= 1`
- `max_visual_diff_ratio`: number `0 <= value <= 1`
- `requires_human_review_if_below`: number `0 <= value <= 1`
- `notes`: array of strings

### uncertainties

Array of objects.

Each object required fields:

- `field`: string
- `reason`: string
- `needs_human_review`: boolean

If model confidence is low, `status` must be `needs_review` and `uncertainties` must contain at least one item.

## Prompt 계약

Prompt는 `tools/style_lab/style_profile_prompt.py`에 둔다.

Developer prompt는 다음 원칙을 포함한다.

- 전체 이미지를 새로 만들지 않는다.
- style profile JSON만 생성한다.
- renderer가 사용할 수 있는 구체적 token 후보를 제안한다.
- 수식 정확성은 미학보다 우선한다.
- 한글/수식 결합 기준은 `style_description.korean_text`, `style_description.formula`, `tokens.text.size_ratio_to_formula`, `tokens.text.line_height_ratio`, `tokens.formula.baseline_jitter_px`, `tokens.stroke.black_width_px`에 반드시 반영한다.
- 근거 없는 값을 단정하지 않는다. 불확실하면 `status=needs_review`와 `uncertainties`를 사용한다.
- API key, 로컬 경로, 원본 파일명, 개인정보를 출력하지 않는다.

User prompt에는 다음 정보를 넣는다.

- preset id/version
- manifest의 core/extended count
- metrics summary
- input artifact 이름
- max_reference_images
- style token skeleton의 key 목록

Prompt에는 전체 JSON Schema를 풀어 쓰지 않는다. JSON Schema는 Responses API `text.format`으로 전달한다.

## OpenAI extractor 계약

`tools/style_lab/style_profile_extractor.py`는 다음을 제공한다.

### StyleProfileExtractionInput

Dataclass fields:

- `preset_id: str`
- `preset_version: str`
- `input_root: Path`
- `reference_image_root: Path`
- `output_path: Path`
- `model: str`
- `image_detail: str`
- `max_reference_images: int`

### MockStyleProfileExtractor

- OpenAI 호출을 하지 않는다.
- deterministic valid profile을 반환한다.
- `calibration_manifest.json.metrics_summary.max_ink_sample_id`가 있으면 `reference_summary.visual_coverage_notes`에 `max_ink_sample_id=<value>` 문자열을 넣는다.
- `calibration_manifest.json.metrics_summary.max_color_sample_id`가 있으면 `reference_summary.visual_coverage_notes`에 `max_color_sample_id=<value>` 문자열을 넣는다.
- 위 두 값이 없으면 `reference_summary.visual_coverage_notes`에 `metrics_summary_unavailable` 문자열을 넣는다.

### OpenAIStyleProfileExtractor

Constructor:

- `api_key: str`
- `client: object | None`
- `timeout_seconds: int`

Validation:

- api key가 비어 있으면 `StyleLabInputError`.
- model이 비어 있으면 `StyleLabInputError`.
- image detail이 허용값이 아니면 `StyleLabInputError`.
- timeout이 1 미만이면 `StyleLabInputError`.

Request:

- `client.responses.create` 메서드 사용.
- `model=input.model`.
- `input`은 developer message와 user message로 구성한다.
- user message content 순서:
  1. input text prompt
  2. `core_contact_sheet.jpg` as `input_image`
  3. core 원본 이미지 최대 `max_reference_images`장 as `input_image`
- `text.format`은 strict JSON schema `style_profile_v1`.

Image selection:

- core sample 순서는 `tools.style_lab.reference_set.get_reference_samples()`가 반환하는 core sample 순서를 그대로 사용한다.
- `max_reference_images=0`이면 core 원본 이미지를 첨부하지 않는다.
- 원본 이미지를 첨부할 때는 아래 순서에서 `max_reference_images`개를 앞에서부터 선택한다.
- 선택한 파일 중 존재하지 않는 파일은 건너뛰고 `reference_image_count`에 포함하지 않는다.
- 선택한 파일 중 존재하는 파일이 PNG/JPEG가 아니면 `StyleLabInputError("unsupported style profile image type: <filename>")`로 실패한다.

```text
GT_024, GT_036, GT_043, GT_049, GT_058, GT_067, GT_073, GT_079, GT_082,
GT_086, GT_090, GT_099, GT_102, GT_116, GT_132, GT_135, GT_141, GT_146,
GT_147
```

Output:

- response output text를 JSON decode한다.
- schema helper로 validate한다.
- `output_path`에 UTF-8, indent 2, sort_keys true, trailing newline으로 저장한다.

Error:

- OpenAI SDK import 실패는 `StyleLabInputError("OpenAI SDK is not installed")`로 감싼다.
- OpenAI API 호출 중 발생한 SDK/network 오류는 `StyleLabInputError("OpenAI style profile request failed")`로 감싼다.
- response output text가 없으면 `StyleLabInputError("OpenAI style profile response was empty")`로 감싼다.
- JSON decode 오류는 `StyleLabInputError("OpenAI style profile response was not valid JSON")`로 감싼다.
- schema validation 오류는 `StyleLabInputError("OpenAI style profile response failed schema validation")`로 감싼다.
- API key나 raw response 전체를 error message에 포함하지 않는다.

## Data URL helper

이번 milestone에서는 `tools/style_lab` 안에 style profile 전용 private data URL helper를 둔다.

지원 mime:

- PNG
- JPEG

지원하지 않는 파일은 `StyleLabInputError`.

이유:

- `tools/style_lab`는 독립 개발 도구다.
- 기존 `packages/ai` helper는 private function이고 analysis client 전용 error type을 사용한다.
- cross-package public API로 승격하는 것은 이번 scope보다 크다.

## 테스트 전략

모든 기본 테스트는 OpenAI API key 없이 통과해야 한다.

### Unit tests

`test_style_profile_schema.py`

- mock valid profile이 schema validate를 통과한다.
- palette가 hex가 아니면 실패한다.
- required top-level field가 빠지면 실패한다.
- numeric token이 범위를 벗어나면 실패한다.
- `status=needs_review`인데 uncertainties가 비어 있으면 실패한다.

`test_style_profile_extractor.py`

- mock extractor가 deterministic valid profile을 반환한다.
- extractor input artifact가 빠지면 `StyleLabInputError`.
- reference image root가 없으면 reference image 없이 성공한다.
- reference image root가 있고 선택된 파일 일부가 없으면 존재하는 파일만 첨부한다.
- data URL helper가 PNG/JPEG를 encode한다.
- unsupported image는 `StyleLabInputError`.
- fake OpenAI client가 받은 request에 developer/user message, input_image, text.format schema가 포함된다.
- fake OpenAI response가 invalid JSON이면 `StyleLabInputError`.
- fake OpenAI response가 schema invalid이면 `StyleLabInputError`.

`test_extract_profile_cli.py`

- mock client로 `extract-profile` 실행 시 output JSON이 생성된다.
- stdout JSON은 `status=ok`, `client=mock`, output path, counts를 포함한다.
- missing `core_contact_sheet.jpg`는 exit code 2.
- output path parent가 파일이면 exit code 2.
- `--max-reference-images`가 음수 또는 7 이상이면 exit code 2.
- `--client openai`인데 API key가 없으면 exit code 2.

### Opt-in smoke test

`test_openai_style_profile_smoke.py`

Skip 조건:

- `CLEANSOLVE_RUN_OPENAI_STYLE_SMOKE != "1"`
- `OPENAI_API_KEY` 없음
- 필수 local style lab artifacts 없음

실행:

```bash
CLEANSOLVE_RUN_OPENAI_STYLE_SMOKE=1 \
python -m pytest tools/style_lab/tests/test_openai_style_profile_smoke.py -q
```

검증:

- 실제 OpenAI extractor를 호출한다.
- `max_reference_images=0`.
- output file이 생성된다.
- schema validate 통과.
- `preset_id=default_pretty_handwriting`.
- `preset_version=v1`.

## 완료 기준

1. `pytest tools/style_lab/tests -q` 통과.
2. `CLEANSOLVE_API_ENV_FILE=/tmp/cleansolve-no-env python -m pytest apps/api/tests packages/ai/tests packages/harness/tests packages/renderer/tests packages/spec/tests packages/workflow/tests -q` 통과.
3. `python -m tools.style_lab.cli extract-profile --client mock` 성공.
4. 사용자가 API key를 넣은 환경에서 opt-in smoke test 1회 성공.
5. 실제 `style_profile.generated.json` 생성.
6. `/image` 산출물은 git에 포함되지 않음.
7. 최종 subagent branch review 승인.

## 다음 milestone

다음 milestone은 renderer calibration이다.

입력:

- `style_profile.generated.json`
- `style_tokens.skeleton.json`
- `core_contact_sheet.jpg`
- renderer primitive output fixtures

목표:

- profile token을 renderer parameter 초안으로 변환한다.
- deterministic renderer가 stroke width, color, jitter, hatching, text/formula spacing을 반영하게 한다.
- style similarity gate 초안을 만든다.
