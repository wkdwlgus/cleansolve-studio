# Handwriting Style Lab

`tools/style_lab`은 `default_pretty_handwriting v1` 스타일을 캘리브레이션하기 위한 개발 도구입니다.

`build` 명령과 mock style profile 추출은 OpenAI API를 호출하지 않습니다. 승인된 손글씨 레퍼런스 이미지 세트를 읽고, 다음 단계의 GPT-5.5 스타일 분석과 deterministic renderer 튜닝이 사용할 기준 산출물을 만듭니다. 실제 OpenAI 호출은 사용자가 `extract-profile --client openai` 또는 opt-in smoke test를 명시적으로 실행할 때만 발생합니다.

## 입력

기본 입력 위치는 `image/clean_solutions`입니다.

이 directory에는 `GT_024.png`처럼 승인된 core/extended sample id와 같은 이름의 PNG 파일이 있어야 합니다.

## 실행

```bash
python -m tools.style_lab.cli build \
  --image-root image/clean_solutions \
  --output-root image/style-lab/default_pretty_handwriting/v1
```

`build` 명령은 같은 입력에 대해 재현 가능한 deterministic 산출물을 만듭니다. 이 산출물은 GPT-5.5 스타일 프로필 추출과 renderer 캘리브레이션 검토의 입력입니다.

## Style Profile 추출

API 호출 없이 schema-valid 로컬 style profile을 만들려면 mock client를 사용합니다.

```bash
python -m tools.style_lab.cli extract-profile \
  --client mock \
  --input-root image/style-lab/default_pretty_handwriting/v1 \
  --reference-image-root image/clean_solutions \
  --output-path image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json
```

실제 GPT-5.5 분석이 필요할 때만 OpenAI client를 명시합니다. 이 경로는 OpenAI Responses API를 호출하며 `OPENAI_API_KEY`가 필요합니다.

```bash
python -m tools.style_lab.cli extract-profile \
  --client openai \
  --input-root image/style-lab/default_pretty_handwriting/v1 \
  --reference-image-root image/clean_solutions \
  --output-path image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json
```

OpenAI smoke test는 명시적으로 opt-in할 때만 실행합니다.

```bash
CLEANSOLVE_RUN_OPENAI_STYLE_SMOKE=1 \
python -m pytest tools/style_lab/tests/test_openai_style_profile_smoke.py -q
```

## 산출물

기본 산출물 위치는 `image/style-lab/default_pretty_handwriting/v1`입니다.

- `core_contact_sheet.jpg`
- `extended_contact_sheet.jpg`
- `calibration_manifest.json`
- `style_tokens.skeleton.json`
- `metrics.csv`
- `style_profile.generated.json`

`/image` 아래 산출물은 gitignore 대상이므로 저장소에 커밋하지 않습니다.

## 범위

이번 도구는 레퍼런스 계약과 산출물 생성을 담당합니다.

다음 작업은 이 산출물과 생성된 style profile을 검토 입력으로 삼아 renderer 파라미터 튜닝을 진행합니다.
