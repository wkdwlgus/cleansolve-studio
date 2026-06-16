# Local Dataset Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `image/`에 들어 있는 로컬 자료를 pilot 10개 문제 단위 샘플로 맞춰보고, 사람이 확인할 수 있는 contact sheet를 만든다.

**Architecture:** 제품 코드가 아니라 로컬 작업용 스크립트 하나로 처리한다. `GT_###.png`를 clean solution PDF 페이지에서 찾아 같은 page index의 original PDF에 bbox를 적용한다.

**Tech Stack:** Python, Pillow, OpenCV, numpy, PyMuPDF.

---

## Source Documents

- 설계 문서: `docs/superpowers/specs/2026-06-15-mvp-dataset-preparation-design.md`
- 입력 폴더: `image/`

## Scope Rules

- `image/`, `var/datasets/`, `.superpowers/`는 커밋하지 않는다.
- 이번 작업에서는 `--mode pilot`만 실행한다.
- `--mode full`은 pilot contact sheet 확인 뒤 별도 승인으로 실행한다.
- 패키지 구조, 테스트 패키지, schema 모듈은 만들지 않는다.

## Files

- Modify: `.gitignore`
- Create: `tools/datasets/local_match_dataset.py`
- Modify: `docs/superpowers/specs/2026-06-15-mvp-dataset-preparation-design.md`
- Modify: `docs/superpowers/plans/2026-06-15-mvp-dataset-preparation.md`

## Task 1: Ignore Local Inputs

- [ ] **Step 1: Add local ignore rules**

Append these lines to `.gitignore` if missing:

```gitignore
/image/
/.superpowers/
```

- [ ] **Step 2: Verify ignore rules**

Run:

```bash
git check-ignore image image/original_pages .superpowers
git status --short image
```

Expected:

- `git check-ignore` prints all three paths.
- `git status --short image` prints nothing.

## Task 2: Add One Local Matching Script

- [ ] **Step 1: Create `tools/datasets/local_match_dataset.py`**

The script must:

- accept `--mode pilot` and `--mode full`
- use these pilot indices: `1, 2, 3, 10, 20, 30, 50, 80, 110, 147`
- treat `B_###.png` and `GT_###.png` as the same crop-sequence pair
- find `GT_###.png` inside clean solution PDF pages by OpenCV template matching
- transfer the matched bbox to the same page index in the paired original PDF
- write output under `var/datasets/pilot/`
- put high-confidence matches in `samples/`
- put medium/low-confidence matches in `review_needed/`
- write `metadata.json` for each sample
- write `contact_sheet.html`

Use these fixed PDF pairs:

```python
PDF_PAIR_NAMES = {
    "기말1.pdf": "기말1 원본.pdf",
    "기말2.pdf": "기말2 원본.pdf",
    "기말3 .pdf": "기말3 원본.pdf",
    "미적분3단원.pdf": "미적분3단원 원본.pdf",
    "미적분4단원.pdf": "미적분4단원 원본.pdf",
}
```

Use these matching constants:

```python
RENDER_DPI = 200
SEARCH_DPI = 80
BBOX_PADDING_PX = 24
HIGH_CONFIDENCE_THRESHOLD = 0.55
MEDIUM_CONFIDENCE_THRESHOLD = 0.35
AMBIGUOUS_SCORE_DELTA = 0.03
```

Use this exact scale tuple in the script:

```python
TEMPLATE_SCALES = (
    0.40,
    0.45,
    0.50,
    0.55,
    0.60,
    0.65,
    0.70,
    0.75,
    0.80,
    0.85,
    0.90,
    0.95,
    1.00,
    1.05,
    1.10,
    1.15,
)
```

Template matching must run at `SEARCH_DPI` on a foreground mask, not on raw grayscale pixels. Track both the best and second-best score; if the score gap is less than `AMBIGUOUS_SCORE_DELTA`, route the sample to `review_needed` even when the absolute score is high. Saved pages and crops must still render at `RENDER_DPI`.

Write output to a temporary sibling folder first, then replace `var/datasets/<mode>` only after every requested sample and `contact_sheet.html` were written. Refuse to delete or replace output if `var/datasets` is a symlink.

- [ ] **Step 2: Keep dependency handling local**

If PyMuPDF is missing, the script must exit with this actionable message:

```text
PyMuPDF is required. Install it with: python -m pip install pymupdf
```

Do not add dependency files in this task.

## Task 3: Generate Pilot Output

- [ ] **Step 1: Run pilot mode**

Run:

```bash
python tools/datasets/local_match_dataset.py --mode pilot
```

If PyMuPDF is missing, run:

```bash
python -m pip install pymupdf
python tools/datasets/local_match_dataset.py --mode pilot
```

- [ ] **Step 2: Verify generated files**

Run:

```bash
find var/datasets/pilot -name metadata.json | wc -l
test -f var/datasets/pilot/contact_sheet.html
```

Expected:

- metadata count is `10`
- contact sheet exists

## Task 4: Final Check And Commit

- [ ] **Step 1: Confirm large local folders are not tracked**

Run:

```bash
git status --short image var/datasets
```

Expected: no output.

- [ ] **Step 2: Review tracked diff**

Run:

```bash
git diff -- .gitignore tools/datasets/local_match_dataset.py docs/superpowers/specs/2026-06-15-mvp-dataset-preparation-design.md docs/superpowers/plans/2026-06-15-mvp-dataset-preparation.md
```

- [ ] **Step 3: Commit**

Run:

```bash
git add .gitignore tools/datasets/local_match_dataset.py docs/superpowers/specs/2026-06-15-mvp-dataset-preparation-design.md docs/superpowers/plans/2026-06-15-mvp-dataset-preparation.md
git commit -m "chore(dataset): add local matching pilot script"
```
