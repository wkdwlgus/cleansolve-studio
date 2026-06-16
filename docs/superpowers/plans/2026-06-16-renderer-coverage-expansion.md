# M3 Renderer Coverage Expansion 구현 Plan

상세 설계: `docs/superpowers/specs/2026-06-16-renderer-coverage-expansion-design.md`

## 목표

`CandidateSpec`의 MVP primitive를 deterministic SVG overlay로 렌더링한다. 원본 이미지는 수정하지 않고, 원본 image artifact id는 SVG metadata로 보존한다.

## 구현 순서

### Task 1. Source image metadata test 추가

파일: `packages/renderer/tests/test_overlay.py`

1. `CandidateSpec.source_images`에 `problem_image_id`, `teacher_solution_image_id`를 넣는다.
2. `render_overlay_svg` 결과에 아래 attribute가 있는지 assert한다.
   - `data-problem-image-id="..."`
   - `data-teacher-solution-image-id="..."`
3. XML parse 가능성을 확인한다.

RED 예상: 현 renderer는 source image metadata attribute를 출력하지 않는다.

### Task 2. Text primitive test 추가

파일: `packages/renderer/tests/test_overlay.py`

1. `formula_line` element를 만든다.
   - `geometry["anchor"] = [30, 40]`
   - `display_text = "x < y"`
   - `color = "navy"`
   - `style["font_size"] = 20`
2. `text_note` element를 만든다.
   - `geometry["anchor"] = [50, 70]`
   - `geometry["text"] = "check & solve"`
3. assert:
   - `data-primitive-type="formula_line"`
   - `<text x="30" y="40" fill="navy" font-family="serif" font-size="20" data-text-kind="formula_line">x &lt; y</text>`
   - `data-primitive-type="text_note"`
   - `font-family="sans-serif"`
   - `check &amp; solve`

RED 예상: 현 renderer는 두 타입을 skip한다.

### Task 3. Highlight/arrow primitive test 추가

파일: `packages/renderer/tests/test_overlay.py`

1. `highlight_line` element:
   - `geometry["start"] = [10, 20]`
   - `geometry["end"] = [110, 20]`
2. `highlight_curve` element:
   - `geometry["start"] = [20, 80]`
   - `geometry["end"] = [120, 80]`
   - `geometry["control_points"] = [[70, 40]]`
3. `arrow` element:
   - `geometry["start"] = [15, 15]`
   - `geometry["end"] = [90, 45]`
4. assert:
   - highlight line `<line ... stroke="#ffd84d" stroke-width="8" ... opacity="0.35"`
   - highlight curve quadratic path `M 20,80 Q 70,40 120,80`
   - arrow line has `marker-end="url(#cleansolve-arrowhead)"`
   - SVG contains `<defs>` and `id="cleansolve-arrowhead"`

RED 예상: 현 renderer는 세 타입을 skip한다.

### Task 4. Shape/label primitive test 추가

파일: `packages/renderer/tests/test_overlay.py`

1. `box` element:
   - `geometry`에는 bbox를 넣지 않는다.
   - `element.bbox = [20, 30, 100, 50]`
2. `circle` element:
   - `geometry`에는 center/radius를 넣지 않는다.
   - `element.bbox = [100, 120, 40, 60]`
3. `point_label` element:
   - `geometry["point"] = [15, 25]`
   - `label = "A"`
   - label anchor 없음
4. `segment_label` element:
   - `geometry["start"] = [30, 90]`
   - `geometry["end"] = [130, 90]`
   - `label = "BC"`
   - label anchor 없음
5. assert:
   - box rect uses fallback bbox.
   - circle uses fallback center `120,150` and radius `20`.
   - point label circle is at `15,25`, label fallback anchor is `23,17`.
   - segment label fallback anchor is midpoint `80,90`.

RED 예상: 현 renderer는 네 타입을 skip한다.

### Task 5. Malformed/unsupported skip test 추가

파일: `packages/renderer/tests/test_overlay.py`

1. malformed `formula_line` with missing anchor
2. malformed `highlight_curve` with invalid control point
3. unsupported `angle_mark`
4. assert:
   - `render_overlay_svg`가 exception 없이 parse 가능한 SVG를 반환한다.
   - malformed/unsupported element id가 SVG에 포함되지 않는다.

RED 예상: 현 renderer는 unsupported는 skip하지만 malformed coverage가 명시되어 있지 않다. 새 primitive는 구현 전에는 전체 skip이다.

### Task 6. Renderer 구현

파일: `packages/renderer/cleansolve_renderer/overlay.py`

1. `render_overlay_svg`에서 element별 output을 list로 만든다.
2. arrow output이 하나 이상 있으면 body 앞에 `<defs>`를 넣는다.
3. 최상위 SVG attribute를 `_render_attrs`로 만든다.
4. `_render_element` dispatch를 상세 설계의 M3 primitive로 확장한다.
5. 다음 helper를 추가한다.
   - `_group_attrs(element)`
   - `_render_text_element(element, text_kind, font_family, default_font_size)`
   - `_render_highlight_line(element)`
   - `_render_highlight_curve(element)`
   - `_render_arrow(element)`
   - `_render_box(element)`
   - `_render_circle(element)`
   - `_render_point_label(element)`
   - `_render_segment_label(element)`
   - `_text_value(element)`
   - `_style_number(style, key, default, min_value=None, max_value=None)`
   - `_is_positive_number(value)`
   - `_as_bbox(value)`
5. 기존 dimension/freehand helper는 기존 테스트가 깨지지 않도록 attribute 순서를 유지한다.

### Task 7. Verification

실행:

```bash
python -m pytest packages/renderer/tests/test_overlay.py -q
python -m pytest -q
git diff --check
```

모두 통과해야 한다.

### Task 8. Review

Superpowers subagent-driven 흐름으로 최소 두 리뷰를 수행한다.

1. spec compliance reviewer
   - 상세 설계와 구현이 일치하는지 확인한다.
2. code quality reviewer
   - renderer helper 구조, escaping, malformed handling, 테스트 누락을 확인한다.

리뷰 지적이 있으면 수정 후 같은 verification을 재실행한다.

### Task 9. Roadmap 갱신과 커밋

파일: `docs/product/mvp-roadmap.md`

1. M3 상태를 `Done`으로 변경한다.
2. Renderer 상태 요약을 MVP primitive coverage 완료로 갱신한다.
3. SoT 성공 기준 추적에서 M3 관련 항목을 갱신한다.

커밋:

```bash
git add docs packages/renderer
git commit -m "feat(renderer): cover MVP overlay primitives"
git push origin feat/mvp-roadmap
```
