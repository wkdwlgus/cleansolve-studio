# Handwriting Style Lab

`tools/style_lab`은 `default_pretty_handwriting v1` 스타일을 캘리브레이션하기 위한 개발 도구입니다.

이 도구는 OpenAI API를 호출하지 않습니다. 승인된 손글씨 레퍼런스 이미지 세트를 읽고, 다음 단계의 GPT-5.5 스타일 분석과 deterministic renderer 튜닝이 사용할 기준 산출물을 만듭니다.

## 입력

기본 입력 위치는 `image/clean_solutions`입니다.

이 directory에는 `GT_024.png`처럼 승인된 core/extended sample id와 같은 이름의 PNG 파일이 있어야 합니다.

## 실행

```bash
python -m tools.style_lab.cli build \
  --image-root image/clean_solutions \
  --output-root image/style-lab/default_pretty_handwriting/v1
```

## 산출물

기본 산출물 위치는 `image/style-lab/default_pretty_handwriting/v1`입니다.

- `core_contact_sheet.jpg`
- `extended_contact_sheet.jpg`
- `calibration_manifest.json`
- `style_tokens.skeleton.json`
- `metrics.csv`

`image/`는 gitignore 대상이므로 위 산출물은 저장소에 커밋하지 않습니다.

## 범위

이번 도구는 레퍼런스 계약과 산출물 생성을 담당합니다.

다음 작업은 이 산출물을 입력으로 삼아 GPT-5.5 스타일 프로필 추출과 renderer 파라미터 튜닝을 진행합니다.
