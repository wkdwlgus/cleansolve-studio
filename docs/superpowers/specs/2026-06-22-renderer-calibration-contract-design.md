# Renderer Calibration Contract 상세 설계

## 목적

이번 milestone의 목적은 `default_pretty_handwriting v1` 스타일 프로필을 deterministic renderer가 사용할 수 있는 calibration contract로 고정하는 것이다.

이 작업은 손글씨 스타일을 완성하는 작업이 아니다. 이번 milestone은 아래 세 가지를 만든다.

1. renderer가 읽을 수 있는 committed calibration JSON.
2. calibration JSON을 검증하고 `RendererStyle`로 해석하는 resolver.
3. 기존 SVG overlay renderer가 `default_pretty_handwriting v1`의 색상, 획 두께, 텍스트 크기, 수식 크기, label offset을 deterministic하게 반영하는 경로.

`image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json`은 이번 설계의 근거 입력이지만, `/image`는 gitignore 대상이므로 runtime renderer가 이 파일을 직접 읽지 않는다.

## 현재 입력 근거

현재 로컬 style profile 산출물은 아래 경로에 있다.

```text
image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json
```

이 파일은 schema-valid이고 `status=needs_review`다. 따라서 이번 milestone은 이 값을 production-approved token으로 선언하지 않는다.

이번 milestone에서 repository에 커밋하는 값은 `draft_needs_review` 상태의 renderer calibration contract다. 이 contract는 다음 renderer calibration/visual QA milestone에서 사람이 보고 조정할 수 있는 시작점이다.

## 범위

### 포함

1. `assets/style-presets/default_pretty_handwriting/renderer_calibration.v1.json` 추가.
2. `assets/style-presets/default_pretty_handwriting/preset.json`에 renderer calibration metadata 추가.
3. renderer package에 calibration schema/loader/resolver 추가.
4. SVG overlay renderer가 `CandidateSpec.style`의 `default_pretty_handwriting v1`에 대해 calibration을 적용.
5. element inline style이 있으면 inline style이 calibration 기본값보다 우선.
6. renderer tests로 calibration load, fallback, inline override, semantic color mapping, calibrated default output을 검증.
7. `docs/product/handwriting-style-reference-set.md`에 이번 calibration contract 상태를 한국어로 문서화.

### 제외

1. `image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json`을 git에 커밋하지 않는다.
2. runtime renderer가 `/image` 아래 파일을 읽지 않는다.
3. `gpt-image-2` asset 생성은 하지 않는다.
4. 손글씨 font 생성 또는 font 학습은 하지 않는다.
5. style similarity gate는 구현하지 않는다.
6. visual diff score gate는 구현하지 않는다.
7. LangGraph workflow runtime에는 연결하지 않는다.
8. Web UI에는 연결하지 않는다.
9. `shaded_area` primitive 또는 hatching renderer를 새로 구현하지 않는다.
10. `draft_needs_review` 상태를 `approved`로 바꾸지 않는다.

## 파일 구조

### 새 파일

- `assets/style-presets/default_pretty_handwriting/renderer_calibration.v1.json`
- `packages/renderer/cleansolve_renderer/style.py`
- `packages/renderer/tests/test_style.py`

### 수정 파일

- `assets/style-presets/default_pretty_handwriting/preset.json`
- `packages/renderer/cleansolve_renderer/overlay.py`
- `packages/renderer/cleansolve_renderer/__init__.py`
- `packages/renderer/tests/test_overlay.py`
- `docs/product/handwriting-style-reference-set.md`

## Renderer calibration JSON 계약

`assets/style-presets/default_pretty_handwriting/renderer_calibration.v1.json`은 정확히 아래 top-level 구조를 사용한다.

```json
{
  "schema_version": "renderer_calibration.v1",
  "preset_id": "default_pretty_handwriting",
  "preset_version": "v1",
  "status": "draft_needs_review",
  "source": {
    "kind": "style_profile",
    "path": "image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json",
    "profile_status": "needs_review"
  },
  "tokens": {
    "stroke": {
      "black_width_px": 2.0,
      "blue_width_px": 2.1,
      "red_width_px": 2.1,
      "jitter_px": 0.45,
      "opacity": 0.94
    },
    "text": {
      "korean_baseline_jitter_px": 1.2,
      "letter_spacing_px": 0.25,
      "line_height_ratio": 1.32,
      "size_ratio_to_formula": 0.88
    },
    "formula": {
      "baseline_jitter_px": 0.9,
      "fraction_bar_width_px": 1.8,
      "symbol_slant_deg": 3.0,
      "vertical_compactness": 0.86
    },
    "diagram": {
      "label_offset_px": 7.0,
      "annotation_line_width_px": 1.9,
      "hatching_gap_px": 6.5,
      "hatching_angle_jitter_deg": 5.0
    },
    "palette": {
      "black": "#222222",
      "blue": "#34309A",
      "red_orange": "#E1583E"
    }
  },
  "renderer_mapping": {
    "formula_font_size_px": 18,
    "text_font_size_px": 16,
    "label_font_size_px": 14,
    "dimension_label_font_size_px": 16,
    "generic_stroke_width_px": 2.0,
    "diagram_stroke_width_px": 1.9,
    "highlight_stroke_width_px": 8,
    "highlight_opacity": 0.35
  },
  "deferred_tokens": [
    "stroke.jitter_px",
    "formula.baseline_jitter_px",
    "formula.symbol_slant_deg",
    "formula.vertical_compactness",
    "diagram.hatching_gap_px",
    "diagram.hatching_angle_jitter_deg"
  ]
}
```

### 값 선택 기준

- `tokens`는 현재 `style_profile.generated.json`에서 추출한 값을 그대로 사용한다.
- `renderer_mapping.formula_font_size_px=18`은 현재 renderer의 `formula_line` 기본값과 동일하다.
- `renderer_mapping.text_font_size_px=16`은 `18 * 0.88 = 15.84`를 nearest integer로 반올림한 값이다.
- `renderer_mapping.label_font_size_px=14`는 기존 point/segment label 기본값을 유지한다.
- `renderer_mapping.dimension_label_font_size_px=16`은 기존 dimension/freehand label 기본값을 유지한다.
- `renderer_mapping.generic_stroke_width_px=2.0`은 `tokens.stroke.black_width_px`와 동일하다.
- `renderer_mapping.diagram_stroke_width_px=1.9`는 `tokens.diagram.annotation_line_width_px`와 동일하다.
- `renderer_mapping.highlight_stroke_width_px=8`과 `highlight_opacity=0.35`는 기존 renderer highlight 기본값을 유지한다. style profile에는 yellow highlight token이 없으므로 새 token 값을 만들지 않는다.

### deferred token 정책

`deferred_tokens`에 있는 값은 JSON에 기록하지만 이번 milestone의 SVG output에는 적용하지 않는다.

이유:

- `stroke.jitter_px`, `formula.baseline_jitter_px`, `formula.symbol_slant_deg`, `formula.vertical_compactness`는 deterministic SVG primitive에 직접 적용하면 수식 정확성을 떨어뜨릴 수 있다.
- `diagram.hatching_gap_px`, `diagram.hatching_angle_jitter_deg`는 현재 renderer가 `shaded_area`/hatching primitive를 렌더링하지 않으므로 적용할 표면이 없다.

## Preset metadata 계약

`assets/style-presets/default_pretty_handwriting/preset.json`에는 아래 object를 추가한다.

```json
{
  "renderer_calibration": {
    "schema_version": "renderer_calibration.v1",
    "status": "draft_needs_review",
    "tokens_filename": "renderer_calibration.v1.json",
    "source_profile_artifact": "image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json",
    "runtime_reads_ignored_artifacts": false
  }
}
```

기존 `calibration_status` 값은 이번 milestone에서 `renderer_calibration_draft`로 변경한다.

## Renderer style resolver 계약

새 모듈 `packages/renderer/cleansolve_renderer/style.py`를 추가한다.

### Public API

```python
@dataclass(frozen=True)
class RendererStyle:
    preset_id: str
    preset_version: str
    status: str
    palette_black: str
    palette_blue: str
    palette_red_orange: str
    generic_stroke_width_px: float
    diagram_stroke_width_px: float
    formula_font_size_px: float
    text_font_size_px: float
    label_font_size_px: float
    dimension_label_font_size_px: float
    text_letter_spacing_px: float
    text_line_height_ratio: float
    label_offset_px: float
    ink_opacity: float
    highlight_stroke_width_px: float
    highlight_opacity: float
```

```python
def load_renderer_calibration(path: Path) -> dict[str, object]
```

```python
def renderer_style_for_preset(style_preset: StylePreset) -> RendererStyle
```

```python
def resolve_semantic_color(color: str | None, style: RendererStyle) -> str
```

```python
def resolve_stroke_width(
    element_style: dict[str, Any],
    *,
    default_width: float,
    min_value: float = 0,
) -> float
```

```python
def resolve_font_size(
    element_style: dict[str, Any],
    *,
    default_size: float,
) -> float
```

```python
def resolve_opacity(
    element_style: dict[str, Any],
    *,
    default_opacity: float,
) -> float
```

### Path resolution

`renderer_style_for_preset`는 아래 조건을 모두 만족할 때 committed calibration JSON을 읽는다.

- `style_preset.source == "system_builtin"`
- `style_preset.preset_id == "default_pretty_handwriting"`
- `style_preset.preset_version == "v1"`

파일 경로는 repository root 기준이 아니라 `style.py` 파일 위치 기준으로 계산한다.

계산식:

```text
Path(__file__).resolve().parents[3] / "assets/style-presets/default_pretty_handwriting/renderer_calibration.v1.json"
```

현재 파일 위치가 `packages/renderer/cleansolve_renderer/style.py`이므로 `parents[3]`는 repository root다.

### Fallback style

지원하지 않는 style preset이 들어오거나 calibration file load가 실패하면 renderer는 crash하지 않고 fallback style을 사용한다.

Fallback 값은 다음과 같다.

```text
preset_id = style_preset.preset_id
preset_version = style_preset.preset_version
status = "fallback"
palette_black = "black"
palette_blue = "blue"
palette_red_orange = "red"
generic_stroke_width_px = 2
diagram_stroke_width_px = 2
formula_font_size_px = 18
text_font_size_px = 16
label_font_size_px = 14
dimension_label_font_size_px = 16
text_letter_spacing_px = 0
text_line_height_ratio = 1
label_offset_px = 8
ink_opacity = 1
highlight_stroke_width_px = 8
highlight_opacity = 0.35
```

### Validation

`load_renderer_calibration`은 아래 조건을 검증한다.

- top-level object다.
- `schema_version == "renderer_calibration.v1"`.
- `preset_id == "default_pretty_handwriting"`.
- `preset_version == "v1"`.
- `status`는 `"draft_needs_review"` 또는 `"approved"` 중 하나다.
- palette 값은 `^#[0-9a-fA-F]{6}$` 형식이다.
- 모든 renderer_mapping 숫자는 `int | float`이고 bool이 아니다.
- 모든 width/font/offset 값은 `> 0`.
- `highlight_opacity`와 `ink_opacity`는 `0 <= value <= 1`.

검증 실패 시 `RendererStyleError`를 발생시킨다. `renderer_style_for_preset`은 이 error를 잡고 fallback style을 반환한다.

`RendererStyleError`는 `ValueError`를 상속한다.

## SVG renderer 적용 계약

`render_overlay_svg(spec: CandidateSpec) -> str` public signature는 바꾸지 않는다.

함수 시작 시 한 번만 호출한다.

```python
renderer_style = renderer_style_for_preset(spec.style)
```

이후 `_render_element(element, renderer_style)`처럼 내부 helper에 style을 전달한다.

### 색상 mapping

`resolve_semantic_color`는 아래 규칙을 사용한다.

| 입력 color | 출력 |
| --- | --- |
| `None` | `style.palette_black` |
| `"black"` | `style.palette_black` |
| `"blue"` | `style.palette_blue` |
| `"red"` | `style.palette_red_orange` |
| `"red_orange"` | `style.palette_red_orange` |
| 그 외 문자열 | 원문 유지 |

공백 문자열 `""`은 유효한 색상이 아니므로 `style.palette_black`으로 처리한다.

### Inline style 우선순위

`element.style`에 유효한 `font_size`, `stroke_width`, `opacity`가 있으면 기존처럼 inline style을 우선한다. `font_size`는 `resolve_font_size`, `stroke_width`는 `resolve_stroke_width`, `opacity`는 `resolve_opacity`로 해석한다.

유효성 규칙:

- number만 허용한다.
- bool은 허용하지 않는다.
- `font_size > 0`.
- `stroke_width > 0`.
- `0 <= opacity <= 1`.

유효하지 않은 값이면 calibration default를 사용한다.

### Primitive별 적용

| primitive | 적용 규칙 |
| --- | --- |
| `formula_line` | fill은 semantic color mapping. font family는 기존 `"serif"` 유지. 기본 font-size는 `formula_font_size_px`. inline `font_size` 우선. `data-style-status`, `data-line-height-ratio`는 group attribute에 넣는다. |
| `text_note` | fill은 semantic color mapping. font family는 기존 `"sans-serif"` 유지. 기본 font-size는 `text_font_size_px`. inline `font_size` 우선. `letter-spacing` attribute는 `text_letter_spacing_px`가 0이 아닐 때만 넣는다. `data-line-height-ratio`는 group attribute에 넣는다. |
| `highlight_line` | 기존 yellow `#ffd84d` 기본 color 유지. stroke-width 기본값은 `highlight_stroke_width_px`. opacity 기본값은 `highlight_opacity`. inline `stroke_width`, `opacity` 우선. |
| `highlight_curve` | `highlight_line`과 동일. |
| `arrow` | color mapping 적용. stroke-width 기본값은 `generic_stroke_width_px`. inline `stroke_width` 우선. |
| `box` | color mapping 적용. stroke-width 기본값은 `generic_stroke_width_px`. inline `stroke_width` 우선. |
| `circle` | color mapping 적용. stroke-width 기본값은 `generic_stroke_width_px`. inline `stroke_width` 우선. |
| `point_label` | point fill과 label fill에 color mapping 적용. label anchor가 없으면 `(point_x + label_offset_px, point_y - label_offset_px)`를 사용. 기본 font-size는 `label_font_size_px`. inline `font_size` 우선. |
| `segment_label` | fill에 color mapping 적용. 기본 font-size는 `label_font_size_px`. inline `font_size` 우선. label anchor fallback은 기존 midpoint 유지. |
| `dimension_line` | color mapping 적용. stroke-width 기본값은 `diagram_stroke_width_px`. inline `stroke_width` 우선. label 기본 font-size는 `dimension_label_font_size_px`. |
| `dimension_curve` | `dimension_line`과 동일. |
| `freehand_dimension_marker` | visible stroke와 label에 color mapping 적용. visible stroke-width 기본값은 `diagram_stroke_width_px`. inline `stroke_width` 우선. label 기본 font-size는 `dimension_label_font_size_px`. |

### SVG metadata

최상위 `<svg>`에 아래 attribute를 추가한다.

```text
data-style-preset-id="default_pretty_handwriting"
data-style-preset-version="v1"
data-renderer-calibration-status="draft_needs_review"
```

fallback style이면 `data-renderer-calibration-status="fallback"`이다.

## Tests

### `packages/renderer/tests/test_style.py`

필수 테스트:

1. `test_load_renderer_calibration_returns_contract`
   - committed JSON을 load한다.
   - `schema_version`, `preset_id`, `preset_version`, `status`, palette, mapping 값을 검증한다.

2. `test_renderer_style_for_default_preset_uses_calibration`
   - `StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1")` 입력.
   - 반환 style의 status가 `draft_needs_review`.
   - `palette_blue == "#34309A"`.
   - `generic_stroke_width_px == 2.0`.

3. `test_renderer_style_for_unknown_preset_uses_fallback`
   - preset id가 `unknown`이면 status가 `fallback`.
   - fallback palette black이 `"black"`.

4. `test_resolve_semantic_color_maps_only_known_semantics`
   - `None`, `"black"`, `"blue"`, `"red"`, `"red_orange"`, `"purple"`를 검증한다.
   - `"purple"`는 원문 유지.

5. `test_invalid_calibration_file_raises_style_error`
   - tmp JSON에서 `schema_version`을 잘못 넣는다.
   - `load_renderer_calibration`이 `RendererStyleError`를 발생시킨다.

6. `test_renderer_style_falls_back_when_calibration_loader_fails`
   - monkeypatch로 calibration path를 깨진 JSON path로 바꾼다.
   - `renderer_style_for_preset`이 fallback을 반환한다.

### `packages/renderer/tests/test_overlay.py`

기존 테스트 기대값을 calibration 적용 결과로 갱신한다.

추가 또는 수정 필수 테스트:

1. `test_renderer_preserves_source_image_metadata`
   - 기존 source image metadata assertion 유지.
   - 추가로 top-level style metadata 3개를 검증한다.

2. `test_renderer_renders_formula_line_and_text_note`
   - inline `font_size=20`이 있는 formula는 그대로 20.
   - color `"navy"`는 원문 유지.
   - text note 기본 fill은 `#222222`.
   - text note 기본 font-size는 `16`.
   - text note에 `letter-spacing="0.25"`가 있다.

3. `test_renderer_uses_calibrated_semantic_palette_and_strokes`
   - arrow color `"blue"`는 `#34309A`.
   - box color `"red"`는 `#E1583E`.
   - circle color `"black"`은 `#222222`.
   - generic stroke-width 기본값은 `2`.

4. `test_renderer_inline_style_overrides_calibration`
   - arrow style `{"stroke_width": 3.5}`면 stroke-width가 `3.5`.
   - text_note style `{"font_size": 21}`면 font-size가 `21`.

5. `test_renderer_ignores_invalid_inline_style_values`
   - bool stroke_width/font_size/opacity는 무시한다.
   - calibration default가 사용된다.

6. `test_renderer_uses_calibrated_point_label_offset`
   - point `[15, 25]`에서 label anchor가 없으면 text 위치는 `x=22`, `y=18`.

7. `test_renderer_uses_calibrated_dimension_stroke_width`
   - `dimension_line`, `dimension_curve`, `freehand_dimension_marker` 기본 stroke-width는 `1.9`.

## Documentation

`docs/product/handwriting-style-reference-set.md`에 아래 내용을 추가한다.

- `renderer_calibration.v1.json`이 repository에 커밋된 deterministic draft contract임.
- `style_profile.generated.json`은 ignored local artifact이며 runtime renderer가 직접 읽지 않음.
- 현재 calibration status는 `draft_needs_review`.
- 이 milestone은 visual QA/style similarity gate를 완료하지 않음.

## Verification

완료 전 반드시 실행한다.

```bash
pytest packages/renderer/tests -q
```

```bash
pytest tools/style_lab/tests -q
```

```bash
CLEANSOLVE_API_ENV_FILE=/tmp/cleansolve-no-env python -m pytest apps/api/tests packages/ai/tests packages/harness/tests packages/spec/tests packages/workflow/tests -q
```

```bash
git diff --check
```

## 완료 기준

1. `renderer_calibration.v1.json`이 committed file로 존재한다.
2. `preset.json`이 renderer calibration metadata를 가진다.
3. renderer가 default preset에 대해 calibration style을 deterministic하게 적용한다.
4. unsupported preset 또는 깨진 calibration file에서 renderer가 crash하지 않고 fallback style을 사용한다.
5. inline element style이 calibration 기본값보다 우선한다.
6. `/image` 산출물은 git에 포함되지 않는다.
7. renderer/style tests와 기존 Python suite가 통과한다.
8. 최종 subagent spec compliance review와 code quality review가 승인된다.
