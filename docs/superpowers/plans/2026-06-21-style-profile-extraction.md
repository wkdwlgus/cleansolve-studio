# Style Profile Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Style Lab 산출물과 GPT-5.5를 사용해 `default_pretty_handwriting v1` style profile JSON을 생성하는 opt-in 추출기를 만든다.

**Architecture:** `tools/style_lab` 안에 schema, prompt, extractor를 독립 모듈로 추가하고, 기존 CLI에 `extract-profile` subcommand를 붙인다. 기본 테스트와 기본 CLI는 mock extractor만 사용하고, 실제 OpenAI 호출은 opt-in smoke test와 `--client openai`에서만 실행한다.

**Tech Stack:** Python 3.11, pytest, Pillow, jsonschema, OpenAI Responses API, existing `tools/style_lab` package.

---

## Source Spec

- Design spec: `docs/superpowers/specs/2026-06-21-style-profile-extraction-design.md`

## Files

- Create: `tools/style_lab/style_profile_schema.py`
- Create: `tools/style_lab/style_profile_prompt.py`
- Create: `tools/style_lab/style_profile_extractor.py`
- Create: `tools/style_lab/tests/test_style_profile_schema.py`
- Create: `tools/style_lab/tests/test_style_profile_extractor.py`
- Create: `tools/style_lab/tests/test_extract_profile_cli.py`
- Create: `tools/style_lab/tests/test_openai_style_profile_smoke.py`
- Modify: `tools/style_lab/cli.py`
- Modify: `tools/style_lab/README.md`
- Modify: `docs/product/handwriting-style-reference-set.md`
- Modify: `apps/api/.env.example`

## Contracts To Preserve

- 기본 pytest는 OpenAI API를 호출하지 않는다.
- API key는 stdout, stderr, test failure message, generated JSON에 포함하지 않는다.
- `/image` 아래 생성물은 git에 포함하지 않는다.
- `style_profile.generated.json`은 schema validation을 통과해야 한다.
- `reference_image_root`가 없으면 OpenAI extractor는 원본 이미지를 0장 첨부하고 성공한다.
- 선택된 reference image 파일이 없으면 해당 파일만 건너뛴다.
- 선택된 reference image 파일이 존재하지만 PNG/JPEG가 아니면 `StyleLabInputError("unsupported style profile image type: <filename>")`로 실패한다.

---

### Task 1: Style Profile Schema

**Files:**
- Create: `tools/style_lab/style_profile_schema.py`
- Test: `tools/style_lab/tests/test_style_profile_schema.py`

- [ ] **Step 1: Write failing schema tests**

Create `tools/style_lab/tests/test_style_profile_schema.py` with tests named exactly:

```python
def test_valid_style_profile_passes_validation():
    profile = build_mock_style_profile()
    validate_style_profile(profile)

def test_palette_requires_hex_color():
    profile = build_mock_style_profile()
    profile["tokens"]["palette"]["blue"] = "blue"
    with pytest.raises(StyleLabInputError, match="style profile schema validation failed"):
        validate_style_profile(profile)

def test_required_top_level_field_is_enforced():
    profile = build_mock_style_profile()
    del profile["quality_gates"]
    with pytest.raises(StyleLabInputError, match="style profile schema validation failed"):
        validate_style_profile(profile)

def test_numeric_token_range_is_enforced():
    profile = build_mock_style_profile()
    profile["tokens"]["stroke"]["black_width_px"] = 99
    with pytest.raises(StyleLabInputError, match="style profile schema validation failed"):
        validate_style_profile(profile)

def test_needs_review_requires_uncertainty():
    profile = build_mock_style_profile()
    profile["status"] = "needs_review"
    profile["uncertainties"] = []
    with pytest.raises(StyleLabInputError, match="needs_review requires at least one uncertainty"):
        validate_style_profile(profile)
```

The test file imports `pytest`, `StyleLabInputError`, `build_mock_style_profile`, and `validate_style_profile`.

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tools/style_lab/tests/test_style_profile_schema.py -q
```

Expected: FAIL because `tools.style_lab.style_profile_schema` does not exist.

- [ ] **Step 3: Implement schema module**

Create `tools/style_lab/style_profile_schema.py` with:

- Constant `STYLE_PROFILE_SCHEMA_NAME = "style_profile_v1"`.
- Constant `STYLE_PROFILE_SCHEMA` containing the JSON Schema described in the design spec.
- Function `build_mock_style_profile() -> dict[str, object]`.
- Function `validate_style_profile(profile: dict[str, object]) -> None`.
- Internal rule after jsonschema validation: if `profile["status"] == "needs_review"` and `profile["uncertainties"] == []`, raise `StyleLabInputError("needs_review requires at least one uncertainty")`.
- jsonschema errors are wrapped as `StyleLabInputError("style profile schema validation failed")`.

The mock profile uses:

```python
{
    "preset_id": "default_pretty_handwriting",
    "preset_version": "v1",
    "schema_version": "style_profile.v1",
    "status": "generated",
    "source": "gpt-5.5_style_profile_extraction",
    "reference_summary": {
        "core_sample_count": 19,
        "extended_sample_count": 26,
        "input_artifacts": [
            "core_contact_sheet.jpg",
            "calibration_manifest.json",
            "style_tokens.skeleton.json",
        ],
        "visual_coverage_notes": ["max_ink_sample_id=GT_132", "max_color_sample_id=GT_135"],
    },
    "style_description": {
        "overall": "균일한 검정 필기와 제한된 빨강/파랑 보조선을 사용하는 풀이 스타일",
        "korean_text": "한글 설명은 작고 촘촘하되 수식 baseline과 붙지 않는다",
        "formula": "분수선과 등호는 얇고 일정하며 기호 기울기는 작다",
        "diagram_annotations": "도형 라벨은 선과 겹치지 않게 짧은 offset을 둔다",
        "color_usage": "빨강은 강조, 파랑은 보조선과 선택 구간에 사용한다",
        "spacing_and_layout": "풀이 블록은 문제 여백을 침범하지 않고 줄 간격을 일정하게 둔다",
    },
    "tokens": {
        "stroke": {"black_width_px": 1.8, "blue_width_px": 2.2, "red_width_px": 2.2, "jitter_px": 1.5, "opacity": 0.96},
        "text": {"korean_baseline_jitter_px": 1.0, "letter_spacing_px": 0.0, "line_height_ratio": 1.18, "size_ratio_to_formula": 0.92},
        "formula": {"baseline_jitter_px": 1.0, "fraction_bar_width_px": 1.4, "symbol_slant_deg": -2.0, "vertical_compactness": 0.94},
        "diagram": {"label_offset_px": 6.0, "annotation_line_width_px": 1.8, "hatching_gap_px": 10.0, "hatching_angle_jitter_deg": 3.0},
        "palette": {"black": "#222222", "blue": "#3448b8", "red_orange": "#d85a3a"},
    },
    "renderer_recommendations": [
        {"target": "stroke", "recommendation": "검정 stroke를 2px 이하로 유지한다", "reason": "core sheet의 검정 필기가 얇다", "priority": "high"}
    ],
    "quality_gates": {
        "style_similarity_threshold": 0.78,
        "max_visual_diff_ratio": 0.22,
        "requires_human_review_if_below": 0.72,
        "notes": ["첫 버전은 사람 검수를 전제로 한다"],
    },
    "uncertainties": [],
}
```

- [ ] **Step 4: Run schema tests and verify pass**

Run:

```bash
pytest tools/style_lab/tests/test_style_profile_schema.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add tools/style_lab/style_profile_schema.py tools/style_lab/tests/test_style_profile_schema.py
git commit -m "feat(style-lab): add style profile schema"
```

---

### Task 2: Prompt And Extractor

**Files:**
- Create: `tools/style_lab/style_profile_prompt.py`
- Create: `tools/style_lab/style_profile_extractor.py`
- Test: `tools/style_lab/tests/test_style_profile_extractor.py`

- [ ] **Step 1: Write failing extractor tests**

Create `tools/style_lab/tests/test_style_profile_extractor.py` with tests named exactly:

```python
def test_mock_extractor_returns_deterministic_valid_profile(tmp_path):
    extraction_input = make_extraction_input(tmp_path)
    profile = MockStyleProfileExtractor().extract(extraction_input)
    validate_style_profile(profile)
    assert profile["preset_id"] == "default_pretty_handwriting"
    assert "max_ink_sample_id=" in " ".join(profile["reference_summary"]["visual_coverage_notes"])

def test_missing_required_artifact_raises_style_lab_error(tmp_path):
    extraction_input = make_extraction_input(tmp_path, omit_core_sheet=True)
    with pytest.raises(StyleLabInputError, match="missing style lab artifacts: core_contact_sheet.jpg"):
        MockStyleProfileExtractor().extract(extraction_input)

def test_reference_image_root_can_be_absent(tmp_path):
    extraction_input = make_extraction_input(tmp_path, reference_root_exists=False)
    client = FakeOpenAIClient(build_mock_style_profile())
    OpenAIStyleProfileExtractor(api_key="test-key", client=client, timeout_seconds=90).extract(extraction_input)
    assert count_request_images(client.last_request) == 1

def test_missing_selected_reference_image_is_skipped(tmp_path):
    extraction_input = make_extraction_input(tmp_path, reference_ids=["GT_024"])
    client = FakeOpenAIClient(build_mock_style_profile())
    OpenAIStyleProfileExtractor(api_key="test-key", client=client, timeout_seconds=90).extract(extraction_input)
    assert count_request_images(client.last_request) == 2

def test_data_url_helper_encodes_png_and_jpeg(tmp_path):
    png_path = create_rgb_image(tmp_path / "sample.png")
    jpg_path = create_rgb_image(tmp_path / "sample.jpg")
    assert _image_to_data_url(png_path).startswith("data:image/png;base64,")
    assert _image_to_data_url(jpg_path).startswith("data:image/jpeg;base64,")

def test_unsupported_reference_image_type_raises(tmp_path):
    extraction_input = make_extraction_input(tmp_path, reference_ids=["GT_024"])
    (extraction_input.reference_image_root / "GT_024.png").write_text("not an image", encoding="utf-8")
    with pytest.raises(StyleLabInputError, match="unsupported style profile image type: GT_024.png"):
        OpenAIStyleProfileExtractor(api_key="test-key", client=FakeOpenAIClient(build_mock_style_profile()), timeout_seconds=90).extract(extraction_input)

def test_openai_request_contains_messages_images_and_schema(tmp_path):
    extraction_input = make_extraction_input(tmp_path, reference_ids=["GT_024", "GT_036"])
    client = FakeOpenAIClient(build_mock_style_profile())
    OpenAIStyleProfileExtractor(api_key="test-key", client=client, timeout_seconds=90).extract(extraction_input)
    request = client.last_request
    assert request["model"] == "gpt-5.5"
    assert request["text"]["format"]["name"] == "style_profile_v1"
    assert request["text"]["format"]["strict"] is True
    assert request["input"][0]["role"] == "developer"
    assert request["input"][1]["role"] == "user"
    assert count_request_images(request) == 3

def test_invalid_json_response_is_wrapped(tmp_path):
    extraction_input = make_extraction_input(tmp_path)
    with pytest.raises(StyleLabInputError, match="OpenAI style profile response was not valid JSON"):
        OpenAIStyleProfileExtractor(api_key="test-key", client=FakeOpenAIClient("not-json"), timeout_seconds=90).extract(extraction_input)

def test_schema_invalid_response_is_wrapped(tmp_path):
    extraction_input = make_extraction_input(tmp_path)
    invalid_profile = build_mock_style_profile()
    del invalid_profile["tokens"]
    with pytest.raises(StyleLabInputError, match="OpenAI style profile response failed schema validation"):
        OpenAIStyleProfileExtractor(api_key="test-key", client=FakeOpenAIClient(invalid_profile), timeout_seconds=90).extract(extraction_input)
```

The test file defines helper functions `make_extraction_input`, `create_rgb_image`, `count_request_images`, and class `FakeOpenAIClient`. `FakeOpenAIClient.responses.create(**kwargs)` stores `kwargs` in `last_request` and returns an object whose `output_text` is either the provided string or `json.dumps(payload, ensure_ascii=False)`.

- [ ] **Step 2: Run extractor tests and verify failure**

Run:

```bash
pytest tools/style_lab/tests/test_style_profile_extractor.py -q
```

Expected: FAIL because extractor modules do not exist.

- [ ] **Step 3: Implement prompt module**

Create `tools/style_lab/style_profile_prompt.py` with:

- Constant `STYLE_PROFILE_DEVELOPER_PROMPT`.
- Function `build_style_profile_user_prompt(*, preset_id: str, preset_version: str, manifest: dict[str, object], skeleton: dict[str, object], max_reference_images: int) -> str`.
- The user prompt includes preset id/version, core/extended counts, metrics summary JSON, input artifact names, max reference image count, and token key paths.
- The prompt does not embed the full JSON Schema.

- [ ] **Step 4: Implement extractor module**

Create `tools/style_lab/style_profile_extractor.py` with:

- Dataclass `StyleProfileExtractionInput`.
- Class `MockStyleProfileExtractor` with method `extract(input: StyleProfileExtractionInput) -> dict[str, object]`.
- Class `OpenAIStyleProfileExtractor` with constructor `api_key: str`, `client: object | None`, `timeout_seconds: int` and method `extract(input: StyleProfileExtractionInput) -> dict[str, object]`.
- Private helper `_load_required_artifacts(input_root: Path) -> tuple[Path, dict[str, object], dict[str, object]]`.
- Private helper `_image_to_data_url(path: Path) -> str`.
- Private helper `_selected_reference_images(reference_image_root: Path, max_reference_images: int) -> list[Path]`.
- Private helper `_extract_output_text(response: object) -> str`.

Request shape:

```python
client.responses.create(
    model=input.model,
    input=[
        {"role": "developer", "content": [{"type": "input_text", "text": STYLE_PROFILE_DEVELOPER_PROMPT}]},
        {"role": "user", "content": user_content},
    ],
    text={
        "format": {
            "type": "json_schema",
            "name": STYLE_PROFILE_SCHEMA_NAME,
            "schema": STYLE_PROFILE_SCHEMA,
            "strict": True,
        }
    },
    timeout=timeout_seconds,
)
```

`user_content` order:

1. `{"type": "input_text", "text": user_prompt}`
2. `{"type": "input_image", "image_url": _image_to_data_url(core_contact_sheet), "detail": api_detail}`
3. one `input_image` item per selected reference image

`api_detail` is `auto` when input detail is `original`; otherwise it is the provided detail.

- [ ] **Step 5: Run extractor tests and verify pass**

Run:

```bash
pytest tools/style_lab/tests/test_style_profile_extractor.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add tools/style_lab/style_profile_prompt.py tools/style_lab/style_profile_extractor.py tools/style_lab/tests/test_style_profile_extractor.py
git commit -m "feat(style-lab): add style profile extractor"
```

---

### Task 3: Extract Profile CLI

**Files:**
- Modify: `tools/style_lab/cli.py`
- Test: `tools/style_lab/tests/test_extract_profile_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tools/style_lab/tests/test_extract_profile_cli.py` with tests named exactly:

```python
def test_extract_profile_mock_writes_output_json(tmp_path):
    input_root = build_style_lab_input_root(tmp_path)
    output_path = tmp_path / "profile.json"
    result = run_cli(["extract-profile", "--input-root", str(input_root), "--output-path", str(output_path), "--client", "mock"])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["client"] == "mock"
    assert payload["model"] == "gpt-5.5"
    assert payload["core_sample_count"] == 19
    assert payload["reference_image_count"] == 0
    validate_style_profile(json.loads(output_path.read_text(encoding="utf-8")))

def test_extract_profile_missing_core_sheet_returns_code_2(tmp_path):
    input_root = build_style_lab_input_root(tmp_path)
    (input_root / "core_contact_sheet.jpg").unlink()
    result = run_cli(["extract-profile", "--input-root", str(input_root), "--output-path", str(tmp_path / "profile.json")])
    assert result.returncode == 2
    assert result.stderr.startswith("Style Lab input error:")
    assert "core_contact_sheet.jpg" in result.stderr

def test_extract_profile_output_parent_file_returns_code_2(tmp_path):
    input_root = build_style_lab_input_root(tmp_path)
    parent_file = tmp_path / "not-dir"
    parent_file.write_text("file", encoding="utf-8")
    result = run_cli(["extract-profile", "--input-root", str(input_root), "--output-path", str(parent_file / "profile.json")])
    assert result.returncode == 2
    assert "output path parent is not a directory" in result.stderr

def test_extract_profile_rejects_negative_max_reference_images(tmp_path):
    input_root = build_style_lab_input_root(tmp_path)
    result = run_cli(["extract-profile", "--input-root", str(input_root), "--max-reference-images", "-1"])
    assert result.returncode == 2
    assert "max-reference-images must be between 0 and 6" in result.stderr

def test_extract_profile_rejects_max_reference_images_over_six(tmp_path):
    input_root = build_style_lab_input_root(tmp_path)
    result = run_cli(["extract-profile", "--input-root", str(input_root), "--max-reference-images", "7"])
    assert result.returncode == 2
    assert "max-reference-images must be between 0 and 6" in result.stderr

def test_extract_profile_openai_without_api_key_returns_code_2(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    input_root = build_style_lab_input_root(tmp_path)
    result = run_cli(["extract-profile", "--input-root", str(input_root), "--client", "openai"])
    assert result.returncode == 2
    assert "OPENAI_API_KEY is required for OpenAI style profile extraction" in result.stderr
```

The test helper `build_style_lab_input_root` writes the three required artifacts: a valid `core_contact_sheet.jpg`, `calibration_manifest.json`, and `style_tokens.skeleton.json`.

- [ ] **Step 2: Run CLI tests and verify failure**

Run:

```bash
pytest tools/style_lab/tests/test_extract_profile_cli.py -q
```

Expected: FAIL because `extract-profile` command is not registered.

- [ ] **Step 3: Add CLI command**

Modify `tools/style_lab/cli.py`:

- Add import for `StyleProfileExtractionInput`, `MockStyleProfileExtractor`, `OpenAIStyleProfileExtractor`.
- Add helper `_parse_bounded_int(value: object, option_name: str, minimum: int, maximum: int) -> int`.
- Add helper `_validate_profile_output_path(output_path: Path) -> None`.
- Add function `extract_style_profile(args: argparse.Namespace) -> dict[str, object]`.
- Add subparser `extract-profile` with all options from the design spec.
- In `main`, dispatch `args.command == "extract-profile"` to `extract_style_profile(args)`.

`extract_style_profile` behavior:

- Resolve `model` from `args.model or os.environ.get("OPENAI_MODEL_ANALYSIS") or "gpt-5.5"`.
- Resolve `image_detail` from `args.image_detail or os.environ.get("OPENAI_STYLE_PROFILE_IMAGE_DETAIL") or "auto"`.
- Resolve `timeout_seconds` from `args.timeout_seconds or os.environ.get("OPENAI_STYLE_PROFILE_TIMEOUT_SECONDS") or "90"`.
- Validate `max_reference_images` between 0 and 6.
- For `--client mock`, call `MockStyleProfileExtractor`.
- For `--client openai`, require `OPENAI_API_KEY`, then call `OpenAIStyleProfileExtractor`.
- Write profile JSON inside extractor and print one-line JSON summary.

- [ ] **Step 4: Run CLI tests and verify pass**

Run:

```bash
pytest tools/style_lab/tests/test_extract_profile_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add tools/style_lab/cli.py tools/style_lab/tests/test_extract_profile_cli.py
git commit -m "feat(style-lab): add extract-profile CLI"
```

---

### Task 4: Opt-in OpenAI Smoke Test And Docs

**Files:**
- Create: `tools/style_lab/tests/test_openai_style_profile_smoke.py`
- Modify: `tools/style_lab/README.md`
- Modify: `docs/product/handwriting-style-reference-set.md`
- Modify: `apps/api/.env.example`

- [ ] **Step 1: Write opt-in smoke test**

Create `tools/style_lab/tests/test_openai_style_profile_smoke.py` with one test:

```python
def test_openai_style_profile_smoke_generates_valid_profile():
    if os.environ.get("CLEANSOLVE_RUN_OPENAI_STYLE_SMOKE") != "1":
        pytest.skip("set CLEANSOLVE_RUN_OPENAI_STYLE_SMOKE=1 to run OpenAI style smoke")
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required")
    input_root = Path("image/style-lab/default_pretty_handwriting/v1")
    required = ["core_contact_sheet.jpg", "calibration_manifest.json", "style_tokens.skeleton.json"]
    missing = [name for name in required if not (input_root / name).exists()]
    if missing:
        pytest.skip(f"missing local style lab artifacts: {', '.join(missing)}")
    output_path = input_root / "style_profile.generated.json"
    extraction_input = StyleProfileExtractionInput(
        preset_id="default_pretty_handwriting",
        preset_version="v1",
        input_root=input_root,
        reference_image_root=Path("image/clean_solutions"),
        output_path=output_path,
        model=os.environ.get("OPENAI_MODEL_ANALYSIS", "gpt-5.5"),
        image_detail=os.environ.get("OPENAI_STYLE_PROFILE_IMAGE_DETAIL", "auto"),
        max_reference_images=0,
    )
    extractor = OpenAIStyleProfileExtractor(
        api_key=os.environ["OPENAI_API_KEY"],
        client=None,
        timeout_seconds=int(os.environ.get("OPENAI_STYLE_PROFILE_TIMEOUT_SECONDS", "90")),
    )
    profile = extractor.extract(extraction_input)
    validate_style_profile(profile)
    assert output_path.exists()
    assert profile["preset_id"] == "default_pretty_handwriting"
    assert profile["preset_version"] == "v1"
```

- [ ] **Step 2: Update env example**

Append to `apps/api/.env.example`:

```text
OPENAI_STYLE_PROFILE_IMAGE_DETAIL=auto
OPENAI_STYLE_PROFILE_TIMEOUT_SECONDS=90
CLEANSOLVE_RUN_OPENAI_STYLE_SMOKE=0
```

- [ ] **Step 3: Update Korean Style Lab README**

Modify `tools/style_lab/README.md`:

- State that `build` creates deterministic artifacts.
- State that `extract-profile --client mock` creates a schema-valid local style profile without API calls.
- State that `extract-profile --client openai` calls GPT-5.5 through the OpenAI Responses API.
- Include exact commands for mock run and opt-in smoke test.
- State that `/image` outputs are ignored and not committed.

- [ ] **Step 4: Update product reference doc**

Modify `docs/product/handwriting-style-reference-set.md`:

- Add a section `## GPT-5.5 Style Profile Extraction`.
- Link the design spec and this implementation plan.
- State that the generated file is `image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json`.
- State that the generated file is review input for the next renderer calibration milestone, not a renderer preset update.

- [ ] **Step 5: Run smoke test in skipped mode**

Run:

```bash
pytest tools/style_lab/tests/test_openai_style_profile_smoke.py -q
```

Expected: SKIPPED unless `CLEANSOLVE_RUN_OPENAI_STYLE_SMOKE=1` is present.

- [ ] **Step 6: Commit Task 4**

```bash
git add tools/style_lab/tests/test_openai_style_profile_smoke.py tools/style_lab/README.md docs/product/handwriting-style-reference-set.md apps/api/.env.example
git commit -m "docs(style-lab): document style profile extraction"
```

---

### Task 5: Verification And Real Opt-in Generation

**Files:**
- Generated ignored artifact: `image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json`

- [ ] **Step 1: Run Style Lab tests**

Run:

```bash
pytest tools/style_lab/tests -q
```

Expected: PASS with OpenAI smoke skipped unless opt-in env is set.

- [ ] **Step 2: Run existing Python suite**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/tmp/cleansolve-no-env python -m pytest apps/api/tests packages/ai/tests packages/harness/tests packages/renderer/tests packages/spec/tests packages/workflow/tests -q
```

Expected: PASS.

- [ ] **Step 3: Run mock extraction CLI**

Run:

```bash
python -m tools.style_lab.cli extract-profile --client mock
```

Expected: exit code 0 and one-line JSON with `"status": "ok"`, `"client": "mock"`, `"model": "gpt-5.5"`.

- [ ] **Step 4: Run opt-in OpenAI smoke**

Run:

```bash
CLEANSOLVE_RUN_OPENAI_STYLE_SMOKE=1 python -m pytest tools/style_lab/tests/test_openai_style_profile_smoke.py -q
```

Expected: PASS and `image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json` exists. If required `/image` artifacts are missing, rebuild with:

```bash
python -m tools.style_lab.cli build \
  --image-root image/clean_solutions \
  --output-root image/style-lab/default_pretty_handwriting/v1
```

Then run the smoke command again.

- [ ] **Step 5: Confirm generated artifact is ignored**

Run:

```bash
git status --short --ignored image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json
```

Expected: output starts with `!! image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json`.

- [ ] **Step 6: Request subagent review**

Request a final branch review using `superpowers:requesting-code-review` with two reviewers:

- Spec compliance reviewer: compare implementation against `docs/superpowers/specs/2026-06-21-style-profile-extraction-design.md`.
- Code quality reviewer: inspect tests, error handling, API key safety, and CLI behavior.

- [ ] **Step 7: Address review findings**

For each actionable finding:

1. Reproduce with a failing test or exact command.
2. Patch implementation.
3. Run the narrow test.
4. Run the relevant full verification command.
5. Commit with a `fix(style-lab): address review finding` message.

- [ ] **Step 8: Push branch and prepare PR**

Run:

```bash
git status --short
git push -u origin feat/style-profile-extraction
```

Prepare PR title:

```text
feat(style-lab): add GPT-5.5 style profile extraction
```

Prepare PR body:

```markdown
## 요약
- Style Lab 산출물을 GPT-5.5 style profile JSON으로 변환하는 schema/prompt/extractor를 추가했습니다.
- 기본 CLI와 테스트는 mock client를 사용하고, 실제 OpenAI 호출은 opt-in smoke test에서만 실행되도록 했습니다.
- `/image` 아래 generated profile은 git에 포함하지 않는 로컬 검수 산출물로 유지했습니다.

## 검증
- [ ] `pytest tools/style_lab/tests -q`
- [ ] `CLEANSOLVE_API_ENV_FILE=/tmp/cleansolve-no-env python -m pytest apps/api/tests packages/ai/tests packages/harness/tests packages/renderer/tests packages/spec/tests packages/workflow/tests -q`
- [ ] `python -m tools.style_lab.cli extract-profile --client mock`
- [ ] `CLEANSOLVE_RUN_OPENAI_STYLE_SMOKE=1 python -m pytest tools/style_lab/tests/test_openai_style_profile_smoke.py -q`
```
