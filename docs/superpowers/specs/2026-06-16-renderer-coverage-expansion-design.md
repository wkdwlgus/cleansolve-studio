# M3 Renderer Coverage Expansion 상세 설계

작성일: 2026-06-16

## 1. 목적

M3의 목적은 `CandidateSpec` 안의 MVP primitive를 deterministic SVG overlay로 미리 볼 수 있게 만드는 것이다. 렌더러는 원본 문제 이미지를 수정하지 않는다. 입력으로 받은 `CandidateSpec`만 읽고, 원본 이미지 artifact id는 SVG metadata로 보존한다.

이 문서는 코딩 에이전트가 임의 결정을 하지 않도록 renderer가 읽을 geometry field, SVG 출력, malformed 입력 처리 방식을 모두 고정한다.

## 2. 범위

이번 milestone에서 구현한다.

- `render_overlay_svg(spec: CandidateSpec) -> str`의 SVG 출력 확장
- 아래 primitive의 최소 SVG output
  - `formula_line`
  - `text_note`
  - `highlight_line`
  - `highlight_curve`
  - `arrow`
  - `box`
  - `circle`
  - `point_label`
  - `segment_label`
  - `dimension_line`
  - `dimension_curve`
  - `freehand_dimension_marker`
- source image artifact id를 최상위 `<svg>` data attribute로 보존
- unsupported 또는 malformed geometry의 no-crash skip policy
- renderer 단위 테스트

이번 milestone에서 구현하지 않는다.

- 원본 bitmap 합성
- PNG/PDF export
- FastAPI render endpoint 추가
- Web/Konva renderer 변경
- OpenAI image model 호출
- handwriting style bitmap generation
- graph, shaded area, choice mark, angle mark renderer

## 3. Renderer 공통 계약

### 3.1 입력

렌더러 입력은 `cleansolve_spec.models.CandidateSpec`이다. 렌더러는 `CandidateSpec`을 수정하지 않는다.

### 3.2 최상위 SVG

`render_overlay_svg`는 항상 parse 가능한 SVG 문자열을 반환한다.

최상위 `<svg>`는 다음 attribute를 가진다.

- `xmlns="http://www.w3.org/2000/svg"`
- `width="{spec.page.width}"`
- `height="{spec.page.height}"`
- `viewBox="0 0 {spec.page.width} {spec.page.height}"`
- `data-problem-image-id="{spec.source_images['problem_image_id']}"`
- `data-teacher-solution-image-id="{spec.source_images['teacher_solution_image_id']}"`

`source_images`에 해당 key가 없으면 해당 data attribute만 생략한다.

### 3.3 숫자 formatting

숫자는 기존 `_format_number` 정책을 유지한다.

- 0은 `"0"`으로 출력한다.
- 그 외 숫자는 `"{value:.15g}"`로 출력한다.
- finite `int` 또는 `float`만 유효한 좌표/길이로 본다.

### 3.4 좌표와 bbox

point는 `[x, y]` 또는 `(x, y)`이고, x/y는 finite number여야 한다.

bbox는 `[x, y, width, height]` 형식만 renderer 입력으로 인정한다. width/height는 0보다 커야 한다.

### 3.5 group attribute

렌더링되는 모든 element는 최상위 child로 `<g>`를 하나 만든다. 이 group은 다음 attribute를 가진다.

- `data-element-id="{element.id}"`
- `data-primitive-type="{element.type}"`

primitive별 target anchor가 있는 경우 아래 attribute를 추가한다.

- `data-target-anchor-start`
- `data-target-anchor-end`

attribute value와 text node는 XML escape한다.

### 3.6 색상

색상은 문자열 검증 없이 그대로 SVG attribute로 출력한다. 이유는 renderer가 style validator가 아니며 기존 동작도 `element.color`를 escape 후 출력한다.

기본 색상은 primitive별 계약을 따른다.

### 3.7 style override

renderer는 `element.style`을 제한적으로만 읽는다.

- `stroke_width`: finite positive number이면 stroke width로 사용한다.
- `opacity`: finite number이고 0 이상 1 이하이면 opacity로 사용한다.
- `font_size`: finite positive number이면 text font size로 사용한다.

이외 style key는 M3에서 무시한다.

### 3.8 label/text 우선순위

텍스트 primitive 또는 label primitive의 표시 문자열은 다음 순서로 선택한다.

1. `element.display_text`
2. `element.text`
3. `geometry["text"]`
4. `geometry["label"]`
5. `element.label`

문자열 후보가 `None`이면 다음 후보로 넘어간다. 빈 문자열 `""`은 유효하지 않은 텍스트로 보고 element를 skip한다.

기존 dimension/freehand label은 기존 `_render_label` 계약을 유지한다. 즉 `geometry["label"]`이 있으면 우선하고, 없으면 `element.label`을 쓴다.

## 4. Primitive별 출력 계약

### 4.1 `formula_line`

필수 입력:

- anchor point: `geometry["anchor"]`
- 표시 문자열: 3.8의 text 우선순위 중 하나

선택 입력:

- `element.color`, 기본값 `"black"`
- `element.style["font_size"]`, 기본값 `18`

SVG 출력:

- `<g data-element-id ... data-primitive-type="formula_line">`
- child `<text>`
  - `x`, `y`: anchor
  - `fill`: color
  - `font-family="serif"`
  - `font-size`: style override 또는 `18`
  - `data-text-kind="formula_line"`
  - text content: escaped 표시 문자열

skip 조건:

- anchor가 유효 point가 아니다.
- 표시 문자열이 없다.

### 4.2 `text_note`

필수 입력:

- anchor point: `geometry["anchor"]`
- 표시 문자열: 3.8의 text 우선순위 중 하나

선택 입력:

- `element.color`, 기본값 `"black"`
- `element.style["font_size"]`, 기본값 `16`

SVG 출력:

- `<g data-element-id ... data-primitive-type="text_note">`
- child `<text>`
  - `x`, `y`: anchor
  - `fill`: color
  - `font-family="sans-serif"`
  - `font-size`: style override 또는 `16`
  - `data-text-kind="text_note"`
  - text content: escaped 표시 문자열

skip 조건:

- anchor가 유효 point가 아니다.
- 표시 문자열이 없다.

### 4.3 `highlight_line`

필수 입력:

- start point: `geometry["start"]`
- end point: `geometry["end"]`

선택 입력:

- `element.color`, 기본값 `"#ffd84d"`
- `element.style["stroke_width"]`, 기본값 `8`
- `element.style["opacity"]`, 기본값 `0.35`

SVG 출력:

- child `<line>`
  - `x1`, `y1`, `x2`, `y2`: start/end
  - `stroke`: color
  - `stroke-width`: style override 또는 `8`
  - `stroke-linecap="round"`
  - `opacity`: style override 또는 `0.35`

skip 조건:

- start 또는 end가 유효 point가 아니다.

### 4.4 `highlight_curve`

필수 입력:

- start point: `geometry["start"]`
- end point: `geometry["end"]`
- control point list: `geometry["control_points"]`

선택 입력:

- `element.color`, 기본값 `"#ffd84d"`
- `element.style["stroke_width"]`, 기본값 `8`
- `element.style["opacity"]`, 기본값 `0.35`

SVG 출력:

- child `<path>`
  - control point가 1개이면 `d="M {start} Q {control0} {end}"`
  - control point가 2개 이상이고 첫 두 control point가 유효하면 `d="M {start} C {control0} {control1} {end}"`
  - `fill="none"`
  - `stroke`: color
  - `stroke-width`: style override 또는 `8`
  - `stroke-linecap="round"`
  - `stroke-linejoin="round"`
  - `opacity`: style override 또는 `0.35`

skip 조건:

- start 또는 end가 유효 point가 아니다.
- control point list가 비어 있다.
- 첫 control point가 유효 point가 아니다.

### 4.5 `arrow`

필수 입력:

- start point: `geometry["start"]`
- end point: `geometry["end"]`

선택 입력:

- `element.color`, 기본값 `"black"`
- `element.style["stroke_width"]`, 기본값 `2`

SVG 출력:

- child `<line>`
  - `x1`, `y1`, `x2`, `y2`: start/end
  - `stroke`: color
  - `stroke-width`: style override 또는 `2`
  - `stroke-linecap="round"`
  - `marker-end="url(#cleansolve-arrowhead)"`

최상위 SVG에 arrow가 하나 이상 있으면 `<defs>`를 body 앞에 추가한다.

- marker id는 반드시 `cleansolve-arrowhead`
- marker path는 `d="M 0 0 L 10 5 L 0 10 z"`
- marker fill은 `"black"`

M3에서는 marker fill을 element color별로 바꾸지 않는다.

skip 조건:

- start 또는 end가 유효 point가 아니다.

### 4.6 `box`

필수 입력:

- bbox: `geometry["bbox"]`가 유효하면 그것을 사용한다.
- `geometry["bbox"]`가 없으면 `element.bbox`를 사용한다.

선택 입력:

- `element.color`, 기본값 `"black"`
- `element.style["stroke_width"]`, 기본값 `2`

SVG 출력:

- child `<rect>`
  - `x`, `y`, `width`, `height`: bbox
  - `fill="none"`
  - `stroke`: color
  - `stroke-width`: style override 또는 `2`

skip 조건:

- geometry bbox와 element bbox가 모두 유효 bbox가 아니다.

### 4.7 `circle`

필수 입력:

- `geometry["center"]` point와 `geometry["radius"]` positive finite number
- 또는 fallback bbox: `geometry["bbox"]`가 유효하면 그것을 사용한다.
- `geometry["bbox"]`가 없으면 `element.bbox`를 사용한다.

선택 입력:

- `element.color`, 기본값 `"black"`
- `element.style["stroke_width"]`, 기본값 `2`

SVG 출력:

- center/radius 입력이 유효하면 child `<circle>`
  - `cx`, `cy`: center
  - `r`: radius
- bbox fallback이면 child `<circle>`
  - `cx`: `bbox.x + bbox.width / 2`
  - `cy`: `bbox.y + bbox.height / 2`
  - `r`: `min(bbox.width, bbox.height) / 2`
- 공통 attribute
  - `fill="none"`
  - `stroke`: color
  - `stroke-width`: style override 또는 `2`

skip 조건:

- center/radius도 유효하지 않고 fallback bbox도 유효하지 않다.

### 4.8 `point_label`

필수 입력:

- point: `geometry["point"]`
- 표시 문자열: 3.8의 text 우선순위 중 하나

선택 입력:

- label anchor: `geometry["label_anchor"]`, 없으면 `[point.x + 8, point.y - 8]`
- `element.color`, 기본값 `"black"`
- `element.style["font_size"]`, 기본값 `14`

SVG 출력:

- child `<circle>`
  - `cx`, `cy`: point
  - `r="3"`
  - `fill`: color
- child `<text>`
  - `x`, `y`: label anchor
  - `fill`: color
  - `font-family="sans-serif"`
  - `font-size`: style override 또는 `14`
  - text content: escaped 표시 문자열

skip 조건:

- point가 유효 point가 아니다.
- 표시 문자열이 없다.

### 4.9 `segment_label`

필수 입력:

- start point: `geometry["start"]`
- end point: `geometry["end"]`
- 표시 문자열: 3.8의 text 우선순위 중 하나

선택 입력:

- label anchor: `geometry["label_anchor"]`, 없으면 start/end midpoint
- `element.color`, 기본값 `"black"`
- `element.style["font_size"]`, 기본값 `14`

SVG 출력:

- child `<text>`
  - `x`, `y`: label anchor 또는 midpoint
  - `fill`: color
  - `font-family="sans-serif"`
  - `font-size`: style override 또는 `14`
  - text content: escaped 표시 문자열

skip 조건:

- start 또는 end가 유효 point가 아니다.
- 표시 문자열이 없다.

### 4.10 `dimension_line`

기존 구현을 유지한다.

필수 입력:

- `geometry["visible_start"]`와 `geometry["visible_end"]`
- 또는 fallback `geometry["target_anchor_start"]`와 `geometry["target_anchor_end"]`

SVG 출력:

- group attribute:
  - `data-target-anchor-start`
  - `data-target-anchor-end`
- child `<line>`
- optional child `<text>` from `_render_label`

skip 조건:

- visible fallback 후 start/end가 유효 point가 아니다.

### 4.11 `dimension_curve`

기존 구현을 유지한다.

필수 입력:

- `geometry["visible_start"]`와 `geometry["visible_end"]`
- 또는 fallback `geometry["target_anchor_start"]`와 `geometry["target_anchor_end"]`
- `geometry["control_points"]` 또는 `geometry["curve_control_points"]`

SVG 출력:

- control point 1개이면 quadratic path
- control point 2개 이상이면 cubic path
- optional child `<text>` from `_render_label`

skip 조건:

- visible fallback 후 start/end가 유효 point가 아니다.
- control point list가 비어 있다.
- 첫 control point가 유효 point가 아니다.

### 4.12 `freehand_dimension_marker`

기존 구현을 유지한다.

필수 입력:

- element type이 `freehand_dimension_marker`

선택 입력:

- `geometry["target_anchor_start"]`
- `geometry["target_anchor_end"]`
- `geometry["visible_strokes"]`
- `geometry["stroke_continuity"]`
- label via `_render_label`

SVG 출력:

- group attribute:
  - `data-target-anchor-start`
  - `data-target-anchor-end`
  - `data-stroke-continuity`
- valid visible stroke마다 child `<polyline>`
- optional child `<text>` from `_render_label`

skip 조건:

- group 자체는 만들 수 있다.
- malformed stroke는 해당 stroke만 skip한다.
- label anchor가 없으면 label만 skip한다.

## 5. Unsupported primitive 정책

M3 범위 밖 primitive는 crash 없이 빈 문자열로 skip한다.

- `angle_mark`
- `graph_point`
- `graph_curve`
- `graph_tangent`
- `shaded_area`
- `choice_mark`
- `freehand_annotation`
- `unsupported_annotation`

이 milestone에서는 skip된 element 목록을 별도 report로 반환하지 않는다. validation report가 필요한 경우 M8에서 보강한다.

## 6. 테스트 요구사항

renderer test는 다음을 검증한다.

1. source image id가 SVG metadata로 보존된다.
2. `formula_line`과 `text_note`가 text fallback 우선순위와 escaping을 지킨다.
3. `highlight_line`, `highlight_curve`, `arrow`가 expected primitive-specific SVG tag를 만든다.
4. arrow가 있을 때 `<defs>`와 `marker-end`가 포함된다.
5. `box`, `circle`이 bbox fallback을 사용한다.
6. `point_label`, `segment_label`이 label anchor fallback을 사용한다.
7. 기존 `dimension_line`, `dimension_curve`, `freehand_dimension_marker` 테스트는 계속 통과한다.
8. malformed geometry와 unsupported primitive는 exception 없이 skip된다.

## 7. 완료 조건

M3는 다음 조건을 모두 만족하면 Done이다.

- `packages/renderer/tests/test_overlay.py`에 M3 primitive coverage가 추가된다.
- `python -m pytest packages/renderer/tests/test_overlay.py -q`가 통과한다.
- `python -m pytest -q`가 통과한다.
- `docs/product/mvp-roadmap.md`의 M3 상태가 Done으로 갱신된다.
- 모든 README류/문서 변경은 한국어로 작성된다.
