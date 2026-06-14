# 가정

- 초기 scaffold는 작업 산출물을 로컬 파일 시스템의 `var/jobs` 아래에 저장한다.
- 내장 손글씨 스타일 프리셋은 먼저 메타데이터로 표현하고, 실제 생성형 스타일 자산은 이후 단계에서 추가한다.
- 이미지 모델은 스타일 자산 생성이나 부분 재생성에는 사용할 수 있지만, 기본 경로는 전체 이미지를 한 번에 다시 생성하는 방식이 아니다.
- 초기 workflow와 harness 테스트에서는 mock AI 출력으로 충분하다.
- 서버 측 deterministic renderer는 PNG/PDF export에 앞서 SVG overlay 출력부터 지원한다.
- 웹 editor shell은 업로드와 export가 완성되기 전에도 샘플 spec과 API job 상태를 렌더링할 수 있다.
